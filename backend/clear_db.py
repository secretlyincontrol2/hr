import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("No DATABASE_URL found.")
    exit(1)

print(f"Connecting to database...")
try:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE hackathons RESTART IDENTITY CASCADE;")
        cur.execute("TRUNCATE TABLE scraper_status RESTART IDENTITY CASCADE;")
        print("Database successfully wiped!")
except Exception as e:
    print(f"Error wiping database: {e}")
finally:
    if 'conn' in locals():
        conn.close()
