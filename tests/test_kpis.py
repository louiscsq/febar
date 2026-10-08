import numpy as np
import pandas as pd
import pytest

from netmon_datagen.config import get_preset, rng_for
from netmon_datagen.faults import Effects
from netmon_datagen.kpis import generate_kpis
from netmon_datagen.topology import build_topology


@pytest.fixture(scope="module")
def week():
    """Seven fault-free days (Mon 2026-09-07 .. Sun) of 15-min KPIs on the small preset."""
    topo = build_topology(get_preset("small"), seed=42)
    ts = np.arange(np.datetime64("2026-09-07T00:00:00"), np.datetime64("2026-09-14T00:00:00"),
                   np.timedelta64(15, "m")).astype("datetime64[s]")
    res = generate_kpis(topo, ts, 15, Effects.zeros(len(ts), topo.n_cells), rng_for(42, "test-kpi"))
    df = res.frame.merge(topo.cells[["element_id", "urbanity", "vendor", "technology"]],
                         left_on="cell_id", right_on="element_id")
    t = pd.to_datetime(df["event_ts"])
    df["hour"] = t.dt.hour
    df["weekend"] = t.dt.dayofweek >= 5
    return df


def test_diurnal_seasonality(week):
    by_hour = week.groupby("hour")["active_users"].mean()
    assert by_hour.loc[18:21].mean() > 3 * by_hour.loc[2:5].mean()
    assert by_hour.idxmin() in range(1, 6)
    assert by_hour.idxmax() in range(16, 22)


def test_weekly_seasonality(week):
    urban_morning = week[(week.urbanity == "urban") & week.hour.isin([8, 9])]
    wd = urban_morning[~urban_morning.weekend]["active_users"].mean()
    we = urban_morning[urban_morning.weekend]["active_users"].mean()
    assert wd > 1.3 * we  # commuter peak disappears at weekends


@pytest.mark.parametrize("tech", ["4G", "5G"])
def test_load_drives_latency_and_quality(week, tech):
    w = week[week.technology == tech]
    c = w[["prb_util_pct", "latency_ms", "packet_loss_pct", "dl_throughput_mbps"]].corr(method="spearman")
    assert c.loc["prb_util_pct", "latency_ms"] > 0.3
    assert c.loc["prb_util_pct", "packet_loss_pct"] > 0.3
    assert c.loc["prb_util_pct", "dl_throughput_mbps"] < -0.3
    busy = w[w.prb_util_pct > 90]
    calm = w[w.prb_util_pct < 50]
    assert len(busy) > 0
    assert busy.session_drop_rate_pct.mean() > calm.session_drop_rate_pct.mean() * 1.5
    assert busy.rrc_setup_success_pct.mean() < calm.rrc_setup_success_pct.mean()


def test_urban_rural_and_technology_differences(week):
    by_urb = week.groupby("urbanity")["session_drop_rate_pct"].mean()
    assert by_urb["rural"] > by_urb["urban"]
    by_tech = week.groupby("technology")
    assert by_tech["dl_throughput_mbps"].mean()["5G"] > 2 * by_tech["dl_throughput_mbps"].mean()["4G"]
    assert by_tech["latency_ms"].mean()["5G"] < by_tech["latency_ms"].mean()["4G"]


def test_values_physically_plausible_without_dq(week):
    for col in ["availability_pct", "prb_util_pct", "rrc_setup_success_pct", "attach_success_pct"]:
        assert week[col].between(0, 100).all(), col
    assert (week["active_users"] >= 0).all()
    assert (week["latency_ms"] > 0).all()
