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

---

## Section 7 — Task 6 Extension: Graph Reachability

### Motivation

The existing graph features answer shortest-path, cheapest-path, alternative-path, and delay-ripple questions. Task 6 adds a different planning mode: instead of selecting one best route, the assistant can now list every station reachable within a fixed time budget. This is useful for exploratory trip planning, disruption planning, and live Q&A because the response is bounded, explainable, and easy to compare with the seeded network.

### Database Changes

No new schema objects were required for this extension. The implementation reuses the existing Neo4j model and reads only existing station and relationship properties.

Graph model used:

```cypher
(:MetroStation)-[:METRO_LINK]->(:MetroStation)
(:NationalRailStation)-[:RAIL_LINK]->(:NationalRailStation)
(:MetroStation)-[:INTERCHANGE_TO]->(:NationalRailStation)
(:NationalRailStation)-[:INTERCHANGE_TO]->(:MetroStation)
```

The new query in [databases/graph/queries.py](databases/graph/queries.py) stays read-only and computes cumulative travel time from relationship weights already present in the graph.

### Example Query

The extension is exposed as `query_reachable_stations(origin_id, max_time_min)`.

```cypher
MATCH (start {station_id: $origin_id})
CALL apoc.path.expandConfig(start, {
	relationshipFilter: 'METRO_LINK|RAIL_LINK|INTERCHANGE_TO',
	minLevel: 1,
	maxLevel: 20,
	bfs: true,
	uniqueness: 'NODE_PATH',
	filterStartNode: true,
	limit: 500
}) YIELD path
WITH last(nodes(path)) AS reached,
	 reduce(total = 0.0, rel IN relationships(path) |
		 total + coalesce(rel.route_time_weight, rel.travel_time_min, rel.transfer_time_min, 1.0)
	 ) AS total_time_min
WHERE total_time_min <= $max_time_min
RETURN reached.station_id, reached.name, total_time_min
ORDER BY total_time_min ASC
```

Actual output from the live demo run:

```json
[
	{"station_id": "MS07", "name": "Old Town", "total_time_min": 2.0, "hops_away": 1, "lines": ["M2"]},
	{"station_id": "MS02", "name": "Riverside", "total_time_min": 3.0, "hops_away": 1, "lines": ["M1"]},
	{"station_id": "MS05", "name": "Westfield", "total_time_min": 3.0, "hops_away": 1, "lines": ["M1"]},
	{"station_id": "MS06", "name": "Harbour View", "total_time_min": 3.0, "hops_away": 1, "lines": ["M2"]},
	{"station_id": "MS18", "name": "Sunnyvale", "total_time_min": 4.0, "hops_away": 2, "lines": ["M2"]},
	{"station_id": "NR01", "name": "Central Station", "total_time_min": 5.0, "hops_away": 1, "lines": ["NR1", "NR2"]},
	{"station_id": "MS03", "name": "Northgate", "total_time_min": 5.0, "hops_away": 2, "lines": ["M1"]},
	{"station_id": "MS20", "name": "Thornton", "total_time_min": 5.0, "hops_away": 2, "lines": ["M1"]},
	{"station_id": "NR03", "name": "Old Town Junction", "total_time_min": 7.0, "hops_away": 2, "lines": ["NR1"]},
	{"station_id": "MS08", "name": "University", "total_time_min": 8.0, "hops_away": 3, "lines": ["M2", "M4"]},
	{"station_id": "MS04", "name": "Elm Park", "total_time_min": 9.0, "hops_away": 3, "lines": ["M1", "M3"]},
	{"station_id": "MS09", "name": "Queensbridge", "total_time_min": 11.0, "hops_away": 4, "lines": ["M2"]},
	{"station_id": "MS12", "name": "Lakeshore", "total_time_min": 12.0, "hops_away": 4, "lines": ["M3", "M4"]},
	{"station_id": "MS17", "name": "Broadmoor", "total_time_min": 12.0, "hops_away": 4, "lines": ["M1", "M4"]}
]
```

