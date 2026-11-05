"""Capture text evidence of step 3 (RCA model, serving, Lakebase) into evidence/step3/.

SQL runs on the warehouse through the Databricks CLI (as scripts/capture_evidence.py); MLflow, Unity Catalog
model registry, Model Serving and Lakebase metadata come from the Databricks SDK with the CLI profile's OAuth
login. No secret is read or written.

    python scripts/capture_evidence_step3.py --profile febar --warehouse <id>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from capture_evidence import Runner, md_table  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "evidence" / "step3"
CAT = "telco_netmon_febar_catalog"
R = f"{CAT}.netmon_rca"
E = f"{CAT}.netmon_eval"
MODEL = f"{R}.rca_ranker"
ENDPOINT = "banksia-rca-ranker"
INSTANCE = "banksia-netmon-lakebase"


class Doc:
    def __init__(self, r: Runner, name: str, title: str, intro: str = ""):
        self.r, self.path = r, OUT / name
        self.parts = [f"# {title}\n", f"Captured {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from workspace profile "
                      f"`{r.profile}` by `scripts/capture_evidence_step3.py`.\n"]
        if intro:
            self.parts.append(intro.strip() + "\n")

    def query(self, heading: str, sql: str, note: str = "") -> list[list]:
        cols, rows = self.r.sql(sql)
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "", "```sql\n" + sql.strip() + "\n```\n",
                       md_table(cols, rows, max_cell=160)]
        return rows

    def text(self, heading: str, body: str) -> None:
        self.parts += [f"## {heading}\n", body.strip() + "\n"]

    def code(self, heading: str, obj, note: str = "", lang: str = "json") -> None:
        body = obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str)
        self.parts += [f"## {heading}\n", note.strip() + "\n" if note else "", f"```{lang}\n{body}\n```\n"]

    def write(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(p for p in self.parts if p))
        print("wrote", self.path)


def latest_run(r: Runner) -> dict:
    cols, rows = r.sql(f"SELECT * FROM {R}.rca_training_runs")
    return dict(zip(cols, rows[0], strict=True))


# ---------------------------------------------------------------------------------------------------

def training(r: Runner, w, run: dict) -> None:
    import mlflow

    mlflow.set_tracking_uri(f"databricks://{r.profile}")
    m = mlflow.MlflowClient()
    mr = m.get_run(run["mlflow_run_id"])
    exp = m.get_experiment(mr.info.experiment_id)
    d = Doc(r, "01_training_run.md", "Training run (MLflow)")
    d.text("Run", "\n".join([
        f"- MLflow run ID: `{mr.info.run_id}`", f"- experiment: `{exp.name}` (`{exp.experiment_id}`)",
        f"- status: `{mr.info.status}`, started {datetime.fromtimestamp(mr.info.start_time / 1000, timezone.utc):%Y-%m-%d %H:%M} UTC, "
        f"{round((mr.info.end_time - mr.info.start_time) / 60000, 1)} min",
        f"- registered model: `{MODEL}` version `{run['model_version']}` (alias `champion`)",
        f"- training job wall time (features + training + evaluation + registration): {run['minutes']} min"]))
    d.code("Parameters", dict(sorted(mr.data.params.items())))
    d.code("Metrics (val = calibration / threshold day, test = held-out days; live = stream run)",
           dict(sorted(mr.data.metrics.items())))
    arts = [a.path for a in m.list_artifacts(mr.info.run_id)] + \
        [a.path for a in m.list_artifacts(mr.info.run_id, "evaluation")]
    d.code("Artifacts", arts, lang="text")
    d.query("Rows, positives and cases per split", f"""
        SELECT split, count(*) AS candidate_rows, count_if(is_root) AS positive_rows,
               count(DISTINCT case_id) AS cases, min(decision_ts) AS first_decision, max(decision_ts) AS last_decision
        FROM {R}.rca_training_labels GROUP BY split ORDER BY min(decision_ts)""",
            "Censored incidents are excluded before the split; rows matched to an incident that starts in a later "
            "split are dropped (embargo).")
    d.query("Case labels per split", f"""
        SELECT split, case_label, count(DISTINCT case_id) AS cases FROM {R}.rca_training_labels
        GROUP BY ALL ORDER BY 1, 2""")
    d.query("Feature importance (permutation, average precision, validation sample)", f"""
        SELECT feature, round(importance_mean, 5) AS importance_mean, round(importance_std, 5) AS importance_std
        FROM {R}.rca_feature_importance ORDER BY importance_mean DESC LIMIT 25""")
    d.query("Alert threshold curve (validation days only)", f"""
        SELECT * FROM {R}.rca_eval_val_alert_precision""",
            "The threshold itself was chosen by validation F1 on case top-1 (threshold_curve.csv artifact); this is the "
            "validation alert-level precision at that threshold.")
    d.write()


def evaluation(r: Runner, run: dict) -> None:
    d = Doc(r, "02_evaluation.md", "Evaluation vs the step-2 localiser (held-out time split)", f"""
