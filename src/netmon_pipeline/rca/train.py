"""End-to-end training and evaluation, shared by the training job (notebooks/rca/03_rca_train.py, which adds
MLflow and the Unity Catalog writes) and local development. `load(name, region)` returns one input frame of
`sources.queries` (topology, health, alarms, maintenance, incidents)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from netmon_pipeline.rca import evaluate, labels, model
from netmon_pipeline.rca.features import LABEL_COLUMNS, RunState, Topology

ACCURACY_COLS = {"model_top1_pct": "hit_at_1", "baseline_top1_pct": "baseline_hit_at_1",
                 "heuristic_same_cases_top1_pct": "heuristic_same_cases_hit_at_1",
                 "model_top3_pct": "hit_at_3", "baseline_top3_pct": "baseline_hit_at_3",
                 "heuristic_same_cases_top3_pct": "heuristic_same_cases_hit_at_3"}
Loader = Callable[[str, str | None], pd.DataFrame]


def build_features(load: Loader, regions: list[str], step: int = 1, log=print) -> pd.DataFrame:
    """Candidate features for every decision time of one run, region by region (bounded memory)."""
    parts = []
    for r in regions:
        topo = Topology(load("topology", r))
        st = RunState(topo, load("health", r), load("alarms", r), load("maintenance", r))
        f = st.features(times=st.decision_times(step), regions=[r])
        log(f"features {r}: {len(f)} rows, {f['case_id'].nunique() if len(f) else 0} cases")
        parts.append(f)
    return pd.concat(parts, ignore_index=True)


@dataclass
class Result:
    model: object  # calibrated classifier
    raw_model: object
    threshold: float
    data: pd.DataFrame  # labelled candidate rows with split and score
    incidents: pd.DataFrame
    threshold_curve: pd.DataFrame
    metrics: dict = field(default_factory=dict)
    tables: dict = field(default_factory=dict)


def train_and_evaluate(feats: pd.DataFrame, gt: pd.DataFrame, split: model.TimeSplit, baseline: pd.DataFrame,
                       step2_loc: pd.DataFrame, step2_dets: pd.DataFrame, params: dict | None = None,
                       log=print) -> Result:
    """Train on `train`, calibrate and choose the threshold on `val`, then evaluate GT-free on val and dev.
    `baseline`: eval_rca_baseline rows of the run; `step2_loc`: eval_incident_detection rows; `step2_dets`:
    eval_detection_log rows (for step-2 alert precision over the same period)."""
    inc = labels.prepare_incidents(gt)
    lab = labels.label(feats, inc)
    lab = lab[lab["case_label"] != "censored"]  # censored incidents are never trained or calibrated on
    data = split.assign(lab, inc)
    train, val, dev = (data[data["split"] == s] for s in ("train", "val", "dev"))
    log(f"rows train/val/dev: {len(train)}/{len(val)}/{len(dev)}; positives {int(train['is_root'].sum())}/"
        f"{int(val['is_root'].sum())}/{int(dev['is_root'].sum())}")
    raw = model.fit(train, params)
    cal = model.calibrate(raw, val)
    data = data.assign(score=model.score(cal, data))
    thr, curve = model.choose_threshold(data[data["split"] == "val"])
    log(f"threshold (validation F1): {thr}")
    res = Result(cal, raw, thr, data, inc, curve)
    # Evaluation is GT-free: score EVERY case of the run (no label, censoring or embargo filter), then match.
    scored = feats.assign(score=model.score(cal, feats))
    for name, (lo, hi) in {"val": (split.val_start, split.dev_start), "dev": (split.dev_start, None)}.items():
        tables, metrics = evaluate_run(scored, inc, thr, baseline, step2_loc, step2_dets, lo, hi, name)
        res.tables.update(tables)
        res.metrics.update(metrics)
    return res


def evaluate_run(scored: pd.DataFrame, inc: pd.DataFrame, threshold: float, baseline: pd.DataFrame | None,
                 step2_loc: pd.DataFrame | None, step2_dets: pd.DataFrame | None, lo=None, hi=None,
                 name: str = "holdout") -> tuple[dict, dict]:
    """Evaluate GT-free outputs of `scored` (features + score, no label columns needed) on the scored incidents
    whose impact starts in [lo, hi). Returns ({table name: frame}, {metric: value})."""
    inc_p = inc[inc["is_scored"].astype(bool) & _between(inc["impact_start_ts"], lo, hi)]
    t_lo = (lo - pd.Timedelta(minutes=30)) if lo is not None else None
    s = scored if t_lo is None else scored[scored["decision_ts"] >= t_lo]
    feat_only = s[[c for c in s.columns if c not in LABEL_COLUMNS]]  # GT-free stage: no label column at all
    out_model = evaluate.case_outputs(feat_only, "score")
    out_heur = evaluate.case_outputs(feat_only.assign(h_score=evaluate.heuristic_score(feat_only)), "h_score")

    ranks = evaluate.rank_incidents(out_model, inc_p)
    heur = evaluate.rank_incidents(out_heur, inc_p)
    ranks = ranks.merge(heur[["incident_id", "top_candidates", "hit_at_1", "hit_at_3"]].rename(
        columns={"top_candidates": "heuristic_same_cases_top", "hit_at_1": "heuristic_same_cases_hit_at_1",
                 "hit_at_3": "heuristic_same_cases_hit_at_3"}), on="incident_id", how="left")
    cols = dict(ACCURACY_COLS)
    if baseline is not None and len(baseline):
        ranks = ranks.merge(baseline[["incident_id", "top_candidates", "hit_at_1", "hit_at_3"]].rename(
            columns={"top_candidates": "baseline_top_candidates", "hit_at_1": "baseline_hit_at_1",
                     "hit_at_3": "baseline_hit_at_3"}), on="incident_id", how="left")
        for c in ("baseline_hit_at_1", "baseline_hit_at_3"):
            ranks[c] = ranks[c].fillna(False).astype(bool)
    else:
        cols = {k: v for k, v in cols.items() if "baseline_" not in v}
    acc = evaluate.summarise(ranks, cols)

    catch = evaluate.early_catch(out_model, inc_p, threshold)
    heur_catch = evaluate.early_catch(out_heur.assign(top1_score=1.0), inc_p, 0.0)  # no threshold: rank only
    catch = catch.merge(heur_catch[["incident_id", "localisation_s", "within_5min"]].rename(
        columns={"localisation_s": "heuristic_same_cases_localisation_s",
                 "within_5min": "heuristic_same_cases_within_5min"}), on="incident_id", how="left")
    if step2_loc is not None:
        catch = catch.merge(step2_loc[["incident_id", "localisation_ttd_s", "localised_within_sla"]].rename(
            columns={"localisation_ttd_s": "step2_localisation_s", "localised_within_sla": "step2_within_5min"}),
            on="incident_id", how="left")
    csum = evaluate.catch_summary(catch[[c for c in catch.columns if not c.startswith("step2_")]], step2_loc)
    hs = catch.assign(localised=catch["heuristic_same_cases_localisation_s"].notna(),
                      within_5min=catch["heuristic_same_cases_within_5min"].fillna(False).astype(bool),
                      localisation_s=catch["heuristic_same_cases_localisation_s"], pre_impact=False)
    hsum = evaluate.catch_summary(hs[["fault_type", "localised", "within_5min", "localisation_s", "pre_impact"]])
    csum = csum.merge(hsum[["fault_type", "model_within_5min_pct", "model_median_signed_s"]].rename(
        columns={"model_within_5min_pct": "heuristic_same_cases_within_5min_pct",
                 "model_median_signed_s": "heuristic_same_cases_median_signed_s"}), on="fault_type", how="left")

    prec_rows = [{"system": "rca_model (top-1 >= threshold)",
                  **evaluate.alert_precision(evaluate.model_alert_rows(_period(s, lo, hi), threshold), inc)}]
    if step2_dets is not None:
        d = step2_dets[_between(step2_dets["signal_start_ts"], lo, hi)]
        prec_rows.append({"system": "step2 detections", **evaluate.alert_precision(d, inc)})
    prec = pd.DataFrame(prec_rows)

    any_alert = evaluate.any_alert_at_sla(out_model, inc_p, threshold)  # non-oracle: no footprint matching
    any_sum = evaluate.any_alert_summary(any_alert, ranks)

    tables = {f"{name}_ranking": ranks, f"{name}_accuracy": acc, f"{name}_early_catch": catch,
              f"{name}_early_catch_summary": csum, f"{name}_alert_precision": prec,
              f"{name}_any_alert": any_alert, f"{name}_any_alert_summary": any_sum}
    a = acc.set_index("fault_type").loc["ALL"]
    c = csum.set_index("fault_type")
    m = {f"{name}_n_incidents": int(a["n"]), f"{name}_top1_pct": float(a["model_top1_pct"]),
         f"{name}_top3_pct": float(a["model_top3_pct"]),
         f"{name}_heuristic_same_cases_top1_pct": float(a["heuristic_same_cases_top1_pct"]),
         f"{name}_heuristic_same_cases_top3_pct": float(a["heuristic_same_cases_top3_pct"]),
         f"{name}_within_5min_pct": float(c.loc["ALL", "model_within_5min_pct"]),
         f"{name}_alert_precision_pct": float(prec_rows[0]["fault_precision_pct"] or 0.0),
         f"{name}_any_alert_correct_pct": float(any_sum.set_index("fault_type").loc["ALL", "any_alert_correct_pct"])}
    if "baseline_top1_pct" in a:
        m[f"{name}_baseline_top1_pct"] = float(a["baseline_top1_pct"])
    if "BACKHAUL_DEGRADATION" in c.index:
        bh = c.loc["BACKHAUL_DEGRADATION"]
        m.update({f"{name}_backhaul_n": int(bh["n"]), f"{name}_backhaul_within_5min_pct": float(bh["model_within_5min_pct"]),
                  f"{name}_backhaul_median_signed_s": float(bh["model_median_signed_s"] or -1)})
    return tables, m


def _between(ts: pd.Series, lo, hi) -> pd.Series:
    ok = pd.Series(True, index=ts.index)
    if lo is not None:
        ok &= (ts >= lo).fillna(False)
    if hi is not None:
        ok &= (ts < hi).fillna(False)
    return ok


def _period(s: pd.DataFrame, lo, hi) -> pd.DataFrame:
    return s[_between(s["decision_ts"], lo, hi)]
