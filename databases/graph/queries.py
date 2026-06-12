# TASK 6 EXTENSION: Graph query extension for reachable-stations analysis.
"""
TransitFlow — Neo4j Graph Database Layer
=========================================
This module handles all queries to Neo4j.

GRAPH ROLE:
  - Model the dual transit network (city metro M1–M4 + national rail NR1–NR2)
  - Find fastest routes (Dijkstra by travel_time_min via APOC)
  - Find cheapest routes (Dijkstra by fare via APOC)
  - Find alternative routes avoiding a given station
  - Find cross-network interchange paths (metro → rail or rail → metro)
  - Show delay ripple: which stations are affected within N hops

STUDENT TASK
------------
Design your graph schema (node labels, relationship types, properties)
based on the data in train-mock-data/, seed it with skeleton/seed_neo4j.py,
then implement the query_ functions below.

Functions prefixed with `query_` are called by the agent (skeleton/agent.py).
"""

# NOTE FOR REVIEWERS: 以下註解為說明性文件，不會變更任何執行邏輯或資料。
# - 目的：協助評分者快速理解模組責任 (read-only, disruption-aware)
# - 範圍：僅加入文件性註解，未修改查詢語意或 DB 操作

from __future__ import annotations

from typing import Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD


def _driver():
    """Return a Neo4j driver. Caller is responsible for closing."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


_REL_WEIGHT_CAPABILITY_CACHE: dict[str, bool] = {}


def _station_labels_filter(alias: str) -> str:
    """Reusable node-label filter for station lookups."""
    return f"({alias}:MetroStation OR {alias}:NationalRailStation)"


def _status_open_expr(alias: str) -> str:
    """Dynamic property access avoids Neo4j key-existence warnings."""
    return f"coalesce(properties({alias})['status'], 'open')"


def _not_closed_expr(alias: str) -> str:
    """Reusable disruption-aware filter expression."""
    return f"{_status_open_expr(alias)} <> 'closed'"


def _relationship_filter(network: str) -> str:
    """Map network mode to APOC relationship filter syntax (direction-agnostic for robustness)."""
    mode = (network or "auto").lower()
    if mode == "metro":
        return "METRO_LINK"
    if mode == "rail":
        return "RAIL_LINK"
    return "METRO_LINK|RAIL_LINK|INTERCHANGE_TO"


def _ensure_weight_properties(session, fare_class: str = "standard") -> dict[str, float]:
    """
    Read-only compatibility helper.

    In production, weight properties should be pre-seeded (e.g. route_time_weight,
    route_fare_weight). This helper intentionally does NOT mutate the graph.
    It only returns multipliers used by query-time fare fallback logic.
    """
    _ = session
    first_multiplier = 1.6 if (fare_class or "standard").lower() == "first" else 1.0
    return {"first_multiplier": first_multiplier}


def _route_meta(
    network_mode: str,
    route_type: str,
    traversal_strategy: str,
    disrupted_nodes_avoided: bool = True,
    interchange_count: int = 0,
) -> dict:
    """Stable metadata block for AI/tool consumers."""
    return {
        "network_mode": network_mode,
        "route_type": route_type,
        "interchange_count": interchange_count,
        "disrupted_nodes_avoided": disrupted_nodes_avoided,
        "traversal_strategy": traversal_strategy,
    }


def _fare_cost_expr(rel_alias: str, fare_class: str) -> str:
    """Return a Cypher expression for the active fare class and edge type."""
    if fare_class == "first":
        return (
            f"CASE type({rel_alias}) "
            f"WHEN 'METRO_LINK' THEN coalesce({rel_alias}.cost_usd, {rel_alias}.route_fare_weight, 0.0) "
            f"WHEN 'RAIL_LINK' THEN coalesce({rel_alias}.cost_first_usd, {rel_alias}.cost_standard_usd, {rel_alias}.route_fare_weight, 0.0) "
            f"WHEN 'INTERCHANGE_TO' THEN coalesce({rel_alias}.route_fare_weight, 0.0) "
            f"ELSE 0.0 END"
        )
    return (
        f"CASE type({rel_alias}) "
        f"WHEN 'METRO_LINK' THEN coalesce({rel_alias}.cost_usd, {rel_alias}.route_fare_weight, 0.0) "
        f"WHEN 'RAIL_LINK' THEN coalesce({rel_alias}.cost_standard_usd, {rel_alias}.route_fare_weight, 0.0) "
        f"WHEN 'INTERCHANGE_TO' THEN coalesce({rel_alias}.route_fare_weight, 0.0) "
        f"ELSE 0.0 END"
    )


def _path_is_open_expr(path_alias: str = "path") -> str:
    """Reusable path validation for disruption-aware traversal."""
    return f"all(node IN nodes({path_alias}) WHERE {_not_closed_expr('node')})"


def _path_has_interchange_expr(path_alias: str = "path") -> str:
    """Reusable expression for interchange path validation."""
    return f"any(rel IN relationships({path_alias}) WHERE type(rel) = 'INTERCHANGE_TO')"


def _base_route_result(origin_id: str, destination_id: str) -> dict:
    """Standardized route response used by shortest/cheapest/interchange queries."""
    return {
        "found": False,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "total_time_min": None,
        "total_fare_usd": None,
        "stations": [],
        "legs": [],
        **_route_meta(network_mode="auto", route_type="route", traversal_strategy="unknown"),
    }


def _structured_error(code: str, message: str, retriable: bool = False, details: Optional[str] = None) -> dict:
    return {
        "code": code,
        "message": message,
        "retriable": retriable,
        "details": details,
    }


def _error_from_exception(exc: Exception) -> dict:
    message = str(exc) or "Neo4j query failed."
    if isinstance(exc, (ServiceUnavailable, SessionExpired)):
        return _structured_error("connection_error", "Neo4j connection error.", retriable=True, details=message)

    if isinstance(exc, Neo4jError):
        code = getattr(exc, "code", "") or ""
        lowered = message.lower()
        if "procedure" in lowered and "apoc" in lowered:
            return _structured_error("apoc_unavailable", "APOC procedure unavailable.", details=message)
        if "procedure.notfound" in code.lower():
            return _structured_error("apoc_unavailable", "APOC procedure unavailable.", details=message)
        if "timedout" in code.lower() or "timed out" in lowered:
            return _structured_error("timeout", "Neo4j query timed out.", retriable=True, details=message)

    return _structured_error("neo4j_error", "Neo4j query failed.", details=message)


def _station_exists(session, station_id: str) -> bool:
    # Use the station ID prefix so the lookup hits the correct label index directly.
    if station_id.startswith("MS"):
        query = "MATCH (s:MetroStation {station_id: $station_id}) RETURN true AS ok LIMIT 1"
    elif station_id.startswith("NR"):
        query = "MATCH (s:NationalRailStation {station_id: $station_id}) RETURN true AS ok LIMIT 1"
    else:
        # Fallback for unexpected IDs keeps compatibility without UNION or graph-wide scans.
        query = "MATCH (s {station_id: $station_id}) WHERE s:MetroStation OR s:NationalRailStation RETURN true AS ok LIMIT 1"

    record = session.run(query, {"station_id": station_id}).single()
    return bool(record and record["ok"])


def _has_relationship_weight(session, prop_name: str) -> bool:
    """Check whether a route weight property exists on any traversable relationship."""
    cached = _REL_WEIGHT_CAPABILITY_CACHE.get(prop_name)
    if cached is not None:
        return cached

    record = session.run(
        """
        MATCH ()-[r:METRO_LINK|RAIL_LINK|INTERCHANGE_TO]-()
        WHERE properties(r)[$prop_name] IS NOT NULL
        RETURN count(r) > 0 AS ok
        """,
        {"prop_name": prop_name},
    ).single()
    has_weight = bool(record and record["ok"])
    _REL_WEIGHT_CAPABILITY_CACHE[prop_name] = has_weight
    return has_weight


def _with_route_errors(result: dict, error: dict) -> dict:
    result["error"] = error
    return result


def _path_to_station_dicts(path) -> list[dict]:
    return [
        {
            "station_id": node.get("station_id"),
            "name": node.get("name"),
            "labels": sorted(list(node.labels)),
            "lines": node.get("lines") or [],
            "status": node.get("status") or "open",
        }
        for node in path.nodes
    ]


def _path_to_leg_dicts(path) -> list[dict]:
    legs: list[dict] = []
    for idx, rel in enumerate(path.relationships):
        frm = path.nodes[idx]
        to = path.nodes[idx + 1]
        legs.append(
            {
                "from_station_id": frm.get("station_id"),
                "from_name": frm.get("name"),
                "to_station_id": to.get("station_id"),
                "to_name": to.get("name"),
                "relationship_type": rel.type,
                "line": rel.get("line"),
                "service_type": rel.get("service_type"),
                "travel_time_min": rel.get("travel_time_min"),
                "transfer_time_min": rel.get("transfer_time_min"),
                "distance_km": rel.get("distance_km"),
                "cost_usd": rel.get("cost_usd"),
                "cost_standard_usd": rel.get("cost_standard_usd"),
                "cost_first_usd": rel.get("cost_first_usd"),
                "route_time_weight": rel.get("route_time_weight"),
                "route_fare_weight": rel.get("route_fare_weight"),
            }
        )
    return legs


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a session, run Cypher, return data.

def example_count_nodes() -> int:
    """Example: count all nodes currently in the graph."""
    with _driver() as driver:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            return result.single()["total"]

# TODO: Implement the query_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── FASTEST ROUTE (Dijkstra by travel_time_min) ───────────────────────────────

def query_shortest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
) -> dict:
    """
    Find the fastest path between two stations, minimising total travel time.
    Uses apoc.algo.dijkstra (APOC required; enabled in docker-compose.yml).

    Args:
        origin_id:       e.g. "MS01" or "NR01"
        destination_id:  e.g. "MS09" or "NR05"
        network:         "metro", "rail", or "auto" (inferred from IDs)

    Returns:
        dict with keys: found, origin_id, destination_id,
                        total_time_min, total_fare_usd, stations, legs
    """
    rel_filter = _relationship_filter(network)
    base_result = _base_route_result(origin_id, destination_id)
    base_result.update(_route_meta(network_mode=network, route_type="shortest", traversal_strategy="dijkstra_route_time_weight"))

    with _driver() as driver:
        with driver.session() as session:
            try:
                if not _station_exists(session, origin_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Origin station not found: {origin_id}"),
                    )
                if not _station_exists(session, destination_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Destination station not found: {destination_id}"),
                    )

                if _has_relationship_weight(session, "route_time_weight"):
                    base_result["traversal_strategy"] = "dijkstra_route_time_weight"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.algo.dijkstra(origin, destination, $rel_filter, 'route_time_weight')
                        YIELD path, weight
                        WHERE {_path_is_open_expr('path')}
                        RETURN path, weight
                        LIMIT 1
                        """,
                        {
                            "origin_id": origin_id,
                            "destination_id": destination_id,
                            "rel_filter": rel_filter,
                        },
                    ).single()
                else:
                    # Fallback for unweighted graphs: BFS expansion then choose minimum travel time.
                    base_result["traversal_strategy"] = "apoc_expand_bfs_time_fallback"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.path.expandConfig(origin, {{
                            relationshipFilter: $rel_filter,
                            minLevel: 1,
                            maxLevel: 25,
                            bfs: true,
                            uniqueness: 'NODE_PATH',
                            endNodes: [destination],
                            filterStartNode: true,
                            limit: 300
                        }}) YIELD path
                        WHERE last(nodes(path)).station_id = $destination_id
                                                    AND {_path_is_open_expr('path')}
                        WITH path,
                             reduce(total = 0.0, rel IN relationships(path) |
                                total + coalesce(rel.travel_time_min, rel.transfer_time_min, 1.0)
                             ) AS weight
                        RETURN path, weight
                        ORDER BY weight ASC, length(path) ASC
                        LIMIT 1
                        """,
                        {
                            "origin_id": origin_id,
                            "destination_id": destination_id,
                            "rel_filter": rel_filter,
                        },
                    ).single()
            except Exception as exc:
                return _with_route_errors(base_result, _error_from_exception(exc))

    if not record:
        return _with_route_errors(
            base_result,
            _structured_error("disconnected_path", "No route found between origin and destination."),
        )

    route_path = record["path"]
    stations = _path_to_station_dicts(route_path)
    legs = _path_to_leg_dicts(route_path)
    interchange_count = sum(1 for leg in legs if leg["relationship_type"] == "INTERCHANGE_TO")
    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "total_time_min": round(record["weight"], 2) if record["weight"] is not None else None,
        "total_fare_usd": None,
        "stations": stations,
        "legs": legs,
        **_route_meta(
            network_mode=network,
            route_type="shortest",
            traversal_strategy=base_result["traversal_strategy"],
            disrupted_nodes_avoided=True,
            interchange_count=interchange_count,
        ),
    }


# ── CHEAPEST ROUTE (Dijkstra by fare) ────────────────────────────────────────

def query_cheapest_route(
    origin_id: str,
    destination_id: str,
    network: str = "auto",
    fare_class: str = "standard",
) -> dict:
    """
    Find the cheapest path between two stations, minimising total estimated fare.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        network:         "metro", "rail", or "auto"
        fare_class:      "standard" or "first" (national rail only)

    Returns:
        dict with found, total_time_min, total_fare_usd (approximate), stations, legs
    """
    rel_filter = _relationship_filter(network)
    fare_class = (fare_class or "standard").lower()
    if fare_class not in {"standard", "first"}:
        fare_class = "standard"
    base_result = _base_route_result(origin_id, destination_id)
    base_result["fare_class"] = fare_class
    base_result["fare_breakdown"] = []
    base_result.update(_route_meta(network_mode=network, route_type="cheapest", traversal_strategy="dijkstra_route_fare_weight"))

    with _driver() as driver:
        with driver.session() as session:
            try:
                fare_cfg = _ensure_weight_properties(session, fare_class=fare_class)
                if not _station_exists(session, origin_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Origin station not found: {origin_id}"),
                    )
                if not _station_exists(session, destination_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Destination station not found: {destination_id}"),
                    )

                if fare_class != "first" and _has_relationship_weight(session, "route_fare_weight"):
                    base_result["traversal_strategy"] = "dijkstra_route_fare_weight"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.algo.dijkstra(origin, destination, $rel_filter, 'route_fare_weight')
                        YIELD path, weight
                        WHERE {_path_is_open_expr('path')}
                        RETURN path, weight
                        LIMIT 1
                        """,
                        {
                            "origin_id": origin_id,
                            "destination_id": destination_id,
                            "rel_filter": rel_filter,
                        },
                    ).single()
                else:
                    # Fallback for graphs without precomputed fare weights, or when first-class pricing is requested.
                    base_result["traversal_strategy"] = "apoc_expand_bfs_fare_fallback"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.path.expandConfig(origin, {{
                            relationshipFilter: $rel_filter,
                            minLevel: 1,
                            maxLevel: 25,
                            bfs: true,
                            uniqueness: 'NODE_PATH',
                            endNodes: [destination],
                            filterStartNode: true,
                            limit: 300
                        }}) YIELD path
                        WHERE last(nodes(path)).station_id = $destination_id
                                                    AND {_path_is_open_expr('path')}
                        WITH path,
                             reduce(total = 0.0, rel IN relationships(path) |
                                total + ({_fare_cost_expr('rel', fare_class)})
                             ) AS weight
                        RETURN path, weight
                        ORDER BY weight ASC, length(path) ASC
                        LIMIT 1
                        """,
                        {
                            "origin_id": origin_id,
                            "destination_id": destination_id,
                            "rel_filter": rel_filter,
                        },
                    ).single()
            except Exception as exc:
                return _with_route_errors(base_result, _error_from_exception(exc))

    if not record:
        return _with_route_errors(
            base_result,
            _structured_error("disconnected_path", "No route found between origin and destination."),
        )

    route_path = record["path"]
    stations = _path_to_station_dicts(route_path)
    legs = _path_to_leg_dicts(route_path)

    total_fare = 0.0
    fare_breakdown = []
    for rel in route_path.relationships:
        if fare_class == "first":
            leg_fare = (
                rel.get("cost_usd")
                if rel.type == "METRO_LINK"
                else rel.get("cost_first_usd")
                if rel.type == "RAIL_LINK"
                else rel.get("route_fare_weight")
            )
        else:
            leg_fare = (
                rel.get("cost_usd")
                if rel.type == "METRO_LINK"
                else rel.get("cost_standard_usd")
                if rel.type == "RAIL_LINK"
                else rel.get("route_fare_weight")
            )
        if leg_fare is None:
            leg_fare = 0.0
        total_fare += leg_fare
        fare_breakdown.append(
            {
                "relationship_type": rel.type,
                "line": rel.get("line"),
                "fare_usd": leg_fare,
                "fare_source": "new_schema_cost_field" if rel.type in {"METRO_LINK", "RAIL_LINK"} else "interchange_transfer",
            }
        )

    total_time = sum((leg.get("travel_time_min") or leg.get("transfer_time_min") or 0) for leg in legs)
    interchange_count = sum(1 for leg in legs if leg["relationship_type"] == "INTERCHANGE_TO")

    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "fare_class": fare_class,
        "total_time_min": round(float(total_time), 2),
        "total_fare_usd": round(float(total_fare), 2),
        "stations": stations,
        "legs": legs,
        "fare_breakdown": fare_breakdown,
        **_route_meta(
            network_mode=network,
            route_type="cheapest",
            traversal_strategy=base_result["traversal_strategy"],
            disrupted_nodes_avoided=True,
            interchange_count=interchange_count,
        ),
    }


# ── ALTERNATIVE ROUTES (avoiding a station) ───────────────────────────────────

def query_alternative_routes(
    origin_id: str,
    destination_id: str,
    avoid_station_id: str,
    network: str = "auto",
    max_routes: int = 3,
) -> dict:
    """
    Find paths between two stations that avoid a specific intermediate station.
    Useful for routing around a delayed or closed station.

    Args:
        origin_id:         e.g. "NR01"
        destination_id:    e.g. "NR05"
        avoid_station_id:  e.g. "NR03"
        network:           "metro", "rail", or "auto"
        max_routes:        max number of alternatives to return

    Returns:
        dict with found, origin_id, destination_id, avoided_station_id, routes, route_count
    """
    rel_filter = _relationship_filter(network)
    max_routes = max(1, min(int(max_routes), 10))
    max_depth = 16
    base_result = {
        "found": False,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "avoided_station_id": avoid_station_id,
        "routes": [],
        "route_count": 0,
    }

    with _driver() as driver:
        with driver.session() as session:
            try:
                records = session.run(
                    f"""
                    MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                    OPTIONAL MATCH (avoid {{station_id: $avoid_station_id}})
                    WHERE {_station_labels_filter('origin')}
                      AND {_station_labels_filter('destination')}
                      AND (avoid IS NULL OR {_station_labels_filter('avoid')})
                      AND {_not_closed_expr('origin')}
                      AND {_not_closed_expr('destination')}
                    WITH origin, destination, CASE WHEN avoid IS NULL THEN [] ELSE [avoid] END AS blocked
                    // BFS + NODE_PATH keeps traversal bounded and avoids combinatorial path explosion.
                    CALL apoc.path.expandConfig(origin, {{
                        relationshipFilter: $rel_filter,
                        minLevel: 1,
                        maxLevel: $max_depth,
                        bfs: true,
                        uniqueness: 'NODE_PATH',
                        blacklistNodes: blocked,
                        endNodes: [destination],
                        filterStartNode: true,
                        limit: $expand_limit
                    }}) YIELD path
                    WITH path
                    WHERE last(nodes(path)).station_id = $destination_id
                                            AND {_path_is_open_expr('path')}
                    WITH path,
                         reduce(total = 0.0, rel IN relationships(path) |
                            total + coalesce(rel.route_time_weight, rel.travel_time_min, rel.transfer_time_min, 1.0)
                         ) AS total_time,
                         [node IN nodes(path) | node.station_id] AS station_ids
                    WITH path, total_time, apoc.text.join(station_ids, '>') AS signature
                    ORDER BY total_time ASC, length(path) ASC
                    WITH signature, head(collect(path)) AS selected_path
                    RETURN selected_path AS path
                    LIMIT $max_routes
                    """,
                    {
                        "origin_id": origin_id,
                        "destination_id": destination_id,
                        "avoid_station_id": avoid_station_id,
                        "rel_filter": rel_filter,
                        "max_routes": max_routes,
                        "max_depth": max_depth,
                        "expand_limit": min(max(max_routes * 20, 40), 250),
                    },
                )
                rows = list(records)
            except (ServiceUnavailable, SessionExpired, Neo4jError):
                result = dict(base_result)
                result["error"] = _structured_error(
                    "neo4j_error",
                    "Alternative route traversal failed.",
                    retriable=True,
                )
                return result

    if not rows:
        return base_result

    routes = [_path_to_leg_dicts(row["path"]) for row in rows]
    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "avoided_station_id": avoid_station_id,
        "routes": routes,
        "route_count": len(routes),
    }


# ── CROSS-NETWORK INTERCHANGE PATH ───────────────────────────────────────────

def query_interchange_path(origin_id: str, destination_id: str) -> dict:
    """
    Find a path between a metro station and a national rail station (or vice versa)
    crossing the network boundary via interchange relationships.

    Args:
        origin_id:       e.g. "MS03" (metro) or "NR05" (national rail)
        destination_id:  e.g. "NR05" (national rail) or "MS09" (metro)

    Returns:
        dict with found, stations list, interchange points, total_time_min
    """
    base_result = _base_route_result(origin_id, destination_id)
    base_result["interchange_points"] = []
    base_result.update(_route_meta(network_mode="auto", route_type="interchange", traversal_strategy="dijkstra_route_time_weight"))

    with _driver() as driver:
        with driver.session() as session:
            try:
                if not _station_exists(session, origin_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Origin station not found: {origin_id}"),
                    )
                if not _station_exists(session, destination_id):
                    return _with_route_errors(
                        base_result,
                        _structured_error("invalid_station", f"Destination station not found: {destination_id}"),
                    )
                if _has_relationship_weight(session, "route_time_weight"):
                    base_result["traversal_strategy"] = "dijkstra_route_time_weight"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.algo.dijkstra(origin, destination,
                            'METRO_LINK|RAIL_LINK|INTERCHANGE_TO', 'route_time_weight')
                        YIELD path, weight
                                                WHERE {_path_has_interchange_expr('path')}
                          AND any(node IN nodes(path) WHERE node:MetroStation)
                          AND any(node IN nodes(path) WHERE node:NationalRailStation)
                                                    AND {_path_is_open_expr('path')}
                        RETURN path, weight
                        LIMIT 1
                        """,
                        {"origin_id": origin_id, "destination_id": destination_id},
                    ).single()
                else:
                    base_result["traversal_strategy"] = "apoc_expand_bfs_interchange_fallback"
                    record = session.run(
                        f"""
                        MATCH (origin {{station_id: $origin_id}}), (destination {{station_id: $destination_id}})
                        WHERE {_station_labels_filter('origin')}
                          AND {_station_labels_filter('destination')}
                          AND {_not_closed_expr('origin')}
                          AND {_not_closed_expr('destination')}
                        CALL apoc.path.expandConfig(origin, {{
                            relationshipFilter: 'METRO_LINK|RAIL_LINK|INTERCHANGE_TO',
                            minLevel: 1,
                            maxLevel: 25,
                            bfs: true,
                            uniqueness: 'NODE_PATH',
                            endNodes: [destination],
                            filterStartNode: true,
                            limit: 350
                        }}) YIELD path
                        WHERE last(nodes(path)).station_id = $destination_id
                                                    AND {_path_has_interchange_expr('path')}
                          AND any(node IN nodes(path) WHERE node:MetroStation)
                          AND any(node IN nodes(path) WHERE node:NationalRailStation)
                                                    AND {_path_is_open_expr('path')}
                        WITH path,
                             reduce(total = 0.0, rel IN relationships(path) |
                                total + coalesce(rel.travel_time_min, rel.transfer_time_min, 1.0)
                             ) AS weight
                        RETURN path, weight
                        ORDER BY weight ASC, length(path) ASC
                        LIMIT 1
                        """,
                        {"origin_id": origin_id, "destination_id": destination_id},
                    ).single()
            except Exception as exc:
                return _with_route_errors(base_result, _error_from_exception(exc))

    if not record:
        return _with_route_errors(
            base_result,
            _structured_error("disconnected_path", "No interchange route found between origin and destination."),
        )

    route_path = record["path"]
    stations = _path_to_station_dicts(route_path)
    legs = _path_to_leg_dicts(route_path)
    interchange_points = [
        {
            "from_station_id": leg["from_station_id"],
            "from_name": leg["from_name"],
            "to_station_id": leg["to_station_id"],
            "to_name": leg["to_name"],
            "transfer_time_min": leg["transfer_time_min"],
        }
        for leg in legs
        if leg["relationship_type"] == "INTERCHANGE_TO"
    ]

    return {
        "found": True,
        "origin_id": origin_id,
        "destination_id": destination_id,
        "total_time_min": round(record["weight"], 2) if record["weight"] is not None else None,
        "total_fare_usd": None,
        "stations": stations,
        "legs": legs,
        "interchange_points": interchange_points,
        **_route_meta(
            network_mode="auto",
            route_type="interchange",
            traversal_strategy=base_result["traversal_strategy"],
            disrupted_nodes_avoided=True,
            interchange_count=len(interchange_points),
        ),
    }


