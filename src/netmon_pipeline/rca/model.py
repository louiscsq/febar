"""The root-cause ranker: a gradient-boosted classifier scoring each candidate of a case, calibrated on the
validation days, plus the time-based split and the alert threshold.

Model choice (docs/rca_model.md): scikit-learn `HistGradientBoostingClassifier`, pointwise ("is this candidate
a root?"), ranked per case by score. It handles missing values natively (a cell with no visible window, a
root with no parent), trains in seconds on ~10^5-10^6 rows, needs no extra dependency on serverless jobs or
Model Serving, and gives a probability that can be calibrated, which the early-warning threshold needs.
A LambdaRank objective (LightGBM / XGBoost) optimises the ranking directly but scores are not comparable
across cases, so an alert threshold would need a second model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from netmon_pipeline.rca.features import FEATURE_COLUMNS, LABEL_COLUMNS

PARAMS = {
    "learning_rate": 0.05, "max_iter": 400, "max_leaf_nodes": 31, "min_samples_leaf": 40, "l2_regularization": 1.0,
    # No class weighting: positives are ~4 % of candidates, the ranking only needs an ordering, and isotonic
    # calibration on the validation days fixes the probabilities. (class_weight also makes sklearn's HGB ~20x
    # slower, through its sample-weight path.)
    "early_stopping": False, "random_state": 7,
}


@dataclass(frozen=True)
class TimeSplit:
    """Train on the earlier days, calibrate and choose the alert threshold on the next day ("val"); the last
    days of the training run are a development set ("dev", seen during design, so not a holdout). The held-out
    result comes from a separate, later run (`holdout_1m`)."""

    val_start: pd.Timestamp
    dev_start: pd.Timestamp

    @classmethod
    def by_days(cls, t0: pd.Timestamp, train_days: int, val_days: int) -> TimeSplit:
        t0 = pd.Timestamp(t0).tz_convert("UTC").normalize()
        return cls(t0 + pd.Timedelta(days=train_days), t0 + pd.Timedelta(days=train_days + val_days))

    def split_of(self, ts: pd.Series) -> pd.Series:
        return pd.Series(np.select([ts < self.val_start, ts < self.dev_start], ["train", "val"], "dev"),
                         index=ts.index)

    def assign(self, labelled: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
        """`split` per candidate row by decision time, with an incident embargo: every incident (any class)
        belongs wholly to the split in which it starts (impact start, else root-cause start), and every row
        matched to it outside that split is dropped. So an incident that starts in train and runs on into val
        contributes no val rows, and one that starts in val contributes no dev rows (and vice versa)."""
        out = labelled.copy()
        out["split"] = self.split_of(out["decision_ts"])
        start = incidents["impact_start_ts"].fillna(incidents["start_ts"])
        inc_split = pd.Series(self.split_of(start).to_numpy(),
                              index=pd.MultiIndex.from_arrays([incidents["source_run"], incidents["incident_id"]]))
        col = "matched_incident_ids" if "matched_incident_ids" in out else "incident_ids"
        ex = out[["source_run", col, "split"]].explode(col).dropna(subset=[col])
        keys = pd.MultiIndex.from_arrays([ex["source_run"], ex[col]])
        own = inc_split.reindex(keys)
        other = own.notna().to_numpy() & (own.to_numpy() != ex["split"].to_numpy())
        drop = out.index.isin(ex.index[other])
        return out[~drop]


def check_features(cols: list[str]) -> None:
    leaked = sorted(set(cols) & set(LABEL_COLUMNS))
    if leaked:
        raise ValueError(f"label columns used as features: {leaked}")


def fit(train: pd.DataFrame, params: dict | None = None):
    from sklearn.ensemble import HistGradientBoostingClassifier

    check_features(FEATURE_COLUMNS)
    clf = HistGradientBoostingClassifier(**{**PARAMS, **(params or {})})
    clf.fit(train[FEATURE_COLUMNS], train["is_root"].astype(int))
    return clf


def calibrate(clf, val: pd.DataFrame):
    """Isotonic calibration of the frozen ranker on the validation days (never the test days)."""
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.frozen import FrozenEstimator

    cal = CalibratedClassifierCV(FrozenEstimator(clf), method="isotonic")
    cal.fit(val[FEATURE_COLUMNS], val["is_root"].astype(int))
    return cal


def score(model, df: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(df[FEATURE_COLUMNS])[:, 1]


def choose_threshold(val_scored: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Alert threshold on the case's top-1 calibrated score, chosen on validation only: maximise F1 of
    "the alerted top-1 element is a true root" (precision over alerting cases, recall over fault cases)."""
    i = val_scored.groupby(["source_run", "case_id"])["score"].idxmax()
    top = val_scored.loc[i.to_numpy()]
    n_fault = int((top["case_label"] == "fault").sum())
    rows = []
    for thr in np.round(np.arange(0.01, 0.96, 0.01), 3):
        a = top[top["score"] >= thr]
        tp = int(a["is_root"].sum())
        p = tp / len(a) if len(a) else 0.0
        r = tp / n_fault if n_fault else 0.0
        rows.append({"threshold": thr, "n_alerting_cases": len(a), "precision": p, "recall": r,
                     "f1": 2 * p * r / (p + r) if p + r else 0.0})
    curve = pd.DataFrame(rows)
    return float(curve.loc[curve["f1"].idxmax(), "threshold"]), curve


def permutation_importance(model, df: pd.DataFrame, n_repeats: int = 3, seed: int = 0) -> pd.DataFrame:
    from sklearn.inspection import permutation_importance as pi

    r = pi(model, df[FEATURE_COLUMNS], df["is_root"].astype(int), scoring="average_precision",
           n_repeats=n_repeats, random_state=seed, n_jobs=-1)
    return pd.DataFrame({"feature": FEATURE_COLUMNS, "importance_mean": r.importances_mean,
                         "importance_std": r.importances_std}).sort_values("importance_mean", ascending=False)
