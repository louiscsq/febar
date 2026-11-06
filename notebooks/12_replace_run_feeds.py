# Databricks notebook source
# MAGIC %md
# MAGIC # Replace a run's alarm feed after the run-unique ID fix (one-off correction, PR #6)
# MAGIC
# MAGIC Before the fix, incident alarm IDs repeated between batch runs and silver's cross-run dedupe on `record_id`
# MAGIC dropped a later run's fault alarms (`evidence/step4/09_holdout_alarm_gap.md`). The runs are regenerated with
# MAGIC the fixed generator (same seeds, same window, `run_id` = the run name) into a **staging** volume
# MAGIC (`banksia-rca-generate-*` with `volume=staging`). This notebook then, per run:
# MAGIC
# MAGIC 1. **verifies** that the regeneration differs from what was ingested only in IDs: KPIs, sessions, topology and
# MAGIC    incident ground truth byte-identical; alarms, the DQ log and the change calendar identical once
# MAGIC    `record_id` / `alarm_id` / `change_id` are removed (`stage=verify` stops here);
# MAGIC 2. **swaps** the three changed feeds in the landing volume: the new files land under new names (`-<revision>`
# MAGIC    suffix, so Auto Loader ingests them) and the superseded files are removed;
# MAGIC 3. **deletes the superseded rows** (from the old files) in bronze, silver, quarantine and the alarm detections.
# MAGIC    The pipeline reads those tables with `skipChangeCommits`, so the deletes do not break its streams.
# MAGIC
# MAGIC The job's next task runs a normal (incremental) pipeline update, which ingests the new files. KPIs, sessions and
# MAGIC every other run are untouched; no full refresh, so the step-2 live run keeps its measured wall-clock latency and
# MAGIC the append-only health windows keep their state. Idempotent: re-running after a completed swap verifies and
# MAGIC deletes nothing new.

# COMMAND ----------

dbutils.widgets.text("catalog", "telco_netmon_febar_catalog")
dbutils.widgets.text("raw_schema", "netmon_raw")
dbutils.widgets.text("landing_volume", "landing")
dbutils.widgets.text("staging_volume", "staging")
dbutils.widgets.text("bronze_schema", "netmon_bronze")
dbutils.widgets.text("silver_schema", "netmon_silver")
dbutils.widgets.text("gold_schema", "netmon_gold")
dbutils.widgets.text("eval_schema", "netmon_eval")
dbutils.widgets.text("runs", "history_1m,holdout_1m")
dbutils.widgets.text("revision", "r2")
dbutils.widgets.dropdown("stage", "verify", ["verify", "swap"])

# COMMAND ----------

import hashlib
import json
import os
import re
import shutil
from pathlib import Path

w = {k: dbutils.widgets.get(k) for k in ["catalog", "raw_schema", "landing_volume", "staging_volume", "bronze_schema",
                                          "silver_schema", "gold_schema", "eval_schema", "runs", "revision", "stage"]}
CAT, REV = w["catalog"], w["revision"]
assert re.fullmatch(r"[a-z0-9]+", REV), REV
RUNS = [r.strip() for r in w["runs"].split(",") if r.strip()]
LANDING = Path(f"/Volumes/{CAT}/{w['raw_schema']}/{w['landing_volume']}")
STAGING = Path(f"/Volumes/{CAT}/{w['raw_schema']}/{w['staging_volume']}")
B, S, G, E = (f"`{CAT}`.`{w[k]}`" for k in ("bronze_schema", "silver_schema", "gold_schema", "eval_schema"))

UNCHANGED = ["kpis", "sessions", "topology_nodes", "topology_edges", "ground_truth/incidents"]
CHANGED = {"alarms": f"{B}.bronze_alarms", "ground_truth/dq_injections": f"{E}.bronze_gt_dq_injections",
           "maintenance_windows": f"{B}.bronze_maintenance_windows"}
ID_FIELDS = re.compile(r'"(record_id|alarm_id|change_id)":"[^"]*"')
TRUNCATED_ID = re.compile(r'"record_id":"[^"]*$')  # a truncated JSON line can end inside its record_id
NEW_FILE_SQL = f"_source_file RLIKE '-{REV}[.]json$'"


def files(root: Path, feed: str) -> dict[str, Path]:
    base = root / feed
    return {str(p.relative_to(base)): p for p in sorted(base.rglob("*.json"))} if base.exists() else {}


def renamed(rel: str) -> str:
    stem, ext = os.path.splitext(rel)
    return f"{stem}-{REV}{ext}"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 23), b""):
            h.update(chunk)
    return h.hexdigest()