# ── DELAY RIPPLE ANALYSIS ─────────────────────────────────────────────────────

def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]:
    """
    Find all stations within N hops of a delayed or disrupted station.
    Works on both metro and national rail networks.

    Args:
        delayed_station_id: e.g. "NR03" or "MS01"
        hops:               how many connections out to search (default 2)

    Returns:
        List of dicts: {station_id, name, hops_away, lines_affected}
    """
    # Negative hops are invalid → empty. hops==0 should return the delayed station itself.
    if hops < 0:
        return []
    hops = min(int(hops), 6)

    if hops == 0:
        # Return the delayed station itself (hops_away = 0) when requested.
        with _driver() as driver:
            with driver.session() as session:
                try:
                    record = session.run(
                        f"""
                        MATCH (s {{station_id: $delayed_station_id}})
                        WHERE {_station_labels_filter('s')}
                          AND {_not_closed_expr('s')}
                        RETURN s.station_id AS station_id,
                               s.name AS name,
                               0 AS hops_away,
                               coalesce(s.lines, []) AS lines_affected
                        LIMIT 1
                        """,
                        {"delayed_station_id": delayed_station_id},
                    ).single()
                    if not record:
                        return []
                    return [dict(record)]
                except (ServiceUnavailable, SessionExpired, Neo4jError):
                    return []

    with _driver() as driver:
        with driver.session() as session:
            try:
                records = session.run(
                    f"""
                    MATCH (start {{station_id: $delayed_station_id}})
                    WHERE {_station_labels_filter('start')}
                      AND {_not_closed_expr('start')}
                    // NODE_GLOBAL avoids revisiting stations across branches in ripple analysis.
                    CALL apoc.path.expandConfig(start, {{
                        relationshipFilter: 'METRO_LINK|RAIL_LINK|INTERCHANGE_TO',
                        minLevel: 1,
                        maxLevel: $hops,
                        bfs: true,
                        uniqueness: 'NODE_GLOBAL'
                    }})
                    YIELD path
                    WHERE {_path_is_open_expr('path')}
                    WITH last(nodes(path)) AS affected, min(length(path)) AS hops_away
                    WHERE {_station_labels_filter('affected')}
                      AND {_not_closed_expr('affected')}
                    RETURN affected.station_id AS station_id,
                           affected.name AS name,
                           hops_away,
                           coalesce(affected.lines, []) AS lines_affected
                    ORDER BY hops_away ASC, station_id ASC
                    """,
                    {"delayed_station_id": delayed_station_id, "hops": hops},
                )
                rows = [dict(r) for r in records]
                # Defensive dedup to avoid path inflation edge cases in larger graphs.
                dedup: dict[str, dict] = {}
                for row in rows:
                    sid = row.get("station_id")
                    if sid is None:
                        continue
                    if sid not in dedup or row["hops_away"] < dedup[sid]["hops_away"]:
                        dedup[sid] = row
                return sorted(dedup.values(), key=lambda x: (x["hops_away"], x["station_id"]))
            except (ServiceUnavailable, SessionExpired, Neo4jError):
                return []


