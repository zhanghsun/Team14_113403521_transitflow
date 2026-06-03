"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)

STUDENT TASK
------------
Design your schema in databases/relational/schema.sql, seed it with
skeleton/seed_postgres.py, then implement the query functions below.

Functions prefixed with `query_`  are read-only lookups called by the agent.
Functions prefixed with `execute_` are write operations (booking/cancellation).

The vector functions (query_policy_vector_search, store_policy_document)
are already implemented — do not modify them.
"""

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a cursor, run SQL, return rows.
# Use _connect() for read-only queries; for write operations use a manual
# connection with conn.commit() / conn.rollback() (see execute_booking below).

def example_query() -> dict:
    """Example: returns the name of the connected database."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_database() AS db;")
            return dict(cur.fetchone())

# TODO: Implement the query_ and execute_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both origin and destination stations
    in the correct order, along with seat occupancy for the requested travel date.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        travel_date:     e.g. "2025-06-01" — used to count bookings; omit for general info
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT *
                FROM national_rail_schedules
                WHERE deleted_at IS NULL
                """
            )

            schedules = cur.fetchall()

            results = []

            for row in schedules:

                stops = row["stops_in_order"]

                if origin_id in stops and destination_id in stops:

                    origin_pos = stops.index(origin_id)
                    destination_pos = stops.index(destination_id)

                    if origin_pos < destination_pos:

                        schedule_dict = dict(row)

                        # ---------- total seats ----------
                        cur.execute(
                            """
                            SELECT coaches
                            FROM national_rail_seat_layouts
                            WHERE schedule_id = %s
                            AND deleted_at IS NULL
                            """,
                            (row["schedule_id"],)
                        )

                        layout = cur.fetchone()

                        total_seats = 0

                        if layout:

                            for coach in layout["coaches"]:
                                total_seats += len(coach["seats"])

                        # ---------- booked seats ----------
                        booked_seats = 0

                        if travel_date:

                            cur.execute(
                                """
                                SELECT COUNT(*)
                                FROM national_rail_bookings
                                WHERE schedule_id = %s
                                AND travel_date = %s
                                AND status = 'confirmed'
                                AND deleted_at IS NULL
                                """,
                                (
                                    row["schedule_id"],
                                    travel_date
                                )
                            )

                            booked_seats = cur.fetchone()["count"]

                        schedule_dict["total_seats"] = total_seats
                        schedule_dict["booked_seats"] = booked_seats
                        schedule_dict["available_seats"] = (
                            total_seats - booked_seats
                        )

                        results.append(schedule_dict)

            return results

def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:
    """
    Calculate the fare for a national rail journey.

    Args:
        schedule_id:     e.g. "NR_SCH01"
        fare_class:      "standard" or "first"
        stops_travelled: number of stops between origin and destination (inclusive)

    Returns:
        dict with fare_class, base_fare_usd, per_stop_rate_usd, total_fare_usd
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT fare_classes
                FROM national_rail_schedules
                WHERE schedule_id = %s
                AND deleted_at IS NULL
                """,
                (schedule_id,)
            )

            row = cur.fetchone()

            if not row:
                return None

            fare_classes = row["fare_classes"]

            if fare_class not in fare_classes:
                return None

            base_fare = float(
                fare_classes[fare_class]["base_fare_usd"]
            )

            per_stop_rate = float(
                fare_classes[fare_class]["per_stop_rate_usd"]
            )

            total_fare = (
                base_fare +
                per_stop_rate * stops_travelled
            )

            return {
                "fare_class": fare_class,
                "base_fare_usd": base_fare,
                "per_stop_rate_usd": per_stop_rate,
                "stops_travelled": stops_travelled,
                "total_fare_usd": round(total_fare, 2)
            }

# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    schedule_id,
                    line,
                    direction,
                    origin_station_id,
                    destination_station_id,
                    first_train_time,
                    last_train_time,
                    base_fare_usd,
                    per_stop_rate_usd,
                    frequency_min,
                    stops_in_order,
                    travel_time_from_origin_min,
                    operates_on
                FROM metro_schedules
                WHERE deleted_at IS NULL
                """
            )

            schedules = cur.fetchall()
            results = []

            for row in schedules:

                stops = row["stops_in_order"]

                if origin_id in stops and destination_id in stops:

                    origin_pos = stops.index(origin_id)
                    destination_pos = stops.index(destination_id)

                    if origin_pos < destination_pos:
                        results.append(dict(row))

            return results