Test split = the last two days of `history_1m` (decision times from 2026-10-14 00:00 UTC), never used for any
choice. Validation (2026-10-13) chose the calibration and the alert threshold ({run['threshold']}). Incidents are
scored faults only (customer-impacting, uncensored). `baseline_*` is step 2's `eval_rca_baseline` exactly as
published (region-wide ranking); `heuristic_same_cases_*` is the same heuristic applied to exactly the cases the
model ranks, so the framing and the model contributions can be told apart. n = incidents.""")
    d.query("Top-1 / top-3 accuracy, overall and by fault type (test)", f"""
        SELECT fault_type, n, model_top1_pct, baseline_top1_pct, heuristic_same_cases_top1_pct,
               model_top3_pct, baseline_top3_pct, heuristic_same_cases_top3_pct
        FROM {R}.rca_eval_test_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC""")
    d.query("Early catch: localised by the model's top-1 above the threshold, vs step-2 localisation (test)", f"""
        SELECT fault_type, n, model_localised_pct, model_within_5min_pct, model_median_s,
               step2_localised_pct, step2_within_5min_pct, step2_median_s
        FROM {R}.rca_eval_test_early_catch_summary ORDER BY fault_type = 'ALL' DESC, n DESC""",
            "Model time = first 1-minute decision time whose top-1 element is a valid root with calibrated score >= "
            "threshold, minus impact start (decision time = when all its inputs had arrived; pipeline latency, median "
            "39 s live in step 2, comes on top). Step 2 = `eval_incident_detection.localisation_ttd_s` (a detection or "
            "the rollup on a root; a lower bound for the rollup path).")
    d.query("Slow backhaul degradation, per incident (test)", f"""
        SELECT incident_id, impact_start_ts, localisation_s AS model_localisation_s, within_5min AS model_within_5min,
               step2_localisation_s, step2_within_5min
        FROM {R}.rca_eval_test_early_catch WHERE fault_type = 'BACKHAUL_DEGRADATION' ORDER BY impact_start_ts""")
    d.query("Secondary: alert-level fault precision (test days), step 2's definitions", f"""
        SELECT system, n_alerts, fault, censored, planned_suppressed, planned_fp, red_herring, unexplained,
               fault_precision_pct, maintenance_suppression_pct
        FROM {R}.rca_eval_test_alert_precision""",
            "Model alerts = case top-1 elements at or above the threshold, grouped per element with step 2's 10-minute "
            "gap and labelled with `netmon_pipeline.scoring` (the same code scores the step-2 detection rows of the "
            "same days). Reported, not optimised.")
    d.query("Validation day (for reference; used for calibration and the threshold)", f"""
        SELECT fault_type, n, model_top1_pct, baseline_top1_pct, heuristic_same_cases_top1_pct, model_top3_pct,
               baseline_top3_pct FROM {R}.rca_eval_val_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC""")
    d.query("Out-of-run check: live stream run (2026-10-08, different run, censored excluded)", f"""
        SELECT fault_type, n, model_top1_pct, baseline_top1_pct, model_top3_pct, baseline_top3_pct
        FROM {R}.rca_eval_live_accuracy ORDER BY fault_type = 'ALL' DESC, n DESC""")
    d.query("Step 2's published RCA baseline per run (eval_rca_baseline)", f"""
        SELECT source_run, count(*) AS n, round(100 * avg(CAST(hit_at_1 AS INT)), 1) AS hit_at_1_pct,
               round(100 * avg(CAST(hit_at_3 AS INT)), 1) AS hit_at_3_pct
        FROM {E}.eval_rca_baseline GROUP BY 1 ORDER BY 1""",
            "The 58 % quoted in step 2 is `history` (15-minute ROP, 19 incidents). The 1-minute training run has ~60x "
            "more concurrent faults, where the region-wide heuristic is much weaker.")
    d.query("Test incidents the model missed at top-1 (sample)", f"""
        SELECT fault_type, incident_id, root_element_ids, top_candidates, baseline_top_candidates, n_cases,
               root_in_candidates
        FROM {R}.rca_eval_test_ranking WHERE NOT hit_at_1 ORDER BY fault_type, incident_id LIMIT 25""")
    d.write()


def registry(r: Runner, w) -> None:
    d = Doc(r, "03_registered_model.md", "Registered model in Unity Catalog")
    m = w.registered_models.get(MODEL, include_aliases=True)
    d.code("Registered model", {"full_name": m.full_name, "owner": m.owner, "description": m.comment,
                                "aliases": [{"alias": a.alias_name, "version": a.version_num} for a in m.aliases or []]})
    vs = [w.model_versions.get(MODEL, v.version) for v in w.model_versions.list(MODEL)]
    d.code("Versions", [{"version": v.version, "status": str(v.status), "run_id": v.run_id,
                         "created": datetime.fromtimestamp(v.created_at / 1000, timezone.utc).isoformat(),
                         "storage_location": v.storage_location} for v in vs])
    import mlflow

    mlflow.set_tracking_uri(f"databricks://{r.profile}")
    mlflow.set_registry_uri(f"databricks-uc://{r.profile}")
    c = mlflow.MlflowClient(tracking_uri=f"databricks://{r.profile}", registry_uri=f"databricks-uc://{r.profile}")
    mv = c.get_model_version_by_alias(MODEL, "champion")
    d.code("champion version tags", mv.tags)
    sig = mlflow.models.get_model_info(f"models:/{MODEL}@champion").signature
    d.code("Signature (inputs -> outputs)", str(sig), lang="text")
    d.write()


def serving(r: Runner, w, run: dict) -> None:
    d = Doc(r, "04_serving_endpoint.md", "Model Serving endpoint")
    ep = w.serving_endpoints.get(ENDPOINT)
    d.code("Endpoint", {"name": ep.name, "state": {"ready": str(ep.state.ready), "config_update": str(
        ep.state.config_update)}, "served_entities": [
        {"name": s.name, "entity_name": s.entity_name, "entity_version": s.entity_version,
         "workload_size": s.workload_size, "scale_to_zero_enabled": s.scale_to_zero_enabled,
         "state": str(s.state.deployment if s.state else None)} for s in ep.config.served_entities]})
    cols, rows = r.sql(f"""
        SELECT f.* FROM {R}.rca_candidate_features f JOIN {R}.rca_training_labels l
          ON l.case_id = f.case_id AND l.element_id = f.element_id
        WHERE l.split = 'test' AND l.case_label = 'fault'
          AND f.case_id = (SELECT case_id FROM {R}.rca_training_labels WHERE split = 'test' AND is_root
                           AND element_id LIKE 'BH-%' ORDER BY decision_ts LIMIT 1)""")
    from netmon_pipeline.rca.features import FEATURE_COLUMNS

    recs = [dict(zip(cols, row, strict=True)) for row in rows]
    body = {"dataframe_records": [{c: (None if x[c] is None else float(x[c])) for c in FEATURE_COLUMNS} for x in recs]}
    t0 = time.perf_counter()
    resp = w.serving_endpoints.query(ENDPOINT, dataframe_records=body["dataframe_records"])
    cold_ms = (time.perf_counter() - t0) * 1000
    lat = []
    for _ in range(20):
        t0 = time.perf_counter()
        w.serving_endpoints.query(ENDPOINT, dataframe_records=body["dataframe_records"][:1])
        lat.append((time.perf_counter() - t0) * 1000)
    preds = resp.predictions
    ranked = sorted(({"element_id": x["element_id"], "element_type": x["element_type"],
                      "p_root": round(float(p[1]), 4)} for x, p in zip(recs, preds, strict=True)),
                    key=lambda z: -z["p_root"])
    d.text("Smoke test", f"Case `{recs[0]['case_id']}` (a held-out backhaul case, {len(recs)} candidates) sent as "
           "`dataframe_records` with the model's 55 feature columns. The endpoint returns `predict_proba` "
           "`[p(not root), p(root)]` per candidate; ranking by `p(root)` gives the suspects.")
    d.code("Request (first 2 of the records)", {"dataframe_records": body["dataframe_records"][:2]})
    d.code("Response (first 3 predictions)", {"predictions": preds[:3]})
    case = recs[0]["case_id"]
    cols2, rows2 = r.sql(f"""SELECT element_id, is_root, round(score, 4) AS batch_score FROM {R}.rca_training_labels
                             WHERE case_id = '{case}'""")
    batch = {x[0]: (x[1], x[2]) for x in rows2}
    for z in ranked:
        z["is_root (ground truth)"], z["batch_score (training job)"] = batch.get(z["element_id"], (None, None))
    d.code("Candidates ranked by endpoint p(root), with the ground truth and the training job's batch score", ranked,
           "The endpoint and the batch scoring in the job give the same calibrated scores (same UC version). This "
           "case holds two concurrent incidents in one cluster (a cell outage under a degrading link), so both "
           "top-2 elements are true roots.")
    d.text("Latency from this laptop (client side, includes internet round trip)",
           f"- first call: {cold_ms:.0f} ms (may include a scale-from-zero start)\n"
           f"- 20 warm single-record calls: p50 {statistics.median(lat):.0f} ms, max {max(lat):.0f} ms")
    d.write()


def lakebase(r: Runner, w) -> None:
    d = Doc(r, "05_lakebase.md", "Lakebase: instance, synced tables, rows, read latency")
    i = w.database.get_database_instance(INSTANCE)
    d.code("Instance (Lakebase Provisioned)", {"name": i.name, "state": str(i.state), "capacity": i.capacity,
                                              "pg_version": i.pg_version, "read_write_dns": i.read_write_dns,
                                              "creator": i.creator, "uid": i.uid})
    for t in ("lb_element_status", "lb_open_incidents"):
        s = w.database.get_synced_database_table(f"{R}.{t}")
        st = s.data_synchronization_status
        d.code(f"Synced table `{R}.{t}`", {
            "source": s.spec.source_table_full_name, "primary_key": s.spec.primary_key_columns,
            "scheduling_policy": str(s.spec.scheduling_policy), "database_instance": s.database_instance_name or getattr(s, "effective_database_instance_name", None),
            "logical_database": s.logical_database_name or getattr(s, "effective_logical_database_name", None), "state": str(st.detailed_state), "message": st.message,
            "pipeline_id": st.pipeline_id,
            "last_sync": str(getattr(st, "triggered_update_status", None) or getattr(st, "last_sync", None))[:600]})
    d.query("Read-latency check (psycopg + OAuth token, from a serverless job; latest run)", f"""
        SELECT run_at, query, n, p50_ms, p95_ms, p99_ms, max_ms, capacity, element_status_rows, open_incidents_rows
        FROM {R}.lakebase_latency_check WHERE run_at = (SELECT max(run_at) FROM {R}.lakebase_latency_check)""")
    cols, rows = r.sql(f"SELECT details FROM {R}.lakebase_latency_check ORDER BY run_at DESC LIMIT 1")
    det = json.loads(rows[0][0])
    d.code("Row counts read from Postgres", {k: v for k, v in det.items() if k.endswith("_rows")})
    d.code("Sample rows read from Postgres: netmon_rca.lb_element_status", det["lb_element_status_sample"])
    d.code("Sample rows read from Postgres: netmon_rca.lb_open_incidents", det["lb_open_incidents_sample"])
    d.code("Primary-key lookup plan (EXPLAIN)", "\n".join(det.get("pk_lookup_plan", [])), lang="text")
    d.write()


def live(r: Runner) -> None:
    d = Doc(r, "06_live_scoring.md", "Live scoring: element_status and open_incidents (Delta sources of Lakebase)")
    d.query("Row counts", f"""
        SELECT 'element_status' AS t, count(*) AS n, max(last_updated_ts) AS data_time, max(refreshed_at) AS refreshed
        FROM {R}.element_status
        UNION ALL SELECT 'open_incidents', count(*), max(last_scored_ts), max(refreshed_at) FROM {R}.open_incidents""")
    d.query("Element states", f"SELECT element_type, state, count(*) AS n FROM {R}.element_status GROUP BY ALL ORDER BY 1, 2")
    d.query("Open incidents with top-3 suspects", f"""
        SELECT incident_id, region_code, detected_ts, last_scored_ts, suspect_1_id, suspect_1_score, suspect_2_id,
               suspect_2_score, suspect_3_id, suspect_3_score, n_impacted_cells
        FROM {R}.open_incidents ORDER BY suspect_1_score DESC LIMIT 15""")
    d.query("Open incidents vs the live run's ground truth (incidents still in flight at the end = censored)", f"""
        SELECT o.incident_id, o.suspect_1_id, g.incident_id AS gt_incident, g.fault_type, g.root_element_ids,
               array_contains(g.root_element_ids, o.suspect_1_id) AS top1_is_root,
               array_contains(g.root_element_ids, o.suspect_1_id) OR array_contains(g.root_element_ids, o.suspect_2_id)
                 OR array_contains(g.root_element_ids, o.suspect_3_id) AS root_in_top3, g.is_censored
        FROM {R}.open_incidents o
        LEFT JOIN {E}.eval_gt_incidents g ON g.source_run = o.source_run AND g.event_class = 'fault'
         AND (array_contains(g.root_element_ids, o.suspect_1_id) OR array_contains(g.affected_element_ids, o.suspect_1_id)
              OR array_contains(g.affected_cell_ids, o.suspect_1_id))
         AND o.last_scored_ts BETWEEN g.start_ts - INTERVAL 5 MINUTES AND coalesce(g.end_ts, g.impact_end_ts) + INTERVAL 10 MINUTES
        ORDER BY o.suspect_1_score DESC LIMIT 20""",
            "Ground truth is joined here for the evidence only; the scoring job never reads it.")
    d.query("Element status sample (non-ok first)", f"""
        SELECT element_id, element_type, region_code, state, n_impacted_cells, impacted_fraction, n_alarms,
               round(rca_score, 3) AS rca_score, open_incident_id, suspect_rank, last_updated_ts
        FROM {R}.element_status ORDER BY state = 'ok', rca_score DESC NULLS LAST LIMIT 15""")
    d.query("Scored candidates appended per scoring run", f"""
        SELECT model_version, count(*) AS rows, count(DISTINCT case_id) AS cases, min(decision_ts), max(decision_ts)
        FROM {R}.rca_live_scores GROUP BY 1""")
    d.write()


def pipeline_notes(r: Runner) -> None:
    d = Doc(r, "07_pr3_review_notes.md", "PR #3 review notes folded in")
    d.text("a. Python late-data rule tied to the Spark transform", """
