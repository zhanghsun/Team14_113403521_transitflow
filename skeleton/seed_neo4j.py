import json
import os
import sys

sys.path.insert(0, ".")

from neo4j import GraphDatabase
from skeleton.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
)

DATA_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "train-mock-data",
    )
)


def load_json(filename):
    with open(
        os.path.join(DATA_DIR, filename),
        encoding="utf-8",
    ) as f:
        return json.load(f)


def seed():

    metro_stations = load_json("metro_stations.json")
    rail_stations = load_json("national_rail_stations.json")

    metro_schedules = load_json("metro_schedules.json")
    rail_schedules = load_json("national_rail_schedules.json")

    # -------------------------
    # Build fare mappings
    # -------------------------

    metro_costs = {}

    for schedule in metro_schedules:

        stops = schedule["stops_in_order"]

        base = schedule["base_fare_usd"]
        rate = schedule["per_stop_rate_usd"]

        for i in range(len(stops)):

            for j in range(i + 1, len(stops)):

                cost = base + (j - i - 1) * rate

                metro_costs[(stops[i], stops[j])] = cost

    rail_costs = {}

    for schedule in rail_schedules:

        stops = schedule["stops_in_order"]

        fares = schedule["fare_classes"]

        for i in range(len(stops)):

            for j in range(i + 1, len(stops)):

                standard = (
                    fares["standard"]["base_fare_usd"]
                    + (j - i - 1)
                    * fares["standard"]["per_stop_rate_usd"]
                )

                first = (
                    fares["first"]["base_fare_usd"]
                    + (j - i - 1)
                    * fares["first"]["per_stop_rate_usd"]
                )

                rail_costs[(stops[i], stops[j])] = {
                    "standard": standard,
                    "first": first,
                }

    # -------------------------
    # Neo4j
    # -------------------------

    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD),
    )

    with driver.session() as session:

        print("Clearing graph...")

        session.run("MATCH (n) DETACH DELETE n")

        # -------------------------
        # Constraints
        # -------------------------

        session.run("""
        CREATE CONSTRAINT IF NOT EXISTS
        FOR (m:MetroStation)
        REQUIRE m.station_id IS UNIQUE
        """)

        session.run("""
        CREATE CONSTRAINT IF NOT EXISTS
        FOR (r:NationalRailStation)
        REQUIRE r.station_id IS UNIQUE
        """)

        # -------------------------
        # MetroStation nodes
        # -------------------------

        for s in metro_stations:

            session.run(
                """
                MERGE (m:MetroStation {
                    station_id:$id
                })

                SET
                    m.name = $name,
                    m.lines = $lines
                """,
                id=s["station_id"],
                name=s["name"],
                lines=s["lines"],
            )

        print(f"Created {len(metro_stations)} MetroStation nodes")

        # -------------------------
        # NationalRailStation nodes
        # -------------------------

        for s in rail_stations:

            session.run(
                """
                MERGE (r:NationalRailStation {
                    station_id:$id
                })

                SET
                    r.name = $name,
                    r.lines = $lines
                """,
                id=s["station_id"],
                name=s["name"],
                lines=s["lines"],
            )

        print(f"Created {len(rail_stations)} NationalRailStation nodes")

        # -------------------------
        # METRO_LINK
        # -------------------------

        metro_links = 0

        for s in metro_stations:

            for adj in s["adjacent_stations"]:

                from_id = s["station_id"]
                to_id = adj["station_id"]

                travel_time = adj["travel_time_min"]

                cost = metro_costs.get(
                    (from_id, to_id),
                    1.1,
                )

                for a, b in [
                    (from_id, to_id),
                    (to_id, from_id),
                ]:

                    session.run(
                        """
                        MATCH (x:MetroStation {
                            station_id:$a
                        })

                        MATCH (y:MetroStation {
                            station_id:$b
                        })

                        MERGE (x)-[r:METRO_LINK]->(y)

                        SET
                            r.line = $line,
                            r.travel_time_min = $tt,
                            r.cost_usd = $cost,
                            r.route_time_weight = $tt,
                            r.route_fare_weight = $cost
                        """,
                        a=a,
                        b=b,
                        line=adj["line"],
                        tt=travel_time,
                        cost=cost,
                    )

                metro_links += 1

        print(f"Created {metro_links} METRO_LINK")

        # -------------------------
        # RAIL_LINK
        # -------------------------

        rail_links = 0

        for s in rail_stations:

            for adj in s["adjacent_stations"]:

                from_id = s["station_id"]
                to_id = adj["station_id"]

                travel_time = adj["travel_time_min"]

                fares = rail_costs.get(
                    (from_id, to_id),
                    {
                        "standard": 4.0,
                        "first": 6.5,
                    },
                )

                for a, b in [
                    (from_id, to_id),
                    (to_id, from_id),
                ]:

                    session.run(
                        """
                        MATCH (x:NationalRailStation {
                            station_id:$a
                        })

                        MATCH (y:NationalRailStation {
                            station_id:$b
                        })

                        MERGE (x)-[r:RAIL_LINK]->(y)

                        SET
                            r.line = $line,
                            r.travel_time_min = $tt,
                            r.cost_standard_usd = $standard,
                            r.cost_first_usd = $first,
                            r.route_time_weight = $tt,
                            r.route_fare_weight = $standard
                        """,
                        a=a,
                        b=b,
                        line=adj["line"],
                        tt=travel_time,
                        standard=fares["standard"],
                        first=fares["first"],
                    )

                rail_links += 1

        print(f"Created {rail_links} RAIL_LINK")

        # -------------------------
        # INTERCHANGE_TO
        # -------------------------

        interchanges = 0

        for s in metro_stations:

            if s.get("is_interchange_national_rail"):

                metro_id = s["station_id"]

                rail_id = s.get(
                    "interchange_national_rail_station_id"
                )

                if rail_id:

                    for a, b in [
                        (metro_id, rail_id),
                        (rail_id, metro_id),
                    ]:

                        session.run(
                            """
                            MATCH (m {
                                station_id:$a
                            })

                            MATCH (r {
                                station_id:$b
                            })

                            MERGE (m)-[x:INTERCHANGE_TO]->(r)

                            SET
                                x.transfer_time_min = 5,
                                x.route_time_weight = 5,
                                x.route_fare_weight = 0
                            """,
                            a=a,
                            b=b,
                        )

                    interchanges += 1

        print(f"Created {interchanges} INTERCHANGE_TO")

    driver.close()

    print("\nNeo4j graph seeded successfully")


if __name__ == "__main__":
    seed()