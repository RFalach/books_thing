const STORAGE_KEY = "user_books";

function loadUserBooks() {
  return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
}
function saveUserBooks(books) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(books));
}
function upsertUserBook(book, rating) {
  const books = loadUserBooks();
  const existing = books.find(b => b.catalog_id === book.id);
  if (existing) {
    existing.rating = rating;
    existing.dislike = dislike;
  } else {
    books.push({ catalog_id: book.id, rating });
  }
  saveUserBooks(books);
  renderProfile();
}


async function searchBooks() {
  const q = document.getElementById("search-input").value.trim();
  const url = q ? `/api/books?search=${encodeURIComponent(q)}&limit=20` : `/api/books?limit=20`;
  const res = await fetch(url);
  const data = await res.json();
  renderSearchResults(data.items);
}

function renderSearchResults(items) {
  const el = document.getElementById("search-results");
  el.innerHTML = "";
  items.forEach(book => {
    const div = document.createElement("div");
    div.className = "book-card";
    div.innerHTML = `
      <strong>${book.title || "?"}</strong> — ${book.author || "?"} (${book.year || "?"})
      <div class="tags">${book.tags.join(", ")}</div>
      <div class="rating">★ ${book.adjusted_rating} (${book.rating_count})</div>
    `;
    const btn = document.createElement("button");
    btn.textContent = "Оцінити";
    btn.onclick = () => {
      const r = prompt("Оцінка 1–10:", "8");
      if (r === null) return;
      const rating = parseInt(r, 10);
      if (isNaN(rating)) return;
      upsertUserBook(book, rating);
    };
    div.appendChild(btn);
    el.appendChild(div);
  });
}


function renderProfile() {
  const books = loadUserBooks();
  const el = document.getElementById("profile-list");
  el.innerHTML = "";
  if (!books.length) {
    el.textContent = "Порожньо. Додайте книги з пошуку.";
    return;
  }
  books.forEach((ub, i) => {
    const div = document.createElement("div");
    div.className = "profile-item";
    const label = `оцінка: ${ub.rating}`;
    div.innerHTML = `ID ${ub.catalog_id} — ${label} `;
    const del = document.createElement("button");
    del.textContent = "✕";
    del.onclick = () => {
      books.splice(i, 1);
      saveUserBooks(books);
      renderProfile();
    };
    div.appendChild(del);
    el.appendChild(div);
  });
}


async function getRecommendations() {
  const userBooks = loadUserBooks();
  if (!userBooks.length) {
    alert("Спочатку додайте хоча б одну книгу.");
    return;
  }
  const excludeRaw = document.getElementById("exclude-tags").value;
  const excludeTags = excludeRaw.split(",").map(s => s.trim()).filter(Boolean);

  const res = await fetch("/api/recommendations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_books: userBooks,
      exclude_tags: excludeTags,
      limit: 50,
      diversity: 5,
    }),
  });
  const data = await res.json();
  renderRecommendations(data);
}

function renderRecommendations(data) {
  const profEl = document.getElementById("profile-display");
  profEl.innerHTML = "<h3>Профіль смаків</h3>";
  Object.entries(data.profile)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .forEach(([tag, w]) => {
      const p = document.createElement("div");
      p.textContent = `${tag}: ${w}`;
      profEl.appendChild(p);
    });

  const el = document.getElementById("recs-list");
  el.innerHTML = "<h3>Рекомендації</h3>";
  data.recommendations.forEach((rec, i) => {
    const div = document.createElement("div");
    div.className = "rec-card";
    div.innerHTML = `
      <strong>${i + 1}. ${rec.title}</strong> — ${rec.author || "?"} (${rec.year || "?"})
      <div class="reason">${rec.reason}</div>
    `;
    el.appendChild(div);
  });
}


document.getElementById("search-btn").onclick = searchBooks;
document.getElementById("recommend-btn").onclick = getRecommendations;
renderProfile();
searchBooks();
