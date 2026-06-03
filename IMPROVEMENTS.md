# IMPROVEMENTS.md

**Date:** 2026-06-01
**Project:** TransitFlow
**Status:** Core System Completed & Integrated

---

# Project Progress Summary

TransitFlow has completed the core implementation of:

* PostgreSQL relational database
* Neo4j graph database
* Authentication system
* Booking and cancellation workflows
* Payment and refund workflows
* AI tool calling integration
* Gradio user interface

All major Phase 1 and Phase 2 components have been implemented and tested.

---

# 1. Authentication System Improvements

## Added Helper Functions

### split_full_name(full_name)

Purpose:

* Split full names into first and last names
* Used during user seeding

Example:

```python
"Alice Tan"
→ ("Alice", "Tan")
```

---

### hash_secret(value)

Purpose:

* Securely hash sensitive information
* Uses Argon2id

Applied to:

* Passwords
* Secret answers

Returns:

```python
None
```

when input is missing.

---

## Authentication Architecture

Authentication data is separated into two tables.

### users

Stores:

* profile information
* email
* phone
* birth date

### user_credentials

Stores:

* password_hash
* secret_question
* secret_answer_hash

Benefits:

* credential isolation
* improved security
* easier maintenance
* production-style design

---

# 2. Password Security Improvements

## Argon2id Implementation

Passwords are never stored in plaintext.

Example format:

```text
$argon2id$v=19$m=65536,t=3,p=4$...
```

Verification performed using:

```python
ph.verify(stored_hash, input_password)
```

---

## Security Rules

Implemented:

* password hashing
* secret answer hashing
* embedded salt storage
* password verification

Not implemented:

* plaintext password storage

Verification completed through PostgreSQL inspection.

Result:

✅ Passwords hashed

✅ Secret answers hashed

---

# 3. Email Normalization

Insert Rule:

```python
email.lower()
```

Query Rule:

```sql
LOWER(email)
```

Benefits:

* avoids duplicate accounts
* avoids casing inconsistencies

Example:

```text
ABC@gmail.com
abc@gmail.com
```

treated as identical users.

---

# 4. Soft Delete Architecture

Tables support:

```sql
deleted_at TIMESTAMP
```

Rules:

```text
deleted_at IS NULL
```

→ active record

```text
deleted_at IS NOT NULL
```

→ archived record

Most queries automatically exclude deleted records.

---

# 5. PostgreSQL Seed Improvements

Completed seeding for:

## Metro

* metro_stations
* metro_station_lines
* metro_schedules
* metro_trips

## National Rail

* national_rail_stations
* national_rail_station_lines
* national_rail_schedules
* national_rail_seat_layouts
* national_rail_bookings

## User System

* users
* user_credentials

## Payments

* payments

## Feedback

* feedback

---

# 6. Query Layer Implementation

## Profile Queries

Completed:

```python
query_user_profile()
query_user_bookings()
query_payment_info()
```

Capabilities:

* retrieve profile information
* retrieve booking history
* retrieve payment information

---

## Availability Queries

Completed:

```python
query_national_rail_availability()
query_national_rail_fare()
query_available_seats()
```

Capabilities:

* train availability lookup
* fare calculation
* seat availability calculation

---

# 7. Booking Workflow

Implemented:

```python
execute_booking()
```

Features:

* schedule validation
* station validation
* travel direction validation
* fare calculation
* seat assignment
* booking creation
* payment creation

Supports:

```text
seat_id = "any"
```

automatic seat assignment.

---

## Booking Verification

Successfully tested:

* booking insertion
* seat assignment
* fare generation
* payment generation

Result:

✅ Pass

---

# 8. Cancellation Workflow

Implemented:

```python
execute_cancellation()
```

Features:

* ownership validation
* booking cancellation
* refund generation
* payment status update

Booking status:

```text
confirmed
→ cancelled
```

Payment status:

```text
paid
→ refunded
```

Verification completed through PostgreSQL and pgAdmin.

Result:

✅ Pass

---

# 9. Payment System

Implemented:

* payment record creation
* payment lookup
* refund processing

Functions:

```python
query_payment_info()
```

Integrated with booking and cancellation workflows.

Verification:

✅ Pass

---

# 10. Neo4j Integration

Graph database implementation completed.

Branch:

```text
jingyuan/graph-neo4j
```

Merged into:

```text
main
```

Capabilities:

* shortest route search
* route planning
* transfer recommendations
* alternative path discovery

Status:

✅ Completed!

---

# 11. AI Tool Calling Integration

Agent successfully connected to:

## PostgreSQL Tools

* profile queries
* availability queries
* booking functions
* payment functions

## Neo4j Tools

* route planning
* graph search

Status:

✅ Operational

---

# 12. Gradio User Interface

UI successfully launched through:

```bash
python skeleton/ui.py
```

Local endpoint:

```text
http://localhost:7860
```

Capabilities:

* natural language queries
* route planning
* booking requests
* policy retrieval

Status:

✅ Operational

---

# Verification Results

| Check                  | Result |
| ---------------------- | ------ |
| PostgreSQL Seeding     | ✅ Pass |
| User Authentication    | ✅ Pass |
| Password Hashing       | ✅ Pass |
| Email Normalization    | ✅ Pass |
| Availability Queries   | ✅ Pass |
| Fare Queries           | ✅ Pass |
| Seat Availability      | ✅ Pass |
| Booking Creation       | ✅ Pass |
| Payment Creation       | ✅ Pass |
| Cancellation Flow      | ✅ Pass |
| Refund Processing      | ✅ Pass |
| User Booking Retrieval | ✅ Pass |
| pgAdmin Verification   | ✅ Pass |
| Neo4j Integration      | ✅ Pass |
| Tool Calling           | ✅ Pass |
| Gradio UI              | ✅ Pass |

---

# Current Team Progress

| Branch                  | Owner          | Status             |
| ----------------------- | -------------- | ------------------ |
| main                    | Team           | 🔄 Integration     |
| zhanghsun/seed-basic    | Zhang Hsun     | ✅ Completed        |
| zhanghsun/seed-complex  | Zhang Hsun     | ✅ Completed        |
| kc/queries-profile      | KC             | ✅ Completed        |
| kc/queries-availability | KC             | ✅ Completed        |
| kc/queries-booking      | KC             | ✅ Completed        |
| jingyuan/graph-neo4j    | Graph Teammate | ✅ Merged into Main |

---

# Remaining Work

* Final integration testing
* Design documentation
* Work allocation documentation
* TASK6 bonus features
* Final acceptance testing

---

# Final Notes

TransitFlow now includes:

* PostgreSQL
* Neo4j
* Authentication
* Booking System
* Payment System
* Refund System
* AI Tool Calling
* RAG Policy Retrieval
* Gradio Interface

Core functionality has been implemented and verified through both programmatic testing and database validation.