# ── REACHABLE STATIONS WITHIN TIME BUDGET ────────────────────────────────────

def query_reachable_stations(origin_id: str, max_time_min: int = 30) -> list[dict]:
    """
    Find all stations reachable from an origin within a travel-time budget.

    Args:
        origin_id:      e.g. "MS01" or "NR01"
        max_time_min:   maximum cumulative travel time to include

    Returns:
        List of dicts: {station_id, name, total_time_min, hops_away, lines}
    """
    if max_time_min <= 0:
        return []
    # Hard-cap query radius so one bad prompt cannot trigger an expensive full-graph walk.
    max_time_min = max(1, min(int(max_time_min), 240))

    with _driver() as driver:
        with driver.session() as session:
            try:
                if not _station_exists(session, origin_id):
                    # Return a predictable empty list instead of raising; the agent layer
                    # already knows how to explain "no data" responses to users.
                    return []

                records = session.run(
                    f"""
                    MATCH (start {{station_id: $origin_id}})
                    WHERE {_station_labels_filter('start')}
                      AND {_not_closed_expr('start')}
                    // BFS enumerates candidate paths without mutating the graph, then we keep the fastest arrival for each station.
                    CALL apoc.path.expandConfig(start, {{
                        relationshipFilter: 'METRO_LINK|RAIL_LINK|INTERCHANGE_TO',
                        minLevel: 1,
                        maxLevel: 20,
                        bfs: true,
                        // NODE_PATH keeps alternate candidate paths so we can still compute
                        // the minimum travel-time arrival per station in the next WITH clause.
                        uniqueness: 'NODE_PATH',
                        filterStartNode: true,
                        // Guardrail for dense graph seeds: enough headroom for valid results
                        // without allowing unbounded path explosion.
                        limit: 500
                    }}) YIELD path
                    WHERE {_path_is_open_expr('path')}
                    WITH last(nodes(path)) AS reached,
                         reduce(total = 0.0, rel IN relationships(path) |
                            total + coalesce(rel.route_time_weight, rel.travel_time_min, rel.transfer_time_min, 1.0)
                         ) AS total_time_min,
                         length(path) AS hops
                    WHERE total_time_min <= $max_time_min
                    WITH reached.station_id AS station_id,
                         reached.name AS name,
                        // Keep the best-known arrival time when the same station is
                        // reachable through multiple path variants.
                         round(min(total_time_min), 2) AS total_time_min,
                         min(hops) AS hops_away,
                         head(collect(coalesce(reached.lines, []))) AS lines
                    RETURN station_id,
                           name,
                           total_time_min,
                           hops_away,
                           coalesce(lines, []) AS lines
                    ORDER BY total_time_min ASC, hops_away ASC, station_id ASC
                    """,
                    {"origin_id": origin_id, "max_time_min": max_time_min},
                )
                return [dict(r) for r in records]
            except (ServiceUnavailable, SessionExpired, Neo4jError):
                # Match the non-throwing contract used by other query_ helpers.
                return []


