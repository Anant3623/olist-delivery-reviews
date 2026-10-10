CREATE SCHEMA IF NOT EXISTS mart;
DROP TABLE IF EXISTS mart.seller_performance;
DROP TABLE IF EXISTS mart.fact_orders;

-- One review per order: most recently answered, then created, then review ID.
CREATE TABLE mart.fact_orders AS
WITH latest_review AS (
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (
               PARTITION BY order_id
               ORDER BY answered_at DESC NULLS LAST, created_at DESC NULLS LAST, review_id DESC
           ) AS rn
    FROM staging.reviews
)
SELECT o.order_id, c.customer_state, o.purchased_at, o.delivered_at,
       o.estimated_at,
       (o.delivered_at::date - o.estimated_at::date) AS delay_days,
       (o.delivered_at::date > o.estimated_at::date) AS is_late,
       r.review_score
FROM staging.orders o
JOIN staging.customers c USING (customer_id)
LEFT JOIN latest_review r ON r.order_id = o.order_id AND r.rn = 1
WHERE o.order_status = 'delivered'
  AND o.delivered_at IS NOT NULL AND o.estimated_at IS NOT NULL
  AND o.purchased_at IS NOT NULL AND o.delivered_at >= o.purchased_at;

ALTER TABLE mart.fact_orders ADD PRIMARY KEY (order_id);
CREATE INDEX fact_orders_state_idx ON mart.fact_orders (customer_state);
CREATE INDEX fact_orders_month_idx ON mart.fact_orders (purchased_at);

-- Each seller receives one attribution per order, even with multiple line items.
-- A multi-seller order is counted once for each participating seller.
CREATE TABLE mart.seller_performance AS
WITH order_sellers AS (
    SELECT DISTINCT order_id, seller_id FROM staging.order_items
)
SELECT os.seller_id, s.seller_state,
       COUNT(*) AS total_orders,
       COUNT(*) FILTER (WHERE f.is_late) AS late_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE f.is_late) / COUNT(*), 2) AS late_pct,
       ROUND(AVG(f.review_score)::numeric, 2) AS avg_review
FROM order_sellers os
JOIN mart.fact_orders f USING (order_id)
JOIN staging.sellers s USING (seller_id)
GROUP BY os.seller_id, s.seller_state
HAVING COUNT(*) >= 30;

ALTER TABLE mart.seller_performance ADD PRIMARY KEY (seller_id);
