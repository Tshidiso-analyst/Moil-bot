from pathlib import Path


def test_authentication_migration_creates_repository_tables_and_constraints():
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "001_authentication.sql"
    )
    sql = migration.read_text(encoding="utf-8").lower()

    assert "create table if not exists users" in sql
    assert "create table if not exists user_sessions" in sql
    assert "create table if not exists notification_preferences" in sql
    assert "references users(id) on delete cascade" in sql
    assert "session_token_hash char(64) not null unique" in sql
    assert "users_username_lower_unique" in sql
    assert "users_email_lower_unique" in sql


def test_authentication_migration_is_transactional():
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "001_authentication.sql"
    )
    sql = migration.read_text(encoding="utf-8").strip().lower()

    assert sql.startswith("begin;")
    assert sql.endswith("commit;")
