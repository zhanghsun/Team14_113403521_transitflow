-- ============================================================
-- TransitFlow PostgreSQL Schema
-- Final Simplified Course Version
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- USERS
-- ============================================================

CREATE TABLE users (
    user_id         VARCHAR(20) PRIMARY KEY,
    first_name      VARCHAR(50) NOT NULL,
    last_name       VARCHAR(50) NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    phone           VARCHAR(20),
    date_of_birth   DATE,
    registered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active       BOOLEAN DEFAULT TRUE,
    deleted_at      TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- USER CREDENTIALS
-- ============================================================

CREATE TABLE user_credentials (
    c_id             SERIAL PRIMARY KEY,
    user_id          VARCHAR(20) NOT NULL UNIQUE
                     REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash    VARCHAR(255) NOT NULL,
    secret_question  VARCHAR(255) NOT NULL,
    secret_answer_hash VARCHAR(255) NOT NULL,
    deleted_at       TIMESTAMP
);
-- ============================================================
-- METRO STATIONS
-- ============================================================

CREATE TABLE metro_stations (
    station_id                     VARCHAR(20) PRIMARY KEY,
    name                           VARCHAR(100) NOT NULL,
    is_interchange_metro           BOOLEAN,
    is_interchange_national_rail   BOOLEAN,
    interchange_national_rail_station_id VARCHAR(20),
    deleted_at                     TIMESTAMP
);

CREATE TABLE metro_station_lines (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(20) REFERENCES metro_stations(station_id),
    line            VARCHAR(10),
    deleted_at      TIMESTAMP
);

-- ============================================================
-- NATIONAL RAIL STATIONS
-- ============================================================

CREATE TABLE national_rail_stations (
    station_id                     VARCHAR(20) PRIMARY KEY,
    name                           VARCHAR(100) NOT NULL,
    is_interchange_national_rail   BOOLEAN,
    is_interchange_metro           BOOLEAN,
    interchange_metro_station_id   VARCHAR(20),
    deleted_at                     TIMESTAMP
);

CREATE TABLE national_rail_station_lines (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(20) REFERENCES national_rail_stations(station_id),
    line            VARCHAR(10),
    deleted_at      TIMESTAMP
);
-- ============================================================
-- METRO SCHEDULES
-- ============================================================

CREATE TABLE metro_schedules (
    schedule_id                VARCHAR(20) PRIMARY KEY,
    line                       VARCHAR(10),
    direction                  VARCHAR(20),
    origin_station_id          VARCHAR(20) REFERENCES metro_stations(station_id),
    destination_station_id     VARCHAR(20) REFERENCES metro_stations(station_id),
    first_train_time           TIME,
    last_train_time            TIME,
    base_fare_usd              NUMERIC(10,2) CHECK (base_fare_usd >= 0),
    per_stop_rate_usd          NUMERIC(10,2) CHECK (per_stop_rate_usd >= 0),
    frequency_min              INTEGER CHECK (frequency_min > 0),
    stops_in_order             JSONB,
    travel_time_from_origin_min JSONB,
    operates_on                JSONB,
    deleted_at                 TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);
-- ============================================================
-- NATIONAL RAIL SCHEDULES
-- ============================================================

CREATE TABLE national_rail_schedules (
    schedule_id                VARCHAR(20) PRIMARY KEY,
    line                       VARCHAR(10),
    service_type               VARCHAR(20),
    direction                  VARCHAR(20),
    origin_station_id          VARCHAR(20) REFERENCES national_rail_stations(station_id),
    destination_station_id     VARCHAR(20) REFERENCES national_rail_stations(station_id),
    first_train_time           TIME,
    last_train_time            TIME,
    frequency_min              INTEGER CHECK (frequency_min > 0),
    stops_in_order             JSONB,
    passed_through_stations    JSONB,
    travel_time_from_origin_min JSONB,
    fare_classes               JSONB,
    operates_on                JSONB,
    deleted_at                 TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);
-- ============================================================
-- NATIONAL RAIL SEAT LAYOUTS
-- ============================================================

CREATE TABLE national_rail_seat_layouts (
    layout_id      VARCHAR(20) PRIMARY KEY,
    schedule_id    VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    coaches        JSONB,
    deleted_at     TIMESTAMP
);
-- ============================================================
-- NATIONAL RAIL BOOKINGS
-- ============================================================

CREATE TABLE national_rail_bookings (
    booking_id                 VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id),
    schedule_id                VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id          VARCHAR(20) REFERENCES national_rail_stations(station_id),
    destination_station_id     VARCHAR(20) REFERENCES national_rail_stations(station_id),
    travel_date                DATE,
    departure_time             TIME,
    ticket_type                VARCHAR(20),
    fare_class                 VARCHAR(20),
    coach                      VARCHAR(5),
    seat_id                    VARCHAR(10),
    stops_travelled            INTEGER CHECK (stops_travelled >= 0),
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    status                     VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    booked_at                  TIMESTAMP,
    travelled_at               TIMESTAMP,
    deleted_at                 TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

-- ============================================================
-- METRO TRIPS
-- ============================================================

CREATE TABLE metro_trips (
    trip_id                    VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id),
    schedule_id                VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id          VARCHAR(20) REFERENCES metro_stations(station_id),
    destination_station_id     VARCHAR(20) REFERENCES metro_stations(station_id),
    travel_date                DATE,
    ticket_type                VARCHAR(20),
    day_pass_ref               VARCHAR(20),
    stops_travelled            INTEGER CHECK (stops_travelled >= 0),
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    status                     VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    purchased_at               TIMESTAMP,
    travelled_at               TIMESTAMP,
    deleted_at                 TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

-- ============================================================
-- PAYMENTS
-- ============================================================

CREATE TABLE payments (
    payment_id                 VARCHAR(20) PRIMARY KEY,
    national_rail_booking_id   VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
    metro_trip_id              VARCHAR(20) REFERENCES metro_trips(trip_id),
    amount_usd                 NUMERIC(10,2) CHECK (amount_usd >= 0),
    method                     VARCHAR(50),
    status                     VARCHAR(20) CHECK (status IN ('paid', 'refunded', 'failed')),
    paid_at                    TIMESTAMP,
    deleted_at                 TIMESTAMP,
    CHECK (national_rail_booking_id IS NOT NULL OR metro_trip_id IS NOT NULL)
);

-- ============================================================
-- FEEDBACK
-- ============================================================

CREATE TABLE feedback (
    feedback_id                VARCHAR(20) PRIMARY KEY,
    user_id                    VARCHAR(20) REFERENCES users(user_id),
    national_rail_booking_id   VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
    metro_trip_id              VARCHAR(20) REFERENCES metro_trips(trip_id),
    rating                     INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment                    TEXT,
    submitted_at               TIMESTAMP,
    deleted_at                 TIMESTAMP,
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
    created_at      TIMESTAMP
);