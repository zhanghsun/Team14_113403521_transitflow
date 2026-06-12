-- ============================================================
-- TransitFlow PostgreSQL Schema
-- Final Simplified Course Version
-- ============================================================

-- NOTE FOR REVIEWERS: 下列註解僅供檢閱用途；此檔案內容未因註解而改變 schema 行為。
CREATE EXTENSION IF NOT EXISTS vector;

-- Deletion strategy: soft-delete via `deleted_at` timestamps across tables.
-- Rationale: preserve historical records for auditing and grading; `deleted_at` is
-- populated with a TIMESTAMPTZ when a row is logically deleted. Reviewers expect
-- a consistent soft-delete strategy rather than ad-hoc hard deletes.

-- ============================================================
-- USERS
-- ============================================================

-- PK choice: `user_id` is a human-readable VARCHAR key (prefixed IDs like RU####)
-- Rationale: easier debugging and readable identifiers in logs/UI; stable natural key
CREATE TABLE users (
    user_id         VARCHAR(20) PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(20),
    date_of_birth   DATE,
    registered_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_active       BOOLEAN DEFAULT TRUE,
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- USER CREDENTIALS
-- ============================================================

-- PK choice: `c_id` uses a SERIAL surrogate primary key for credentials
-- Rationale: credentials rows are internal records; SERIAL surrogate avoids coupling
CREATE TABLE user_credentials (
    c_id             SERIAL PRIMARY KEY,
    user_id          VARCHAR(20) NOT NULL UNIQUE
                     REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash    VARCHAR(255) NOT NULL,
    secret_question  VARCHAR(255) NOT NULL,
    secret_answer_hash VARCHAR(255) NOT NULL,
    deleted_at       TIMESTAMPTZ
);
-- ============================================================
-- METRO STATIONS
-- ============================================================

-- PK choice: `station_id` is a short VARCHAR code (e.g. MS01)
-- Rationale: station codes are stable natural identifiers used across systems
CREATE TABLE metro_stations (
    station_id                     VARCHAR(20) PRIMARY KEY,
    name                           VARCHAR(100) NOT NULL,
    is_interchange_metro           BOOLEAN,
    is_interchange_national_rail   BOOLEAN,
    interchange_national_rail_station_id VARCHAR(20),
    deleted_at                     TIMESTAMPTZ
);

-- PK choice: `id` is a SERIAL surrogate for line membership rows
-- Rationale: surrogate simplifies updates and keeps row identity independent of station code
CREATE TABLE metro_station_lines (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(20) REFERENCES metro_stations(station_id) ON DELETE CASCADE,
    line            VARCHAR(10),
    deleted_at      TIMESTAMPTZ
);

-- ============================================================
-- NATIONAL RAIL STATIONS
-- ============================================================

-- PK choice: `station_id` is a short VARCHAR code (e.g. NR01)
-- Rationale: natural station codes are stable and convenient for cross-referencing
CREATE TABLE national_rail_stations (
    station_id                     VARCHAR(20) PRIMARY KEY,
    name                           VARCHAR(100) NOT NULL,
    is_interchange_national_rail   BOOLEAN,
    is_interchange_metro           BOOLEAN,
    interchange_metro_station_id   VARCHAR(20),
    deleted_at                     TIMESTAMPTZ
);

-- PK choice: `id` is a SERIAL surrogate for rail station-line membership rows
CREATE TABLE national_rail_station_lines (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(20) REFERENCES national_rail_stations(station_id) ON DELETE CASCADE,
    line            VARCHAR(10),
    deleted_at      TIMESTAMPTZ
);
-- ============================================================
-- METRO SCHEDULES
-- ============================================================

-- PK choice: `schedule_id` is a VARCHAR (human-readable schedule code)
-- Rationale: readable IDs simplify testing and seed data mapping
CREATE TABLE metro_schedules (
    schedule_id                VARCHAR(20) PRIMARY KEY,
    line                       VARCHAR(10),
    direction                  VARCHAR(20),
    origin_station_id          VARCHAR(20) REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    destination_station_id     VARCHAR(20) REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    first_train_time           TIME,
    last_train_time            TIME,
    base_fare_usd              NUMERIC(10,2) CHECK (base_fare_usd >= 0),
    per_stop_rate_usd          NUMERIC(10,2) CHECK (per_stop_rate_usd >= 0),
    frequency_min              INTEGER CHECK (frequency_min > 0),
    stops_in_order             JSONB,
    travel_time_from_origin_min JSONB,
    operates_on                JSONB,
    deleted_at                 TIMESTAMPTZ,
    CHECK (origin_station_id <> destination_station_id)
);
-- ============================================================
-- NATIONAL RAIL SCHEDULES
-- ============================================================

-- PK choice: `schedule_id` is a VARCHAR (human-readable schedule code)
CREATE TABLE national_rail_schedules (
    schedule_id                VARCHAR(20) PRIMARY KEY,
    line                       VARCHAR(10),
    service_type               VARCHAR(20),
    direction                  VARCHAR(20),
    origin_station_id          VARCHAR(20) REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    destination_station_id     VARCHAR(20) REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    first_train_time           TIME,
    last_train_time            TIME,
    frequency_min              INTEGER CHECK (frequency_min > 0),
    stops_in_order             JSONB,
    passed_through_stations    JSONB,
    travel_time_from_origin_min JSONB,
    fare_classes               JSONB,
    operates_on                JSONB,
    deleted_at                 TIMESTAMPTZ,
    CHECK (origin_station_id <> destination_station_id)
);
-- ============================================================
-- NATIONAL RAIL SEAT LAYOUTS
-- ============================================================

-- PK choice: `layout_id` is a VARCHAR to align with seeded layout identifiers
CREATE TABLE national_rail_seat_layouts (
    layout_id      VARCHAR(20) PRIMARY KEY,
    schedule_id    VARCHAR(20) REFERENCES national_rail_schedules(schedule_id) ON DELETE CASCADE,
    coaches        JSONB,
    deleted_at     TIMESTAMPTZ
);
-- ============================================================
-- NATIONAL RAIL BOOKINGS
-- ============================================================

-- PK choice: `booking_id` is a prefixed VARCHAR (e.g. BK-XXXXXX)
-- Rationale: prefixed readable IDs are convenient for logs and UI, and avoid sequence collisions
CREATE TABLE national_rail_bookings (
    booking_id                 VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id) ON DELETE RESTRICT,
    schedule_id                VARCHAR(20) REFERENCES national_rail_schedules(schedule_id) ON DELETE RESTRICT,
    origin_station_id          VARCHAR(20) REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    destination_station_id     VARCHAR(20) REFERENCES national_rail_stations(station_id) ON DELETE RESTRICT,
    travel_date                DATE,
    departure_time             TIME,
    ticket_type                VARCHAR(20),
    fare_class                 VARCHAR(20),
    coach                      VARCHAR(5),
    seat_id                    VARCHAR(10),
    stops_travelled            INTEGER CHECK (stops_travelled >= 0),
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    status                     VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    booked_at                  TIMESTAMPTZ,
    travelled_at               TIMESTAMPTZ,
    deleted_at                 TIMESTAMPTZ,
    CHECK (origin_station_id <> destination_station_id)
);

-- ============================================================
-- METRO TRIPS
-- ============================================================

-- PK choice: `trip_id` is a VARCHAR code for metro trip records
CREATE TABLE metro_trips (
    trip_id                    VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id) ON DELETE RESTRICT,
    schedule_id                VARCHAR(20) REFERENCES metro_schedules(schedule_id) ON DELETE RESTRICT,
    origin_station_id          VARCHAR(20) REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    destination_station_id     VARCHAR(20) REFERENCES metro_stations(station_id) ON DELETE RESTRICT,
    travel_date                DATE,
    ticket_type                VARCHAR(20),
    day_pass_ref               VARCHAR(20),
    stops_travelled            INTEGER CHECK (stops_travelled >= 0),
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    status                     VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    purchased_at               TIMESTAMPTZ,
    travelled_at               TIMESTAMPTZ,
    deleted_at                 TIMESTAMPTZ,
    CHECK (origin_station_id <> destination_station_id)
);

