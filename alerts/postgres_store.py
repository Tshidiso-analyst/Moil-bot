from __future__ import annotations

from alerts.models import Alert, AlertEvent
from database.db import get_connection


_ALERT_COLUMNS = (
    "alert_id, symbol, alert_type, severity, title, message, "
    "created_at, status, decision_id, dedupe_key"
)


class PostgresAlertStore:
    """PostgreSQL-backed alert repository with atomic deduplication."""

    def add(self, alert: Alert) -> Alert:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO moil_alerts ({_ALERT_COLUMNS})
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING {_ALERT_COLUMNS}
                    """,
                    self._values(alert),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Alert already exists: {alert.alert_id}")
            connection.commit()
            return self._from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def create(self, event: AlertEvent, alert_id: str, created_at) -> Alert:
        candidate = Alert(
            alert_id=alert_id,
            symbol=event.symbol,
            alert_type=event.alert_type,
            severity=event.severity,
            title=event.title,
            message=event.message,
            created_at=created_at,
            decision_id=event.decision_id,
            dedupe_key=event.dedupe_key,
        )
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO moil_alerts ({_ALERT_COLUMNS})
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING {_ALERT_COLUMNS}
                    """,
                    self._values(candidate),
                )
                row = cursor.fetchone()
            if row is not None:
                connection.commit()
                return self._from_row(row)
            connection.rollback()
            if event.dedupe_key:
                existing = self.by_dedupe_key(event.dedupe_key)
                if existing is not None:
                    return existing
            raise ValueError(f"Alert already exists: {alert_id}")
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get(self, alert_id: str) -> Alert | None:
        return self._one(
            f"SELECT {_ALERT_COLUMNS} FROM moil_alerts WHERE alert_id = %s",
            (alert_id,),
        )

    def by_dedupe_key(self, dedupe_key: str) -> Alert | None:
        if not dedupe_key:
            return None
        return self._one(
            f"SELECT {_ALERT_COLUMNS} FROM moil_alerts WHERE dedupe_key = %s",
            (dedupe_key,),
        )

    def all(self) -> list[Alert]:
        return self._many(
            f"SELECT {_ALERT_COLUMNS} FROM moil_alerts ORDER BY created_at DESC, alert_id"
        )

    def by_symbol(self, symbol: str) -> list[Alert]:
        return self._many(
            f"SELECT {_ALERT_COLUMNS} FROM moil_alerts WHERE symbol = %s ORDER BY created_at DESC",
            (symbol,),
        )

    def by_status(self, status: str) -> list[Alert]:
        return self._many(
            f"SELECT {_ALERT_COLUMNS} FROM moil_alerts WHERE status = %s ORDER BY created_at DESC",
            (status,),
        )

    def acknowledge(self, alert_id: str) -> Alert:
        return self._set_status(alert_id, "acknowledged")

    def resolve(self, alert_id: str) -> Alert:
        return self._set_status(alert_id, "resolved")

    def record_deliveries(self, alert: Alert, deliveries) -> None:
        if not deliveries:
            return
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                for delivery in deliveries:
                    cursor.execute(
                        """
                        INSERT INTO moil_alert_deliveries
                            (alert_id, channel, sent, message)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            alert.alert_id,
                            delivery.channel,
                            bool(delivery.sent),
                            str(delivery.message),
                        ),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _set_status(self, alert_id: str, status: str) -> Alert:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE moil_alerts
                    SET status = %s
                    WHERE alert_id = %s
                    RETURNING {_ALERT_COLUMNS}
                    """,
                    (status, alert_id),
                )
                row = cursor.fetchone()
            if row is None:
                raise KeyError(f"Alert not found: {alert_id}")
            connection.commit()
            return self._from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _one(self, query: str, params: tuple = ()) -> Alert | None:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                row = cursor.fetchone()
            return self._from_row(row) if row is not None else None
        finally:
            connection.close()

    def _many(self, query: str, params: tuple = ()) -> list[Alert]:
        connection = get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [self._from_row(row) for row in rows]
        finally:
            connection.close()

    @staticmethod
    def _values(alert: Alert) -> tuple:
        return (
            alert.alert_id,
            alert.symbol,
            alert.alert_type,
            alert.severity,
            alert.title,
            alert.message,
            alert.created_at,
            alert.status,
            alert.decision_id,
            alert.dedupe_key,
        )

    @staticmethod
    def _from_row(row) -> Alert:
        return Alert(
            alert_id=row[0],
            symbol=row[1],
            alert_type=row[2],
            severity=row[3],
            title=row[4],
            message=row[5],
            created_at=row[6],
            status=row[7],
            decision_id=row[8],
            dedupe_key=row[9],
        )
