"""Two-sided Mann–Whitney U test of late vs on-time ordinal review scores.

Uses scipy.stats.mannwhitneyu when installed. The fallback computes SciPy's
asymptotic, tie-corrected result so the project can be verified offline.
"""
import csv
from collections import Counter
from math import erfc, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "exports/fact_orders.csv"


def asymptotic_from_counts(late: Counter, ontime: Counter):
    n1, n2 = sum(late.values()), sum(ontime.values())
    u = sum(late[score] * (sum(n for x, n in ontime.items() if x < score) +
                            ontime[score] / 2) for score in late)
    n = n1 + n2
    ties = late + ontime
    tie_term = sum(t**3 - t for t in ties.values())
    sd = sqrt(n1 * n2 / 12 * ((n + 1) - tie_term / (n * (n - 1))))
    z = (abs(u - n1 * n2 / 2) - 0.5) / sd
    return u, erfc(z / sqrt(2)), z


def main():
    if not SOURCE.exists():
        raise SystemExit("Run the mart export first: exports/fact_orders.csv missing")
    late, ontime = Counter(), Counter()
    with SOURCE.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["review_score"]:
                is_late = row["is_late"].lower() in ("t", "true")
                (late if is_late else ontime)[int(row["review_score"])] += 1
    n1, n2 = sum(late.values()), sum(ontime.values())
    u, fallback_p, z = asymptotic_from_counts(late, ontime)
    method = "tie-corrected normal approximation"
    try:
        from scipy.stats import mannwhitneyu
        # Data are 1–5 ordinal scores. 'asymptotic' handles large samples/ties.
        result = mannwhitneyu(
            [score for score, count in late.items() for _ in range(count)],
            [score for score, count in ontime.items() for _ in range(count)],
            alternative="two-sided", method="asymptotic",
        )
        u, p = float(result.statistic), float(result.pvalue)
        method = "scipy.stats.mannwhitneyu (asymptotic, two-sided)"
    except ImportError:
        p = fallback_p
    print(f"method: {method}")
    print(f"late reviewed orders: {n1}; on-time reviewed orders: {n2}")
    print(f"U: {u:,.0f}; z: {z:.2f}; p: {'<1e-300' if p == 0 else f'{p:.3g}'}")
    print(f"rank-biserial effect (late vs on-time): {2*u/(n1*n2)-1:.3f}")


if __name__ == "__main__":
    main()
