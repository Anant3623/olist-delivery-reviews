CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE VIEW staging.orders AS
SELECT order_id, customer_id, order_status,
       NULLIF(order_purchase_timestamp, '')::timestamp AS purchased_at,
       NULLIF(order_delivered_customer_date, '')::timestamp AS delivered_at,
       NULLIF(order_estimated_delivery_date, '')::timestamp AS estimated_at
FROM raw.orders;

CREATE OR REPLACE VIEW staging.reviews AS
SELECT review_id, order_id, NULLIF(review_score, '')::integer AS review_score,
       NULLIF(review_creation_date, '')::timestamp AS created_at,
       NULLIF(review_answer_timestamp, '')::timestamp AS answered_at
FROM raw.order_reviews;

CREATE OR REPLACE VIEW staging.order_items AS
SELECT order_id, NULLIF(order_item_id, '')::integer AS order_item_id,
       seller_id, NULLIF(price, '')::numeric AS price
FROM raw.order_items;

CREATE OR REPLACE VIEW staging.sellers AS
SELECT seller_id, seller_state
FROM raw.sellers;

CREATE OR REPLACE VIEW staging.customers AS
SELECT customer_id, customer_state
FROM raw.customers;
