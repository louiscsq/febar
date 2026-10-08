"""Topology rollup, incident scoring and path helpers (netmon_pipeline.hierarchy / scoring / paths)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from netmon_datagen.config import get_preset
from netmon_datagen.topology import build_topology
from netmon_pipeline import hierarchy, paths, schemas, scoring
from netmon_pipeline.settings import Settings


@pytest.fixture(scope="module")
def cells():
    nodes = build_topology(get_preset("tiny"), 42).public_nodes()
    return nodes[nodes.element_type == "CELL"].to_dict("records"), nodes


def test_ancestor_columns_cover_every_level(cells):
    cs, nodes = cells
    chain = hierarchy.ancestors(cs[0])
    assert [t for _e, t, _l in chain] == ["CELL", "SITE", "BACKHAUL_LINK", "AGG_ROUTER", "UPF_SGW", "AMF_MME"]
    types = nodes.set_index("element_id")["element_type"]
    assert all(types[e] == t for e, t, _l in chain)
    assert hierarchy.stack_sql().startswith("stack(6, cell_id, 'CELL', 5, site_id, 'SITE', 4")


def test_rollup_counts_descendants_and_impacted_children(cells):
    cs, nodes = cells
    site = cs[0]["site_id"]
    site_cells = [c["element_id"] for c in cs if c["site_id"] == site]
    out = hierarchy.rollup(cs, set(site_cells))
    assert out[site]["n_desc_cells"] == len(site_cells) and out[site]["impacted_fraction"] == 1.0
    assert out[site]["n_impacted_children"] == out[site]["n_children"] == len(site_cells)
    bh = cs[0]["backhaul_id"]
    assert out[bh]["n_impacted_children"] == 1
    assert out[bh]["n_desc_cells"] == sum(c["backhaul_id"] == bh for c in cs)
    amf = cs[0]["amf_id"]
    assert out[amf]["n_desc_cells"] == sum(c["amf_id"] == amf for c in cs)
    assert 0 < out[amf]["impacted_fraction"] < 1
    # Router failure: every cell under the router impacted -> router fraction 1, UPF fraction < 1.
    r = cs[0]["router_id"]
    under = {c["element_id"] for c in cs if c["router_id"] == r}
    o2 = hierarchy.rollup(cs, under)
    assert o2[r]["impacted_fraction"] == 1.0
    assert hierarchy.lowest_common_ancestor([c for c in cs if c["element_id"] in under]) == (r, "AGG_ROUTER") or \
        len({c["backhaul_id"] for c in cs if c["router_id"] == r}) == 1


def test_lowest_common_ancestor(cells):
    cs, _ = cells
    assert hierarchy.lowest_common_ancestor([cs[0]]) == (cs[0]["element_id"], "CELL")
    assert hierarchy.lowest_common_ancestor([]) is None
    other = next(c for c in cs if c["amf_id"] != cs[0]["amf_id"])
    assert hierarchy.lowest_common_ancestor([cs[0], other]) is None  # different regions: no common root


INC = {"incident_id": "INC-1", "root_element_id": "SITE-A", "root_element_ids": ["SITE-A", "SITE-B"],
       "affected_element_ids": ["CELL-A1"], "affected_cell_ids": ["CELL-A1", "CELL-B1"],
       "impact_start_s": 1000, "impact_end_s": 4000, "is_customer_impacting": True, "is_censored": False}


def det(eid, start, avail, end=None):
    return {"element_id": eid, "signal_start_s": start, "signal_end_s": end or start + 60, "available_s": avail}


def test_matching_and_time_to_detect():
    assert scoring.incident_elements(INC) == {"SITE-A", "SITE-B", "CELL-A1", "CELL-B1"}
    dets = [det("CELL-X", 1100, 1150), det("CELL-B1", 1200, 1290), det("SITE-A", 1300, 1400),
            det("CELL-A1", 9000, 9100)]  # last one is long after the impact
    assert scoring.matches(dets[1], INC) and not scoring.matches(dets[0], INC) and not scoring.matches(dets[3], INC)
    assert scoring.time_to_detect(INC, dets) == 290
    assert scoring.time_to_detect(INC, [dets[0]]) is None
    # A pre-impact alarm whose signal overlaps the impact counts, with TTD clipped at 0.
    assert scoring.time_to_detect(INC, [det("SITE-A", 950, 980, end=1010)]) == 0.0
    assert scoring.is_scored(INC) and not scoring.is_scored({**INC, "is_censored": True})


def test_impact_detection_vs_root_localisation():
    # A symptom cell is detected quickly, but the root (SITE-A / SITE-B cluster) only later.
    dets = [det("CELL-A1", 1100, 1150), det("SITE-B", 1400, 1700)]
    assert scoring.time_to_detect(INC, dets) == 150  # (a) impact: any footprint element
    assert scoring.localisation_time(INC, dets) == 700  # (b) localisation: a root element (any cluster root)
    assert scoring.localisation_time(INC, [dets[0]]) is None  # symptom only: not localised
    roll = [{"element_id": "SITE-A", "available_s": 1500}, {"element_id": "CELL-A1", "available_s": 1100}]
    assert scoring.localisation_time(INC, [dets[0]], roll) == 500
    single = {**INC, "root_element_ids": []}  # falls back to root_element_id
    assert scoring.roots(single) == {"SITE-A"}


def test_detection_labels_and_fault_precision():
    fault = {"event_class": "fault", "is_censored": False}
    cens = {"event_class": "fault", "is_censored": True}
    planned = {"event_class": "planned", "is_censored": False}
    surge = {"event_class": "red_herring", "is_censored": False}
    assert scoring.label_detection([surge, fault]) == "fault"
    assert scoring.label_detection([cens, planned]) == "censored"
    assert scoring.label_detection([surge]) == "red_herring"  # e.g. TRAFFIC_SURGE: a false positive
    assert scoring.label_detection([]) == "unexplained"
    p = scoring.fault_precision([("fault", False)] * 6 + [("red_herring", False)] + [("unexplained", False)]
                                + [("planned", True)] * 3 + [("planned", False)] + [("censored", False)] * 5)
    assert p["fault"] == 6 and p["censored"] == 5
    assert p["fault_precision_pct"] == 66.7  # 6 / (6 + 1 surge + 1 unexplained + 1 unsuppressed planned)
    assert p["maintenance_suppression_pct"] == 75.0


def test_summary_and_percentiles():
    s = scoring.summarise([60, 120, 240, 600, None])
    assert s["n_incidents"] == 5 and s["n_detected"] == 4 and s["detected_pct"] == 80.0
    assert s["median_ttd_s"] == 180 and s["within_sla_pct"] == 60.0
    assert scoring.percentile([1, 2, 3, 4], 0.9) == pytest.approx(3.7)
    assert scoring.summarise([])["within_sla_pct"] is None


def test_rca_hit_scores_cluster_roots():
    assert scoring.rca_hit(["SITE-B", "BH-1"], INC["root_element_ids"])  # any cluster site counts
    assert not scoring.rca_hit(["BH-1", "SITE-B"], INC["root_element_ids"], k=1)
    assert scoring.rca_hit(["BH-1", "SITE-B"], INC["root_element_ids"], k=3)


def test_paths_landing_time_and_run():
    p = "/Volumes/c/netmon_raw/landing/stream/kpis/date=2026-10-08/batch-20261008T104400-000012.json"
    assert paths.run_name(p) == "stream"
    assert paths.landed_at(p, 60) == datetime(2026, 10, 8, 10, 45, tzinfo=timezone.utc)
    assert paths.landed_at(p.replace("000012", "final"), 60) is not None
    assert paths.landed_at("/Volumes/c/s/landing/history/kpis/date=2026-09-01/part-00000-0.json", 60) is None
    assert "INTERVAL 60 SECONDS" in paths.landed_at_sql("_source_file", 60)


def test_stream_file_names_match_the_generator(tmp_path):
    from netmon_datagen.config import DQConfig, GeneratorConfig
    from netmon_datagen.stream import run_stream

    cfg = GeneratorConfig.for_scale("tiny", dq=DQConfig.none())
    run_stream(cfg, tmp_path / "landing" / "stream", interval_seconds=0, max_batches=2,
               start="2026-10-08T10:44:00Z", log=lambda *a: None)
    files = sorted(str(p) for p in (tmp_path / "landing" / "stream" / "kpis").rglob("*.json"))
    # 1-minute KPIs are delivered 6-30 s after their period ends, so the first KPI file is batch 1
    # (simulated 10:45-10:46), which lands at 10:46.
    assert files[0].endswith("batch-20261008T104500-000001.json")
    assert paths.landed_at(files[0], 60) == datetime(2026, 10, 8, 10, 46, tzinfo=timezone.utc)
    assert {paths.run_name(f) for f in files} == {"stream"}


def test_schemas_cover_generator_columns():
    from netmon_datagen.alarms import ALARM_COLUMNS
    from netmon_datagen.engine import KPI_COLUMNS_OUT
    from netmon_datagen.sessions import SESSION_COLUMNS

    assert schemas.columns(schemas.KPIS) == KPI_COLUMNS_OUT
    assert schemas.columns(schemas.ALARMS) == ALARM_COLUMNS
    assert schemas.columns(schemas.SESSIONS) == SESSION_COLUMNS
    assert "root_element_ids" in schemas.columns(schemas.INCIDENTS)
    assert schemas.with_corrupt_column(schemas.KPIS).endswith("_corrupt_record STRING")


def test_settings_from_conf():
    conf = {"netmon.catalog": "cat", "netmon.landing_root": "/Volumes/cat/raw/landing/",
            "netmon.bronze_schema": "b", "netmon.silver_schema": "s", "netmon.gold_schema": "g",
            "netmon.eval_schema": "e", "netmon.gov_schema": "gov", "netmon.stream_step_seconds": "60"}
    s = Settings.from_conf(conf.__getitem__)
    assert s.gold == "`cat`.`g`" and s.feed_path("kpis") == "/Volumes/cat/raw/landing/*/kpis/"


def test_no_cross_run_credit_for_localisation_or_detection():
    # Two runs overlap on the same root element and time: only same-run evidence counts.
    inc = {**INC, "source_run": "history"}
    live_det = {**det("SITE-A", 1100, 1200), "source_run": "stream"}
    live_roll = {"element_id": "SITE-A", "available_s": 1150, "source_run": "stream"}
    assert scoring.time_to_detect(inc, [live_det]) is None
    assert scoring.localisation_time(inc, [live_det], [live_roll]) is None
    hist_roll = {"element_id": "SITE-B", "available_s": 1900, "source_run": "history"}
    assert scoring.localisation_time(inc, [live_det], [live_roll, hist_roll]) == 900


def test_first_localisation_reports_element_of_earliest_row():
    roll = [{"element_id": "SITE-B", "available_s": 1600}, {"element_id": "SITE-A", "available_s": 1300}]
    assert scoring.first_localisation(INC, [], roll) == (1300, "SITE-A")


def test_alerts_group_detections_per_element_episode():
    rows = [{"source_run": "s", "element_id": "C1", "signal_start_s": t, "label": "fault"} for t in (0, 60, 120)]
    rows += [{"source_run": "s", "element_id": "C1", "signal_start_s": 5000, "label": "unexplained"}]
    rows += [{"source_run": "h", "element_id": "C1", "signal_start_s": 60, "label": "red_herring",
              "in_maintenance": False}]
    al = scoring.alerts(rows)
    assert sorted(len(a) for a in al) == [1, 1, 3]  # one 3-row episode, a separate later one, other run apart
    labels = sorted(scoring.alert_label(a)[0] for a in al)
    assert labels == ["fault", "red_herring", "unexplained"]
    p = scoring.fault_precision([scoring.alert_label(a) for a in al])
    assert p["fault_precision_pct"] == 33.3  # 1 TP alert vs 2 FP alerts, though 3 of 5 rows are TP
    planned = [{"source_run": "s", "element_id": "S1", "signal_start_s": 0, "label": "planned", "in_maintenance": True},
               {"source_run": "s", "element_id": "S1", "signal_start_s": 60, "label": "planned",
                "in_maintenance": False}]
    assert scoring.alert_label(planned) == ("planned", True)
    # Back-to-back 15-minute periods (end = next start) stay one alert although starts are 15 min apart.
    hist = [{"element_id": "C9", "signal_start_s": t, "signal_end_s": t + 900, "label": "fault"} for t in (0, 900, 1800)]
    assert len(scoring.alerts(hist)) == 1
