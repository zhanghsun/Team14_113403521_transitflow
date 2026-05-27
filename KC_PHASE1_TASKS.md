# TransitFlow Phase 1 Team Handoff Guide

## 📌 Zhang Hsun 已完成（zhanghsun/seed-basic）

### Phase 1 Seeding — ✅ DONE

**Location:** `skeleton/seed_postgres.py`

**Completed Functions:**
1. ✅ `seed_metro_stations()` — 20 rows inserted
2. ✅ `seed_metro_station_lines()` — 25 rows (line decomposition)
3. ✅ `seed_national_rail_stations()` — 10 rows
4. ✅ `seed_national_rail_station_lines()` — 11 rows
5. ✅ `seed_users()` — 20 users + 20 credentials

**Helper Functions Added:**
- ✅ `split_full_name(full_name)` — Splits "Alice Tan" → ("Alice", "Tan")
- ✅ `hash_secret(value)` — Hashes with argon2id (password + secret_answer)

**Key Implementation Details:**
- Email normalized to lowercase during insert
- Full names split into first_name + last_name in users table
- Passwords and secret answers hashed with argon2id (MCF format with embedded salt)
- ON CONFLICT DO NOTHING for idempotent re-runs
- 20 test users ready in database

**Database Status:**
- PostgreSQL running ✅
- Schema applied ✅
- Test data seeded ✅
- Argon2id verified ✅

**Reference:** [IMPROVEMENTS.md](IMPROVEMENTS.md), [AI_SESSION_CONTEXT.md](AI_SESSION_CONTEXT.md)

---

## 📌 KC 要做的（kc/queries-profile）

### Phase 1 Queries — TO START

**Location:** `databases/relational/queries.py`

**7 Functions to Implement:**

#### 🔐 Authentication Functions (4)

1. **`login_user(email: str, password: str) -> Optional[dict]`**
   - Query user from `users` table by email (case-insensitive?)
   - Fetch password_hash from `user_credentials`
   - Verify: `ph.verify(db_password_hash, password)`
   - Return user dict if success, None if failed
   - Security: Must NOT return password in result

2. **`register_user(email: str, first_name: str, surname: str, year_of_birth: int, password: str, secret_question: str, secret_answer: str) -> tuple[bool, str]`**
   - Check if email already exists (raise error if duplicate)
   - Generate user_id (or auto-increment if using SERIAL)
   - Hash password: `ph.hash(password)`
   - Hash secret_answer: `ph.hash(secret_answer)`
   - Insert into users table (email UNIQUE constraint will catch duplicates)
   - Insert into user_credentials table
   - Return (True, user_id) if success, (False, error_msg) if failed

3. **`get_user_secret_question(email: str) -> Optional[str]`**
   - Query user_credentials by email
   - Return secret_question, or None if user not found

4. **`verify_secret_answer(email: str, answer: str) -> bool`**
   - Query user_credentials by email
   - Verify: `ph.verify(db_secret_answer_hash, answer)`
   - Return True if correct, False if incorrect or user not found

#### 👤 User Profile Functions (2)

5. **`query_user_profile(user_email: str) -> Optional[dict]`**
   - Query `users` table by email
   - Return dict with: user_id, first_name, last_name, email, phone, date_of_birth, registered_at, is_active
   - Return None if not found or deleted_at IS NOT NULL

6. **`query_user_bookings(user_email: str) -> dict`**
   - Query `national_rail_bookings` and `metro_trips` by user (via users.user_id)
   - Return: `{"national_rail": [...], "metro": [...]}`
   - Only return non-deleted bookings (deleted_at IS NULL)
   - Security: Only return if user is logged in (explicit requirement)

#### 🔄 Password Recovery Function (1)

7. **`update_password(email: str, new_password: str) -> bool`**
   - Query user_credentials by email
   - Hash new password: `ph.hash(new_password)`
   - Update password_hash in user_credentials
   - Return True if success, False if user not found

---

## 🔑 Critical Security Notes for KC

### Argon2id Pattern (MANDATORY)

