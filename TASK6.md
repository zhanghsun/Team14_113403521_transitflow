# TASK 6 EXTENSION: INVENTORY

This file lists the Task 6 extension work in this branch so the bonus changes are easy to review.
It is also used as the post-merge source of truth for Section 7 write-up.

## Modified Files

### databases/graph/queries.py

Added function:

- `query_reachable_stations(origin_id, max_time_min=30)`

Also updated supporting behavior in existing query helpers to keep this extension read-only, bounded, and disruption-aware.

Purpose:

- Return every station reachable from a starting station within a travel-time budget.
- Traverse both metro and national rail edges, including `INTERCHANGE_TO` links.

Graph objects used:

- Node labels: `MetroStation`, `NationalRailStation`
- Relationship types: `METRO_LINK`, `RAIL_LINK`, `INTERCHANGE_TO`

### skeleton/agent.py

Added tool integration:

- Imported `query_reachable_stations`
- Added the `get_reachable_stations` tool definition
- Routed `get_reachable_stations` to `query_reachable_stations`

Updated related Task 6 logic:

- Reachability fallback rule in deterministic tool router
- Reachability result normalization before final answer generation

Purpose:

- Make the new graph query callable from the AI assistant UI and tool-calling pipeline.

### task6_graph_demo.py

Added runnable demo / smoke-test script:

- `main()`
- `build_parser()`
- `_print_section()`

Purpose:

- Demonstrate the new reachability query live during grading.
- Verify the graph layer still supports shortest-route and delay-ripple queries after the extension.
- Provide a repeatable smoke test after Neo4j seeding.

## Added Files

- None

## Function Inventory (Task 6)

- `databases/graph/queries.py`:
	- `query_reachable_stations(origin_id, max_time_min=30)`
- `skeleton/agent.py`:
	- tool name `get_reachable_stations` in `TOOLS`
	- branch handling for `get_reachable_stations` in `_execute_tool(...)`
	- deterministic fallback for reachability in `run_agent(...)`
	- normalization block for `get_reachable_stations` results in `run_agent(...)`
- `task6_graph_demo.py`:
	- `_print_section(title, payload)`
	- `build_parser()`
	- `main()`

## Data Object Inventory (Task 6)

- Relational tables added: none
- Vector tables/documents added: none
- Graph labels used:
	- `MetroStation`
	- `NationalRailStation`
- Graph relationship types used:
	- `METRO_LINK`
	- `RAIL_LINK`
	- `INTERCHANGE_TO`

## Post-Merge Checklist (Main Branch)

Complete these only after both Task 6 branches are merged to `main`:

1. Re-run this inventory against `main` and update any final file/function list changes.
2. Add Section 7 to your design document with:
	 - Motivation for the extension
	 - Schema/model changes (or explicit "no schema changes")
	 - Example query and explanation
	 - Testing evidence and screenshots
3. Paste one real reachable-stations output block from live run (chat UI or demo script).
4. Attach/insert screenshots of:
	 - Query invocation
	 - Returned result
	 - Any validation command/output used during testing

## Notes
- No new relational tables were added for this Task 6 graph extension.
- The extension is read-only and does not mutate Neo4j data.
- The demo script is intentionally read-only and prints JSON output so reviewers can inspect the exact returned shape.
## 
## Relational Database Extension

### Modified Files

#### databases/relational/queries.py

Added functions:

* `query_user_travel_history(user_email)`
* `query_route_statistics()`

### Purpose

#### query_user_travel_history(user_email)

Purpose:

* Provide a unified travel-history dashboard across both transport systems.
* Combine national rail bookings and metro trips into a single timeline.
* Convert station IDs into human-readable station names.
* Support future dashboard and reporting functionality.

Tables Used:

* `users`
* `national_rail_bookings`
* `metro_trips`
* `national_rail_stations`
* `metro_stations`

Returns:

* `trip_type`
* `record_id`
* `origin`
* `destination`
* `travel_date`
* `ticket_type`
* `amount_usd`
* `status`

Testing Evidence:

Function executed:

* `query_user_travel_history("alice.tan@email.com")`

Verified:

* Combined national rail and metro travel records.
* Correct station-name joins for origin and destination stations.
* Correct travel dates, fares, ticket types, and statuses.
* Travel history sorted correctly by travel date.

Example Output:

* `Central Station -> Stonehaven`
* `Bridgeport -> Central Station`
* `Central Square -> Elm Park`

---

#### query_route_statistics()

Purpose:

* Provide route-level analytics across the transport network.
* Identify the most frequently travelled national rail routes.
* Identify the most frequently travelled metro routes.
* Support analytics dashboards and operational reporting.

Tables Used:

* `national_rail_bookings`
* `metro_trips`
* `national_rail_stations`
* `metro_stations`

Returns:

* `top_national_rail_routes`
* `top_metro_routes`
* `total_national_rail_bookings`
* `total_metro_trips`

Testing Evidence:

Function executed:

* `query_route_statistics()`

Verified:

* Top national rail routes returned correctly.
* Top metro routes returned correctly.
* Route popularity counts validated in PostgreSQL.
* Total booking and trip counts matched database values.

Example Output:

* `Central Station -> Stonehaven (4 trips)`
* `total_national_rail_bookings = 23`
* `total_metro_trips = 24`

Validation Performed Using:

* Python function execution
* PostgreSQL (pgAdmin) verification queries

### Data Object Inventory (Task 6)

Relational tables added:

* none

Existing tables referenced:

* `users`
* `national_rail_bookings`
* `metro_trips`
* `national_rail_stations`
* `metro_stations`

### Notes

* No schema changes were required for this extension.
* No new relational tables were added.
* The extension is read-only and does not modify booking or trip data.
* The extension focuses on travel-history reporting and analytics functionality.
