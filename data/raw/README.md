# Raw Olist files

Download the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), unzip it, and place these **original, unedited** CSV files here:

- `olist_customers_dataset.csv`
- `olist_geolocation_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_payments_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_products_dataset.csv`
- `olist_sellers_dataset.csv`
- `product_category_name_translation.csv`

The raw CSVs are excluded from Git. The loader checks that all nine are present and preserves every source column as text before the staging views cast the fields used by the analysis. See the [README](../../README.md) for the analysis controls and run instructions.
