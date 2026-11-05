"""End-to-end training and evaluation, shared by the training job (notebooks/rca/03_rca_train.py, which adds
MLflow and the Unity Catalog writes) and local development. `load(name, region)` returns one input frame of
`sources.queries` (topology, health, alarms, maintenance, incidents)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from netmon_pipeline.rca import evaluate, labels, model
from netmon_pipeline.rca.features import RunState, Topology

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
    """`baseline`: eval_rca_baseline rows (incident_id, top_candidates, hit_at_1, hit_at_3) of the run.
    `step2_loc`: eval_incident_detection rows (incident_id, localisation_ttd_s, localised_within_sla).
    `step2_dets`: eval_detection_log rows of the run (for step-2 alert precision on the test days)."""
    inc = labels.prepare_incidents(gt)
    lab = labels.label(feats, inc)
    lab = lab[lab["case_label"] != "censored"]  # censored incidents are excluded everywhere
    data = split.assign(lab, inc)
    train, val, test = (data[data["split"] == s] for s in ("train", "val", "test"))
    log(f"rows train/val/test: {len(train)}/{len(val)}/{len(test)}; positives {int(train['is_root'].sum())}/"
        f"{int(val['is_root'].sum())}/{int(test['is_root'].sum())}")
    raw = model.fit(train, params)
    cal = model.calibrate(raw, val)
    data = data.assign(score=model.score(cal, data))
    thr, curve = model.choose_threshold(data[data["split"] == "val"])
    log(f"threshold (validation F1): {thr}")

    res = Result(cal, raw, thr, data, inc, curve)
    for name in ("val", "test"):
        _evaluate_split(res, name, split, baseline, step2_loc, step2_dets)
    return res


def _in_split(inc: pd.DataFrame, split: model.TimeSplit, name: str) -> pd.DataFrame:
    s = split.split_of(inc["impact_start_ts"])
    return inc[(s == name).to_numpy()]


def _evaluate_split(res: Result, name: str, split: model.TimeSplit, baseline: pd.DataFrame,
                    step2_loc: pd.DataFrame, step2_dets: pd.DataFrame) -> None:
    d = res.data[res.data["split"] == name]
    inc = _in_split(res.incidents, split, name)
    ranks = evaluate.rank_incidents(d, inc)
    heur = evaluate.rank_incidents(d.assign(h_score=evaluate.heuristic_score(d)), inc, score="h_score")
    ranks = ranks.merge(heur[["incident_id", "top_candidates", "hit_at_1", "hit_at_3"]].rename(
        columns={"top_candidates": "heuristic_same_cases_top", "hit_at_1": "heuristic_same_cases_hit_at_1",
                 "hit_at_3": "heuristic_same_cases_hit_at_3"}), on="incident_id", how="left")
    base = baseline[["incident_id", "top_candidates", "hit_at_1", "hit_at_3"]].rename(
        columns={"top_candidates": "baseline_top_candidates", "hit_at_1": "baseline_hit_at_1",
                 "hit_at_3": "baseline_hit_at_3"})
    ranks = ranks.merge(base, on="incident_id", how="left")
    for c in ("baseline_hit_at_1", "baseline_hit_at_3"):
        ranks[c] = ranks[c].fillna(False).astype(bool)
    acc = evaluate.summarise(ranks, ACCURACY_COLS)

    catch = evaluate.early_catch(d, inc, res.threshold).merge(
        step2_loc[["incident_id", "localisation_ttd_s", "localised_within_sla"]].rename(
            columns={"localisation_ttd_s": "step2_localisation_s", "localised_within_sla": "step2_within_5min"}),
        on="incident_id", how="left")
    catch["step2_within_5min"] = catch["step2_within_5min"].fillna(False).astype(bool)
    rows = []
    for ft, g in [("ALL", catch), *catch.groupby("fault_type")]:
        rows.append({"fault_type": ft, "n": len(g),
                     "model_localised_pct": round(100 * g["localisation_s"].notna().mean(), 1),
                     "model_within_5min_pct": round(100 * g["within_5min"].mean(), 1),
                     "model_median_s": evaluate.median_or_none(g["localisation_s"]),
                     "step2_localised_pct": round(100 * g["step2_localisation_s"].notna().mean(), 1),
                     "step2_within_5min_pct": round(100 * g["step2_within_5min"].mean(), 1),
                     "step2_median_s": evaluate.median_or_none(g["step2_localisation_s"])})
    catch_summary = pd.DataFrame(rows)

    lo, hi = (split.val_start, split.test_start) if name == "val" else (split.test_start, None)
    dets = step2_dets[(step2_dets["signal_start_ts"] >= lo) & ((hi is None) | (step2_dets["signal_start_ts"] < hi))] \
        if hi is not None else step2_dets[step2_dets["signal_start_ts"] >= lo]
    p_model = evaluate.alert_precision(evaluate.model_alert_rows(d, res.threshold), res.incidents)
    p_step2 = evaluate.alert_precision(dets, res.incidents)
    prec = pd.DataFrame([{"system": "rca_model (top-1 >= threshold)", **p_model},
                         {"system": "step2 detections", **p_step2}])

    res.tables[f"{name}_ranking"] = ranks
    res.tables[f"{name}_accuracy"] = acc
    res.tables[f"{name}_early_catch"] = catch
    res.tables[f"{name}_early_catch_summary"] = catch_summary
    res.tables[f"{name}_alert_precision"] = prec
    a = acc.set_index("fault_type").loc["ALL"]
    c = catch_summary.set_index("fault_type")
    bh = c.loc["BACKHAUL_DEGRADATION"] if "BACKHAUL_DEGRADATION" in c.index else None
    res.metrics.update({
        f"{name}_n_incidents": int(a["n"]), f"{name}_top1_pct": float(a["model_top1_pct"]),
        f"{name}_top3_pct": float(a["model_top3_pct"]), f"{name}_baseline_top1_pct": float(a["baseline_top1_pct"]),
        f"{name}_baseline_top3_pct": float(a["baseline_top3_pct"]),
        f"{name}_heuristic_same_cases_top1_pct": float(a["heuristic_same_cases_top1_pct"]),
        f"{name}_heuristic_same_cases_top3_pct": float(a["heuristic_same_cases_top3_pct"]),
        f"{name}_alert_precision_pct": p_model["fault_precision_pct"] or 0.0,
        f"{name}_step2_alert_precision_pct": p_step2["fault_precision_pct"] or 0.0,
    })
    if bh is not None:
        res.metrics.update({f"{name}_backhaul_n": int(bh["n"]),
                            f"{name}_backhaul_within_5min_pct": float(bh["model_within_5min_pct"]),
                            f"{name}_backhaul_median_s": float(bh["model_median_s"] or -1),
                            f"{name}_step2_backhaul_within_5min_pct": float(bh["step2_within_5min_pct"])})
