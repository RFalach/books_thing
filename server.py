import sqlite3
from contextlib import closing
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from recommend import (
    load_books,
    build_taste_profile,
    compute_score,
    tag_score,
    adjusted_rating,
    recommend as recommend_logic,
    DB_PATH,
)

app = FastAPI(title="Book Recommender API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserBook(BaseModel):
    catalog_id: int
    rating: int = 0


class RecommendRequest(BaseModel):
    user_books: list[UserBook] = Field(default_factory=list)
    exclude_tags: list[str] = Field(default_factory=list)
    limit: int = 10
    diversity: Optional[int] = None


class BookOut(BaseModel):
    id: int
    title: Optional[str]
    author: Optional[str]
    year: Optional[int]
    tags: list[str]
    avg_rating: Optional[float]
    rating_count: int
    adjusted_rating: float


class RecommendationOut(BookOut):
    score: float
    reason: str


class RecommendResponse(BaseModel):
    profile: dict[str, float]
    recommendations: list[RecommendationOut]


def get_books():
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return load_books(conn)


def book_to_out(book: dict) -> dict:
    ar = adjusted_rating(book["avg_rating"], book["rating_count"])
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
        "tags": sorted(book["tags"]),
        "avg_rating": book["avg_rating"],
        "rating_count": book["rating_count"],
        "adjusted_rating": round(ar, 3),
    }


def make_reason(book: dict, profile: dict, score: float) -> str:
    matched = sorted(
        [(t, profile[t]) for t in book["tags"] if t in profile],
        key=lambda x: x[1],
        reverse=True,
    )
    parts = [f"{t} ({w:.1f})" for t, w in matched[:3]]
    ar = adjusted_rating(book["avg_rating"], book["rating_count"])
    return (
        f"теги: {', '.join(parts)} | "
        f"рейтинг: {ar:.2f} ({book['rating_count']} гол.) | "
        f"score: {score:.3f}"
    )



@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/books")
def list_books(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    tag: Optional[str] = None,
):
    books = get_books()
    items = list(books.values())

    if search:
        q = search.lower()
        items = [
            b for b in items
            if (b["title"] and q in b["title"].lower())
            or (b["author"] and q in b["author"].lower())
        ]
    if tag:
        items = [b for b in items if tag in b["tags"]]

    total = len(items)
    items = items[offset: offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [book_to_out(b) for b in items],
    }


@app.get("/api/books/{book_id}")
def get_book(book_id: int):
    books = get_books()
    book = books.get(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book_to_out(book)


@app.post("/api/recommendations", response_model=RecommendResponse)
def recommendations(req: RecommendRequest):
    books = get_books()
    user_books = [ub.model_dump() for ub in req.user_books]
    candidates, profile = recommend_logic(
        user_books,
        books,
        limit=req.limit,
        diversity=req.diversity,
        exclude_tags=set(req.exclude_tags),
    )

    if not candidates:
        return RecommendResponse(
            profile={k: round(v, 3) for k, v in profile.items()},
            recommendations=[],
        )

    recs = []
    for c in candidates:
        b = c["book"]
        out = book_to_out(b)
        out["score"] = round(c["score"], 4)
        out["reason"] = make_reason(b, profile, c["score"])
        recs.append(out)

    return RecommendResponse(
        profile={k: round(v, 3) for k, v in profile.items()},
        recommendations=recs,
    )


app.mount("/", StaticFiles(directory="static", html=True), name="static")
