"""Test whether state-level late rates track distance from São Paulo.

State median geolocation is only a rough destination proxy, not route length.
This check is descriptive and cannot identify a logistics mechanism.
"""

import csv
from collections import defaultdict
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from statistics import median

from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data/raw/olist_geolocation_dataset.csv"
FACT = ROOT / "exports/fact_orders.csv"


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def main() -> None:
    if not GEO.exists() or not FACT.exists():
        raise SystemExit("Download Olist CSVs and run 'make export' first")
    coordinates = defaultdict(lambda: [[], []])
    with GEO.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            lat, lon = float(row["geolocation_lat"]), float(row["geolocation_lng"])
            if -35 <= lat <= 6 and -75 <= lon <= -32:
                point = coordinates[row["geolocation_state"]]
                point[0].append(lat)
                point[1].append(lon)
    centroids = {state: (median(lat), median(lon))
                 for state, (lat, lon) in coordinates.items() if lat}
    outcomes = defaultdict(lambda: [0, 0])
    with FACT.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            state = row["customer_state"]
            outcomes[state][0] += 1
            outcomes[state][1] += row["is_late"] == "true"
    points = [(state, distance_km(centroids["SP"], centroids[state]), late / orders)
              for state, (orders, late) in outcomes.items()
              if orders >= 100 and state in centroids]
    result = spearmanr([point[1] for point in points], [point[2] for point in points])
    print(f"States with >=100 orders: {len(points)}")
    print(f"Spearman rho (SP-centroid distance vs late rate): {result.statistic:.3f}; "
          f"two-sided p = {result.pvalue:.3f}")
    print("Distance from SP is a weak state-level proxy; seller origins, actual routes, "
          "carriers, and promise-setting are not controlled here.")


if __name__ == "__main__":
    main()
