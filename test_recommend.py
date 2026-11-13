import pytest
from recommend import (
    build_taste_profile,
    tag_score,
    compute_score,
    recommend,
    adjusted_rating,
    GLOBAL_AVG,
    K_TAG
)


@pytest.fixture
def mock_books():
    return {
        1: {"id": 1, "title": "Book A", "author": "A", "year": 2000, 
            "avg_rating": 4.5, "rating_count": 100, "tags": {"fantasy", "horror"}},
        2: {"id": 2, "title": "Book B", "author": "B", "year": 2005, 
            "avg_rating": 3.0, "rating_count": 10, "tags": {"fantasy"}},
        3: {"id": 3, "title": "Book C", "author": "C", "year": 2010, 
            "avg_rating": 4.0, "rating_count": 50, "tags": {"children"}},
        4: {"id": 4, "title": "Book D", "author": "D", "year": 2015, 
            "avg_rating": 2.0, "rating_count": 5, "tags": {"fantasy", "children"}},
    }


def test_adjusted_rating_smoothing():
    ar_1_vote = adjusted_rating(5.0, 1)

    ar_1000_votes = adjusted_rating(5.0, 1000)
    
    assert ar_1_vote < 4.5, "Згладжування не працює для 1 голосу"
    assert ar_1000_votes > 4.9, "Згладжування заважає книзі з 1000 голосів"
    assert adjusted_rating(None, 0) == GLOBAL_AVG


def test_build_taste_profile_simple(mock_books):

    user_books = [
        {"catalog_id": 1, "rating": 10},
        {"catalog_id": 2, "rating": 8}
    ]
    
    profile, global_avg = build_taste_profile(user_books, mock_books)
    
    assert global_avg == 9.0
    
    assert "horror" in profile
    assert profile["horror"] > 0
    
    assert round(profile["fantasy"], 2) == 9.0


def test_tag_score(mock_books):
    profile = {"fantasy": 10.0, "horror": 5.0}
    
    score_1 = tag_score(mock_books[1], profile)
    assert score_1 == 7.5
    
    score_3 = tag_score(mock_books[3], profile)
    assert score_3 is None

def test_recommend_flow(mock_books):
    user_books = [
        {"catalog_id": 1, "rating": 10},
    ]

    exclude_tags = {"children"}
    
    result = recommend(
        user_books=user_books,
        books=mock_books,
        limit=10,
        exclude_tags=exclude_tags
    )
    
    candidates, profile = result
    

    assert len(candidates) == 1
    assert candidates[0]["book"]["title"] == "Book B"
    assert candidates[0]["tag_score"] > 0


def test_recommend_empty_profile(mock_books):
    user_books = []
    
    candidates, profile = recommend(user_books, mock_books)
    
    assert candidates == []
    assert profile == {}

def test_recommend_all_excluded(mock_books):
    user_books = [{"catalog_id": 3, "rating": 10}]
    
    exclude_tags = {"fantasy", "horror", "children"}
    
    candidates, _ = recommend(
        user_books=user_books, 
        books=mock_books, 
        exclude_tags=exclude_tags
    )
    
    assert len(candidates) == 0
