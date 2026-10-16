import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Open a PostgreSQL connection using the project's environment settings."""
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            "Missing database configuration: " + ", ".join(missing)
        )

    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def test_database_connection():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            database_name = cursor.fetchone()[0]

        print(f"Connected to database: {database_name}")
    finally:
        connection.close()


if __name__ == "__main__":
    test_database_connection()
