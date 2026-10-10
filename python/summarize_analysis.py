"""Write portable Olist analysis tables from the validated order-level export.

Every delivered order and observed purchase month / calendar-day delay is kept.
Missing review scores remain missing and never enter the rating denominator.
"""

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACT = ROOT / "exports/fact_orders.csv"
SELLERS = ROOT / "exports/seller_performance.csv"
OUTPUT = ROOT / "analysis"
BUCKET_ORDER = ("On-time", "1–3 days", "4–7 days", "8+ days")
METRIC_COLUMNS = (
    "orders", "late_orders", "on_time_orders", "reviewed_orders",
    "missing_review_orders", "review_score_sum", "review_coverage_pct",
    "late_rate_pct", "on_time_rate_pct", "average_review_score",
    "late_delay_days_sum", "average_late_delay_days", "delay_days_sum",
    "average_delay_days",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def ratio(numerator: int, denominator: int, scale: int = 1) -> float | None:
    return scale * numerator / denominator if denominator else None


@dataclass
class Metrics:
    orders: int = 0
    late_orders: int = 0
    reviewed_orders: int = 0
    review_score_sum: int = 0
    late_delay_days_sum: int = 0
    delay_days_sum: int = 0

    def add(self, late: bool, delay: int, score: int | None) -> None:
        self.orders += 1
        self.late_orders += int(late)
        self.delay_days_sum += delay
        self.late_delay_days_sum += delay if late else 0
        if score is not None:
            self.reviewed_orders += 1
            self.review_score_sum += score

    def values(self) -> dict:
        return {
            "orders": self.orders,
            "late_orders": self.late_orders,
            "on_time_orders": self.orders - self.late_orders,
            "reviewed_orders": self.reviewed_orders,
            "missing_review_orders": self.orders - self.reviewed_orders,
            "review_score_sum": self.review_score_sum,
            "review_coverage_pct": ratio(self.reviewed_orders, self.orders, 100),
            "late_rate_pct": ratio(self.late_orders, self.orders, 100),
            "on_time_rate_pct": ratio(self.orders - self.late_orders, self.orders, 100),
            "average_review_score": ratio(self.review_score_sum, self.reviewed_orders),
            "late_delay_days_sum": self.late_delay_days_sum,
            "average_late_delay_days": ratio(self.late_delay_days_sum, self.late_orders),
            "delay_days_sum": self.delay_days_sum,
            "average_delay_days": ratio(self.delay_days_sum, self.orders),
        }


def write_table(filename: str, dimension: str, groups: dict, keys: list) -> None:
    with (OUTPUT / filename).open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=[dimension, *METRIC_COLUMNS])
        writer.writeheader()
        for key in keys:
            row = {dimension: key, **groups[key].values()}
            writer.writerow({k: round(v, 8) if isinstance(v, float) else v
                             for k, v in row.items()})


def seller_source_summary() -> dict | None:
    if not SELLERS.exists():
        return None
    seen = set()
    states = set()
    with SELLERS.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        require(set(reader.fieldnames or []) >= {
            "seller_id", "seller_state", "total_orders", "late_orders", "late_pct", "avg_review"
        }, "Seller export has missing columns")
        for row in reader:
            seller_id = row["seller_id"]
            require(seller_id not in seen, f"Duplicate seller: {seller_id}")
            seen.add(seller_id)
            orders, late = int(row["total_orders"]), int(row["late_orders"])
            require(orders >= 30 and 0 <= late <= orders,
                    f"Invalid qualified seller counts: {seller_id}")
            require(abs(float(row["late_pct"]) - 100 * late / orders) <= 0.0051,
                    f"Invalid seller late percentage: {seller_id}")
            score = float(row["avg_review"]) if row["avg_review"] else None
            require(score is None or 1 <= score <= 5, f"Invalid seller rating: {seller_id}")
            states.add(row["seller_state"])
    return {
        "source": "exports/seller_performance.csv",
        "qualified_sellers": len(seen),
        "seller_states": len(states),
        "minimum_delivered_orders_per_seller": 30,
        "period": "All period",
        "attribution": "One distinct order per participating seller; a multi-seller order can count for multiple sellers.",
    }


