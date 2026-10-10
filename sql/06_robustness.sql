-- Within-group descriptive cuts, not causal estimates.
-- Each group's on-time minus late mean is weighted by its late reviewed orders.

WITH state_scores AS (
    SELECT customer_state,
           COUNT(*) FILTER (WHERE NOT is_late) AS ontime_reviews,
           COUNT(*) FILTER (WHERE is_late) AS late_reviews,
           AVG(review_score) FILTER (WHERE NOT is_late) AS ontime_mean,
           AVG(review_score) FILTER (WHERE is_late) AS late_mean
    FROM mart.fact_orders
    WHERE review_score IS NOT NULL
    GROUP BY customer_state
), eligible AS (
    SELECT * FROM state_scores
    WHERE ontime_reviews >= 100 AND late_reviews >= 30
)
SELECT 'same customer state' AS comparison,
       COUNT(*) AS qualifying_groups,
       SUM(late_reviews) AS late_reviewed_orders,
       COUNT(*) FILTER (WHERE ontime_mean > late_mean) AS groups_with_lower_late_score,
       ROUND(SUM(late_reviews * (ontime_mean - late_mean)) / SUM(late_reviews), 3)
           AS late_weighted_review_gap
FROM eligible;

WITH order_sellers AS (
    SELECT DISTINCT order_id, seller_id FROM staging.order_items
), seller_scores AS (
    SELECT os.seller_id,
           COUNT(*) FILTER (WHERE NOT f.is_late) AS ontime_reviews,
           COUNT(*) FILTER (WHERE f.is_late) AS late_reviews,
           AVG(f.review_score) FILTER (WHERE NOT f.is_late) AS ontime_mean,
           AVG(f.review_score) FILTER (WHERE f.is_late) AS late_mean
    FROM order_sellers os
    JOIN mart.fact_orders f USING (order_id)
    WHERE f.review_score IS NOT NULL
    GROUP BY os.seller_id
), eligible AS (
    SELECT * FROM seller_scores
    WHERE ontime_reviews >= 20 AND late_reviews >= 5
)
SELECT 'same participating seller' AS comparison,
       COUNT(*) AS qualifying_groups,
       SUM(late_reviews) AS late_reviewed_order_attributions,
       COUNT(*) FILTER (WHERE ontime_mean > late_mean) AS groups_with_lower_late_score,
       ROUND(SUM(late_reviews * (ontime_mean - late_mean)) / SUM(late_reviews), 3)
           AS late_weighted_review_gap
FROM eligible;
