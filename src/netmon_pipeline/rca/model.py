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
    "class_weight": "balanced", "early_stopping": False, "random_state": 7,
}


@dataclass(frozen=True)
class TimeSplit:
    """Train on earlier days, choose the calibration and threshold on the next day(s), test on the last."""

    val_start: pd.Timestamp
    test_start: pd.Timestamp

    @classmethod
    def by_days(cls, t0: pd.Timestamp, train_days: int, val_days: int) -> TimeSplit:
        t0 = pd.Timestamp(t0).tz_convert("UTC").normalize()
        return cls(t0 + pd.Timedelta(days=train_days), t0 + pd.Timedelta(days=train_days + val_days))

    def split_of(self, ts: pd.Series) -> pd.Series:
        return pd.Series(np.select([ts < self.val_start, ts < self.test_start], ["train", "val"], "test"),
                         index=ts.index)

    def assign(self, labelled: pd.DataFrame, incidents: pd.DataFrame) -> pd.DataFrame:
        """`split` per candidate row by decision time, with an embargo: a row matched to an incident that
        starts in a later split is dropped, so no incident is seen in two splits."""
        out = labelled.copy()
        out["split"] = self.split_of(out["decision_ts"])
        start = incidents.set_index(["source_run", "incident_id"])["impact_start_ts"]
        inc_split = self.split_of(start.reset_index(drop=True)).set_axis(start.index)
        order = {"train": 0, "val": 1, "test": 2}
        ex = out[["source_run", "incident_ids", "split"]].explode("incident_ids").dropna(subset=["incident_ids"])
        inc_rank = pd.Series([order[x] for x in inc_split.to_numpy()], index=inc_split.index)
        later = pd.Series(list(zip(ex["source_run"], ex["incident_ids"], strict=True)), index=ex.index).map(inc_rank)
        drop_idx = ex.index[(later > ex["split"].map(order)).to_numpy()]
        drop = out.index.isin(drop_idx)
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
    for thr in np.round(np.arange(0.05, 0.96, 0.025), 3):
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
