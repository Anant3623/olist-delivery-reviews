"""Validate analysis control aggregates and their source exports.

The aggregates-only mode checks the portable control data without raw CSVs.
The default mode also checks exported orders, seller metrics and source items.
"""

import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis/control_aggregates.json"
FACT = ROOT / "exports/fact_orders.csv"
SELLERS = ROOT / "exports/seller_performance.csv"
ITEMS = ROOT / "data/raw/olist_order_items_dataset.csv"
BUCKETS = {"On-time", "1–3 days", "4–7 days", "8+ days"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_aggregates() -> dict:
    require(DATA.is_file(), "Analysis control aggregates are missing")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "Analysis control aggregates must be an object")
    return data


def fields(record: dict) -> tuple:
    return (record["orders"], record["late"], record["late_delay"],
            *record["reviews"], *record["scores"])


def combined(records) -> tuple:
    result = [0] * 7
    for record in records:
        for index, value in enumerate(fields(record)):
            result[index] += value
    return tuple(result)


def validate_record(record: dict, label: str) -> None:
    orders, late, late_delay, ontime_reviews, late_reviews, ontime_scores, late_scores = fields(record)
    require(all(isinstance(value, int) for value in fields(record)), f"Non-integer metric: {label}")
    require(0 <= late <= orders and late_delay >= late, f"Invalid delivery counts: {label}")
    require(0 <= ontime_reviews <= orders - late and 0 <= late_reviews <= late,
            f"Invalid review counts: {label}")
    require(ontime_reviews <= ontime_scores <= 5 * ontime_reviews and
            late_reviews <= late_scores <= 5 * late_reviews, f"Invalid review scores: {label}")


def validate_aggregates(data: dict) -> None:
    months = data["months"]
    require(months and list(months) == sorted(months), "Months must be sorted")
    require(set(months) == set(data["buckets"]) == set(data["states"]), "Missing month breakdown")
    all_states = set()
    for month, record in months.items():
        require(re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", month) is not None,
                f"Invalid month: {month}")
        validate_record(record, month)
        bucket_rows = data["buckets"][month]
        require(set(bucket_rows) <= BUCKETS, f"Unknown delay bucket: {month}")
        for label, row in bucket_rows.items():
            validate_record(row, f"{month}/{label}")
            require((row["late"] == 0) if label == "On-time" else
                    (row["late"] == row["orders"]), f"Bucket/late mismatch: {month}/{label}")
        require(combined(bucket_rows.values()) == fields(record), f"Bucket total mismatch: {month}")
        state_rows = data["states"][month]
        for state, row in state_rows.items():
            require(re.fullmatch(r"[A-Z]{2}", state) is not None, f"Invalid state: {state}")
            validate_record(row, f"{month}/{state}")
        require(combined(state_rows.values()) == fields(record), f"State total mismatch: {month}")
        all_states.update(state_rows)

    require(set(data["daily"]) <= set(months), "Daily curve has an unknown month")
    for month, day_rows in data["daily"].items():
        for day, row in day_rows.items():
            require(-20 <= int(day) <= 20 and row["reviews"] > 0,
                    f"Invalid day point: {month}/{day}")
            require(row["reviews"] <= row["scores"] <= 5 * row["reviews"],
                    f"Invalid day review scores: {month}/{day}")
        require(sum(row["reviews"] for row in day_rows.values()) <=
                sum(months[month]["reviews"]), f"Daily curve exceeds reviewed orders: {month}")

    sellers = data["sellers"]
    require(len({row["id"] for row in sellers}) == len(sellers), "Duplicate seller IDs")
    for row in sellers:
        require(row["orders"] >= 30 and 0 <= row["late"] <= row["orders"],
                f"Invalid seller denominator: {row['id']}")
        require(abs(row["rate"] - row["late"] / row["orders"]) <= 0.000051,
                f"Invalid seller rate: {row['id']}")
        require(row["review"] is None or 1 <= row["review"] <= 5,
                f"Invalid seller review: {row['id']}")
    require(all(sellers[index]["rate"] >= sellers[index+1]["rate"]
                for index in range(len(sellers)-1)), "Seller ranking out of order")

    overall = combined(months.values())
    require(overall[0] == 96_470 and overall[1] == 6_534 and
            overall[3] + overall[4] == 95_824 and
            overall[5] + overall[6] == 398_233 and overall[2] == 69_392 and
            len(all_states) == 27,
            "Control aggregates does not match the documented Olist baseline")
    expected_robustness = {
        "state": (21, 6333, 21, 2.005, 100, 30),
        "seller": (287, 4675, 286, 1.971, 20, 5),
    }
    for name, expected in expected_robustness.items():
        row = data["robustness"][name]
        actual = (row["groups"], row["late_reviews"], row["positive_groups"],
                  row["gap"], row["min_ontime"], row["min_late"])
        require(actual == expected, f"Robustness summary differs from verified baseline: {name}")
    print(f"Control aggregates OK: {overall[0]:,} orders, {overall[1]:,} late, "
          f"{len(all_states)} states, {len(sellers)} qualified sellers")


