"""
TransitFlow — Neo4j Seeder
Run once after starting Docker:
    python skeleton/seed_neo4j.py

Loads station and network data from train-mock-data/:
  - metro_stations.json         — city metro stations and adjacencies
  - national_rail_stations.json — national rail stations and adjacencies

Design your graph schema (node labels, relationship types, properties)
based on the data in these files, then implement the seed() function below.
"""

import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "train-mock-data")
)


def _load(filename):
    with open(os.path.join(_DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def seed():
    metro_stations = _load("metro_stations.json")
    rail_stations  = _load("national_rail_stations.json")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:

        session.run("MATCH (n) DETACH DELETE n")
        print("  Cleared existing graph data")

        # -------------------------
        # Schema constraints
        # -------------------------
        # Use unique constraint for station ids to allow fast node lookup
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MetroStation) REQUIRE m.station_id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NationalRailStation) REQUIRE n.station_id IS UNIQUE"
        )

        # -------------------------
        # Node creation
        # -------------------------
        # We keep node properties compatible with the provided JSON but
        # also accept optional extras (zone/operator/status) to support
        # route planning, fare zoning and disruption status.
        for s in metro_stations:
            session.run(
                """
                MERGE (m:MetroStation {station_id: $station_id})
                SET m.name = $name,
                    m.lines = $lines,
                    m.is_interchange_national_rail = $is_interchange_national_rail,
                    m.interchange_national_rail_station_id = $interchange_national_rail_station_id,
                    m.zone = $zone,
                    m.operator = $operator,
                    m.status = $status
                """,
                {
                    "station_id": s["station_id"],
                    "name": s.get("name"),
                    "lines": s.get("lines", []),
                    "is_interchange_national_rail": s.get("is_interchange_national_rail", False),
                    "interchange_national_rail_station_id": s.get(
                        "interchange_national_rail_station_id"
                    ),
                    # optional fields: keep None if not provided
                    "zone": s.get("zone"),
                    "operator": s.get("operator"),
                    "status": s.get("status"),
                },
            )

        print(f"  Created {len(metro_stations)} MetroStation nodes")

        for r in rail_stations:
            session.run(
                """
                MERGE (rs:NationalRailStation {station_id: $station_id})
                SET rs.name = $name,
                    rs.lines = $lines,
                    rs.is_interchange_metro = $is_interchange_metro,
                    rs.interchange_metro_station_id = $interchange_metro_station_id,
                    rs.zone = $zone,
                    rs.operator = $operator,
                    rs.status = $status
                """,
                {
                    "station_id": r["station_id"],
                    "name": r.get("name"),
                    "lines": r.get("lines", []),
                    "is_interchange_metro": r.get("is_interchange_metro", False),
                    "interchange_metro_station_id": r.get("interchange_metro_station_id"),
                    "zone": r.get("zone"),
                    "operator": r.get("operator"),
                    "status": r.get("status"),
                },
            )

        print(f"  Created {len(rail_stations)} NationalRailStation nodes")

        # -------------------------
        # Relationship creation
        # -------------------------
        # Relationship modeling decisions:
        # - Use distinct relationship types to make queries clearer:
        #   METRO_LINK for metro-to-metro, RAIL_LINK for rail-to-rail,
        #   INTERCHANGE_TO for transfers between systems.
        # - MERGE only on connectivity (no properties) then SET properties
        #   to avoid duplicate relationships caused by property differences.
        # - Create explicit reverse relationships to make traversal
        #   symmetric and to support bidirectional shortest-path queries.

        metro_links = 0
        for s in metro_stations:
            src = s["station_id"]
            for adj in s.get("adjacent_stations", []):
                dst = adj["station_id"]
                line = adj.get("line")
                tt = adj.get("travel_time_min")
                # defaults for improved planning / simulation
                dist = adj.get("distance_km")
                service = adj.get("service_type", "metro")

                # MERGE on relationship connectivity only, then SET properties
                session.run(
                    """
                    MATCH (a:MetroStation {station_id: $src})
                    MATCH (b:MetroStation {station_id: $dst})
                    MERGE (a)-[r:METRO_LINK]->(b)
                    SET r.line = $line,
                        r.travel_time_min = $tt,
                        r.distance_km = $dist,
                        r.service_type = $service
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt, "dist": dist, "service": service},
                )
                # create reverse direction to ensure bidirectional traversal
                session.run(
                    """
                    MATCH (a:MetroStation {station_id: $src})
                    MATCH (b:MetroStation {station_id: $dst})
                    MERGE (b)-[r:METRO_LINK]->(a)
                    SET r.line = $line,
                        r.travel_time_min = $tt,
                        r.distance_km = $dist,
                        r.service_type = $service
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt, "dist": dist, "service": service},
                )
                metro_links += 1

        print(f"  Created {metro_links} METRO_LINK relationships (and reverses)")

        rail_links = 0
        for r in rail_stations:
            src = r["station_id"]
            for adj in r.get("adjacent_stations", []):
                dst = adj["station_id"]
                line = adj.get("line")
                tt = adj.get("travel_time_min")
                dist = adj.get("distance_km")
                service = adj.get("service_type", "rail")

                session.run(
                    """
                    MATCH (a:NationalRailStation {station_id: $src})
                    MATCH (b:NationalRailStation {station_id: $dst})
                    MERGE (a)-[r:RAIL_LINK]->(b)
                    SET r.line = $line,
                        r.travel_time_min = $tt,
                        r.distance_km = $dist,
                        r.service_type = $service
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt, "dist": dist, "service": service},
                )
                session.run(
                    """
                    MATCH (a:NationalRailStation {station_id: $src})
                    MATCH (b:NationalRailStation {station_id: $dst})
                    MERGE (b)-[r:RAIL_LINK]->(a)
                    SET r.line = $line,
                        r.travel_time_min = $tt,
                        r.distance_km = $dist,
                        r.service_type = $service
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt, "dist": dist, "service": service},
                )
                rail_links += 1

        print(f"  Created {rail_links} RAIL_LINK relationships (and reverses)")

        # -------------------------
        # Interchanges between Metro and National Rail
        # -------------------------
        # Use INTERCHANGE_TO relationship with a `transfer_time_min` property
        # to accurately model transfer cost in route planning. If JSON does not
        # provide a transfer time we default to 5 minutes (can be tuned later).
        interchanges = 0
        for s in metro_stations:
            if s.get("is_interchange_national_rail"):
                msid = s["station_id"]
                nrid = s.get("interchange_national_rail_station_id")
                if nrid:
                    transfer_time = s.get("transfer_time_min", 5)
                    session.run(
                        """
                        MATCH (m:MetroStation {station_id: $msid})
                        MATCH (n:NationalRailStation {station_id: $nrid})
                        MERGE (m)-[t:INTERCHANGE_TO]->(n)
                        SET t.transfer_time_min = $transfer_time,
                            t.type = 'metro->rail'
                        MERGE (n)-[t2:INTERCHANGE_TO]->(m)
                        SET t2.transfer_time_min = $transfer_time,
                            t2.type = 'rail->metro'
                        """,
                        {"msid": msid, "nrid": nrid, "transfer_time": transfer_time},
                    )
                    interchanges += 1

        print(f"  Created {interchanges} INTERCHANGE_TO relationships (bidirectional)")

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
