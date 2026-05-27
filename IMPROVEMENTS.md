# Phase 1 Code Improvements — Handoff to KC

**Date:** 2025-05-27  
**Branch:** `zhanghsun/seed-basic`  
**Status:** ✅ Completed & Tested

---

## Summary of Improvements

Enhanced `skeleton/seed_postgres.py` for **code clarity, maintainability, and KC handoff preparation**.

### 1. ✅ Added Helper Functions

#### `split_full_name(full_name: str) -> tuple[str, str]`
- Extracts `first_name` and `last_name` from full name string
- Example: `"Alice Tan"` → `("Alice", "Tan")`
- Used in `seed_users()` for name decomposition

#### `hash_secret(value: str | None) -> str | None`
- Hashes sensitive strings with **argon2id** (NOT MD5/SHA)
- Embeds salt in MCF format — no separate salt column needed
- Used for both passwords and secret answers
- Returns `None` if input is `None`

### 2. ✅ Improved `seed_users()` Function

**Changes:**
- Uses new `split_full_name()` and `hash_secret()` helper functions
- Added comprehensive docstring with **CRITICAL security notes for KC**
- Added email normalization to lowercase (`.lower()`)
- Better code organization: separate loops for user rows vs credential rows
- Improved variable naming: `cred_rows` → `credential_rows`

**Security Notes for KC (included in code):**

```
IMPORTANT SECURITY NOTES (for KC's queries.py):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Passwords are hashed with argon2id (NOT plaintext, NOT MD5/SHA)
- Salt is EMBEDDED in argon2id MCF format — do NOT store separately
- To verify a password in queries.py:
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    ph.verify(db_password_hash, user_input_password)
- Secret answers are ALSO hashed with argon2id — use same verification
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3. ✅ Added Code Organization Comments

- `# ── helper functions ────────────────────────────────────────────`
- `# ── data loading & connection ───────────────────────────────────`

Helps KC navigate code sections quickly.

---

## Verification Results

| Check | Result |
|-------|--------|
| Syntax validation | ✅ Pass |
| Helper functions work | ✅ Pass |
| `split_full_name()` decomposes correctly | ✅ Pass (Alice Tan → Alice, Tan) |
| `argon2id` hash format correct | ✅ Pass ($argon2id$...) |
| Email normalization | ✅ Pass (alice.tan@email.com) |
| Phase 1 seeding still works | ✅ Pass (20 users, 20 credentials) |
| ON CONFLICT DO NOTHING idempotent | ✅ Pass (0 rows on re-run = expected) |

---

## Key Information for KC's Phase 1 Queries

### User Credentials Table Schema
```sql
user_credentials
├── c_id (SERIAL PRIMARY KEY)
├── user_id (VARCHAR(20), UNIQUE FK→users)
├── password_hash (VARCHAR(255))  ← Argon2id MCF format with embedded salt
├── secret_question (VARCHAR(255))
├── secret_answer_hash (VARCHAR(255))  ← Also argon2id (NOT plaintext!)
└── deleted_at (TIMESTAMP, nullable)
```

### Password Verification Pattern (for KC)
```python
from argon2 import PasswordHasher

ph = PasswordHasher()

# When user logs in with password:
try:
    ph.verify(db_password_hash, user_input_password)
    # Login successful!
except:
    # Invalid password
```

### Secret Answer Verification Pattern (for KC)
```python
# Same as password verification
try:
    ph.verify(db_secret_answer_hash, user_input_answer)
    # Answer correct!
except:
    # Invalid answer
```

---

## Changes Made

| File | Section | Change | Reason |
|------|---------|--------|--------|
| `skeleton/seed_postgres.py` | Top level | Added `split_full_name()` and `hash_secret()` helper functions | Reusability, clarity |
| `skeleton/seed_postgres.py` | `seed_users()` | Added comprehensive docstring with KC security notes | Team handoff |
| `skeleton/seed_postgres.py` | `seed_users()` | Email normalized to lowercase | Consistent queries |
| `skeleton/seed_postgres.py` | Code org | Added section divider comments | Better navigation |

---

## Next Steps for KC

1. **Phase 1 Queries** (`kc/queries-profile`)
   - Use `ph.verify(db_password_hash, input_password)` for login
   - Use `ph.verify(db_secret_answer_hash, input_answer)` for password reset
   - Query user profile from `users` table (user_id, first_name, last_name, email, phone, etc.)

2. **Notes**
   - Phase 1 schema matches exactly
   - All 20 test users + credentials seeded and ready
   - Table names: `users`, `user_credentials` (NOT `registered_users`)
   - No need for separate salt column — argon2id MCF format includes it

---

## Branches

- ✅ `main` — Final approved schema.sql
- ✅ `zhanghsun/seed-basic` — Phase 1 seeding (THIS BRANCH) — Ready for merge
- ⏳ `kc/queries-profile` — KC's Phase 1 queries (awaiting this handoff)
- ⏳ `zhanghsun/seed-complex` — Phase 2+ seeding (future work)

---

**Status:** Ready for team review and KC handoff ✅