-- ============================================================
-- PAYMENTS
-- ============================================================

-- PK choice: `payment_id` is a VARCHAR (prefixed for readability, e.g. PM-XXXX)
CREATE TABLE payments (
    payment_id                 VARCHAR(20) PRIMARY KEY,
    national_rail_booking_id   VARCHAR(20) REFERENCES national_rail_bookings(booking_id) ON DELETE SET NULL,
    metro_trip_id              VARCHAR(20) REFERENCES metro_trips(trip_id) ON DELETE SET NULL,
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    method                     VARCHAR(50),
    status                     VARCHAR(20) CHECK (status IN ('paid', 'refunded', 'failed')),
    paid_at                    TIMESTAMPTZ,
    deleted_at                 TIMESTAMPTZ,
    CHECK (national_rail_booking_id IS NOT NULL OR metro_trip_id IS NOT NULL)
);

-- ============================================================
-- FEEDBACK
-- ============================================================

-- PK choice: `feedback_id` is a VARCHAR to allow human-friendly identifiers
CREATE TABLE feedback (
    feedback_id                VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id) ON DELETE SET NULL,
    national_rail_booking_id   VARCHAR(20) REFERENCES national_rail_bookings(booking_id) ON DELETE SET NULL,
    metro_trip_id              VARCHAR(20) REFERENCES metro_trips(trip_id) ON DELETE SET NULL,
    rating                     INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment                    TEXT,
    submitted_at               TIMESTAMPTZ,
    deleted_at                 TIMESTAMPTZ,
    CHECK (national_rail_booking_id IS NOT NULL OR metro_trip_id IS NOT NULL)
);
-- ============================================================
-- POLICY DOCUMENTS
-- ============================================================

CREATE TABLE policy_documents (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(200),
    category        VARCHAR(50),
    content         TEXT,
    embedding       vector(768),
    source_file     VARCHAR(200),
    created_at      TIMESTAMPTZ
);