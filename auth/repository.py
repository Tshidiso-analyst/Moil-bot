from datetime import datetime

from database.db import get_connection
from auth.models import Session, User


class UserRepository:
    """MySQL repository for Moil Bot users and sessions."""

    def create_user(
        self,
        full_name: str,
        username: str,
        email: str,
        password_hash: str,
    ) -> User:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users (
                    full_name,
                    username,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    full_name,
                    username,
                    email,
                    password_hash,
                ),
            )

            user_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO notification_preferences (user_id)
                VALUES (%s)
                """,
                (user_id,),
            )

            connection.commit()

            cursor.execute(
                """
                SELECT
                    id,
                    full_name,
                    username,
                    email,
                    password_hash,
                    email_verified_at,
                    is_active
                FROM users
                WHERE id = %s
                """,
                (user_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if row is None:
                raise RuntimeError("User was created but could not be retrieved.")

            return self._user_from_row(row)

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def find_by_username_or_email(self, identifier: str) -> User | None:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    full_name,
                    username,
                    email,
                    password_hash,
                    email_verified_at,
                    is_active
                FROM users
                WHERE username = %s
                   OR email = %s
                LIMIT 1
                """,
                (identifier, identifier),
            )

            row = cursor.fetchone()
            cursor.close()

            if row is None:
                return None

            return self._user_from_row(row)

        finally:
            connection.close()

    def find_by_id(self, user_id: int) -> User | None:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    full_name,
                    username,
                    email,
                    password_hash,
                    email_verified_at,
                    is_active
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (user_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if row is None:
                return None

            return self._user_from_row(row)

        finally:
            connection.close()

    def create_session(
        self,
        user_id: int,
        session_token_hash: str,
        expires_at: datetime,
    ) -> Session:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO user_sessions (
                    user_id,
                    session_token_hash,
                    expires_at
                )
                VALUES (%s, %s, %s)
                """,
                (
                    user_id,
                    session_token_hash,
                    expires_at,
                ),
            )

            session_id = cursor.lastrowid
            connection.commit()

            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    session_token_hash,
                    expires_at,
                    created_at,
                    last_seen_at
                FROM user_sessions
                WHERE id = %s
                """,
                (session_id,),
            )

            row = cursor.fetchone()
            cursor.close()

            if row is None:
                raise RuntimeError(
                    "Session was created but could not be retrieved."
                )

            return Session(
                id=row[0],
                user_id=row[1],
                session_token_hash=row[2],
                expires_at=row[3],
                created_at=row[4],
                last_seen_at=row[5],
            )

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def find_session(self, session_token_hash: str) -> Session | None:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    session_token_hash,
                    expires_at,
                    created_at,
                    last_seen_at
                FROM user_sessions
                WHERE session_token_hash = %s
                  AND expires_at > UTC_TIMESTAMP()
                LIMIT 1
                """,
                (session_token_hash,),
            )

            row = cursor.fetchone()
            cursor.close()

            if row is None:
                return None

            return Session(
                id=row[0],
                user_id=row[1],
                session_token_hash=row[2],
                expires_at=row[3],
                created_at=row[4],
                last_seen_at=row[5],
            )

        finally:
            connection.close()

    def delete_session(self, session_token_hash: str) -> None:
        connection = get_connection()

        try:
            cursor = connection.cursor()

            cursor.execute(
                """
                DELETE FROM user_sessions
                WHERE session_token_hash = %s
                """,
                (session_token_hash,),
            )

            connection.commit()
            cursor.close()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    @staticmethod
    def _user_from_row(row) -> User:
        return User(
            id=row[0],
            full_name=row[1],
            username=row[2],
            email=row[3],
            password_hash=row[4],
            email_verified_at=row[5],
            is_active=bool(row[6]),
        )