```python
from argon2 import PasswordHasher

ph = PasswordHasher()

# Hashing (seeding/registration)
password_hash = ph.hash(user_password)  # Returns MCF format string
answer_hash = ph.hash(secret_answer)

# Verification (login/password reset)
try:
    ph.verify(db_password_hash, user_input_password)
    # Success! Password is correct
except:
    # Failed! Password is incorrect
```

### Important Facts

1. **Salt is embedded** in argon2id MCF format: `$argon2id$v=19$m=65536,t=3,p=4$[salt]$[hash]`
   - NO separate salt column needed
   - `ph.verify()` automatically extracts salt from hash

2. **Secret answer is ALSO hashed**, NOT plaintext
   - Same `ph.verify()` pattern as passwords
   - Critical for password recovery flow

3. **Email queries** should be case-insensitive (consider `.lower()` in WHERE clause)

4. **Deleted users** should not authenticate
   - Check `deleted_at IS NULL` in WHERE clause

---

## 📋 Implementation Checklist for KC

### Before Starting
- [ ] Review AI_SESSION_CONTEXT.md for function signatures
- [ ] Review IMPROVEMENTS.md for seeding implementation details
- [ ] Understand argon2id pattern (see above)

### Implementation Order (Recommended)
1. [ ] `login_user()` — Core auth function
2. [ ] `register_user()` — User creation
3. [ ] `get_user_secret_question()` — Password recovery prep
4. [ ] `verify_secret_answer()` — Password recovery verification
5. [ ] `update_password()` — Password reset completion
6. [ ] `query_user_profile()` — User data retrieval
7. [ ] `query_user_bookings()` — Booking history

### Testing
- [ ] Test with 20 seeded users from registered_users.json
- [ ] Test password verification with argon2id
- [ ] Test secret answer verification
- [ ] Test deletion/archival (deleted_at logic)
- [ ] Test email case-insensitivity

---

## 📚 Reference Data

### Seeded Test Users (20 total)
- Source: `train-mock-data/registered_users.json`
- All passwords hashed with argon2id
- All emails normalized to lowercase

### Database Connection Pattern (use this)

```python
import psycopg2
from psycopg2.extras import RealDictCursor
from argon2 import PasswordHasher

def _connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )

def login_user(email: str, password: str):
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Query logic here
            ...
```

### Schema Tables for Reference

```sql
-- users table
user_id (VARCHAR(20) PK)
first_name (VARCHAR(50))
last_name (VARCHAR(50))
email (VARCHAR(255) UNIQUE)
phone (VARCHAR(20))
date_of_birth (DATE)
registered_at (TIMESTAMP)
is_active (BOOLEAN)
deleted_at (TIMESTAMP)

-- user_credentials table
c_id (SERIAL PK)
user_id (VARCHAR(20) UNIQUE FK→users)
password_hash (VARCHAR(255))
secret_question (VARCHAR(255))
secret_answer_hash (VARCHAR(255))
deleted_at (TIMESTAMP)
```

---

## 🎯 Phase 1 Success Criteria

✅ All 7 functions implemented with correct signatures
✅ Argon2id used for password + secret answer (NOT MD5/SHA)
✅ Soft delete logic respected (deleted_at checks)
✅ Empty results return None/[] (not exceptions)
✅ Type hints on all functions
✅ Docstrings with Args: and Returns: sections
✅ Tests pass with 20 seeded users

---

## 📞 Communication with Teammates

- Zhang Hsun (Seeding): Phase 1 ✅ DONE, ready for KC
- KC (Queries): Phase 1 in progress
- Graph Student: Neo4j work (separate track)

**Git Branches:**
- `main` — Schema only
- `zhanghsun/seed-basic` — Phase 1 seeding ✅ DONE
- `kc/queries-profile` — Phase 1 queries (KC's branch)

---

## 🚀 Next Phase (Phase 2)

After Phase 1 Queries are done:
- Zhang Hsun: `zhanghsun/seed-complex` — Phase 2+ seeding (JSONB handling)
- KC: `kc/queries-availability` — Phase 2 queries (schedules, availability)