def main() -> None:
    require(FACT.is_file(), "Missing exports/fact_orders.csv; generate or copy the fact export first")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    overall = Metrics()
    by_status = defaultdict(Metrics)
    by_bucket = defaultdict(Metrics)
    by_month = defaultdict(Metrics)
    by_state = defaultdict(Metrics)
    by_day = defaultdict(Metrics)
    seen = set()
    first_purchase = last_purchase = None

    with FACT.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        require(set(reader.fieldnames or []) >= {
            "order_id", "customer_state", "purchased_at", "delivered_at",
            "estimated_at", "delay_days", "is_late", "review_score"
        }, "Fact export has missing columns")
        for row in reader:
            order_id = row["order_id"]
            require(order_id and order_id not in seen, f"Missing or duplicate order ID: {order_id}")
            seen.add(order_id)
            purchased = datetime.fromisoformat(row["purchased_at"])
            delivered = datetime.fromisoformat(row["delivered_at"])
            estimated = datetime.fromisoformat(row["estimated_at"])
            delay = (delivered.date() - estimated.date()).days
            require(delivered >= purchased and int(row["delay_days"]) == delay,
                    f"Invalid chronology or calendar-day delay: {order_id}")
            require(row["is_late"] in {"true", "false"}, f"Invalid late flag: {order_id}")
            late = row["is_late"] == "true"
            require(late == (delay > 0), f"Late flag disagrees with calendar dates: {order_id}")
            state = row["customer_state"]
            require(re.fullmatch(r"[A-Z]{2}", state) is not None, f"Invalid customer state: {order_id}")
            score = int(row["review_score"]) if row["review_score"] else None
            require(score is None or 1 <= score <= 5, f"Invalid review score: {order_id}")
            status = "Late" if late else "On-time"
            bucket = ("On-time" if delay <= 0 else "1–3 days" if delay <= 3 else
                      "4–7 days" if delay <= 7 else "8+ days")
            month = purchased.strftime("%Y-%m")
            for metrics in (overall, by_status[status], by_bucket[bucket],
                            by_month[month], by_state[state], by_day[delay]):
                metrics.add(late, delay, score)
            first_purchase = min(first_purchase, purchased) if first_purchase else purchased
            last_purchase = max(last_purchase, purchased) if last_purchase else purchased

    controls = (overall.orders, overall.late_orders, overall.reviewed_orders,
                overall.review_score_sum, overall.late_delay_days_sum)
    require(controls == (96_470, 6_534, 95_824, 398_233, 69_392),
            f"Prepared analysis differs from the verified Olist baseline: {controls}")
    for name, groups in (("status", by_status), ("bucket", by_bucket), ("month", by_month),
                         ("state", by_state), ("day", by_day)):
        observed = tuple(sum(getattr(m, field) for m in groups.values()) for field in
                         ("orders", "late_orders", "reviewed_orders", "review_score_sum", "late_delay_days_sum"))
        require(observed == controls, f"{name} groups do not reconcile with overall totals")

    write_table("delivery_summary.csv", "delivery_status", by_status, ["On-time", "Late"])
    write_table("delay_buckets.csv", "delay_bucket", by_bucket, list(BUCKET_ORDER))
    write_table("monthly_delivery.csv", "purchase_month", by_month, sorted(by_month))
    write_table("state_delivery.csv", "customer_state", by_state, sorted(by_state))
    write_table("daily_delay_reviews.csv", "delay_days", by_day, sorted(by_day))

    ontime_review = by_status["On-time"].values()["average_review_score"]
    late_review = by_status["Late"].values()["average_review_score"]
    summary = {
        "source": "Brazilian E-Commerce Public Dataset by Olist, 2016–2018",
        "fact_source": "exports/fact_orders.csv",
        "grain": "One delivered order per row, with usable delivery and estimated dates",
        "controls_reconciled": True,
        "overall": overall.values(),
        "review_score_by_delivery_status": {
            "on_time": ontime_review,
            "late": late_review,
            "on_time_minus_late_points": ontime_review - late_review,
        },
        "coverage": {
            "first_purchase": first_purchase.isoformat(sep=" "),
            "last_purchase": last_purchase.isoformat(sep=" "),
            "purchase_months": len(by_month),
            "customer_states": len(by_state),
            "observed_calendar_day_delays": len(by_day),
            "minimum_delay_days": min(by_day),
            "maximum_delay_days": max(by_day),
        },
        "table_grains": {
            "delivery_summary.csv": "One row per delivery status; no duplicate overall row",
            "delay_buckets.csv": "One row per non-overlapping delay bucket",
            "monthly_delivery.csv": "One row per observed purchase month, including tiny cohorts",
            "state_delivery.csv": "One row per customer state; all states retained",
            "daily_delay_reviews.csv": "One row per observed signed calendar-day delay; no display-range truncation",
        },
        "methods": {
            "late": "Delivered calendar date after estimated calendar date; same-day deliveries are on time",
            "reviews": "Mean score among reviewed orders only; missing scores are excluded, not treated as zero",
            "duplicate_reviews": "The SQL fact export selects the latest answered review to preserve order grain",
            "denominators": "Rates use delivered-order counts; review means use reviewed-order counts; late-delay mean uses late-order count",
            "numeric_precision": "CSV ratios and means are rounded to eight decimals; JSON retains full floating-point precision; counts and sums are exact integers",
        },
        "limits": [
            "Delivery/rating differences are descriptive associations, not proof of causation or intervention impact.",
            "Only eligible delivered orders are included; canceled, undelivered and missing-date orders can have different review patterns.",
            "Small cohorts can produce volatile rates; inspect order and reviewed-order counts before interpreting rankings.",
            "Historical Brazilian public data do not establish current business performance.",
        ],
        "seller_source": seller_source_summary(),
    }
    (OUTPUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"Analysis OK: {overall.orders:,} orders, {overall.late_orders:,} late, "
          f"{overall.reviewed_orders:,} reviewed")
    print(f"Exact controls: review score sum {overall.review_score_sum:,}; "
          f"late delay sum {overall.late_delay_days_sum:,}")
    print(f"Wrote five CSVs and summary.json to {OUTPUT}")


if __name__ == "__main__":
    main()
