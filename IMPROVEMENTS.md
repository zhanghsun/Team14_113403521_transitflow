# Phase 1 Code Improvements — Team Handoff & Development Guide

**Date:** 2025-05-27
**Project:** TransitFlow
**Primary Branch:** `zhanghsun/seed-basic`
**Current Status:** ✅ Completed & Tested
**Related Branch:** `kc/queries-profile` ✅ Mostly Completed

---

## Summary of Improvements

Enhanced `skeleton/seed_postgres.py` and related authentication architecture for:

* code clarity
* maintainability
* production-style authentication
* team handoff preparation
* future Phase 2 integration

This document should be reviewed before continuing development.

---

## 1. ✅ Added Helper Functions

### `split_full_name(full_name: str) -> tuple[str, str]`

* Extracts `first_name` and `last_name` from full name string
* Example: `"Alice Tan"` → `("Alice", "Tan")`
* Used in `seed_users()` for name decomposition

### `hash_secret(value: str | None) -> str | None`

* Hashes sensitive strings with **argon2id** (NOT MD5/SHA)
* Embeds salt in MCF format — no separate salt column needed
* Used for:

  * passwords
  * secret answers
* Returns `None` if input is `None`

---

## 2. ✅ Improved `seed_users()` Function

### Changes

* Uses `split_full_name()` and `hash_secret()`
* Added email normalization (`.lower()`)
* Better variable naming
* Separate loops for:

  * user_rows
  * credential_rows
* Added detailed security notes for KC

### Authentication Architecture

Authentication is now split into:

#### `users`

Stores:

* user profile
* email
* phone
* birth date

#### `user_credentials`

Stores:

* password_hash
* secret_question
* secret_answer_hash

### Why This Design?

Reason:

* credential isolation
* improved security
* production-style architecture
* easier future maintenance

---

## 3. ✅ KC Completed Authentication Query Refactor

### Branch

`kc/queries-profile`

### Completed Functions

| Function               | Status |
| ---------------------- | ------ |
| register_user()        | ✅      |
| login_user()           | ✅      |
| verify_secret_answer() | ✅      |
| update_password()      | ✅      |
| query_user_profile()   | ✅      |

### Partially Pending

| Function                   | Notes                       |
| -------------------------- | --------------------------- |
| get_user_secret_question() | may require JOIN refinement |
| query_user_bookings()      | waiting for Phase 2 tables  |

---

## 4. ✅ Argon2id Security Rules

### IMPORTANT SECURITY NOTES

```python
from argon2 import PasswordHasher

ph = PasswordHasher()

# Hashing
password_hash = ph.hash(password)

# Verification
try:
    ph.verify(db_password_hash, input_password)
except:
    # invalid password
```

### Important Notes

* Passwords are NEVER stored in plaintext
* Secret answers are ALSO hashed
* Salt is EMBEDDED in argon2id MCF format
* No separate salt column is required

---

## 5. ✅ Email Normalization

### Insert Rule

```python
email.lower()
```

### Query Rule

```sql
LOWER(email)
```

### Reason

Avoid:

* duplicate accounts
* casing inconsistency

Example:

* `ABC@gmail.com`
* `abc@gmail.com`

should be treated as the same account.

---

## 6. ✅ Soft Delete Architecture

Tables use:

```sql
deleted_at TIMESTAMP
```

### Rule

* `deleted_at IS NULL` → active
* `deleted_at IS NOT NULL` → archived/logically deleted

### Future Query Rule

Most future queries should include:

```sql
AND deleted_at IS NULL
```

unless intentionally querying archived data.

---

## 7. ✅ Added Code Organization Comments

Examples:

```python
# ── helper functions ─────────────────────────────
# ── data loading & connection ────────────────────
```

Purpose:

* improve readability
* faster teammate navigation
* easier debugging

---

## Verification Results

| Check                             | Result |
| --------------------------------- | ------ |
| Syntax validation                 | ✅ Pass |
| Helper functions work             | ✅ Pass |
| `split_full_name()` decomposition | ✅ Pass |
| Argon2id hash format correct      | ✅ Pass |
| Email normalization               | ✅ Pass |
| Phase 1 seeding still works       | ✅ Pass |
| ON CONFLICT DO NOTHING idempotent | ✅ Pass |
| 20 users seeded                   | ✅ Pass |
| 20 credentials seeded             | ✅ Pass |

---

## Current Database Status

### ✅ Ready Tables

* metro_stations
* metro_station_lines
* national_rail_stations
* national_rail_station_lines
* users
* user_credentials

### ⏳ Pending Phase 2 Tables

* metro_schedules
* national_rail_schedules
* national_rail_bookings
* metro_trips
* payments
* feedback
* seat_layouts

---

## Current Team Progress

| Branch                  | Owner          | Status             |
| ----------------------- | -------------- | ------------------ |
| main                    | Team           | 🔄 integration     |
| zhanghsun/seed-basic    | Zhang Hsun     | ✅ completed        |
| kc/queries-profile      | KC             | ✅ mostly completed |
| zhanghsun/seed-complex  | Zhang Hsun     | 🔄 in progress     |
| kc/queries-availability | KC             | ⏳ waiting          |
| kc/queries-booking      | KC             | ⏳ waiting          |
| jingyuan/graph-neo4j    | Graph teammate | 🔄 parallel        |

---

## Next Steps

### Zhang Hsun

### Branch

`zhanghsun/seed-complex`

### Tasks

* seed_metro_schedules()
* seed_national_rail_schedules()
* seed_seat_layouts()
* seed_national_rail_bookings()
* seed_metro_travels()
* seed_payments()
* seed_feedback()

---

### KC

### Branch

`kc/queries-availability`

### Tasks

* query_metro_schedules()
* query_national_rail_schedules()
* query_available_seats()
* query_national_rail_fare()
* query_metro_fare()

### Dependency Warning

⚠️ Wait until Phase 2 seeding/schema stabilizes before implementing JOIN-heavy queries.

---

## Current Architecture Discussion

### Seat Availability Design

Discussion topic:

> Should available seats be dynamically calculated or stored in an occupancy table?

Still under evaluation.

Possible considerations:

* query complexity
* consistency
* redundancy
* scalability
* performance

---

## Recommended Workflow Before Starting Work

Always run:

```bash
git fetch origin
git merge origin/<teammate-branch>
```

before continuing development.

Avoid directly modifying:

```bash
main
```

Use feature branches only.

---

## Important Files to Review Before Working

| File                  | Purpose             |
| --------------------- | ------------------- |
| AI_SESSION_CONTEXT.md | architecture memory |
| IMPROVEMENTS.md       | development history |
| schema.sql            | relational schema   |
| seed_postgres.py      | seeding logic       |
| queries.py            | query layer         |

---

## Final Notes

This project now includes:

* PostgreSQL
* Neo4j
* authentication systems
* AI tool calling
* RAG/vector policy retrieval
* multi-stage normalization

Future development should preserve:

* argon2id authentication flow
* deleted_at logic
* email normalization
* branch workflow
* schema consistency
