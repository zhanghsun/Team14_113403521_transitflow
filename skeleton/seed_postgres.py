"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values
from argon2 import PasswordHasher

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg

# Initialize argon2 password hasher
ph = PasswordHasher()


def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    data = load("metro_stations.json")
    rows = [
        (
            s["station_id"],
            s["name"],
            s.get("is_interchange_metro", False),
            s.get("is_interchange_national_rail", False),
            s.get("interchange_national_rail_station_id"),
        )
        for s in data
    ]
    n = insert_many(
        cur,
        "metro_stations",
        ["station_id", "name", "is_interchange_metro", "is_interchange_national_rail", "interchange_national_rail_station_id"],
        rows,
    )
    print(f"  metro_stations: {n} rows")


def seed_metro_station_lines(cur):
    data = load("metro_stations.json")
    rows = []
    for station in data:
        for line in station.get("lines", []):
            rows.append((station["station_id"], line))
    n = insert_many(
        cur,
        "metro_station_lines",
        ["station_id", "line"],
        rows,
    )
    print(f"  metro_station_lines: {n} rows")


def seed_national_rail_stations(cur):
    data = load("national_rail_stations.json")
    rows = [
        (
            s["station_id"],
            s["name"],
            s.get("is_interchange_national_rail", False),
            s.get("is_interchange_metro", False),
            s.get("interchange_metro_station_id"),
        )
        for s in data
    ]
    n = insert_many(
        cur,
        "national_rail_stations",
        ["station_id", "name", "is_interchange_national_rail", "is_interchange_metro", "interchange_metro_station_id"],
        rows,
    )
    print(f"  national_rail_stations: {n} rows")


def seed_national_rail_station_lines(cur):
    data = load("national_rail_stations.json")
    rows = []
    for station in data:
        for line in station.get("lines", []):
            rows.append((station["station_id"], line))
    n = insert_many(
        cur,
        "national_rail_station_lines",
        ["station_id", "line"],
        rows,
    )
    print(f"  national_rail_station_lines: {n} rows")


def seed_metro_schedules(cur):
    data = load("metro_schedules.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_national_rail_schedules(cur):
    data = load("national_rail_schedules.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_seat_layouts(cur):
    data = load("national_rail_seat_layouts.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_users(cur):
    data = load("registered_users.json")
    
    # Insert users
    user_rows = []
    cred_rows = []
    
    for user in data:
        # Split full_name into first_name and last_name
        full_name = user.get("full_name", "")
        parts = full_name.split(" ", 1)
        first_name = parts[0] if len(parts) > 0 else ""
        last_name = parts[1] if len(parts) > 1 else ""
        
        user_rows.append((
            user["user_id"],
            first_name,
            last_name,
            user["email"],
            user.get("phone"),
            user.get("date_of_birth"),
            user.get("registered_at"),
            user.get("is_active", True),
        ))
        
        # Hash password and secret answer using argon2
        password_hash = ph.hash(user["password"])
        secret_answer_hash = ph.hash(user["secret_answer"])
        
        cred_rows.append((
            user["user_id"],
            password_hash,
            user["secret_question"],
            secret_answer_hash,
        ))
    
    # Insert user records
    n_users = insert_many(
        cur,
        "users",
        ["user_id", "first_name", "last_name", "email", "phone", "date_of_birth", "registered_at", "is_active"],
        user_rows,
    )
    print(f"  users: {n_users} rows")
    
    # Insert credentials
    n_creds = insert_many(
        cur,
        "user_credentials",
        ["user_id", "password_hash", "secret_question", "secret_answer_hash"],
        cred_rows,
    )
    print(f"  user_credentials: {n_creds} rows")


def seed_national_rail_bookings(cur):
    data = load("bookings.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_metro_travels(cur):
    data = load("metro_travel_history.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_payments(cur):
    data = load("payments.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


def seed_feedback(cur):
    data = load("feedback.json")
    # TODO: Design your table schema, then implement the INSERT logic here.
    pass


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")
        print("\n[Phase 1 — Basic Infrastructure]")
        seed_metro_stations(cur)
        seed_metro_station_lines(cur)
        seed_national_rail_stations(cur)
        seed_national_rail_station_lines(cur)
        seed_users(cur)
        
        print("\n[Phase 2+ — Schedules & Bookings]")
        seed_metro_schedules(cur)
        seed_national_rail_schedules(cur)
        seed_seat_layouts(cur)
        seed_national_rail_bookings(cur)
        seed_metro_travels(cur)
        seed_payments(cur)
        seed_feedback(cur)
        
        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
