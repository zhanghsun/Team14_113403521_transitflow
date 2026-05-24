# AI Session Context — TransitFlow

**How to use this file:**
At the start of every AI coding session, paste the full contents of this file as your first message to your AI assistant. This gives the AI the context it needs to produce code that fits your codebase and is consistent with your teammates' work.

**Who maintains this file:**
Whoever makes a schema change or architectural decision updates this file in the same commit. Treat it like a team contract.

---

## Project Overview

TransitFlow is a Python-based AI chat assistant for a fictional transit operator. It queries three databases — PostgreSQL (relational + vector), Neo4j (graph) — and uses an LLM to answer user questions. Our task as students is to design the database schema and implement the query functions in `databases/relational/queries.py` and `databases/graph/queries.py`.

## Tech Stack

- Language: Python 3.11+
- Relational DB: PostgreSQL via `psycopg2` with `RealDictCursor`
- Graph DB: Neo4j via the `neo4j` Python driver
- Vector search: `pgvector` extension (already implemented — do not modify)
- Web UI: Gradio
- LLM: Google Gemini or local Ollama (configured via `.env`)

## Coding Conventions

- **Naming:** `snake_case` for all Python names and SQL identifiers
- **Docstrings:** All functions must have a docstring with `Args:` and `Returns:` sections
- **Return types:** Use type hints. Read-only functions return `list[dict]` or `Optional[dict]`
- **Empty results:** Return `[]` or `None` (as documented), never raise an exception for "not found"
- **SQL:** Use `%s` placeholders for all user inputs — never string-format into SQL
- **Relational pattern:** Use `_connect()` helper + `psycopg2.extras.RealDictCursor`:
  ```python
  with _connect() as conn:
      with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
          cur.execute("SELECT ...", (param,))
          return [dict(row) for row in cur.fetchall()]
  ```
- **Graph pattern:** Use `_driver()` helper + session:
  ```python
  with _driver() as driver:
      with driver.session() as session:
          result = session.run("MATCH ...", station_id=station_id)
          return [dict(record) for record in result]
  ```

## Agreed Relational Schema

13 tables with natural keys (VARCHAR(20) PK), JSONB for complex nested data, soft delete via `deleted_at`, and polymorphic FKs with CHECK constraints. All authentication data isolated in `user_credentials` table.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Users and Authentication
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

CREATE TABLE user_credentials (
    c_id             SERIAL PRIMARY KEY,
    user_id          VARCHAR(20) NOT NULL UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash    VARCHAR(255) NOT NULL,
    secret_question  VARCHAR(255) NOT NULL,
    secret_answer_hash VARCHAR(255) NOT NULL,
    deleted_at       TIMESTAMP
);

-- Metro Stations & Lines
CREATE TABLE metro_stations (
    station_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_metro BOOLEAN,
    is_interchange_national_rail BOOLEAN,
    interchange_national_rail_station_id VARCHAR(20),
    deleted_at TIMESTAMP
);

CREATE TABLE metro_station_lines (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(20) REFERENCES metro_stations(station_id),
    line VARCHAR(10),
    deleted_at TIMESTAMP
);

-- National Rail Stations & Lines
CREATE TABLE national_rail_stations (
    station_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_national_rail BOOLEAN,
    is_interchange_metro BOOLEAN,
    interchange_metro_station_id VARCHAR(20),
    deleted_at TIMESTAMP
);

CREATE TABLE national_rail_station_lines (
    id SERIAL PRIMARY KEY,
    station_id VARCHAR(20) REFERENCES national_rail_stations(station_id),
    line VARCHAR(10),
    deleted_at TIMESTAMP
);

-- Schedules (JSONB: stops_in_order, travel_time_from_origin_min, operates_on, fare_classes, passed_through_stations)
CREATE TABLE metro_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10),
    direction VARCHAR(20),
    origin_station_id VARCHAR(20) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES metro_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    base_fare_usd NUMERIC(10,2) CHECK (base_fare_usd >= 0),
    per_stop_rate_usd NUMERIC(10,2) CHECK (per_stop_rate_usd >= 0),
    frequency_min INTEGER CHECK (frequency_min > 0),
    stops_in_order JSONB,
    travel_time_from_origin_min JSONB,
    operates_on JSONB,
    deleted_at TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

CREATE TABLE national_rail_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10),
    service_type VARCHAR(20),
    direction VARCHAR(20),
    origin_station_id VARCHAR(20) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES national_rail_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    frequency_min INTEGER CHECK (frequency_min > 0),
    stops_in_order JSONB,
    passed_through_stations JSONB,
    travel_time_from_origin_min JSONB,
    fare_classes JSONB,
    operates_on JSONB,
    deleted_at TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

-- Seat Layouts (JSONB: coaches array with seat details)
CREATE TABLE national_rail_seat_layouts (
    layout_id VARCHAR(20) PRIMARY KEY,
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    coaches JSONB,
    deleted_at TIMESTAMP
);

