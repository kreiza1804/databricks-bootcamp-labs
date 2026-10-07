# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 03 · Delta Lake & managed Iceberg
# MAGIC Prerequisite: the `orders_pipeline` from lab 01 has run at least once.
# MAGIC
# MAGIC 1. Create a Delta table and a managed Iceberg table
# MAGIC 2. MERGE late-arriving updates
# MAGIC 3. Multi-statement transaction
# MAGIC 4. Time travel and RESTORE
# MAGIC 5. Row-level changes
# MAGIC 6. Automatic liquid clustering

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

# MAGIC %md ## 1 · Delta and managed Iceberg tables

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Delta table used again in the governance lab (email will be masked there)
# MAGIC CREATE OR REPLACE TABLE customer_profiles
# MAGIC COMMENT 'Customer profiles (Delta) — governed in lab 02'
# MAGIC AS SELECT customer_id, first_name, last_name, email, region, segment, to_date(signup_date) AS signup_date
# MAGIC FROM customers;
# MAGIC
# MAGIC CREATE OR REPLACE TABLE orders_iceberg
# MAGIC USING ICEBERG
# MAGIC COMMENT 'Managed Iceberg copy of silver orders, readable by external Iceberg clients'
# MAGIC AS SELECT * FROM orders_silver;
# MAGIC
# MAGIC SELECT count(*) AS iceberg_rows FROM orders_iceberg;

# COMMAND ----------

# MAGIC %md ## 2 · MERGE late-arriving updates

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TEMP VIEW profile_updates AS
# MAGIC SELECT * FROM VALUES
# MAGIC   (1,   'enterprise'),     -- existing customer upgraded
# MAGIC   (2,   'smb'),
# MAGIC   (9001, 'consumer')       -- brand-new customer
# MAGIC AS t(customer_id, segment);
# MAGIC
# MAGIC MERGE INTO customer_profiles AS t
# MAGIC USING profile_updates AS s
# MAGIC ON t.customer_id = s.customer_id
# MAGIC WHEN MATCHED THEN UPDATE SET t.segment = s.segment
# MAGIC WHEN NOT MATCHED THEN INSERT (customer_id, segment, signup_date)
# MAGIC   VALUES (s.customer_id, s.segment, current_date());

# COMMAND ----------

# MAGIC %md ## 3 · Multi-statement transaction
# MAGIC Refund an order: mark it refunded **and** record the refund — both or neither.
# MAGIC Transactions across Unity Catalog managed Delta tables are GA since July 2026; check the docs if your workspace reports that the feature is not enabled.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE orders_status AS
# MAGIC SELECT order_id, customer_id, amount, 'completed' AS status FROM orders_silver;
# MAGIC
# MAGIC CREATE TABLE IF NOT EXISTS refunds (order_id BIGINT, refunded_at TIMESTAMP, amount DECIMAL(12, 2));
# MAGIC
# MAGIC -- Enable catalog commits for multi-statement transaction support
# MAGIC ALTER TABLE orders_status SET TBLPROPERTIES ('delta.feature.catalogManaged' = 'supported');
# MAGIC ALTER TABLE refunds SET TBLPROPERTIES ('delta.feature.catalogManaged' = 'supported');

# COMMAND ----------

# MAGIC %sql
# MAGIC BEGIN ATOMIC
# MAGIC   UPDATE orders_status SET status = 'refunded' WHERE order_id = 1;
# MAGIC   INSERT INTO refunds SELECT order_id, current_timestamp(), amount FROM orders_status WHERE order_id = 1;
# MAGIC END;

# COMMAND ----------

# MAGIC %md ## 4 · Time travel and RESTORE

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Oops: someone deletes all EMEA customers
# MAGIC DELETE FROM customer_profiles WHERE region = 'EMEA';
# MAGIC DESCRIBE HISTORY customer_profiles;

# COMMAND ----------

history = spark.sql("DESCRIBE HISTORY customer_profiles")
delete_version = history.filter("operation = 'DELETE'").agg({"version": "max"}).first()[0]
before = delete_version - 1
print("EMEA rows before the delete:",
      spark.sql(f"SELECT count(*) FROM customer_profiles VERSION AS OF {before} WHERE region = 'EMEA'").first()[0])
display(spark.sql(f"RESTORE TABLE customer_profiles TO VERSION AS OF {before}"))

# COMMAND ----------

# MAGIC %md ## 5 · Row-level changes

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Automatic change data feed (GA Sept 2026) computes changes from row tracking.
# MAGIC -- On older runtimes, enable CDF explicitly first:
# MAGIC ALTER TABLE customer_profiles SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
# MAGIC UPDATE customer_profiles SET segment = 'enterprise' WHERE customer_id = 3;
# MAGIC

# COMMAND ----------

latest = spark.sql("DESCRIBE HISTORY customer_profiles").agg({"version": "max"}).first()[0]
display(spark.sql(f"""
  SELECT _change_type, _commit_version, customer_id, segment
  FROM table_changes('customer_profiles', {latest})
  ORDER BY customer_id, _change_type
"""))

# COMMAND ----------

# MAGIC %md ## 6 · Let the platform optimise layout

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE orders_status CLUSTER BY AUTO;
# MAGIC DESCRIBE DETAIL orders_status;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stretch
# MAGIC * Read `orders_iceberg` from an external engine using the Unity Catalog Iceberg REST endpoint.
# MAGIC * Parse raw JSON into a `VARIANT` column: `SELECT parse_json(to_json(struct(*))) AS v FROM orders_bronze LIMIT 5`.