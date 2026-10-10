-- Each failed value is the number of rows, except multiple_reviews counts
-- affected orders. IQR fences include early and late deliveries and are flags.
WITH delivered AS (
    SELECT (delivered_at::date - estimated_at::date) AS delay_days
    FROM staging.orders
    WHERE order_status = 'delivered'
      AND delivered_at IS NOT NULL AND estimated_at IS NOT NULL
), quartiles AS (
    SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY delay_days) AS q1,
           percentile_cont(0.75) WITHIN GROUP (ORDER BY delay_days) AS q3
    FROM delivered
)
SELECT 'delivered_but_no_date' AS check_name, COUNT(*) AS failed
FROM staging.orders WHERE order_status = 'delivered' AND delivered_at IS NULL
UNION ALL
SELECT 'delivered_before_purchase', COUNT(*)
FROM staging.orders WHERE delivered_at < purchased_at
UNION ALL
SELECT 'duplicate_order_id', COUNT(*) - COUNT(DISTINCT order_id)
FROM staging.orders
UNION ALL
SELECT 'orphan_order_item_rows', COUNT(*)
FROM staging.order_items i LEFT JOIN staging.orders o USING (order_id)
WHERE o.order_id IS NULL
UNION ALL
SELECT 'orders_with_multiple_reviews', COUNT(*)
FROM (SELECT order_id FROM staging.reviews GROUP BY order_id HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'delay_iqr_outlier_orders', COUNT(*)
FROM delivered d CROSS JOIN quartiles q
WHERE d.delay_days < q.q1 - 1.5 * (q.q3 - q.q1)
   OR d.delay_days > q.q3 + 1.5 * (q.q3 - q.q1)
ORDER BY check_name;
