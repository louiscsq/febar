import numpy as np
import pandas as pd
import pytest

from netmon_datagen.config import get_preset, rng_for
from netmon_datagen.faults import Effects
from netmon_datagen.kpis import generate_kpis, local_clock, seasonal_profile
from netmon_datagen.topology import build_topology


def _local(df: pd.DataFrame) -> pd.DataFrame:
    """Add local hour / weekend columns from each row's cell time zone (timestamps are UTC)."""
    t = pd.to_datetime(df["event_ts"])
    df["utc_hour"] = t.dt.hour + t.dt.minute / 60
    df["hour"], df["weekend"] = 0, False
    for z, g in df.groupby("timezone"):
        loc = t[g.index].dt.tz_convert(z)
        df.loc[g.index, "hour"] = loc.dt.hour
        df.loc[g.index, "weekend"] = loc.dt.dayofweek >= 5
    return df


@pytest.fixture(scope="module")
def week():
    """Seven fault-free days (Mon 2026-09-07 .. Sun) of 15-min KPIs on the small preset (UTC+8 .. +10)."""
    topo = build_topology(get_preset("small"), seed=42)
    ts = np.arange(np.datetime64("2026-09-07T00:00:00"), np.datetime64("2026-09-14T00:00:00"),
                   np.timedelta64(15, "m")).astype("datetime64[s]")
    res = generate_kpis(topo, ts, 15, Effects.zeros(len(ts), topo.n_cells), rng_for(42, "test-kpi"))
    df = res.frame.merge(topo.cells[["element_id", "urbanity", "vendor", "technology", "region_code", "timezone",
                                     "base_latency_ms"]], left_on="cell_id", right_on="element_id")
    return _local(df)


def test_diurnal_seasonality(week):
    by_hour = week.groupby("hour")["active_users"].mean()  # local hour
    assert by_hour.loc[18:21].mean() > 3 * by_hour.loc[2:5].mean()
    assert by_hour.idxmin() in range(1, 6)
    assert by_hour.idxmax() in range(16, 22)


def test_busy_hour_follows_local_time(week):
    """Perth (UTC+8) peaks at the same local hour as Sydney (UTC+10 in September), i.e. 2 h later in UTC."""
    peaks = {}
    for rc in ("NSW", "WA"):
        w = week[(week.region_code == rc) & ~week.weekend & week.urbanity.isin(["urban", "suburban"])]
        by_utc = w.groupby("utc_hour")["active_users"].mean().rolling(4, center=True, min_periods=1).mean()
        by_local = w.groupby("hour")["active_users"].mean()
        peaks[rc] = (by_utc.idxmax(), by_local.idxmax())
    utc_lag = (peaks["WA"][0] - peaks["NSW"][0]) % 24
    assert 1.5 <= utc_lag <= 3.0, peaks
    assert abs(peaks["WA"][1] - peaks["NSW"][1]) <= 1, peaks


def test_weekly_seasonality(week):
    urban_morning = week[(week.urbanity == "urban") & week.hour.isin([8, 9])]
    wd = urban_morning[~urban_morning.weekend]["active_users"].mean()
    we = urban_morning[urban_morning.weekend]["active_users"].mean()
    assert wd > 1.3 * we  # commuter peak disappears at weekends


@pytest.mark.parametrize("tech", ["4G", "5G"])
def test_load_drives_latency_and_quality(week, tech):
    w = week[week.technology == tech].copy()
    # Latency relative to the cell's own baseline: transport distance (e.g. 1,400 km of long-haul from
    # North Queensland) adds a per-cell offset that has nothing to do with load.
    w["latency_ms"] = w["latency_ms"] / w["base_latency_ms"]
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


def test_local_clock_handles_dst_and_half_hour_zones():
    ts = np.array(["2026-07-01T00:00:00", "2026-10-04T00:00:00", "2026-04-05T00:00:00"], dtype="datetime64[s]")
    zones = ["Australia/Sydney", "Australia/Brisbane", "Australia/Adelaide", "Australia/Darwin", "Australia/Perth",
             "Australia/Hobart", "Australia/Melbourne"]
    hours, _ = local_clock(ts, zones)
    got = dict(zip(zones, hours.tolist(), strict=True))
    # July: standard time everywhere. 4 Oct 2026: DST started that morning in the south-east and SA.
    # 5 Apr 2026: DST ended that morning (03:00 -> 02:00), so 00:00 UTC is standard time again.
    assert got["Australia/Sydney"] == [10.0, 11.0, 10.0]
    assert got["Australia/Melbourne"] == [10.0, 11.0, 10.0]
    assert got["Australia/Hobart"] == [10.0, 11.0, 10.0]
    assert got["Australia/Brisbane"] == [10.0, 10.0, 10.0]  # no DST
    assert got["Australia/Adelaide"] == [9.5, 10.5, 9.5]
    assert got["Australia/Darwin"] == [9.5, 9.5, 9.5]  # no DST
    assert got["Australia/Perth"] == [8.0, 8.0, 8.0]


def test_seasonality_tracks_dst_transition():
    """Across the 4 Oct 2026 transition (16:00 UTC on 3 Oct) Sydney moves from UTC+10 to +11 and Brisbane
    stays at +10: identical profiles before, Sydney one hour ahead after."""
    ts = np.arange(np.datetime64("2026-10-01T00:00:00"), np.datetime64("2026-10-07T00:00:00"),
                   np.timedelta64(15, "m")).astype("datetime64[s]")
    zones = ["Australia/Brisbane", "Australia/Sydney"]
    for urb in range(4):
        p = seasonal_profile(ts, np.array([urb, urb]), np.array([0, 1]), zones)
        bne, syd = p[:, 0], p[:, 1]
        switch = np.datetime64("2026-10-03T16:00:00")
        before, after = ts < switch, ts >= switch
        np.testing.assert_allclose(syd[before], bne[before])
        shift = 4  # 1 hour of 15-minute steps
        a = np.flatnonzero(after)[:-shift]
        np.testing.assert_allclose(syd[a], bne[a + shift], rtol=1e-3)  # rtol: UTC-day growth term


def test_weekend_starts_at_local_midnight():
    t = np.array(["2026-09-04T14:00:00"], dtype="datetime64[s]")  # Fri 14:00 UTC
    _, weekend = local_clock(t, ["Australia/Sydney", "Australia/Perth"])
    assert weekend[:, 0].tolist() == [True, False]  # Sat 00:00 in Sydney, still Fri 22:00 in Perth