def without_ids(p: Path) -> list[str]:
    return [TRUNCATED_ID.sub("", ID_FIELDS.sub("", line)) for line in p.read_text().splitlines()]


def sql(stmt: str) -> int:
    rows = spark.sql(stmt).collect()
    n = int(rows[0]["num_affected_rows"]) if rows and "num_affected_rows" in rows[0].asDict() else 0
    print(f"{n:>8}  {' '.join(stmt.split())[:160]}")
    return n

# COMMAND ----------

# MAGIC %md ## 1. Verify: the regeneration differs from the ingested run only in IDs

# COMMAND ----------

report = {}
for run in RUNS:
    land, stage = LANDING / run, STAGING / run
    manifest = json.loads((stage / "_manifest.json").read_text())
    assert manifest["run_key"] == run, f"{run}: staging was generated with run_key {manifest['run_key']!r}"
    rep = {"run_key": manifest["run_key"], "unchanged_files": 0, "changed_files": 0, "already_swapped": 0}
    for feed in UNCHANGED:
        old, new = files(land, feed), files(stage, feed)
        assert set(old) == set(new) and new, f"{run}/{feed}: file sets differ"
        for rel in new:
            assert old[rel].stat().st_size == new[rel].stat().st_size and sha256(old[rel]) == sha256(new[rel]), \
                f"{run}/{feed}/{rel} differs"
        rep["unchanged_files"] += len(new)
    for feed in CHANGED:
        old, new = files(land, feed), files(stage, feed)
        for rel, p in new.items():
            target = land / feed / renamed(rel)
            if rel in old:
                a, b = without_ids(old[rel]), without_ids(p)
                assert a == b, f"{run}/{feed}/{rel}: differs beyond record_id / alarm_id / change_id"
                rep["changed_files"] += 1
            else:
                assert target.exists() and sha256(target) == sha256(p), f"{run}/{feed}/{rel}: missing in landing"
                rep["already_swapped"] += 1
        extra = {r for r in old if not r.endswith(f"-{REV}.json")} - set(new)
        assert not extra, f"{run}/{feed}: landing files with no regenerated counterpart: {sorted(extra)[:5]}"
    report[run] = rep
print(json.dumps(report, indent=1))
if w["stage"] == "verify":
    dbutils.notebook.exit(json.dumps({"stage": "verify", "report": report}))

# COMMAND ----------

# MAGIC %md ## 2. Swap the changed feeds in the landing volume (new names, superseded files removed)

# COMMAND ----------

for run in RUNS:
    land, stage = LANDING / run, STAGING / run
    for feed in CHANGED:
        for rel, p in files(stage, feed).items():
            target = land / feed / renamed(rel)
            if not (target.exists() and sha256(target) == sha256(p)):
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(f".{target.name}.tmp")  # not *.json: Auto Loader never sees a partial file
                shutil.copyfile(p, tmp)
                os.replace(tmp, target)
            old = land / feed / rel
            if old.exists():
                old.unlink()
    shutil.copyfile(stage / "_manifest.json", land / "_manifest.json")
    print(run, "swapped")

# COMMAND ----------

# MAGIC %md ## 3. Delete the superseded rows (rows ingested from the replaced files)

# COMMAND ----------

deleted = {}
for run in RUNS:
    r = f"'{run}'"
    d = {}
    for table in CHANGED.values():
        d[table] = sql(f"DELETE FROM {table} WHERE _source_run = {r} AND NOT {NEW_FILE_SQL}")
    d["silver_alarms"] = sql(f"DELETE FROM {S}.silver_alarms WHERE source_run = {r} AND NOT {NEW_FILE_SQL}")
    d["silver_quarantine"] = sql(f"DELETE FROM {S}.silver_quarantine WHERE _source_run = {r} AND feed = 'alarms' "
                                 f"AND NOT {NEW_FILE_SQL}")
    # Alarm detections carry no file name: keep exactly those whose record is (still) in silver.
    for table in (f"{G}.gold_impact_detections", f"{E}.eval_detection_log"):
        d[table] = sql(f"""DELETE FROM {table} AS t WHERE t.source_run = {r} AND t.signal_source = 'alarm'
                           AND NOT EXISTS (SELECT 1 FROM {S}.silver_alarms s
                                           WHERE s.source_run = {r} AND s.record_id = t.record_id)""")
    deleted[run] = d
print(json.dumps(deleted, indent=1))
dbutils.notebook.exit(json.dumps({"stage": "swap", "report": report, "deleted": deleted}))
