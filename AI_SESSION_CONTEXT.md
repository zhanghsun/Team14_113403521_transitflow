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

<!-- ============================================================
  FILL THIS IN after your team completes the schema design workshop.
  Paste your final CREATE TABLE statements here.
  ============================================================ -->

```sql
-- TODO: paste your final schema.sql contents here after team review
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

<!-- Add entries as you make decisions. Format: "Decision: X. Why: Y." -->

- [ ] Schema design: TODO — add your table/column decisions here
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

## 📌 一、核心設計與商業邏輯 (Business Logic & Core Design)

* **商業邏輯規範**：開發前需完整理解並遵守專案中的 Business Rules。
* **資料刪除方式**：所有資料皆需採用軟刪除（Soft Delete）機制處理，不可直接將資料從資料庫永久移除。
* **存取權限管理**：使用者若尚未登入，不得查詢或取得任何訂票相關紀錄。
* **主鍵設計 (PK)**：可由團隊自行選擇使用 **UUID v7**（建議搭配 `binary(16)` 儲存以降低空間使用）或 **Auto Increment**（自動遞增）。
* **驗收重點**：主要檢查系統回傳結果是否正確；若問題來自 AI 助理本身能力限制，可不列入扣分考量。

## 🔒 二、資訊安全與帳密管理 (Security & Credential Management)

* **密碼保護規範**：禁止以明碼儲存密碼，且不得使用 MD5 或 SHA 系列作為 Hash 演算法，建議採用 **argon2id**。
* **帳密分離設計**：密碼資料不可直接存放於 `user` 資料表，應獨立建立如 `user_credentials` 的資料表。

  * **欄位需求**：需包含 `c_id`（代理鍵 / Surrogate Key）、`u_id`（外鍵 / Foreign Key）、hash、salt 等欄位。
  * **存取限制**：此資料表需設定更嚴格的權限控管，也可考慮拆分至不同 Schema 儲存。
* **Salt 產生方式**：建議使用 **CSPRNG** 產生安全隨機值，並妥善設定資料庫中的欄位長度。
* **驗證流程**：Hash 的驗證與比對可在 Web Server 或資料庫端執行。
* **帳號復原機制**：系統需提供秘密問題（Secret Question）與答案驗證功能，以利帳號救援。

## 📁 三、專案檔案整合與實作細節 (Implementation & Configurations)

* **Schema First 原則**：需先完成資料表設計，並確保 `schema.sql`、`seed_postgres.py` 與 `registered_users.json` 三者之間的欄位與邏輯一致。
* **向量資料庫設定 (Vector DB)**：`seed_vectors.py` 已預先完成，目前採用「一份文件對應一個向量」的架構，開發時不需修改。
* **Timeout 設定**：系統預設逾時時間為 300 秒，如有需要可於 `skeleton/config.py` 中自行調整。
* **彈性擴充區域**：`feedback.json` 尚未定義固定用途，團隊可依需求自由規劃與應用。
