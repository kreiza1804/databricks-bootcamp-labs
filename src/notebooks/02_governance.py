# Databricks notebook source
# MAGIC %md
# MAGIC # Lab 04 · Unity Catalog, Domains & Metric Views
# MAGIC Prerequisites: labs 02–03 completed; you created the groups `bootcamp_analysts` and
# MAGIC `bootcamp_engineers` and added yourself to `bootcamp_engineers` (lab 00, part 2.5).
# MAGIC
# MAGIC UI steps (Domains, glossary, lineage) are in `labs/lab-02-data-governance/README.md`.

# COMMAND ----------

# MAGIC %run ./_setup

# COMMAND ----------

# MAGIC %md ## 1 · Privileges

# COMMAND ----------

spark.sql(f"GRANT USE SCHEMA, SELECT ON SCHEMA `{catalog}`.`{schema}` TO `bootcamp_analysts`")
spark.sql(f"GRANT USE SCHEMA, SELECT, MODIFY, CREATE TABLE ON SCHEMA `{catalog}`.`{schema}` TO `bootcamp_engineers`")
display(spark.sql(f"SHOW GRANTS ON SCHEMA `{catalog}`.`{schema}`"))

# COMMAND ----------

# MAGIC %md ## 2 · Tag sensitive columns and mask them

# COMMAND ----------

# MAGIC %sql
# MAGIC ALTER TABLE customer_profiles ALTER COLUMN email SET TAGS ('pii' = 'email');
# MAGIC ALTER TABLE customer_profiles ALTER COLUMN last_name SET TAGS ('pii' = 'name');

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE FUNCTION mask_email(email STRING)
# MAGIC RETURNS STRING
# MAGIC COMMENT 'Shows full e-mail to engineers, domain only to everyone else'
# MAGIC RETURN CASE
# MAGIC   WHEN is_account_group_member('bootcamp_engineers') THEN email
# MAGIC   ELSE concat('***@', split_part(email, '@', 2))
# MAGIC END;
# MAGIC
# MAGIC ALTER TABLE customer_profiles ALTER COLUMN email SET MASK mask_email;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- You are in bootcamp_engineers: full e-mails. Now remove yourself from the group
# MAGIC -- (Settings → Identity and access → Groups), wait ~1 minute and re-run: e-mails are masked.
# MAGIC -- Add yourself back afterwards.
# MAGIC SELECT customer_id, first_name, email, region FROM customer_profiles LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ### Stretch · the same control with ABAC
# MAGIC Attribute-based policies apply to **every** column tagged `pii`, in every table of the schema,
# MAGIC instead of one table at a time. Follow the ABAC docs for your workspace
# MAGIC (policy syntax and availability vary by release — metastore-level policies are Beta):
# MAGIC https://docs.databricks.com/aws/en/data-governance/unity-catalog/abac/
# MAGIC
# MAGIC Optional: create a *tag automation* rule (Beta) that tags every new column named `email` with `pii=email`.

# COMMAND ----------

# MAGIC %md ## 3 · A governed metric view

# COMMAND ----------

metric_yaml = f"""
version: 1.1
comment: Governed sales KPIs for dashboards, Genie Agents and apps
source: {catalog}.{schema}.orders_enriched
dimensions:
  - name: order_month
    expr: DATE_TRUNC('MONTH', order_date)
  - name: region
    expr: region
  - name: segment
    expr: segment
  - name: category
    expr: category
  - name: channel
    expr: channel
measures:
  - name: revenue
    expr: SUM(amount)
  - name: order_count
    expr: COUNT(DISTINCT order_id)
  - name: avg_order_value
    expr: SUM(amount) / COUNT(DISTINCT order_id)
"""
spark.sql(f"CREATE OR REPLACE VIEW orders_metrics WITH METRICS LANGUAGE YAML AS $${metric_yaml}$$")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT order_month, region,
# MAGIC        MEASURE(revenue)         AS revenue,
# MAGIC        MEASURE(avg_order_value) AS aov
# MAGIC FROM orders_metrics
# MAGIC GROUP BY ALL
# MAGIC ORDER BY order_month, region;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4 · Troubleshoot
# MAGIC Break it yourself: `REVOKE SELECT ON TABLE customer_profiles FROM bootcamp_analysts`.
# MAGIC Then use **Catalog Explorer → Permissions** and **Lineage** to find which downstream objects analysts can no
# MAGIC longer read (metric view, dashboard), and grant it back.