-- Bookings & Trips
CREATE TABLE national_rail_bookings (
    booking_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) REFERENCES users(user_id),
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id VARCHAR(20) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES national_rail_stations(station_id),
    travel_date DATE,
    departure_time TIME,
    ticket_type VARCHAR(20),
    fare_class VARCHAR(20),
    coach VARCHAR(5),
    seat_id VARCHAR(10),
    stops_travelled INTEGER CHECK (stops_travelled >= 0),
    amount_usd NUMERIC(10,2) CHECK (amount_usd >= 0),
    status VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    booked_at TIMESTAMP,
    travelled_at TIMESTAMP,
    deleted_at TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

CREATE TABLE metro_trips (
    trip_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) REFERENCES users(user_id),
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id VARCHAR(20) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES metro_stations(station_id),
    travel_date DATE,
    ticket_type VARCHAR(20),
    day_pass_ref VARCHAR(20),
    stops_travelled INTEGER CHECK (stops_travelled >= 0),
    amount_usd NUMERIC(10,2) CHECK (amount_usd >= 0),
    status VARCHAR(20) CHECK (status IN ('confirmed', 'completed', 'cancelled')),
    purchased_at TIMESTAMP,
    travelled_at TIMESTAMP,
    deleted_at TIMESTAMP,
    CHECK (origin_station_id <> destination_station_id)
);

-- Polymorphic Relations: Payments & Feedback (reference either booking OR trip, not both)
CREATE TABLE payments (
    payment_id VARCHAR(20) PRIMARY KEY,
    national_rail_booking_id VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
    metro_trip_id VARCHAR(20) REFERENCES metro_trips(trip_id),
    amount_usd NUMERIC(10,2) CHECK (amount_usd >= 0),
    method VARCHAR(50),
    status VARCHAR(20) CHECK (status IN ('paid', 'refunded', 'failed')),
    paid_at TIMESTAMP,
    deleted_at TIMESTAMP,
    CHECK (national_rail_booking_id IS NOT NULL OR metro_trip_id IS NOT NULL)
);

CREATE TABLE feedback (
    feedback_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) REFERENCES users(user_id),
    national_rail_booking_id VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
    metro_trip_id VARCHAR(20) REFERENCES metro_trips(trip_id),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    submitted_at TIMESTAMP,
    deleted_at TIMESTAMP,
    CHECK (national_rail_booking_id IS NOT NULL OR metro_trip_id IS NOT NULL)
);

-- Vector DB for RAG (policy documents)
CREATE TABLE policy_documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200),
    category VARCHAR(50),
    content TEXT,
    embedding vector(768),
    source_file VARCHAR(200),
    created_at TIMESTAMP
);
```

## Agreed Graph Schema

<!-- ============================================================
  FILL THIS IN after your team agrees on Neo4j node labels and
  relationship types.
  ============================================================ -->

```
Node labels:
- TODO

Relationship types:
- TODO

Key properties:
- TODO
```

## Function Signatures We Are Implementing

These are fixed contracts. AI-generated code must match these signatures exactly.

### Relational (`databases/relational/queries.py`)

```python
# Read-only
def query_national_rail_availability(origin_id: str, destination_id: str, travel_date: Optional[str] = None) -> list[dict]: ...
def query_national_rail_fare(schedule_id: str, fare_class: str, stops_travelled: int) -> Optional[dict]: ...
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]: ...
def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]: ...
def query_available_seats(schedule_id: str, travel_date: str, fare_class: str) -> list[dict]: ...
def query_user_profile(user_email: str) -> Optional[dict]: ...
def query_user_bookings(user_email: str) -> dict: ...  # returns {"national_rail": [...], "metro": [...]}
def query_payment_info(booking_id: str) -> Optional[dict]: ...

# Write operations
def execute_booking(user_id, schedule_id, origin_station_id, destination_station_id, travel_date, fare_class, seat_id, ticket_type="single") -> tuple[bool, dict | str]: ...
def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]: ...