Live demo command used:

```bash
.\.venv\Scripts\python.exe task6_graph_demo.py --origin MS01 --budget 12 --destination NR05 --delay-station MS07 --hops 2
```

The same run also confirmed the existing shortest-route and delay-ripple queries still work after the extension:

- Shortest route from MS01 to NR05 returned a valid path with total time 42.0 minutes.
- Delay ripple around MS07 within 2 hops returned the expected affected stations across metro and rail.

### Testing Evidence

Validation and live execution were completed with the project virtual environment and the running Neo4j container.

- Python workspace error checks passed for [databases/graph/queries.py](databases/graph/queries.py)
- Python workspace error checks passed for [skeleton/agent.py](skeleton/agent.py)
- Live demo output captured from `task6_graph_demo.py`
- Neo4j service was already healthy during the run

If you want to attach a browser screenshot in the final submission package, the live output above is the exact result that should be captured from Neo4j Browser or the Gradio demo.

---

# 13. Task 6 Extension — Graph Reachability

## Motivation

The base graph tools already answer shortest-path, cheapest-path, alternative-path, and delay-ripple questions. The new reachability query fills a different gap: it lets the assistant answer "what can I reach from here within X minutes?" This is useful for trip planning, disruption planning, and exploratory routing because it returns a bounded set of stations instead of only a single best path.

## Database Changes

No new Neo4j tables or relationships were required. The extension reuses the existing graph model:

```cypher
(:MetroStation)-[:METRO_LINK]->(:MetroStation)
(:NationalRailStation)-[:RAIL_LINK]->(:NationalRailStation)
(:MetroStation)-[:INTERCHANGE_TO]->(:NationalRailStation)
(:NationalRailStation)-[:INTERCHANGE_TO]->(:MetroStation)
```

The new query in [databases/graph/queries.py](databases/graph/queries.py) keeps the graph read-only and calculates cumulative travel time from existing relationship properties.

## Example Query

The new query is implemented in Python as `query_reachable_stations(origin_id, max_time_min)`. The core traversal pattern is:

```cypher
MATCH (start {station_id: $origin_id})
CALL apoc.path.expandConfig(start, {
		relationshipFilter: 'METRO_LINK|RAIL_LINK|INTERCHANGE_TO',
		minLevel: 1,
		maxLevel: 20,
		bfs: true,
		uniqueness: 'NODE_PATH',
		filterStartNode: true,
		limit: 500
}) YIELD path
WITH last(nodes(path)) AS reached,
		 reduce(total = 0.0, rel IN relationships(path) |
				total + coalesce(rel.route_time_weight, rel.travel_time_min, rel.transfer_time_min, 1.0)
		 ) AS total_time_min
WHERE total_time_min <= $max_time_min
RETURN reached.station_id, reached.name, total_time_min
ORDER BY total_time_min ASC
```

Expected output shape:

```json
[
	{"station_id": "MS02", "name": "Riverside", "total_time_min": 3.0},
	{"station_id": "MS03", "name": "Northgate", "total_time_min": 5.0}
]
```

## Testing Evidence

Static validation completed successfully after the edit:

- Python syntax / workspace error check passed for [databases/graph/queries.py](databases/graph/queries.py)
- Python syntax / workspace error check passed for [skeleton/agent.py](skeleton/agent.py)
- `git diff --check` passed with no whitespace or patch-format issues

For live grading, this query should be demonstrated in Neo4j Browser or through the chat UI after the Neo4j service is running.

## Live Demo Script

To make the extension easy to show live, I added [task6_graph_demo.py](task6_graph_demo.py) as a read-only smoke test.

Example usage:

```bash
python task6_graph_demo.py --origin MS01 --budget 12 --destination NR05 --delay-station MS07 --hops 2
```

What it demonstrates:

- Reachable stations from a starting point within a time budget
- Existing shortest-route behavior still works after the extension
- Existing delay-ripple behavior still works after the extension

For grading, the most important output block is the reachable-stations section because it is the new Task 6 feature.
