from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """
    One pooled engine per process, built lazily.

    Lazy construction means importing a model no longer opens a connection, so
    tests can point at a different database before anything connects.
    """
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,  # survives a database restart or idle timeout
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        echo=settings.db_echo,
        future=True,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """
    Request-scoped session and **the transaction boundary**.

    The whole request is one transaction: it commits when the handler returns
    and rolls back on any exception. Services therefore never call `commit()`,
    so a multi-step operation can no longer half-commit.
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
