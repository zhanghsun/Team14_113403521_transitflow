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

        # Create uniqueness constraints for station ids
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:MetroStation) REQUIRE m.station_id IS UNIQUE"
        )
        session.run(
            "CREATE CONSTRAINT IF NOT EXISTS FOR (r:RailStation) REQUIRE r.station_id IS UNIQUE"
        )

        # Create MetroStation nodes
        for s in metro_stations:
            session.run(
                """
                MERGE (m:MetroStation {station_id: $station_id})
                SET m.name = $name,
                    m.lines = $lines,
                    m.is_interchange_national_rail = $is_interchange_national_rail,
                    m.interchange_national_rail_station_id = $interchange_national_rail_station_id
                """,
                {
                    "station_id": s["station_id"],
                    "name": s.get("name"),
                    "lines": s.get("lines", []),
                    "is_interchange_national_rail": s.get("is_interchange_national_rail", False),
                    "interchange_national_rail_station_id": s.get(
                        "interchange_national_rail_station_id"
                    ),
                },
            )

        print(f"  Created {len(metro_stations)} MetroStation nodes")

        # Create RailStation nodes
        for r in rail_stations:
            session.run(
                """
                MERGE (rs:RailStation {station_id: $station_id})
                SET rs.name = $name,
                    rs.lines = $lines,
                    rs.is_interchange_metro = $is_interchange_metro,
                    rs.interchange_metro_station_id = $interchange_metro_station_id
                """,
                {
                    "station_id": r["station_id"],
                    "name": r.get("name"),
                    "lines": r.get("lines", []),
                    "is_interchange_metro": r.get("is_interchange_metro", False),
                    "interchange_metro_station_id": r.get("interchange_metro_station_id"),
                },
            )

        print(f"  Created {len(rail_stations)} RailStation nodes")

        # Create LINKS_TO relationships for metro adjacencies
        links_created = 0
        for s in metro_stations:
            src = s["station_id"]
            for adj in s.get("adjacent_stations", []):
                dst = adj["station_id"]
                line = adj.get("line")
                tt = adj.get("travel_time_min")
                session.run(
                    """
                    MATCH (a:MetroStation {station_id: $src})
                    MATCH (b:MetroStation {station_id: $dst})
                    MERGE (a)-[r:LINKS_TO {line: $line, travel_time_min: $tt}]->(b)
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt},
                )
                links_created += 1

        print(f"  Created {links_created} metro LINKS_TO relationships")

        # Create LINKS_TO relationships for national rail adjacencies
        rail_links = 0
        for r in rail_stations:
            src = r["station_id"]
            for adj in r.get("adjacent_stations", []):
                dst = adj["station_id"]
                line = adj.get("line")
                tt = adj.get("travel_time_min")
                session.run(
                    """
                    MATCH (a:RailStation {station_id: $src})
                    MATCH (b:RailStation {station_id: $dst})
                    MERGE (a)-[r:LINKS_TO {line: $line, travel_time_min: $tt}]->(b)
                    """,
                    {"src": src, "dst": dst, "line": line, "tt": tt},
                )
                rail_links += 1

        print(f"  Created {rail_links} rail LINKS_TO relationships")

        # Create INTERCHANGE relationships between Metro and Rail stations
        interchanges = 0
        for s in metro_stations:
            if s.get("is_interchange_national_rail"):
                msid = s["station_id"]
                nrid = s.get("interchange_national_rail_station_id")
                if nrid:
                    session.run(
                        """
                        MATCH (m:MetroStation {station_id: $msid})
                        MATCH (r:RailStation {station_id: $nrid})
                        MERGE (m)-[x:INTERCHANGE]->(r)
                        SET x.type = 'metro-rail'
                        """,
                        {"msid": msid, "nrid": nrid},
                    )
                    interchanges += 1

        print(f"  Created {interchanges} INTERCHANGE relationships")

    driver.close()
    print("\nNeo4j graph seeded successfully.")
    print("   Open http://localhost:7475 to explore the graph.")


if __name__ == "__main__":
    print("Connecting to Neo4j...")
    seed()
