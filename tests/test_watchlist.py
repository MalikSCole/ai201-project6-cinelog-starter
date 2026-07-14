"""Tests for the CineLog watchlist service."""

import pytest

from app import create_app, db
from models import User, Film, WatchlistEntry
from services.collection_service import FilmNotFoundError
from services.watchlist_service import (
    add_to_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
)


@pytest.fixture
def app():
    """Create an isolated test app with an in-memory database."""
    app = create_app(
        config={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    """Create a user for watchlist tests."""
    with app.app_context():
        user = User(
            username="watchlistuser",
            email="watchlist@example.com",
        )
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    """Create a film for watchlist tests."""
    with app.app_context():
        film = Film(
            title="Arrival",
            year=2016,
            genre="Science Fiction",
        )
        db.session.add(film)
        db.session.commit()
        return film.id


def test_add_to_watchlist_creates_entry(app, sample_user, sample_film):
    """Adding a valid film should create and persist a watchlist entry."""
    with app.app_context():
        entry = add_to_watchlist(
            user_id=sample_user,
            film_id=sample_film,
        )

        assert entry is not None
        assert entry.user_id == sample_user
        assert entry.film_id == sample_film

        stored_entry = WatchlistEntry.query.filter_by(
            user_id=sample_user,
            film_id=sample_film,
        ).first()

        assert stored_entry is not None


def test_add_to_watchlist_duplicate_raises(
    app,
    sample_user,
    sample_film,
):
    """Adding the same film twice should raise an explicit error."""
    with app.app_context():
        add_to_watchlist(
            user_id=sample_user,
            film_id=sample_film,
        )

        with pytest.raises(AlreadyInWatchlistError):
            add_to_watchlist(
                user_id=sample_user,
                film_id=sample_film,
            )

        count = WatchlistEntry.query.filter_by(
            user_id=sample_user,
            film_id=sample_film,
        ).count()

        assert count == 1


def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    """A nonexistent film ID should raise FilmNotFoundError."""
    with app.app_context():
        fake_film_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(
                user_id=sample_user,
                film_id=fake_film_id,
            )


def test_get_watchlist_returns_newest_first(app, sample_user):
    """The most recently added watchlist film should appear first."""
    with app.app_context():
        from datetime import datetime, timedelta, timezone

        film_a = Film(title="Alien", year=1979, genre="Horror")
        film_b = Film(
            title="Blade Runner",
            year=1982,
            genre="Science Fiction",
        )
        db.session.add_all([film_a, film_b])
        db.session.commit()

        earlier = datetime.now(timezone.utc) - timedelta(days=5)
        later = datetime.now(timezone.utc)

        entry_a = WatchlistEntry(
            user_id=sample_user,
            film_id=film_a.id,
            date_added=earlier,
        )
        entry_b = WatchlistEntry(
            user_id=sample_user,
            film_id=film_b.id,
            date_added=later,
        )

        db.session.add_all([entry_a, entry_b])
        db.session.commit()

        watchlist = get_watchlist(sample_user)
        titles = [film["title"] for film in watchlist]

        assert titles == ["Blade Runner", "Alien"]