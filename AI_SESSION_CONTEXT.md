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
    Neo4j Graph Schema (Agreed)
    This section documents node labels, relationship types, properties,
    and conventions used by `databases/graph/queries.py` and
    `skeleton/seed_neo4j.py`.
    ============================================================ -->

### Overview

The graph model represents physical stations (metro and national rail),
the links between them (service edges), and interchange connections
used for multimodal routing and disruption analysis. Nodes are
lightweight and focused on traversal attributes (ids, geo, type,
operational flags). Relationships are directional but modeled as
bidirectional logical links via twin edges (see seeding conventions).

---

### Node Labels

- `MetroStation`
    - Purpose: Represents a metro/underground stop used for short-haul,
        high-frequency routing inside the metro network.
    - Key properties:
        - `station_id` (STRING, unique natural key)
        - `name` (STRING)
        - `lat` / `lon` (FLOAT)
        - `lines` (LIST of STRING) — lines that serve the station
        - `is_interchange_metro` (BOOLEAN)
        - `is_interchange_national_rail` (BOOLEAN)
        - `operational` (BOOLEAN) — current service availability flag
    - Small Cypher example:
        ```cypher
        MERGE (s:MetroStation {station_id: $station_id})
            SET s.name = $name, s.lat = $lat, s.lon = $lon, s.lines = $lines
        RETURN s
        ```

- `NationalRailStation`
    - Purpose: Represents mainline or regional rail stations used for
        longer-distance services with fare-class complexity and seat
        allocation metadata.
    - Key properties:
        - `station_id` (STRING, unique natural key)
        - `name` (STRING)
        - `lat` / `lon` (FLOAT)
        - `lines` (LIST of STRING)
        - `is_interchange_national_rail` (BOOLEAN)
        - `is_interchange_metro` (BOOLEAN)
        - `operational` (BOOLEAN)
        - `fare_zone` (OPTIONAL STRING)
    - Small Cypher example:
        ```cypher
        MERGE (r:NationalRailStation {station_id: $station_id})
            SET r.name = $name, r.lat = $lat, r.lon = $lon, r.fare_zone = $zone
        RETURN r
        ```

---

### Relationship Types

- `METRO_LINK`
    - Purpose: Connects neighboring `MetroStation` nodes representing
        a scheduled service or physical track segment on a given line.
    - Key properties:
        - `line` (STRING)
        - `travel_time_min` (INTEGER) — nominal travel time in minutes
        - `distance_m` (INTEGER) — optional geographic distance in meters
        - `weight` (FLOAT) — precomputed routing weight (see seeding)
        - `operational` (BOOLEAN)
    - Traversal usage:
        - Used for shortest-paths, time-weighted Dijkstra, and APOC
            k-shortest-path traversals inside the metro subgraph.
        - `weight` is preferred by route-finding algorithms.
    - Cypher example:
        ```cypher
        MATCH (a:MetroStation {station_id:$from}), (b:MetroStation {station_id:$to})
        MERGE (a)-[r:METRO_LINK {line:$line}]->(b)
            SET r.travel_time_min = $t, r.distance_m = $d, r.weight = $w
        RETURN r
        ```

- `RAIL_LINK`
    - Purpose: Connects `NationalRailStation` nodes representing scheduled
        or express rail links, often with larger travel-times and fare
        attributes.
    - Key properties:
        - `service_id` (STRING) — optional schedule/svc id
        - `travel_time_min` (INTEGER)
        - `distance_m` (INTEGER)
        - `fare_base` (NUMERIC) — base fare used in simple fare heuristics
        - `weight` (FLOAT)
        - `operational` (BOOLEAN)
    - Traversal usage:
        - Used by longer-range routing algorithms and cheapest-route
            heuristics that combine fare and time into a composite weight.
    - Cypher example:
        ```cypher
        MATCH (x:NationalRailStation {station_id:$from}), (y:NationalRailStation {station_id:$to})
        MERGE (x)-[r:RAIL_LINK {service_id:$svc}]->(y)
            SET r.travel_time_min = $t, r.fare_base = $fare
        RETURN r
        ```

- `INTERCHANGE_TO`
    - Purpose: Represents pedestrian interchange connections between a
        `MetroStation` and a `NationalRailStation` (or vice-versa). These
        edges model transfer penalty/time/cost.
    - Key properties:
        - `walk_time_min` (INTEGER)
        - `transfer_penalty` (FLOAT) — additive penalty used in routing
        - `is_accessible` (BOOLEAN)
        - `operational` (BOOLEAN)
    - Traversal usage:
        - Used by multimodal routing to include transfer cost; considered
            during interchange path searches and alternative route
            generation.
    - Cypher example:
        ```cypher
        MATCH (m:MetroStation {station_id:$metro}), (r:NationalRailStation {station_id:$rail})
        MERGE (m)-[t:INTERCHANGE_TO]->(r)
            SET t.walk_time_min = $walk, t.transfer_penalty = $penalty
        RETURN t
        ```