def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """
    Calculate the metro fare for a single-ticket journey.

    Args:
        schedule_id:     e.g. "MS_SCH01"
        stops_travelled: number of stops between origin and destination

    Returns:
        dict with base_fare_usd, per_stop_rate_usd, total_fare_usd
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT
                    base_fare_usd,
                    per_stop_rate_usd
                FROM metro_schedules
                WHERE schedule_id = %s
                AND deleted_at IS NULL
                """,
                (schedule_id,)
            )

            row = cur.fetchone()

            if not row:
                return None

            base_fare = float(row["base_fare_usd"])
            per_stop_rate = float(row["per_stop_rate_usd"])

            total_fare = base_fare + (
                per_stop_rate * stops_travelled
            )

            return {
                "base_fare_usd": base_fare,
                "per_stop_rate_usd": per_stop_rate,
                "stops_travelled": stops_travelled,
                "total_fare_usd": round(total_fare, 2)
            }

# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
    """
    Return available seats for a national rail journey on a given date.

    Args:
        schedule_id:  e.g. "NR_SCH01"
        travel_date:  e.g. "2025-06-01"
        fare_class:   "standard" or "first"

    Returns:
        List of dicts: {seat_id, coach, row, column}
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            # 1. Get seat layout
            cur.execute(
                """
                SELECT coaches
                FROM national_rail_seat_layouts
                WHERE schedule_id = %s
                AND deleted_at IS NULL
                """,
                (schedule_id,)
            )

            layout = cur.fetchone()

            if not layout:
                return []

            # 2. Get booked seats
            cur.execute(
                """
                SELECT seat_id
                FROM national_rail_bookings
                WHERE schedule_id = %s
                AND travel_date = %s
                AND fare_class = %s
                AND status = 'confirmed'
                AND deleted_at IS NULL
                """,
                (
                    schedule_id,
                    travel_date,
                    fare_class
                )
            )

            booked_rows = cur.fetchall()

            booked_seats = {
                row["seat_id"]
                for row in booked_rows
            }

            # 3. Build available seat list
            available_seats = []

            for coach in layout["coaches"]:

                if coach["fare_class"] != fare_class:
                    continue

                for seat in coach["seats"]:

                    if seat["seat_id"] not in booked_seats:

                        available_seats.append(
                            {
                                "seat_id": seat["seat_id"],
                                "coach": coach["coach"],
                                "row": seat["row"],
                                "column": seat["column"]
                            }
                        )

            return available_seats


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible (same row preferred,
    then adjacent rows). Returns a list of seat_ids.

    Args:
        available_seats: output of query_available_seats()
        count:           number of seats needed
    """
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_profile(user_email: str) -> Optional[dict]:
    """Return a user's profile by email."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *,
                       first_name || ' ' || last_name AS full_name
                FROM users
                WHERE email = %s
                """,
                (user_email,)
            )

            row = cur.fetchone()

            if row:
                return dict(row)

            return None


def query_user_bookings(user_email: str) -> dict:
    """
    Return a user's combined booking history (national rail + metro).

    Returns:
        dict with keys 'national_rail' (list) and 'metro' (list)
    """

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT user_id
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                AND deleted_at IS NULL
                """,
                (user_email,)
            )

            user = cur.fetchone()

            if not user:
                return {
                    "national_rail": [],
                    "metro": []
                }

            user_id = user["user_id"]

            cur.execute(
                """
                SELECT *
                FROM national_rail_bookings
                WHERE user_id = %s
                AND deleted_at IS NULL
                ORDER BY booked_at DESC
                """,
                (user_id,)
            )

            national_rail = [
                dict(row)
                for row in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT *
                FROM metro_trips
                WHERE user_id = %s
                AND deleted_at IS NULL
                ORDER BY purchased_at DESC
                """,
                (user_id,)
            )

            metro = [
                dict(row)
                for row in cur.fetchall()
            ]

            return {
                "national_rail": national_rail,
                "metro": metro
            }