# Auth
def register_user(email, first_name, surname, year_of_birth, password, secret_question, secret_answer) -> tuple[bool, str]: ...
def login_user(email: str, password: str) -> Optional[dict]: ...
def get_user_secret_question(email: str) -> Optional[str]: ...
def verify_secret_answer(email: str, answer: str) -> bool: ...
def update_password(email: str, new_password: str) -> bool: ...
```

### Graph (`databases/graph/queries.py`)

```python
def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict: ...
def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict: ...
def query_alternative_routes(origin_id, destination_id, avoid_station_id, network="auto", max_routes=3) -> list[list[dict]]: ...
def query_interchange_path(origin_id: str, destination_id: str) -> dict: ...
def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]: ...
def query_station_connections(station_id: str) -> list[dict]: ...
```

## Team Decisions Log

**Schema Design:**

- [x] **Split `full_name` into `first_name` and `last_name`** in `users` table. Why: Matches `register_user()` API signature; improves search/sort by surname; enables personalized greetings.

- [x] **Natural Keys** (e.g., `station_id VARCHAR(20) PRIMARY KEY`) as PKs for all entities except `user_credentials` (`c_id SERIAL PRIMARY KEY`). Why: Simplifies FK relations; facilitates data seeding (mock data provides IDs); improves debuggability.

- [x] **Soft Delete via `deleted_at TIMESTAMP`** across all major tables. Why: Required by business rules; preserves historical audit trail; enables transaction/booking history recovery.

- [x] **`user_credentials` table fully decoupled from `users`**. Why: Security isolation of authentication data; stricter access control possible; complies with credential management requirements.

- [x] **Store `secret_question` and `secret_answer_hash` in `user_credentials`, not `users`**. Why: Account recovery is authentication-sensitive; grouping all credentials in one table improves security posture.

- [x] **No separate `salt` column** (use Argon2id instead). Why: Argon2id automatically generates CSPRNG salt and embeds it in MCF hash format (`$argon2id$v=19$m=...$salt$hash`); separate column is redundant.

- [x] **Use JSONB for semi-structured fields**: `stops_in_order`, `travel_time_from_origin_min`, `operates_on`, `coaches`, `fare_classes`. Why: Simplifies querying with `jsonb_array_elements[_text]`; reduces normalization table overhead; aligns with mock JSON data structure.

- [x] **Separate nullable FKs for polymorphic relationships** (`payments` and `feedback` reference either `national_rail_bookings` OR `metro_trips`). Why: Maintains referential integrity via CHECK constraints without requiring a parent table; supports dual-network booking model.

- [x] **Separate `metro_*` and `national_rail_*` table families**. Why: Different scheduling structures (single vs. multi-class), fare logic, seat handling, and booking flows justify separation; simplifies schema logic.

- [x] **Explicit interchange station references** (`interchange_national_rail_station_id`, `interchange_metro_station_id`). Why: Transfer hubs must be explicitly linkable; simplifies interchange path queries.

- [x] **Vector embedding support** in `policy_documents` table (PostgreSQL `pgvector` extension). Why: Enables future semantic search and AI-assisted policy retrieval for RAG pipeline.

**Graph Schema:**
- [ ] Graph schema: TODO — add your node label and relationship type decisions here

- [ ] (example) Metro schedule stop ordering: using `jsonb_array_elements` approach — easier to debug than containment operators



## Prompts That Worked

<!-- Share prompts that produced good output so teammates can reuse them. -->

### Schema design prompt that worked:
```
TODO — add a prompt here after your schema design workshop
```

### Query implementation prompt that worked:
```
TODO — add after implementing your first function
```

# TransitFlow 專案開發與資料庫設計規範

##  一、核心設計與商業邏輯 (Business Logic & Core Design)

* **商業邏輯規範**：開發前需完整理解並遵守專案中的 Business Rules。
* **資料刪除方式**：所有資料皆需採用軟刪除（Soft Delete）機制處理，不可直接將資料從資料庫永久移除。
* **存取權限管理**：使用者若尚未登入，不得查詢或取得任何訂票相關紀錄。
* **主鍵設計 (PK)**：可由團隊自行選擇使用 **UUID v7**（建議搭配 `binary(16)` 儲存以降低空間使用）或 **Auto Increment**（自動遞增）。
* **驗收重點**：主要檢查系統回傳結果是否正確；若問題來自 AI 助理本身能力限制，可不列入扣分考量。

##  二、資訊安全與帳密管理 (Security & Credential Management)

* **密碼保護規範**：禁止以明碼儲存密碼，且不得使用 MD5 或 SHA 系列作為 Hash 演算法，建議採用 **argon2id**。
* **帳密分離設計**：密碼資料不可直接存放於 `user` 資料表，應獨立建立如 `user_credentials` 的資料表。

  * **欄位需求**：需包含 `c_id`（代理鍵 / Surrogate Key）、`u_id`（外鍵 / Foreign Key）、hash、salt 等欄位。
  * **存取限制**：此資料表需設定更嚴格的權限控管，也可考慮拆分至不同 Schema 儲存。
* **Salt 產生方式**：建議使用 **CSPRNG** 產生安全隨機值，並妥善設定資料庫中的欄位長度。
* **驗證流程**：Hash 的驗證與比對可在 Web Server 或資料庫端執行。
* **帳號復原機制**：系統需提供秘密問題（Secret Question）與答案驗證功能，以利帳號救援。

##  三、專案檔案整合與實作細節 (Implementation & Configurations)

* **Schema First 原則**：需先完成資料表設計，並確保 `schema.sql`、`seed_postgres.py` 與 `registered_users.json` 三者之間的欄位與邏輯一致。
* **向量資料庫設定 (Vector DB)**：`seed_vectors.py` 已預先完成，目前採用「一份文件對應一個向量」的架構，開發時不需修改。
* **Timeout 設定**：系統預設逾時時間為 300 秒，如有需要可於 `skeleton/config.py` 中自行調整。
* **彈性擴充區域**：`feedback.json` 尚未定義固定用途，團隊可依需求自由規劃與應用。