def validate_exports(data: dict) -> None:
    require(FACT.exists() and SELLERS.exists() and ITEMS.exists(),
            "Exports or raw order items missing; generate the exports and provide the raw Olist CSVs")
    seen = set()
    counts = defaultdict(lambda: [0] * 7)
    state_counts = defaultdict(lambda: [0] * 7)
    bucket_counts = defaultdict(lambda: [0] * 7)
    day_counts = defaultdict(lambda: [0, 0])
    state_reviews = defaultdict(lambda: [[0, 0], [0, 0]])
    reviewed_orders = {}
    valid_states = {state for month_rows in data["states"].values()
                    for state in month_rows}

    def record(metrics: list, late: bool, delay: int, review: int | None) -> None:
        metrics[0] += 1
        metrics[1] += int(late)
        metrics[2] += delay if late else 0
        if review is not None:
            group = 4 if late else 3
            metrics[group] += 1
            metrics[group + 2] += review

    with FACT.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        require(set(reader.fieldnames or []) >= {"order_id", "customer_state", "purchased_at",
                "delivered_at", "estimated_at", "delay_days", "is_late", "review_score"},
                "Fact export has missing columns")
        for row in reader:
            order_id = row["order_id"]
            require(order_id not in seen, f"Duplicate fact order: {order_id}")
            seen.add(order_id)
            purchased = datetime.fromisoformat(row["purchased_at"])
            delivered = datetime.fromisoformat(row["delivered_at"])
            estimated = datetime.fromisoformat(row["estimated_at"])
            delay = (delivered.date() - estimated.date()).days
            require(delivered >= purchased and int(row["delay_days"]) == delay,
                    f"Invalid order chronology/delay: {order_id}")
            require(row["is_late"] in {"true", "false"}, f"Invalid late flag: {order_id}")
            late = row["is_late"] == "true"
            require(late == (delay > 0), f"Late flag disagrees with dates: {order_id}")
            require(row["customer_state"] in valid_states,
                    f"Unknown customer state: {order_id}")
            review = None
            if row["review_score"]:
                review = int(row["review_score"])
                require(1 <= review <= 5, f"Review outside 1–5: {order_id}")
            month = row["purchased_at"][:7]
            bucket = ("On-time" if delay <= 0 else "1–3 days" if delay <= 3 else
                      "4–7 days" if delay <= 7 else "8+ days")
            record(counts[month], late, delay, review)
            record(state_counts[month, row["customer_state"]], late, delay, review)
            record(bucket_counts[month, bucket], late, delay, review)
            if review is not None:
                reviewed_orders[order_id] = (late, review)
                group = state_reviews[row["customer_state"]][int(late)]
                group[0] += 1
                group[1] += review
                if -20 <= delay <= 20:
                    day_counts[month, str(delay)][0] += 1
                    day_counts[month, str(delay)][1] += review
    require(set(counts) == set(data["months"]), "Export/aggregates months disagree")
    for month, values in counts.items():
        require(tuple(values) == fields(data["months"][month]),
                f"Export/aggregates totals disagree: {month}")
    for (month, state), values in state_counts.items():
        require(tuple(values) == fields(data["states"][month][state]),
                f"Export/aggregates state disagrees: {month}/{state}")
    for (month, bucket), values in bucket_counts.items():
        require(tuple(values) == fields(data["buckets"][month][bucket]),
                f"Export/aggregates bucket disagrees: {month}/{bucket}")
    require({month for month, _ in day_counts} == set(data["daily"]),
            "Daily curve months disagree with exports")
    require(len(day_counts) == sum(len(rows) for rows in data["daily"].values()),
            "Daily curve point count disagrees with exports")
    for (month, day), (reviews, scores) in day_counts.items():
        require(data["daily"][month][day] == {"reviews": reviews, "scores": scores},
                f"Daily curve disagrees with export: {month}/{day}")

    def compare(groups: dict, minimum_ontime: int, minimum_late: int) -> tuple:
        eligible = [rows for rows in groups.values()
                    if rows[0][0] >= minimum_ontime and rows[1][0] >= minimum_late]
        late_count = sum(rows[1][0] for rows in eligible)
        gap = round(sum(rows[1][0] *
                        (rows[0][1] / rows[0][0] - rows[1][1] / rows[1][0])
                        for rows in eligible) / late_count, 3)
        return len(eligible), late_count, sum(rows[0][1]/rows[0][0] > rows[1][1]/rows[1][0]
                                             for rows in eligible), gap

    state_cut = data["robustness"]["state"]
    require(compare(state_reviews, 100, 30) ==
            (state_cut["groups"], state_cut["late_reviews"],
             state_cut["positive_groups"], state_cut["gap"]),
            "State robustness summary disagrees with exports")

    seller_reviews = defaultdict(lambda: [[0, 0], [0, 0]])
    unique_pairs = set()
    with ITEMS.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            pair = row["order_id"], row["seller_id"]
            if pair in unique_pairs:
                continue
            unique_pairs.add(pair)
            reviewed = reviewed_orders.get(row["order_id"])
            if reviewed:
                late, review = reviewed
                group = seller_reviews[row["seller_id"]][int(late)]
                group[0] += 1
                group[1] += review
    seller_cut = data["robustness"]["seller"]
    require(compare(seller_reviews, 20, 5) ==
            (seller_cut["groups"], seller_cut["late_reviews"],
             seller_cut["positive_groups"], seller_cut["gap"]),
            "Seller robustness summary disagrees with source order items")

    aggregate_sellers = {row["id"]: row for row in data["sellers"]}
    seller_ids = set()
    with SELLERS.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            seller_id = row["seller_id"]
            require(seller_id not in seller_ids, f"Duplicate seller export: {seller_id}")
            seller_ids.add(seller_id)
            require(seller_id in aggregate_sellers, f"Seller missing from aggregates: {seller_id}")
            displayed = aggregate_sellers[seller_id]
            require(displayed["state"] == row["seller_state"] and
                    displayed["orders"] == int(row["total_orders"]) and
                    displayed["late"] == int(row["late_orders"]) and
                    displayed["rate"] == float(row["late_pct"]) / 100 and
                    displayed["review"] == (float(row["avg_review"]) if row["avg_review"] else None),
                    f"Seller export/aggregates disagrees: {seller_id}")
    require(seller_ids == set(aggregate_sellers),
            "Seller export/aggregates IDs disagree")
    print(f"Exports OK: {len(seen):,} unique fact orders and {len(seller_ids)} sellers")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregates-only", action="store_true",
                        help="check analysis control data without raw CSVs or exports")
    args = parser.parse_args()
    data = read_aggregates()
    validate_aggregates(data)
    if not args.aggregates_only:
        validate_exports(data)


if __name__ == "__main__":
    main()
