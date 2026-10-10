"""Export the two analysis marts with PostgreSQL COPY."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PSQL = os.environ.get("PSQL") or shutil.which("psql") or "/Library/PostgreSQL/18/bin/psql"

queries = {
    "fact_orders": """SELECT order_id, customer_state, purchased_at, delivered_at,
        estimated_at, delay_days, is_late::text AS is_late, review_score
        FROM mart.fact_orders ORDER BY order_id""",
    "seller_performance": "SELECT * FROM mart.seller_performance ORDER BY late_pct DESC, total_orders DESC",
}
for table, query in queries.items():
    target = ROOT / "exports" / f"{table}.csv"
    sql = f"COPY ({query}) TO STDOUT WITH (FORMAT csv, HEADER true)"
    with target.open("wb") as output:
        subprocess.run([PSQL, "-X", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       stdout=output, check=True)
    print(f"Exported {target}")
