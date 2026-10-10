"""Load Olist CSVs as lossless text into PostgreSQL using its COPY protocol.

Identifiers and original timestamp strings remain unchanged in raw; staging casts
only the columns needed for analysis. Requires the PostgreSQL psql command.
"""
import csv
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "olist_customers_dataset.csv": "customers",
    "olist_geolocation_dataset.csv": "geolocation",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_orders_dataset.csv": "orders",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "product_category_name_translation",
}


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def psql(*args: str, stdin=None) -> str:
    binary = os.environ.get("PSQL") or shutil.which("psql") or "/Library/PostgreSQL/18/bin/psql"
    result = subprocess.run(
        [binary, "-X", "-v", "ON_ERROR_STOP=1", *args],
        stdin=stdin, text=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or b"psql failed").decode(errors="replace"))
    return result.stdout.decode().strip() if result.stdout else ""


def main() -> None:
    missing = [name for name in FILES if not (ROOT / "data/raw" / name).exists()]
    if missing:
        raise SystemExit("Missing CSVs in data/raw/: " + ", ".join(missing))
    psql("-c", "CREATE SCHEMA IF NOT EXISTS raw")
    for filename, table in FILES.items():
        path = ROOT / "data/raw" / filename
        with path.open(encoding="utf-8-sig", newline="") as file:
            columns = next(csv.reader(file))
        # The translation CSV contains a UTF-8 BOM, stripped above from the header.
        definitions = ", ".join(f"{quote(col)} text" for col in columns)
        psql("-c", f"CREATE TABLE IF NOT EXISTS raw.{quote(table)} ({definitions}); TRUNCATE raw.{quote(table)}")
        names = ", ".join(map(quote, columns))
        with path.open("rb") as file:
            # COPY skips the header. PostgreSQL tolerates the BOM in that line.
            psql("-c", f"COPY raw.{quote(table)} ({names}) FROM STDIN WITH (FORMAT csv, HEADER true)", stdin=file)
        count = psql("-At", "-c", f"SELECT count(*) FROM raw.{quote(table)}")
        print(f"{table}: {count} rows")


if __name__ == "__main__":
    main()