---

### Graph Architecture Decisions

- Bidirectional edge design
    - Decision: Persist logical bidirectional connectivity via two
        directional relationships (A->B and B->A) rather than using
        undirected semantics.
    - Why: Neo4j indexes and traversal algorithms operate on directed
        relationships; explicit twin edges make traversal rules,
        permissions, and per-direction operational flags (e.g., one-way
        maintenance) deterministic.

- Weighted routing strategy
    - Decision: Precompute and store a `weight` on each relationship.
    - Why: Allows flexible composite weights (time, distance, fare,
        transfer_penalty) and avoids recomputing expensive functions at
        query-time. Enables fast Dijkstra/A* searches and k-shortest-paths
        with APOC/graph algorithms.

- Interchange routing design
    - Decision: Model interchanges as explicit `INTERCHANGE_TO` edges
        with transfer metadata instead of implicit node attributes.
    - Why: Transfer time, accessibility, and penalty vary by pair and
        influence route ranking; edges encode these transfer costs cleanly.

- Disruption-aware routing
    - Decision: Include `operational` flags and support runtime
        filtering of edges/nodes to simulate outages.
    - Why: Enables `WHERE r.operational = true` style constraints for
        live-routing and delay-ripple analyses without changing graph
        topology.

- APOC traversal usage
    - Decision: Prefer APOC procedures for complex traversals and
        k-shortest-paths (e.g., `apoc.algo.kShortestPaths`, `apoc.path.expandConfig`).
    - Why: APOC provides battle-tested traversal utilities, path
        weighting, and path filtering that are more expressive than pure
        Cypher for advanced routing needs.

---

### Graph Query Layer (`databases/graph/queries.py`)

This subsection documents the implemented query functions and the
expected traversal patterns. All functions must be read-only and return
JSON-serializable Python dictionaries/lists.

- `query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict`
    - Purpose: Return the fastest route between two stations (time
        optimized), optionally auto-selecting the network(s) (metro, rail,
        or multimodal).
    - Routing logic: Use Dijkstra/A* style shortest-path using the
        `weight` property set to travel time (plus transfer_penalty where
        applicable). If `network='auto'` the query searches across both
        `METRO_LINK` and `RAIL_LINK` edges plus `INTERCHANGE_TO`.
    - APOC usage: `apoc.algo.dijkstra` or `apoc.path.expandConfig` with
        `weightProperty:'weight'` for configurable pruning.
    - Traversal strategy: Restrict traversal to nodes/edges where
        `operational = true`; return structured path with segments,
        cumulative time, and per-segment metadata.

- `query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict`
    - Purpose: Find a route minimizing monetary cost for a given fare
        class (may trade time for lower fare).
    - Routing logic: Composite weight combining `fare_base` (for
        rail edges), per-stop fare heuristics, and `travel_time_min` where
        needed. Weights are normalized and combined into `weight` during
        seeding; queries pick the `fare_class`-adjusted weight where
        precomputed.
    - APOC usage: `apoc.algo.kShortestPaths` or `apoc.path.expandConfig`
        with custom `weightProperty` that reflects fare-aware weights.
    - Traversal strategy: Multimodal traversal that penalizes transfers
        more heavily when fare class has transfer penalties; returns fare
        breakdown and time tradeoffs.

- `query_alternative_routes(origin_id, destination_id, avoid_station_id, network="auto", max_routes=3) -> list[list[dict]]`
    - Purpose: Generate alternative viable routes avoiding a given
        station (e.g., due to disruption) or providing k diverse
        alternatives.
    - Routing logic: Use k-shortest-paths with exclusion rules
        (e.g., `WHERE NOT (n.station_id = $avoid_station_id)`) and
        diversity heuristics (node/edge overlap penalty).
    - APOC usage: `apoc.algo.kShortestPaths` + `apoc.path.subgraphNodes`
        for candidate filtering.
    - Traversal strategy: Ensure alternatives differ by at least one
        major interchange or line; return route metadata for UI ranking.

- `query_interchange_path(origin_id: str, destination_id: str) -> dict`
    - Purpose: Explicitly compute the interchange portion(s) of a
        multimodal journey (where transfers occur and transfer penalties).
    - Routing logic: Isolate paths that include `INTERCHANGE_TO` edges,
        compute per-transfer walk_time and accessibility flags.
    - APOC usage: `apoc.path.expandConfig` with relationshipFilter
        including `INTERCHANGE_TO` to enumerate transfer possibilities.
    - Traversal strategy: Return ordered transfer steps with station
        pairs, walk_time, and recommended routing (e.g., avoid inaccessible
        transfers when `needs_accessible=true`).