def query_payment_info(booking_id: str) -> Optional[dict]:
    """Return payment record for a booking or metro trip."""

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT *
                FROM payments
                WHERE national_rail_booking_id = %s
                AND deleted_at IS NULL
                """,
                (booking_id,)
            )

            payment = cur.fetchone()

            if not payment:
                return None

            return dict(payment)

# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT *
                FROM national_rail_schedules
                WHERE schedule_id = %s
                AND deleted_at IS NULL
                """,
                (schedule_id,)
            )

            schedule = cur.fetchone()
            
            departure_time = schedule["first_train_time"]

            if not schedule:
                return (False, "Schedule not found")

            stops = schedule["stops_in_order"]

            if (
                origin_station_id not in stops
                or destination_station_id not in stops
            ):
                return (False, "Invalid stations")

            origin_pos = stops.index(origin_station_id)
            destination_pos = stops.index(destination_station_id)

            if origin_pos >= destination_pos:
                return (False, "Invalid travel direction")

            stops_travelled = destination_pos - origin_pos
            
            fare_info = query_national_rail_fare(
                schedule_id,
                fare_class,
                stops_travelled
            )

            if not fare_info:
                return (False, "Fare not found")

            amount_usd = fare_info["total_fare_usd"]
            
            available_seats = query_available_seats(
                schedule_id,
                travel_date,
                fare_class
            )

            if not available_seats:
                return (False, "No available seats")
                            
            selected_seat = None
            
            if seat_id == "any":
    
                selected = auto_select_adjacent_seats(
                    available_seats,
                    1
                )

                if not selected:
                    return (False, "No available seats")

                seat_id = selected[0]


            for seat in available_seats:

                if seat["seat_id"] == seat_id:
                    selected_seat = seat
                    break

            if not selected_seat:
                return (False, "Seat not available")

            coach = selected_seat["coach"]
            
            booking_id = _gen_booking_id()

            cur.execute(
                """
                INSERT INTO national_rail_bookings (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    departure_time,
                    ticket_type,
                    fare_class,
                    coach,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                    status,
                    booked_at
)
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, NOW()
                )
                """,
                (
                    booking_id,
                    user_id,
                    schedule_id,
                    origin_station_id,
                    destination_station_id,
                    travel_date,
                    departure_time,
                    ticket_type,
                    fare_class,
                    coach,
                    seat_id,
                    stops_travelled,
                    amount_usd,
                    "confirmed"
                )
            )
            payment_id = _gen_payment_id()

            cur.execute(
                """
                INSERT INTO payments (
                    payment_id,
                    national_rail_booking_id,
                    amount_usd,
                    method,
                    status,
                    paid_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, NOW()
                )
                """,
                (
                    payment_id,
                    booking_id,
                    amount_usd,
                    "card",
                    "paid"
                )
            )

            conn.commit()

            return (
                True,
                {
                    "booking_id": booking_id,
                    "payment_id": payment_id,
                    "seat_id": seat_id,
                    "coach": coach,
                    "amount_usd": amount_usd,
                    "status": "confirmed"
                }
            )


def execute_cancellation(
    booking_id: str,
    user_id: str
) -> tuple[bool, dict | str]:

    with _connect() as conn:
        with conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:

            cur.execute(
                """
                SELECT *
                FROM national_rail_bookings
                WHERE booking_id = %s
                AND deleted_at IS NULL
                """,
                (booking_id,)
            )

            booking = cur.fetchone()

            if not booking:
                return (False, "Booking not found")

            if booking["user_id"] != user_id:
                return (False, "Unauthorized")

            if booking["status"] == "cancelled":
                return (False, "Booking already cancelled")

            refund_amount = booking["amount_usd"]

            cur.execute(
                """
                UPDATE national_rail_bookings
                SET status = 'cancelled'
                WHERE booking_id = %s
                """,
                (booking_id,)
            )
            cur.execute(
                """
                UPDATE payments
                SET status = 'refunded'
                WHERE national_rail_booking_id = %s
                AND deleted_at IS NULL
                """,
                (booking_id,)
            )
            
            conn.commit()
            
            return (
                True,
                {
                    "booking_id": booking_id,
                    "refund_amount_usd": refund_amount,
                    "status": "cancelled"
                }
            )

# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    last_name: str,
    date_of_birth: str,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (True, user_id) on success or (False, error_message) on failure.
    """

    with _connect() as conn:
        with conn.cursor() as cur:

            # Check if email already exists
            cur.execute(
                """
                SELECT 1
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                AND deleted_at IS NULL
                """,
                (email,)
            )

            if cur.fetchone():
                return (False, "Email already registered")

            # Generate user ID
            user_id = "RU" + ''.join(random.choices(string.digits, k=4))

            # Normalise date_of_birth: the UI passes only a birth year (int/float/str).
            # Always convert to "YYYY-01-01" so psycopg2 can bind it to DATE column.
            date_of_birth = f"{str(date_of_birth).strip()[:4]}-01-01"

            # Hash sensitive data
            password_hash = ph.hash(password)
            secret_answer_hash = ph.hash(secret_answer)

            # Insert into users
            cur.execute(
                """
                INSERT INTO users (
                    user_id,
                    email,
                    first_name,
                    last_name,
                    date_of_birth
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    email,
                    first_name,
                    last_name,
                    date_of_birth
                )
            )

            # Insert into credentials table
            cur.execute(
                """
                INSERT INTO user_credentials (
                    user_id,
                    password_hash,
                    secret_question,
                    secret_answer_hash
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    user_id,
                    password_hash,
                    secret_question,
                    secret_answer_hash
                )
            )

            return (True, user_id)
        
def login_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns a user dict on success or None on failure.
    """

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(
                """
                SELECT
                    u.user_id,
                    u.first_name,
                    u.last_name AS surname,
                    u.email,
                    u.phone,
                    u.date_of_birth,
                    u.registered_at,
                    u.is_active,
                    uc.password_hash
                FROM users u
                JOIN user_credentials uc
                    ON u.user_id = uc.user_id
                WHERE LOWER(u.email) = LOWER(%s)
                AND u.deleted_at IS NULL
                AND uc.deleted_at IS NULL
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return None

            try:
                ph.verify(row["password_hash"], password)

                user_data = dict(row)
                user_data.pop("password_hash", None)

                return user_data

            except VerifyMismatchError:
                return None


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""

    with _connect() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT uc.secret_question
                FROM users u
                JOIN user_credentials uc ON u.user_id = uc.user_id
                WHERE LOWER(u.email) = LOWER(%s)
                AND u.deleted_at IS NULL
                AND uc.deleted_at IS NULL
                """,
                (email,)
            )

            row = cur.fetchone()

            if row:
                return row[0]

            return None


def verify_secret_answer(email: str, answer: str) -> bool:
    """Return True if the provided answer matches the stored secret answer."""

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            cur.execute(
                """
                SELECT uc.secret_answer_hash
                FROM users u
                JOIN user_credentials uc
                    ON u.user_id = uc.user_id
                WHERE LOWER(u.email) = LOWER(%s)
                AND u.deleted_at IS NULL
                AND uc.deleted_at IS NULL
                """,
                (email,)
            )

            row = cur.fetchone()

            if not row:
                return False

            try:
                ph.verify(row["secret_answer_hash"], answer)
                return True

            except VerifyMismatchError:
                return False

def update_password(email: str, new_password: str) -> bool:
    """Update the password for a user."""

    password_hash = ph.hash(new_password)

    with _connect() as conn:
        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE user_credentials
                SET password_hash = %s
                WHERE user_id = (
                    SELECT user_id
                    FROM users
                    WHERE LOWER(email) = LOWER(%s)
                    AND deleted_at IS NULL
                )
                AND deleted_at IS NULL
                """,
                (password_hash, email)
            )

            return cur.rowcount > 0

# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Find the most relevant policy documents for a given query embedding.

    Args:
        embedding: Query vector from llm.embed(user_question)
        top_k:     Number of results to return

    Returns:
        List of dicts with title, category, content, and similarity score
    """
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """
    Insert a policy document with its embedding into the database.
    Used by skeleton/seed_vectors.py — students don't need to call this directly.

    Returns:
        The new document's id
    """
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]
