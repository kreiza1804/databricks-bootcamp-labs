# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Lab 00 · Free Edition setup (run once, ~2 minutes)
# MAGIC Creates the three environment catalogs and checks everything the labs need in **your** Free Edition workspace.
# MAGIC Run it on **Serverless** from your Git folder: `setup/free_edition_setup`.
# MAGIC
# MAGIC | Environment | Catalog | Who deploys | Workspace path |
# MAGIC |---|---|---|---|
# MAGIC | dev | `bootcamp_dev` (schema `dev_<you>_sales`) | you, from the workspace or CLI | `/Users/<you>/.bundle/…/dev` |
# MAGIC | staging | `bootcamp_staging` (schema `sales`) | GitHub Actions only | `/Users/<ci identity>/.bundle/…/staging` |
# MAGIC | prod | `bootcamp_prod` (schema `sales`) | GitHub Actions only, after approval | `/Users/<ci identity>/.bundle/…/prod` |

# COMMAND ----------

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
me = w.current_user.me()
print(f"Workspace URL : {w.config.host}")
print(f"You           : {me.user_name}")

# COMMAND ----------

# MAGIC %md ## 1 · Environment catalogs

# COMMAND ----------

results = {}
for cat in ["bootcamp_dev", "bootcamp_staging", "bootcamp_prod"]:
    try:
        spark.sql(f"CREATE CATALOG IF NOT EXISTS `{cat}` COMMENT 'Databricks bootcamp — {cat.split('_')[1]} environment'")
        results[cat] = "ok"
    except Exception as e:  # noqa: BLE001
        results[cat] = f"FAILED: {str(e).splitlines()[0][:160]}"
for k, v in results.items():
    print(f"{k:18} {v}")

if any(v != "ok" for v in results.values()):
    print("""
Could not create catalogs in this workspace.
→ Use the single-catalog fallback: in databricks.yml add  "config/*.yml"  to the include list.
  All environments will then live in the built-in 'workspace' catalog, isolated by schema
  (dev_<you>_sales / staging_sales / prod_sales).""")

# COMMAND ----------

# MAGIC %md ## 2 · Groups for the governance lab (create in the **account console**, not the workspace UI)
# MAGIC
# MAGIC Workspace-local groups (created from Settings → Identity and access → Groups) are **invisible to Unity Catalog**.
# MAGIC Create the groups in the [account console](https://accounts.cloud.databricks.com) instead:
# MAGIC
# MAGIC 1. **User Management → Groups → Add group** → create `bootcamp_analysts` and `bootcamp_engineers`
# MAGIC 2. **Workspaces → your workspace → Permissions** → add both groups to the workspace
# MAGIC 3. Add yourself as a member of `bootcamp_engineers`
# MAGIC
# MAGIC The cell below checks that the groups exist **and** are account-level (`type=Group`).

# COMMAND ----------

# DBTITLE 1,Check groups are account-level
wanted = ["bootcamp_engineers", "bootcamp_analysts"]
me = w.current_user.me()

print("Checking groups for the governance lab:\n")
for name in wanted:
    matches = [g for g in w.groups.list() if g.display_name == name]
    if not matches:
        print(f"  {name:20} MISSING → create it in the account console (accounts.cloud.databricks.com)")
        continue
    for g in matches:
        rt = g.meta.resource_type if g.meta else "unknown"
        if rt == "Group":
            in_eng = any(m.display == me.user_name for m in (g.members or []))
            extra = " (you are a member)" if in_eng else ""
            print(f"  {name:20} ok (account-level, id={g.id}){extra}")
        else:
            print(f"  {name:20} WARNING: workspace-local group (type={rt}) — UC cannot see it!")
            print(f"  {'':20}   Delete it and recreate in the account console as an account-level group.")

# COMMAND ----------

# MAGIC %md ## 3 · SQL warehouse (used by dashboards, Genie and bundle lookups)

# COMMAND ----------

names = [wh.name for wh in w.warehouses.list()]
print("Warehouses:", names)
if "Serverless Starter Warehouse" not in names and names:
    print(f"→ Set variable warehouse_name to '{names[0]}' in databricks.yml")

# COMMAND ----------

# MAGIC %md ## 4 · Values for GitHub (lab 00, part 5)

# COMMAND ----------

print(f"""
GitHub → your repo → Settings → Secrets and variables → Actions

  Variables tab:  DATABRICKS_HOST   = {w.config.host}
  Secrets tab:    DATABRICKS_TOKEN  = <personal access token created in lab 00, part 4>

(Or, if you created a service principal in lab 00, part 4 (option B):
  DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET instead of DATABRICKS_TOKEN.)
""")