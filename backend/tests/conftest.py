"""
Test fixtures.

Each test runs inside a transaction that is rolled back afterwards, so tests
are isolated, order-independent and leave no rows behind. No live server is
needed: requests go through FastAPI's TestClient in-process.
"""

import os
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Configure before anything imports settings.
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("AI_FEATURES_ENABLED", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-any-real-environment")

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.shared.registry import Base  # noqa: E402

TEST_DB_SUFFIX = "_test"


@pytest.fixture(scope="session")
def engine():
    """
    A dedicated test database, created once and dropped at the end.

    Kept separate from the development database so a test run can never
    truncate real data.
    """
    settings = get_settings()
    admin_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"
    test_db = settings.database_url.rsplit("/", 1)[1] + TEST_DB_SUFFIX
    test_url = settings.database_url.rsplit("/", 1)[0] + "/" + test_db

    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db}"'))
        conn.execute(text(f'CREATE DATABASE "{test_db}"'))
    admin.dispose()

    test_engine = create_engine(test_url, future=True)
    with test_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{test_db}' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text(f'DROP DATABASE IF EXISTS "{test_db}"'))
    admin.dispose()


@pytest.fixture
def db_session(engine) -> Generator[Session, None, None]:
    """One outer transaction per test, rolled back regardless of outcome."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    TestClient with the database dependency overridden.

    The override yields the test's transaction-bound session and does not
    commit, so the outer rollback still discards everything the request wrote.
    """
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        # Savepoint per request so HTTP 4xx/5xx can roll back request writes
        # without aborting the outer test transaction.
        nested = db_session.begin_nested()
        try:
            yield db_session
            db_session.flush()
            nested.commit()
        except Exception:
            nested.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(client: TestClient):
    """Registers a user and returns its auth headers."""

    def make(email: str | None = None) -> dict[str, str]:
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "a strong passphrase", "fullName": "Test User"},
        )
        assert response.status_code == 201, response.text
        return {"Authorization": f"Bearer {response.json()['accessToken']}"}

    return make


@pytest.fixture
def auth_headers(user_factory) -> dict[str, str]:
    return user_factory()


@pytest.fixture
def company(client: TestClient, auth_headers) -> dict:
    response = client.post(
        "/api/v1/companies",
        headers=auth_headers,
        json={
            "name": "Pharma GmbH",
            "industryKey": "pharma",
            "locationKey": "vienna-at",
            "regulationIds": ["eu-gmp", "annex-11"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
