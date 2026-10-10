-- 1. Late vs on-time review: denominator excludes orders without a review.
SELECT CASE WHEN is_late THEN 'Late' ELSE 'On-time' END AS delivery_group,
       COUNT(*) AS delivered_orders, COUNT(review_score) AS reviewed_orders,
       ROUND(AVG(review_score)::numeric, 3) AS avg_review
FROM mart.fact_orders GROUP BY is_late ORDER BY is_late;

-- 2. Inclusive buckets; >7 means 8+ calendar days late.
WITH bucketed AS (
    SELECT CASE WHEN delay_days <= 0 THEN 'On-time'
                WHEN delay_days <= 3 THEN '1-3 days'
                WHEN delay_days <= 7 THEN '4-7 days'
                ELSE '8+ days' END AS delay_bucket,
           CASE WHEN delay_days <= 0 THEN 1 WHEN delay_days <= 3 THEN 2
                WHEN delay_days <= 7 THEN 3 ELSE 4 END AS sort_order,
           review_score
    FROM mart.fact_orders
)
SELECT delay_bucket, COUNT(*) AS delivered_orders,
       COUNT(review_score) AS reviewed_orders,
       ROUND(AVG(review_score)::numeric, 3) AS avg_review
FROM bucketed GROUP BY delay_bucket, sort_order ORDER BY sort_order;

-- 3. States with at least 100 delivered orders to stabilize the ranking.
SELECT customer_state, COUNT(*) AS delivered_orders,
       COUNT(*) FILTER (WHERE is_late) AS late_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_late) / COUNT(*), 2) AS late_pct
FROM mart.fact_orders GROUP BY customer_state HAVING COUNT(*) >= 100
ORDER BY late_pct DESC, delivered_orders DESC LIMIT 10;

-- 4. Purchase-month cohorts, not delivery-month cohorts.
SELECT to_char(date_trunc('month', purchased_at), 'YYYY-MM') AS purchase_month,
       COUNT(*) AS delivered_orders,
       COUNT(*) FILTER (WHERE is_late) AS late_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE is_late) / COUNT(*), 2) AS late_pct
FROM mart.fact_orders GROUP BY 1 ORDER BY 1;

-- Supplement: seller ranking after the >=30 order qualification.
SELECT * FROM mart.seller_performance
ORDER BY late_pct DESC, total_orders DESC LIMIT 10;
