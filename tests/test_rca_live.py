"""Live outputs: open incidents with top-3 suspects, element status, and their Spark schemas."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from test_rca_features import FAULT_FROM, N_MIN, alarms_df, health_df, topo_df

from netmon_pipeline.rca import live
from netmon_pipeline.rca.features import RunState, Topology


@pytest.fixture(scope="module")
def scored():
    st = RunState(Topology(topo_df()), health_df(), alarms_df())
    f = st.features(times=range(FAULT_FROM, N_MIN + 2))
    return f.assign(score=np.where(f["element_id"] == "BH-1", 0.9, 0.05))


def test_open_incident_has_top3_suspects_and_detection_time(scored):
    inc = live.open_incidents(scored, threshold=0.5, model_version="3")
    assert len(inc) == 1
    r = inc.iloc[0]
    assert r["suspect_1_id"] == "BH-1" and r["suspect_1_score"] == 0.9 and r["suspect_3_id"] is not None
    assert r["detected_ts"] == scored.loc[scored["element_id"] == "BH-1", "decision_ts"].min()
    assert r["last_scored_ts"] == scored["decision_ts"].max() and r["status"] == "open"


def test_no_open_incident_below_threshold(scored):
    assert live.open_incidents(scored, threshold=0.95, model_version="3").empty


def test_element_status_covers_every_element(scored):
    inc = live.open_incidents(scored, 0.5, "3")
    st = live.element_status(topo_df(), scored, inc).set_index("element_id")
    assert len(st) == len(topo_df())
    assert st.loc["BH-1", "state"] == "degraded" and st.loc["BH-1", "suspect_rank"] == 1
    assert st.loc["SITE-3", "state"] == "ok" and st.loc["BH-1", "open_incident_id"] == inc.iloc[0]["incident_id"]


def test_conform_matches_the_spark_schemas(scored, spark):
    inc = live.open_incidents(scored, 0.5, "3").assign(refreshed_at=pd.Timestamp.now(tz="UTC"))
    st = live.element_status(topo_df(), scored, inc).assign(refreshed_at=pd.Timestamp.now(tz="UTC"),
                                                             model_version="3")
    for df, ddl in ((inc, live.OPEN_INCIDENTS_DDL), (st, live.ELEMENT_STATUS_DDL),
                    (inc.iloc[0:0], live.OPEN_INCIDENTS_DDL)):
        c = live.conform(df, ddl)
        assert list(c.columns) == [p.strip().split(" ")[0] for p in ddl.split(",")]
        assert spark.createDataFrame(c, schema=ddl).count() == len(df)
