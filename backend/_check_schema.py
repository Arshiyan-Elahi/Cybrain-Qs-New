from sqlalchemy import create_engine, text

from app.core.config import get_settings

e = create_engine(get_settings().database_url)
with e.connect() as c:
    print("alembic", c.execute(text("select version_num from alembic_version")).fetchall())
    print(
        "creation_request_id",
        c.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_name='companies' and column_name='creation_request_id'"
            )
        ).fetchall(),
    )
    print(
        "documents.kind",
        c.execute(
            text(
                "select column_name from information_schema.columns "
                "where table_name='documents' and column_name='kind'"
            )
        ).fetchall(),
    )
    print(
        "profile table",
        c.execute(
            text(
                "select table_name from information_schema.tables "
                "where table_name='company_onboarding_profiles'"
            )
        ).fetchall(),
    )