- `query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]`
    - Purpose: Find stations and services likely affected within N hops
        of a delayed station (for operational impact analysis).
    - Routing logic: Breadth-first traversal up to `hops` across
        `METRO_LINK` and `RAIL_LINK`, considering schedules and service
        frequencies in heuristics; weight by likely ripple severity.
    - APOC usage: `apoc.path.subgraphNodes` or `apoc.path.expand` with
        `minLevel`/`maxLevel` to bound hops and then aggregate.
    - Traversal strategy: Filter to `operational=true` edges but mark
        those that would be impacted because they share services with the
        delayed station; return severity score per node.

- `query_station_connections(station_id: str) -> list[dict]`
    - Purpose: Return immediate neighbors and interchange options for a
        station — used by UIs for station detail pages and predictive
        transfer suggestions.
    - Routing logic: One-hop traversal collecting outgoing and incoming
        edges grouped by relationship type; include `distance_m`,
        `travel_time_min`, and `operational` flags.
    - APOC usage: Minimal — pure Cypher `MATCH (s {station_id:$id})-[r]->(n)`
        is sufficient; APOC used for convenience helpers when expanding
        repeated properties.
    - Traversal strategy: Read-only, return list of connection dicts.

---

### Neo4j Query Conventions

- Use the `_driver()` helper in `databases/graph/__init__.py` for all
    driver/session management to centralize auth and connection configs.
- Return JSON-serializable outputs: `list[dict]` or `dict` composed of
    primitives (no raw Neo4j Record objects). Example return:
    ```py
    return {
            "path": [ {"station_id": "S1", "name": "..."}, ... ],
            "total_time_min": 12,
            "total_fare": 3.20
    }
    ```
- Read-only query philosophy: All `queries.py` functions must never
    mutate graph state; seeding and schema changes are managed by
    `skeleton/seed_neo4j.py`.
- Disruption-aware traversal: Always include optional `operational`
    filters in traversal patterns; expose boolean flags to the caller to
    include/exclude non-operational elements.
- Structured return dictionaries: Provide `meta` and `segments`
    sections to make responses predictable for UIs and downstream AI
    processors (e.g., `{"meta": {...}, "segments": [...]}`).
- APOC traversal preference: For k-shortest or complex path
    constraints prefer APOC procedures for performance and clarity.

---

### Seeding Conventions (`skeleton/seed_neo4j.py`)

- Use `MERGE` instead of `CREATE` to allow idempotent runs of the seed
    script and safe re-seeding during development.
- Ensure uniqueness constraints exist (created once):
    ```cypher
    CREATE CONSTRAINT IF NOT EXISTS ON (m:MetroStation) ASSERT m.station_id IS UNIQUE;
    CREATE CONSTRAINT IF NOT EXISTS ON (r:NationalRailStation) ASSERT r.station_id IS UNIQUE;
    ```
- Bidirectional relationships: When modeling bidirectional
    connectivity, create twin edges `()-[:METRO_LINK]->()` and
    `()-[:METRO_LINK]->()` in the opposite direction so per-direction
    metadata (e.g., `operational`) can diverge if needed.
- Precomputed routing weights: Compute `weight` at seed time using a
    deterministic formula (e.g., `weight = travel_time_min + transfer_penalty * 60 * penalty_factor + fare_component`) and store it
    on the relationship to accelerate queries.
- Schema alignment: Keep property names and semantics aligned between
    `seed_neo4j.py` and `databases/graph/queries.py` (e.g., `travel_time_min`,
    `weight`, `operational`, `walk_time_min`) to avoid runtime mapping
    errors.

---

### Neo4j Design Philosophy

- The graph database is primarily optimized for traversal and
    operations that benefit from graph topology and path-centric
    reasoning. Core use cases include:
    - Shortest-path traversal (time-optimized routing)
    - Cheapest-route analysis (fare-aware routing)
    - Multimodal routing (metro + national rail + interchanges)
    - Interchange traversal with transfer penalties and accessibility
        metadata
    - Disruption simulation and delay ripple analysis
    - AI-assisted route planning where path metadata is fed to models

- Practical constraints:
    - Keep node schemas small and push expensive attributes (e.g.,
        full schedules) to relational tables. Use the graph for topology
        and precomputed routing weights only.
    - Favor read-only query functions in `databases/graph/queries.py` and
        perform writes only through dedicated seed/migration scripts.

---

Please extend this section only with additional agreed-on labels or
relationship types. Do not modify relational schema sections above or
existing team decisions recorded in the file.

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
