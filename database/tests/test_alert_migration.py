from pathlib import Path


def test_persistent_alert_migration_creates_alert_and_delivery_tables():
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "002_persistent_alerts.sql"
    )
    sql = migration.read_text(encoding="utf-8").lower()

    assert "create table if not exists moil_alerts" in sql
    assert "create table if not exists moil_alert_deliveries" in sql
    assert "references moil_alerts(alert_id) on delete cascade" in sql
    assert "moil_alerts_dedupe_unique" in sql
    assert "moil_alert_deliveries_alert_idx" in sql


def test_persistent_alert_migration_is_transactional():
    migration = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "002_persistent_alerts.sql"
    )
    sql = migration.read_text(encoding="utf-8").strip().lower()

    assert sql.startswith("begin;")
    assert sql.endswith("commit;")
