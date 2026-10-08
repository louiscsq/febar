"""Element alarms: background noise, chronically flapping elements, and RAISE/CLEAR event expansion.

Incident-driven alarm cascades live in `faults.incident_alarms`; everything here is the noise floor
a NOC has to see through.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from netmon_datagen.config import FaultConfig, rng_for
from netmon_datagen.faults import Incident, opaque_id
from netmon_datagen.kpis import to_iso
from netmon_datagen.topology import Topology

# Background (non-incident) alarm rate per element per day, and the codes each element type raises.
BACKGROUND_RATE = {"CELL": 0.15, "SITE": 0.4, "BACKHAUL_LINK": 0.5, "AGG_ROUTER": 3.0, "UPF_SGW": 5.0, "AMF_MME": 5.0}
NOISE_CODES = {
    "CELL": ["VSWR_HIGH", "HIGH_INTERFERENCE", "SYNC_LOSS", "CELL_DEGRADED"],
    "SITE": ["DOOR_OPEN", "TEMPERATURE_HIGH", "FAN_FAILURE", "MAINS_FAILURE", "NTP_SYNC_LOSS"],
    "BACKHAUL_LINK": ["HIGH_BER", "RSL_LOW", "LINK_DEGRADED", "LOS"],
    "AGG_ROUTER": ["INTERFACE_DOWN", "FAN_FAILURE", "TEMPERATURE_HIGH", "BGP_PEER_FLAP", "CPU_HIGH",
                   "POWER_SUPPLY_FAIL"],
    "UPF_SGW": ["CPU_HIGH", "PACKET_DROP_HIGH", "NTP_SYNC_LOSS", "LICENSE_THRESHOLD"],
    "AMF_MME": ["CORE_CPU_OVERLOAD", "LICENSE_THRESHOLD", "NTP_SYNC_LOSS", "N2_S1MME_ASSOC_DOWN"],
}
# Full alarm-code catalogue per element type (noise codes + incident codes), documented in docs/data_model.md.
ALARM_CODES = {
    "CELL": NOISE_CODES["CELL"] + ["CELL_OUT_OF_SERVICE", "RRU_FAILURE"],
    "SITE": NOISE_CODES["SITE"] + ["BATTERY_LOW", "NE_UNREACHABLE", "S1_NG_LINK_FAILURE"],
    "BACKHAUL_LINK": NOISE_CODES["BACKHAUL_LINK"] + ["LINK_DOWN"],
    "AGG_ROUTER": NOISE_CODES["AGG_ROUTER"] + ["NODE_DOWN", "NTP_SYNC_LOSS", "DOOR_OPEN", "LICENSE_THRESHOLD"],
    "UPF_SGW": NOISE_CODES["UPF_SGW"] + ["GTPU_PATH_FAILURE", "USER_PLANE_CONGESTION"],
    "AMF_MME": NOISE_CODES["AMF_MME"] + ["SIGNALLING_OVERLOAD"],
}
FLAP_CODE = {"CELL": "SYNC_LOSS", "SITE": "S1_NG_LINK_FAILURE", "BACKHAUL_LINK": "LINK_DOWN"}
UNCLEARED_P = 0.03  # stale alarms that never receive a CLEAR

ALARM_COLUMNS = ["record_id", "alarm_id", "event_type", "element_id", "element_type", "alarm_code", "severity",
                 "event_ts", "emitted_ts", "vendor", "additional_text", "source_system"]


def select_flapping(topo: Topology, cfg: FaultConfig, seed: int) -> list[tuple[str, str]]:
    if not (cfg.enabled and cfg.red_herrings):
        return []
    rng = rng_for(seed, "flapping")
    pool = topo.nodes.index[topo.nodes["element_type"].isin(list(FLAP_CODE))].to_numpy()
    n = max(1, int(round(cfg.flapping_fraction * len(pool))))
    chosen = sorted(rng.choice(pool, size=min(n, len(pool)), replace=False).tolist())
    return [(e, FLAP_CODE[topo.nodes.at[e, "element_type"]]) for e in chosen]


def flapping_incidents(flappers: list[tuple[str, str]], topo: Topology, ws, we, prefix: str = "FLAP") -> list[Incident]:
    e = np.array([], dtype="datetime64[s]")
    out = []
    for n, (eid, _code) in enumerate(flappers, 1):
        row = topo.nodes.loc[eid]
        out.append(Incident(
            incident_id=f"{prefix}-{n:05d}", fault_type="FLAPPING_ELEMENT", event_class="red_herring",
            root_element_id=eid, root_element_type=row["element_type"], region_code=row["region_code"],
            start=np.datetime64(ws, "s"), end=np.datetime64(we, "s"), cell_idx=np.array([], dtype=int),
            onset=e, cell_end=e, severity=np.array([])))
    return out


def background_alarms(topo: Topology, hour_start: np.datetime64, seed: int,
                      flappers: list[tuple[str, str]]) -> list[dict]:
    """Noise alarms whose RAISE falls in [hour_start, hour_start + 1h)."""
    h0 = np.datetime64(hour_start, "s")
    stamp = str(h0)
    rng = rng_for(seed, "bg-alarms", stamp)
    rows: list[dict] = []
    for etype, rate in BACKGROUND_RATE.items():
        ids = topo.ids_of_type(etype)
        n = int(rng.poisson(rate * len(ids) / 24.0))
        if not n:
            continue
        el = rng.choice(ids, size=n)
        codes = rng.choice(NOISE_CODES[etype], size=n)
        sev = rng.choice(["WARNING", "MINOR", "MAJOR", "CRITICAL"], size=n, p=[0.35, 0.4, 0.2, 0.05])
        offs = rng.integers(0, 3600, size=n)
        dur = np.maximum(30, rng.exponential(2400, size=n)).astype(int)
        uncleared = rng.random(n) < UNCLEARED_P
        for k in range(n):
            t = h0 + np.timedelta64(int(offs[k]), "s")
            rows.append(dict(element_id=str(el[k]), alarm_code=str(codes[k]), severity=str(sev[k]), raise_ts=t,
                             clear_ts=None if uncleared[k] else t + np.timedelta64(int(dur[k]), "s"),
                             text="Threshold crossed", alarm_id=opaque_id("ALM", seed, "bg", stamp, etype, k)))
    frng = rng_for(seed, "flaps", stamp)
    for eid, code in flappers:
        if frng.random() >= 0.15:
            continue
        t = h0 + np.timedelta64(int(frng.integers(0, 3600)), "s")
        stop = t + np.timedelta64(int(frng.uniform(600, 3000)), "s")
        k = 0
        while t < stop:
            up = t + np.timedelta64(int(frng.uniform(20, 180)), "s")
            rows.append(dict(element_id=eid, alarm_code=code, severity="MAJOR", raise_ts=t, clear_ts=up,
                             text="Intermittent link state change",
                             alarm_id=opaque_id("ALM", seed, "flap", stamp, eid, k)))
            t = up + np.timedelta64(int(frng.uniform(60, 480)), "s")
            k += 1
    return rows


def expand_events(alarm_rows: list[dict], topo: Topology, rng: np.random.Generator) -> pd.DataFrame:
    """Turn alarm lifecycles into RAISE/CLEAR event records (pre-DQ, with private `_event_time`)."""
    if not alarm_rows:
        return pd.DataFrame(columns=[c for c in ALARM_COLUMNS if c != "emitted_ts"] + ["_event_time", "_emit_delay_s"])
    raise_part = pd.DataFrame({
        "alarm_id": [a["alarm_id"] for a in alarm_rows],
        "event_type": "RAISE",
        "element_id": [a["element_id"] for a in alarm_rows],
        "alarm_code": [a["alarm_code"] for a in alarm_rows],
        "severity": [a["severity"] for a in alarm_rows],
        "_event_time": np.array([a["raise_ts"] for a in alarm_rows], dtype="datetime64[s]"),
        "additional_text": [a["text"] for a in alarm_rows],
    })
    cl = [a for a in alarm_rows if a["clear_ts"] is not None]
    clear_part = pd.DataFrame({
        "alarm_id": [a["alarm_id"] for a in cl],
        "event_type": "CLEAR",
        "element_id": [a["element_id"] for a in cl],
        "alarm_code": [a["alarm_code"] for a in cl],
        "severity": "CLEARED",
        "_event_time": np.array([a["clear_ts"] for a in cl], dtype="datetime64[s]"),
        "additional_text": "Alarm cleared",
    })
    ev = pd.concat([raise_part, clear_part], ignore_index=True)
    ev["record_id"] = ev["alarm_id"] + np.where(ev["event_type"] == "RAISE", "-R", "-C")
    ev["element_type"] = topo.nodes.loc[ev["element_id"], "element_type"].to_numpy()
    ev["vendor"] = topo.nodes.loc[ev["element_id"], "vendor"].to_numpy()
    ev["source_system"] = "oss-fm"
    ev["event_ts"] = to_iso(ev["_event_time"].to_numpy())
    ev["_emit_delay_s"] = rng.uniform(1, 20, len(ev))
    ev = ev.sort_values(["_event_time", "record_id"], kind="stable").reset_index(drop=True)
    return ev[[c for c in ALARM_COLUMNS if c != "emitted_ts"] + ["_event_time", "_emit_delay_s"]]

