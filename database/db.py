import os

import psycopg
from dotenv import load_dotenv

load_dotenv()


def test_database_connection():
    connection = psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database();")
        database_name = cursor.fetchone()[0]

    connection.close()

    print(f"Connected to database: {database_name}")


if __name__ == "__main__":
    test_database_connection()