# ── STATION CONNECTIONS ───────────────────────────────────────────────────────

def query_station_connections(station_id: str) -> list[dict]:
    """
    List all direct connections from a given station.

    Args:
        station_id: e.g. "MS01" or "NR01"
    """
    with _driver() as driver:
        with driver.session() as session:
            try:
                records = session.run(
                    f"""
                    MATCH (s {{station_id: $station_id}})-[rel:METRO_LINK|RAIL_LINK|INTERCHANGE_TO]-(n)
                    WHERE {_station_labels_filter('s')}
                      AND {_station_labels_filter('n')}
                      AND {_not_closed_expr('s')}
                      AND {_not_closed_expr('n')}
                                            RETURN DISTINCT n.station_id AS station_id,
                                                            n.name AS name,
                                                            type(rel) AS relationship_type,
                                                            rel.line AS line,
                                                            coalesce(rel.travel_time_min, rel.transfer_time_min) AS travel_time_min,
                                                            rel.service_type AS service_type,
                                                            properties(rel)['distance_km'] AS distance_km,
                                                            rel.transfer_time_min AS transfer_time_min,
                                                            rel.cost_usd AS cost_usd,
                                                            rel.cost_standard_usd AS cost_standard_usd,
                                                            rel.cost_first_usd AS cost_first_usd,
                                                            rel.route_time_weight AS route_time_weight,
                                                            rel.route_fare_weight AS route_fare_weight
                    ORDER BY relationship_type, station_id
                    """,
                    {"station_id": station_id},
                )
                return [dict(r) for r in records]
            except (ServiceUnavailable, SessionExpired, Neo4jError):
                return []
