import sqlite3
import json
import argparse
from collections import defaultdict

DB_PATH = "library.db"
K_SMOOTHING = 20
K_TAG = 2
GLOBAL_AVG = 4.0
W_TAG = 0.7
W_RATING = 0.3


def load_books(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, author, first_publish_year, avg_rating, rating_count
        FROM books
    """)
    books = {}
    for bid, title, author, year, avg, cnt in cur.fetchall():
        books[bid] = {
            "id": bid,
            "title": title,
            "author": author,
            "year": year,
            "avg_rating": avg,
            "rating_count": cnt or 0,
            "tags": set(),
        }

    cur.execute("""
        SELECT bt.book_id, t.name
        FROM book_tags bt JOIN tags t ON t.id = bt.tag_id
    """)
    for bid, tag in cur.fetchall():
        if bid in books:
            books[bid]["tags"].add(tag)
    return books


def load_preferences(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    user_books = data.get("user_books", [])
    exclude_tags = set(data.get("exclude_tags", []))
    return user_books, exclude_tags


def adjusted_rating(avg, count):
    if avg is None or count == 0:
        return GLOBAL_AVG
    return (avg * count + GLOBAL_AVG * K_SMOOTHING) / (count + K_SMOOTHING)


def build_taste_profile(user_books, books):
    tag_sum = defaultdict(float)
    tag_count = defaultdict(int)
    positive_ratings = []

    for ub in user_books:
        book = books.get(ub.get("catalog_id"))
        if not book:
            continue
        rating = ub.get("rating", 0)
        if rating <= 0:
            continue
        positive_ratings.append(rating)
        for tag in book["tags"]:
            tag_sum[tag] += rating
            tag_count[tag] += 1

    global_avg = (
        sum(positive_ratings) / len(positive_ratings)
        if positive_ratings else 5.0
    )

    profile = {}
    for tag in tag_sum:
        n = tag_count[tag]
        s = tag_sum[tag]
        if s < 0:
            profile[tag] = s / n
        else:
            avg = (s + global_avg * K_TAG) / (n + K_TAG)
            if n == 1:
                avg *= 0.7
            profile[tag] = avg
    return profile, global_avg


def tag_score(book, profile):
    weights = [profile[t] for t in book["tags"] if t in profile]
    if not weights:
        return None
    return sum(weights) / len(weights)


def compute_score(book, profile, max_tag):
    ts = tag_score(book, profile)
    if ts is None:
        return None
    ts_norm = ts / max_tag if max_tag > 0 else 0.0
    ts_norm = max(0.0, min(1.0, ts_norm))
    ar = adjusted_rating(book["avg_rating"], book["rating_count"])
    ar_norm = (ar - 1) / 4
    return W_TAG * ts_norm + W_RATING * ar_norm


def recommend(user_books, books, limit=10, diversity=None,
              exclude_tags=None):
    exclude_tags = exclude_tags or set()
    profile, global_avg = build_taste_profile(user_books, books)
    if not profile:
        print("! Порожній профіль смаків — немає оцінених книг із відомими тегами.")
        return [], profile

    max_tag = max((v for v in profile.values() if v > 0), default=1.0)
    read_ids = {ub["catalog_id"] for ub in user_books}

    candidates = []
    for bid, book in books.items():
        if bid in read_ids:
            continue
        if not book["tags"]:
            continue

        if exclude_tags and (book["tags"] & exclude_tags):
            continue

        ts = tag_score(book, profile)
        if ts is None:
            continue
        if ts < 0:
            continue

        score = compute_score(book, profile, max_tag)
        if score is None:
            continue

        dominant = max(
            (t for t in book["tags"] if t in profile),
            key=lambda t: profile[t],
            default=None,
        )
        if dominant is None:
            continue

        candidates.append({
            "book": book,
            "score": score,
            "tag_score": ts,
            "dominant": dominant,
        })

    candidates.sort(
        key=lambda c: (
            c["score"],
            len(c["book"]["tags"]),
            c["book"]["year"] or 0,
        ),
        reverse=True,
    )

    if diversity:
        per_tag = defaultdict(int)
        diversified = []
        for c in candidates:
            if per_tag[c["dominant"]] >= diversity:
                continue
            diversified.append(c)
            per_tag[c["dominant"]] += 1
            if len(diversified) >= limit:
                break
        if len(diversified) < limit:
            used = {id(c) for c in diversified}
            for c in candidates:
                if id(c) not in used:
                    diversified.append(c)
                    if len(diversified) >= limit:
                        break
        candidates = diversified[:limit]
    else:
        candidates = candidates[:limit]

    return candidates, profile


def explain(c, profile):
    book = c["book"]
    matched = sorted(
        [(t, profile[t]) for t in book["tags"] if t in profile],
        key=lambda x: x[1], reverse=True,
    )
    parts = [f"{t} ({w:.1f})" for t, w in matched[:3]]
    ar = adjusted_rating(book["avg_rating"], book["rating_count"])
    return (
        f"теги: {', '.join(parts)} | "
        f"рейтинг: {ar:.2f} ({book['rating_count']} гол.) | "
        f"score: {c['score']:.3f}"
    )

