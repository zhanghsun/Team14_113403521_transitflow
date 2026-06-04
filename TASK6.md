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