`tests/test_pipeline_windows_spark.py` runs, on a local SparkSession, the functions the pipeline itself calls:
`windows.is_late_sql` (silver `is_late`, kpis / alarms / sessions), `windows.realtime_records` and
`windows.window_health` (gold `gold_cell_health_1m` / `_5m`). It checks per record that `rules.is_late_py`
equals the Spark `is_late`, and per window that `windows.realtime_window` (the Python mirror) gives the same
report count, qualification and observable time as the Spark window, including the threshold edge
(exactly 20 min late is on time, 20 min + 1 s is late). A second test asserts gold.py / silver.py call these
shared functions and contain no private copy of the rule.""")
    d.query("b. Real (signed) evidence lag: alarms that arrive before the impact starts", f"""
        SELECT source_run, fault_type, n_incidents, median_evidence_lag_s, median_signed_evidence_lag_s,
               min_signed_evidence_lag_s, n_evidence_before_impact
        FROM {E}.eval_ttd_summary WHERE event_class = 'fault' AND fault_type <> 'ALL' ORDER BY 1, 2""",
            "`eval_incident_detection` now carries `signed_evidence_lag_s` (negative when the first matching evidence "
            "predates `impact_start_ts`) and `evidence_before_impact`; the clipped `evidence_lag_s` is unchanged. "
            "Router failures raise NODE_DOWN before their cells lose service, hence the negative lags.")
    d.query("b. Incidents whose first evidence predates impact (sample)", f"""
        SELECT source_run, incident_id, fault_type, first_signal_source, first_flags, signed_evidence_lag_s,
               evidence_lag_s, impact_ttd_s
        FROM {E}.eval_incident_detection WHERE evidence_before_impact ORDER BY signed_evidence_lag_s LIMIT 10""")
    d.text("c. One baseline-comparison code path", """
`windows.score_against_baseline(kpis, baseline)` (join the record's baseline row, add z-scores and the fired
rules) is used by both the real-time stream (`kpis_scored` -> `gold_cell_health_1m` / `_5m`) and the
after-the-fact `gold_cell_health_5m_retrospective`, which also share `windows.window_health`. The test above
asserts both call sites.""")
    d.write()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="febar")
    ap.add_argument("--warehouse", required=True)
    ap.add_argument("--only")
    a = ap.parse_args()
    from databricks.sdk import WorkspaceClient

    r = Runner(a.profile, a.warehouse)
    w = WorkspaceClient(profile=a.profile)
    run = latest_run(r)
    steps = {"training": lambda: training(r, w, run), "evaluation": lambda: evaluation(r, run),
             "registry": lambda: registry(r, w), "serving": lambda: serving(r, w, run),
             "lakebase": lambda: lakebase(r, w), "live": lambda: live(r), "notes": lambda: pipeline_notes(r)}
    for k, f in steps.items():
        if a.only and k not in a.only.split(","):
            continue
        f()


if __name__ == "__main__":
    main()
