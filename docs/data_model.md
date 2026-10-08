# Synthetic network data model

The `netmon_datagen` package generates telemetry for **Banksia Mobile**, a fictional tier-1 Australian
mobile network operator. The customer is Banksia's national Network Operations Centre (NOC) in Sydney. The
NOC watches a network that runs from Sydney's CBD to Pilbara mining towns 1,500 km from their core,
across seven IANA time zones (up to five distinct UTC offsets), and through bushfire and cyclone seasons.
The data is built so a NOC pipeline has something real to work against: customer impact has to be
detected within 5 minutes, and the network element most likely causing it has to be named. Everything
is synthetic. Identifiers use reserved test ranges, vendors are fictional, and only the geography
(Australian town coordinates and coarse coastlines) and the time zones are real.

- [Output layout](#output-layout)
- [Topology](#topology): `topology_nodes`, `topology_edges`
- [Regions and time zones](#regions-and-time-zones)
- [KPIs](#kpis): `kpis`
- [Alarms](#alarms): `alarms`
- [Sessions](#sessions): `sessions`
- [Maintenance calendar](#maintenance-calendar): `maintenance_windows`
- [Ground truth](#ground-truth): `ground_truth/incidents`, `ground_truth/dq_injections`
- [Fault taxonomy and propagation](#fault-taxonomy-and-propagation)
- [Data-quality defects](#data-quality-defects)
- [Volumes and performance](#volumes-and-performance)
- [Design rationale](#design-rationale)

## Output layout

```
<out>/
  _manifest.json                         config, window, row counts
  topology_nodes/part-00000.<fmt>        network inventory (reference data)
  topology_edges/part-00000.<fmt>
  kpis/date=YYYY-MM-DD/*.<fmt>           raw feeds, partitioned by *emitted* date
  alarms/date=YYYY-MM-DD/*.<fmt>
  sessions/date=YYYY-MM-DD/*.<fmt>
  maintenance_windows/*.<fmt>            change calendar (operational data the NOC would have)
  ground_truth/incidents/...             labels: never an input to detection
  ground_truth/dq_injections/date=.../   audit log of every injected defect
```

- **Batch mode** writes Parquet (default) or JSON lines. Files are named `part-<day>-<chunk>`, and records
  emitted after the window closes go to `part-final`.
- **Streaming mode** always writes JSON lines, one file per feed per micro-batch:
  `<feed>/date=.../batch-<simtime>-<seq>.json`. Each file is written to a dot-prefixed temp name and then
  renamed, so Auto Loader never picks up a half-written file.
- Raw feeds are partitioned by **emitted** date (when the record reached the collector), not event
  date. This is how a landing zone behaves, and it means late records land in later partitions.
- Every timestamp is an ISO-8601 UTC **string** (`2026-09-04T17:15:00Z`) in the raw feeds and ground truth.
  Raw collectors emit strings. Keeping them as strings also lets malformed timestamps survive into bronze, so
  the pipeline has to parse and quarantine them. Local time never appears in a stored timestamp; use
  `topology_nodes.timezone` to convert (see [time zones](#regions-and-time-zones)).
- `date=` partitions are UTC dates, so one local Australian day spans two of them: a Sydney day starts at
  13:00 or 14:00 UTC the day before. The evening busy hour (18–21h local) falls at about 07:00–13:00 UTC
  depending on zone and DST, so it never straddles a partition boundary.

## Topology

The network is a forest with one tree per region. Every non-root node has exactly one parent:

| level | `element_type` | id pattern | per region (large) | notes |
|---|---|---|---|---|
| 0 | `AMF_MME` | `AMF-NSW-01` | 1 | control-plane core (5G AMF / 4G MME) |
| 1 | `UPF_SGW` | `UPF-NSW-01` | 2 | user-plane core (5G UPF / 4G SGW) |
| 2 | `AGG_ROUTER` | `AGG-NSW-03` | 10 | aggregation routers at the most urban sites; sites home onto the nearest one |
| 3 | `BACKHAUL_LINK` | `BH-NSW-0042` | ~220 | fibre, microwave or satellite; 1–5 sites chained per link |
| 4 | `SITE` | `SITE-NSW-00123` | ~500 | gNB/eNB; `4G` or `4G/5G` |
| 5 | `CELL` | `CELL-NSW-00123-5G2` | ~2,300 | one per sector (3) per technology |

RAN vendors (`Arcturus`, `Borealis`) are assigned per region, as operators usually split the country
between suppliers. Core is `Eridani Core` and transport is `Cygnus Networks`. All three are fictional.

### `topology_nodes`

| column | type | description |
|---|---|---|
| `element_id` | string | primary key |
| `element_type` | string | one of the six types above |
| `name` | string | human-readable name |
| `parent_id` | string | parent element (null for `AMF_MME` roots) |
| `level` | int | 0 (core) … 5 (cell) |
| `region_code`, `region` | string | e.g. `NSW`, `Sydney & NSW` (row-filter key for governance) |
| `state` | string | Australian state or territory (`NSW`, `VIC`, `QLD`, `WA`, `SA`, `TAS`, `ACT`, `NT`) |
| `timezone` | string | IANA zone of the element's region, e.g. `Australia/Perth` |
| `lat`, `lon` | double | WGS84. Urban sites cluster on the region's towns, rural sites spread wider, remote sites anywhere in the service area. Core nodes of `TAS`, `NQL` and `PIL` sit in the capital-city data centre they home onto |
| `vendor` | string | equipment vendor (fictional) |
| `technology` | string | cells `4G`/`5G`; sites `4G` or `4G/5G`; core `4G/5G` |
| `urbanity` | string | sites/cells: `urban`, `suburban`, `rural`, `remote` |
| `transport_medium` | string | backhaul links: `fibre` / `microwave` / `satellite` (microwave likelier in rural areas, satellite only in rural and remote ones); routers: `fibre` |
| `uplink_km` | double | routers: fibre route length to the core data centre (> 250 km = long-haul); backhaul links: route length to their router |
| `sector` | int | cells: 1–3 |
| `capacity_users` | int | cells: nominal concurrent-user capacity (by technology × urbanity) |
| `coverage_radius_km` | double | cells: nominal coverage radius. Urban 0.4–1.5 km … remote 15–40 km; 5G layer 0.6× |
| `amf_id`, `upf_id`, `router_id`, `backhaul_id`, `site_id` | string | denormalised ancestors, so "everything under X" is a single filter |

### `topology_edges`

| column | type | description |
|---|---|---|
| `parent_id`, `child_id` | string | directed edge, upstream → downstream |
| `edge_type` | string | `control_plane` (AMF→UPF), `user_plane` (UPF→router), `transport` (router→link), `backhaul` (link→site), `hosts` (site→cell) |
| `parent_type`, `child_type` | string | element types of the two ends |

Invariants (tested): one parent per non-root node, levels increase by exactly 1 along every edge (so the
graph is acyclic), every node reaches an `AMF_MME` root, and every non-cell node has at least one child.

## Regions and time zones

Ten regions cover the capitals plus the regional and remote areas that make Australian NOC work hard.
Coordinates are real. Each region has a coarse service-area polygon drawn just inside the coastline, with
Port Phillip and Western Port cut out, and every site is sampled inside it, so nothing lands at sea. The
large preset uses all ten in this order. `tiny` uses `NSW` + `NQL` (one DST zone, one non-DST tropical
long-haul zone). `small` uses `NSW`, `VIC`, `WA` and `NQL` (UTC+8 to +11).

| code | region | state | IANA zone (UTC offset) | hubs | pop. (M) | site share | urban / suburban / rural / remote | core |
|---|---|---|---|---|---|---|---|---|
| `NSW` | Sydney & NSW | NSW | `Australia/Sydney` (+10 / +11 DST) | Sydney, Newcastle, Wollongong, Bathurst | 8.4 | 29 % | 45 / 30 / 20 / 5 | Sydney |
| `VIC` | Melbourne & Victoria | VIC | `Australia/Melbourne` (+10 / +11) | Melbourne, Geelong, Ballarat, Bendigo | 6.9 | 24 % | 45 / 30 / 20 / 5 | Melbourne |
| `QLD` | Brisbane & South East QLD | QLD | `Australia/Brisbane` (+10, no DST) | Brisbane, Gold Coast, Sunshine Coast, Toowoomba | 4.0 | 16 % | 45 / 32 / 20 / 3 | Brisbane |
| `WA` | Perth & South West WA | WA | `Australia/Perth` (+8, no DST) | Perth, Mandurah, Northam | 2.3 | 9 % | 50 / 30 / 17 / 3 | Perth |
| `SA` | Adelaide & SA | SA | `Australia/Adelaide` (+9:30 / +10:30) | Adelaide, Murray Bridge, Victor Harbor | 1.5 | 6.5 % | 45 / 30 / 20 / 5 | Adelaide |
| `TAS` | Tasmania | TAS | `Australia/Hobart` (+10 / +11) | Hobart, Launceston, Devonport | 0.58 | 3 % | 25 / 30 / 35 / 10 | Melbourne (Bass Strait fibre) |
| `ACT` | Canberra | ACT | `Australia/Sydney` (+10 / +11) | Canberra | 0.47 | 2 % | 60 / 30 / 10 / 0 | Canberra |
| `NT` | Darwin & Top End | NT | `Australia/Darwin` (+9:30, no DST) | Darwin, Palmerston, Katherine | 0.25 | 1.5 % | 30 / 20 / 20 / 30 | Darwin |
| `NQL` | North Queensland | QLD | `Australia/Brisbane` (+10) | Townsville, Cairns, Mackay | 0.75 | 5 % | 30 / 25 / 30 / 15 | Brisbane (~1,400 km) |
| `PIL` | Pilbara (Regional WA) | WA | `Australia/Perth` (+8) | Karratha, South Hedland, Newman, Tom Price | 0.06 | 2 % | 15 / 10 / 25 / 50 | Perth (~1,600 km) |

- **Site share vs subscribers.** Site share is over-weighted towards regional and remote areas, because
  coverage, not population, sets their site count. Subscribers follow resident population: the IMSI pool
  of each region is proportional to its population, and within a region it follows cell demand.
- **Remote areas** get sparse sites spread across the whole service area, coverage radii of 15–40 km,
  low base load, 5 % 5G, and backhaul that is 50 % microwave chains and 35 % satellite.
- **Latency.** A cell's baseline latency includes its transport path. That path is fibre distance to its
  router and on to the core (0.015 ms RTT per route-km), plus 35–55 ms for a LEO satellite hop. Pilbara
  cells therefore idle at ~60 ms against ~28 ms in Sydney & NSW. Satellite-backhauled cells also get 40 % of
  normal peak throughput.
- **Tropical regions** (`NT`, `NQL`, `PIL`) are exposed to cyclones. Regions homed onto a distant core
  (`TAS`, `NQL`, `PIL`) have long-haul router uplinks, which are exposed to fibre cuts.

**Time zones.** Every stored timestamp is UTC. Local time drives behaviour only:

- KPI load, and therefore sessions, follow each cell's **local** hour of day and **local** day of week.
  Weekends start at local midnight. A Perth cell peaks at the same local hour as a Sydney cell, which is 2 h
  later in UTC (3 h during eastern DST).
- Busy-hour fault windows (17–21h), traffic surges (17–20h) and maintenance windows (opening
  00:00–01:30) are in the root element's local time. Maintenance windows open on the half hour, so they
  align with local time in UTC+9:30 zones too.
- DST is handled by the IANA tz database through pandas' vectorised `tz_convert`, one conversion per
  distinct zone per time chunk, so the cost does not grow with cell count. On the first Sunday of October
  (16:00 UTC the day before) `Australia/Sydney`, `Melbourne` and `Hobart` move from +10 to +11 and
  `Adelaide` from +9:30 to +10:30; they return on the first Sunday of April. Brisbane, Darwin and Perth
  have no DST, so during the southern summer Perth and Sydney clocks differ by 3 h instead of 2. The
  tests check both transitions and the half-hour zones.

## KPIs

`kpis` holds one record per cell per reporting period. Batch mode uses 15 minutes, the 3GPP PM
reporting-period default. Streaming mode uses `step_seconds`, 1 minute by default.

| column | type | description |
|---|---|---|
| `record_id` | string | `K-<cell_id>-<yyyymmddHHMM>`, the natural key and dedupe key |
| `event_ts` | string | period start (UTC) |
| `emitted_ts` | string | when the collector delivered the record: period end + 30–240 s for 15-min periods, + 6–30 s for 1-min streaming periods (late records much later) |
| `cell_id` | string | FK → `topology_nodes` |
| `granularity_s` | int | 900 in batch, 60 in streaming |
| `availability_pct` | double | share of the period the cell was in service |
| `active_users` | int | mean connected users |
| `prb_util_pct` | double | downlink PRB utilisation |
| `rrc_setup_success_pct` | double | RRC connection setup success rate |
| `attach_success_pct` | double | attach/registration success rate (core-dependent) |
| `session_drop_rate_pct` | double | abnormal E-RAB / QoS-flow release rate |
| `dl_throughput_mbps`, `ul_throughput_mbps` | double | average user throughput |
| `latency_ms` | double | user-plane round-trip latency |
| `packet_loss_pct` | double | user-plane packet loss |

**How the values are made.**

1. **Load** = cell base load × seasonal profile × growth × lognormal noise. The seasonal profile is
   evaluated at the cell's **local** time and interpolated from hourly anchors that differ by urbanity
   and by weekday or weekend:
   - urban cells have a commuter morning peak that disappears at weekends;
   - suburban and rural cells peak in the evening (busy hour ~18–21h) and are busier at weekends;
   - remote cells (mining towns, FIFO camps) add a 05–06h shift-change peak and look the same at weekends.

   Base load varies by urbanity, plus a site-level and a cell-level random effect, so some cells are
   chronically hot. Traffic grows by about 1.5 % per month.
2. **PRB** ≈ 6 % + 88 % × load. **Congestion** is a knee above 70 % PRB.
3. Latency, loss and drop rise gently with utilisation and sharply with congestion. Throughput falls with
   utilisation. RRC and attach success dip under congestion. Load therefore drives every quality KPI;
   the Spearman correlation within a technology is > 0.3 (tested).
4. Cells also differ by technology (5G: about 5× throughput and roughly half the latency), urbanity
   (rural and remote: higher drops, latency and RRC failures), transport path (long-haul distance, satellite)
   and vendor (`Borealis` RRC runs ~0.15 pp lower).
5. Fault effects are applied on top (see below). With faults disabled, the baseline is bit-identical for
   the same seed.

Only the rows of dark cells are missing: site power outages or bushfire grid outages after the battery is
exhausted (or the 5G layer is shed), and cells isolated by a long-haul fibre cut.
Everything else always reports. Before DQ injection, a full outage looks like
`availability_pct = 0`, `active_users = 0` and success rates of 0. It never shows up as nulls, so every
null in the feed is an injected DQ defect.

## Alarms

`alarms` holds one record per alarm lifecycle event: a `RAISE`, then a `CLEAR` that shares its
`alarm_id`. About 3 % of background alarms never clear. These stale alarms are a classic NOC annoyance.

| column | type | description |
|---|---|---|
| `record_id` | string | `<alarm_id>-R` / `<alarm_id>-C` |
| `alarm_id` | string | opaque (hash) id, the same on RAISE and CLEAR. It carries no incident linkage |
| `event_type` | string | `RAISE` / `CLEAR` |
| `element_id`, `element_type` | string | FK → topology |
| `alarm_code` | string | see catalogue below |
| `severity` | string | `CRITICAL`, `MAJOR`, `MINOR`, `WARNING` on RAISE; `CLEARED` on CLEAR |
| `event_ts`, `emitted_ts` | string | event time / delivery time (+1–20 s) |
| `vendor` | string | element vendor |
| `additional_text` | string | free text |
| `source_system` | string | `oss-fm` |

**Alarm codes by element type.** Noise codes appear in background alarms. Incident codes appear in
fault cascades, and some appear in both.

| element type | background noise | incident-driven |
|---|---|---|
| `CELL` | `VSWR_HIGH`, `HIGH_INTERFERENCE`, `SYNC_LOSS`, `CELL_DEGRADED` | `CELL_OUT_OF_SERVICE`, `RRU_FAILURE`, `CELL_DEGRADED` |
| `SITE` | `DOOR_OPEN`, `TEMPERATURE_HIGH`, `FAN_FAILURE`, `MAINS_FAILURE`, `NTP_SYNC_LOSS` | `MAINS_FAILURE`, `BATTERY_LOW`, `NE_UNREACHABLE`, `S1_NG_LINK_FAILURE`, `TEMPERATURE_HIGH` (bushfire) |
| `BACKHAUL_LINK` | `HIGH_BER`, `RSL_LOW`, `LINK_DEGRADED`, `LOS` | `LINK_DOWN`, `LOS`, `HIGH_BER`, `RSL_LOW`, `LINK_DEGRADED` |
| `AGG_ROUTER` | `INTERFACE_DOWN`, `FAN_FAILURE`, `TEMPERATURE_HIGH`, `BGP_PEER_FLAP`, `CPU_HIGH`, `POWER_SUPPLY_FAIL` | `NODE_DOWN`, `LOS`, `NE_UNREACHABLE` (+ storm codes) |
| `UPF_SGW` | `CPU_HIGH`, `PACKET_DROP_HIGH`, `NTP_SYNC_LOSS`, `LICENSE_THRESHOLD` | `GTPU_PATH_FAILURE`, `USER_PLANE_CONGESTION`, `PACKET_DROP_HIGH` |
| `AMF_MME` | `CORE_CPU_OVERLOAD`, `LICENSE_THRESHOLD`, `NTP_SYNC_LOSS`, `N2_S1MME_ASSOC_DOWN` | `SIGNALLING_OVERLOAD`, `CORE_CPU_OVERLOAD` |

**Background rates** (raises per element per day): cell 0.15, site 0.4, backhaul link 0.5,
router 3, UPF 5, AMF 5. Severity mix: 35 % WARNING, 40 % MINOR, 20 % MAJOR, 5 % CRITICAL. Clear time is
exponential with a 40-minute mean.

**Flapping elements.** About 0.1 % of cells, sites and links (at least one) are chronically noisy. Each
simulated hour there is a 15 % chance of a 10–50-minute episode of RAISE/CLEAR cycles
(`SYNC_LOSS`, `S1_NG_LINK_FAILURE` or `LINK_DOWN`, MAJOR). The episodes never affect customers.

## Sessions

`sessions` is a sampled xDR feed (`session_sample_rate` of real volume, 0.25 % at large scale). The
`imsi` and `msisdn` columns are the PII that the governance layer masks.

| column | type | description |
|---|---|---|
| `record_id` | string | session id |
| `imsi` | string | `00101` + 10 digits. MCC 001 / MNC 01 is the ITU test network, never allocated to an operator |
| `msisdn` | string | `+999` + 9 digits. E.164 country code 999 is unassigned |
| `cell_id` | string | serving cell |
| `start_ts`, `end_ts`, `emitted_ts` | string | xDRs are emitted 5–90 s after the session closes |
| `duration_s` | int | 0 for setup failures |
| `service_type` | string | `data` 62 %, `video` 18 %, `volte` 14 %, `iot` 6 % |
| `dnn` | string | `internet`, `ims`, `iot.m2m` |
| `bytes_dl`, `bytes_ul` | long | duration × service rate × radio quality (cell DL throughput) |
| `outcome` | string | `COMPLETED`, `DROPPED`, `SETUP_FAILED` |
| `cause_code` | string | `NORMAL_RELEASE`, `RADIO_LINK_FAILURE`, `TRANSPORT_TIMEOUT`, `RRC_SETUP_FAILURE`, `ATTACH_REJECT_CONGESTION`, `NO_SERVICE` |

Each subscriber has a home cell. 90 % of a cell's sessions come from its home pool and 10 % from
roamers. Session **attempts** follow *expected* demand, so subscribers keep trying during an outage. The
outcome is drawn from the serving cell's KPIs in the same period:
`P(setup fail) = 1 − rrc × attach × availability`, and the drop probability rises with the drop rate and
with session length. Faults therefore show up in this feed as bursts of `SETUP_FAILED / NO_SERVICE` or
`DROPPED` records for real IMSIs. This is the customer-impact signal.

## Maintenance calendar

`maintenance_windows` is the change calendar the NOC uses to suppress planned work.

| column | description |
|---|---|
| `change_id` | opaque id |
| `element_id`, `element_type` | element under change (router or site) |
| `planned_start_ts`, `planned_end_ts` | approved 4-hour window, opening between 00:00 and 01:30 **local** time (stored as UTC) |
| `change_type` | `software_upgrade` (routers) / `hardware_swap` (sites) |
| `status` | `approved` |

## Ground truth

### `ground_truth/incidents`

There is one row per incident, red herring, planned outage and flapping element. Use it as ML labels
and to measure time-to-detect against `impact_start_ts`.

**Observation-window guarantee.** In batch mode the scheduler only accepts an incident whose full
extent lies inside `[window_start, window_end)`. The extent covers root start and end, every cell's
onset (including propagation delay) and recovery, and every alarm the incident raises or clears.
Candidates that would cross the edge are redrawn. Every batch row is therefore uncensored
(`is_censored = false`): each labelled impact has matching KPI and session telemetry, and incident
alarms never fall outside the window. Flapping elements span exactly the window. In streaming mode,
see `is_censored` below.

| column | type | description |
|---|---|---|
| `incident_id` | string | `INC-00001` (batch) / `INC-<yyyymmddHH>-00001` (stream) / `FLAP-00001` |
| `event_class` | string | `fault`, `planned`, `red_herring` |
| `fault_type` | string | see taxonomy |
| `root_element_id`, `root_element_type` | string | the true root cause. For geographic clusters, the epicentre (first element hit) |
| `root_element_ids` | array<string> | every root element: `[root_element_id]`, except bushfire and cyclone clusters, where it lists every site that lost mains or every backhaul link that was cut or degraded (nearest the epicentre first). Score RCA hits against this list |
| `region_code` | string | |
| `start_ts`, `end_ts` | string | root-cause start (e.g. mains failure) / restoration |
| `impact_start_ts`, `impact_end_ts` | string | first and last moment any cell is impacted (null if no customer impact) |
| `is_customer_impacting` | bool | false for alarm storms, flapping, and power outages that end before the battery runs out. For censored rows: only impact that was actually observed counts |
| `is_censored` | bool | the incident was not fully observed. Always false in batch. In streaming, a bounded run (`max_batches`) that stops mid-incident writes the row with `end_ts` / `impact_end_ts` clipped to the end of the observed window. Flapping elements are open-ended, with a null `end_ts`. Exclude censored rows from duration and impact metrics |
| `severity` | string | `critical` (≥ 2,000 subscribers, or a major-incident type: router/core failure, long-haul cut, bushfire or cyclone), `major` (≥ 200), `minor`, `none` |
| `affected_element_ids` | array<string> | every element strictly below any root, excluding the epicentre root itself (for surges: venue + neighbouring sites and their cells) |
| `affected_cell_ids` | array<string> | cells whose KPIs are altered |
| `n_affected_cells` | int | |
| `estimated_impacted_subscribers` | int | Σ over affected cells of peak expected concurrent users during the impact × per-cell severity |
| `n_alarms` | int | alarm lifecycles generated by the incident |
| `description` | string | per type; weather types use an off-season wording (severe storm, thunderstorm flooding) outside their season |

### `ground_truth/dq_injections`

| column | description |
|---|---|
| `feed` | `kpis`, `alarms`, `sessions` |
| `record_id` | affected record (for duplicates: the duplicated id) |
| `defect_type` | `duplicate`, `late_arrival`, `malformed`, `null`, `out_of_range` |
| `defect_subtype` | `redelivery`, `delayed_delivery`, `bad_timestamp`, `type_mismatch`, `truncated_json`, `missing_value`, `impossible_value`, `clock_skew` |
| `column` | column that was altered (if any) |
| `injected_value` | the value written (stringified), or the delay for late arrivals |

## Fault taxonomy and propagation

| fault_type | class | root | rate (per element per day) | duration | when | impact on descendants |
|---|---|---|---|---|---|---|
| `AGG_ROUTER_FAILURE` | fault | router | 0.005 | 15–120 min | any time | all cells: availability → ~3 %, users → ~3 %, RRC/attach success → ~10 %. Onset 1–3 min after the root fails; staggered recovery 1–5 min after restoration |
| `BACKHAUL_DEGRADATION` | fault | backhaul link | 0.001 | 30–240 min | any | latency +140 ms, loss +6 %, throughput −65 %, drops +3 pp at full intensity. **Ramps in over 10–30 min**; severity 0.4–1.0 per incident × 0.85–1.0 per cell |
| `SITE_POWER_OUTAGE` | fault | site | 0.0003 | 1–6 h | any | runs on battery for 20–90 min (10 % of sites have no battery), then the cells go **dark: no KPI rows**. Recovery 3–8 min after mains returns. Power restored before the battery runs out means no customer impact |
| `CELL_OUTAGE` | fault | cell | 0.0003 | 20–180 min | any | that cell: availability 0, users 0 |
| `CORE_CONGESTION` | fault | UPF/SGW | 0.01 | 30–120 min | local busy hour 17–21h | every cell under the UPF: latency +80 ms, throughput −60 %, loss +3 %. Ramps over 10–20 min, and hotter cells suffer more |
| `AMF_OVERLOAD` | fault | AMF/MME | 0.015 | 15–60 min | local busy hour | the whole region: attach success −40 %, RRC −6 %, users −20 %. Ramps over 5 min |
| `PLANNED_MAINTENANCE` | planned | router (0.0025) / site (0.00015) | 10–45 min of downtime | inside a 4-h window opening 00:00–01:30 local | like an outage, but announced in `maintenance_windows` |
| `TRAFFIC_SURGE` | red herring | urban site | 0.00008 | 2–4 h | local 17–20h | venue site + 2 nearest sites: load × 2–3, ramping over 30–45 min. **Organic congestion with no faulty element** |
| `BUSHFIRE_GRID_OUTAGE` | fault | cluster of rural/remote sites | 2e-5 per site; × 3 in Dec–Feb, × 0.3 otherwise | 5–16 h | any | see below. Cells go **dark** (no KPI rows) |
| `CYCLONE_BACKHAUL_CUT` | fault | cluster of backhaul links in `NT` / `NQL` / `PIL` | 4e-4 per link; × 2 in Nov–Apr, × 0.2 otherwise | 4–20 h | any | see below. Cut links: availability → ~3 %, users → ~5 %; degraded links: proportionally less, plus latency/loss |
| `LONG_HAUL_FIBRE_CUT` | fault | router with `uplink_km` > 250 (`TAS`, `NQL`, `PIL`) | 0.003 | 3–10 h | any | every cell behind the router goes **dark** within 30 s; staggered return 1–5 min after the splice |
| `ALARM_STORM` | red herring | router (0.003) / site (0.00014) | 5–20 min | any | 50–400 equipment alarms (some CRITICAL); no KPI impact |
| `FLAPPING_ELEMENT` | red herring | cell/site/link | fixed set | whole window | – | repeated RAISE/CLEAR; no KPI impact |

On top of these Poisson rates, every batch run includes at least `min_per_type` (default 1) of each
type, so short histories still contain every story. This includes the weather types out of season, which
then use their off-season wording: a 30-day September run still has one storm-driven grid outage and
one thunderstorm-flood backhaul cut. In streaming mode the minimum is off, and
`fault_rate_multiplier` makes demos busier. Batch runs only keep incidents that fit the window, so a
very short window (for example 1 day) can hold fewer than `min_per_type` of the long or busy-hour
types.

**Australian fault types.**

- `BUSHFIRE_GRID_OUTAGE`: a fire front or severe storm takes out grid power across rural and remote sites.
  The cluster is every eligible site in the epicentre site's region within 15–45 km, capped at 30 and
  listed in `root_element_ids`. Mains loss sweeps outward at 10–40 km/h. Each site then runs on battery
  for 1–4 h (10 % have none). During that time it sheds its 5G layer after 5–20 min to save energy, and
  its 4G cells go dark when the battery is exhausted. Restoration is gradual and partial: each site gets
  mains back somewhere between 35 % and 100 % of the way through the event, and about a quarter (always
  including the epicentre) only at the very end. A site restored before its battery runs out has no
  customer impact. Alarms per site: `MAINS_FAILURE`, `BATTERY_LOW`, `NE_UNREACHABLE` and, in fire season,
  `TEMPERATURE_HIGH` on about 30 % of sites before the fire front arrives. The sites in a cluster need not share a router.
  Topology-only RCA tends to blame a common ancestor that never failed, so the label is the set of sites.
- `CYCLONE_BACKHAUL_CUT`: a cyclone track (or, off season, thunderstorm flooding) crosses a tropical
  region. The cluster is every backhaul link within 40–150 km of the epicentre link, capped at 40, hit as
  the system moves at 12–30 km/h. Each link is cut (microwave 70 %, fibre 45 %, satellite 20 %; the
  epicentre always) or degraded to 30–70 % severity by rain fade or water ingress. Repairs are
  staggered, because crews cannot get out until the system passes. Cut links raise `LINK_DOWN` (radio) or
  `LOS` (fibre washout), and their sites raise `S1_NG_LINK_FAILURE`. Degraded links raise `RSL_LOW` /
  `HIGH_BER`.
- `LONG_HAUL_FIBRE_CUT`: roadworks or a washout cuts the single long-haul route between a remote
  aggregation router and its capital-city core. Unlike `AGG_ROUTER_FAILURE`, where the cells keep reporting
  at ~3 % availability and every downstream element alarms, the isolated sites cannot report at all.
  Their KPI rows disappear, and the only alarms come from the core side and the OSS: `LOS` and
  `NE_UNREACHABLE` on the router, `GTPU_PATH_FAILURE` on its UPF, and `NE_UNREACHABLE` per site.

The seasonal factor averages the multiplier of each day's (UTC) calendar month over the scheduling window.
The window/censoring rules apply unchanged: a cluster is accepted only if its whole extent fits, and it
counts as one incident for overlap checks and `min_per_type`.

**Streaming emission ordering.** A micro-batch file `batch-<t>-<seq>.json` lands at simulated time
`t + step`. A record lands in the first micro-batch that ends after its `emitted_ts`, so its emission is
due. The stream guarantees:

- **Ground truth never runs ahead of its telemetry.** An incident's row is written only once its full
  extent has played out *and* every associated record has landed. The associated records are all of its
  alarm RAISE/CLEAR events and every KPI record of its affected cells for a period overlapping
  `[impact_start_ts, impact_end_ts)`, including DQ late arrivals and redeliveries. Within a micro-batch,
  feeds are written before ground truth. Nominal collection lag (6–30 s for 1-minute KPIs) only delays
  a label by a batch or two. With DQ defects on, a large incident usually has at least one late-arriving
  record (up to 36 h), so its label waits for it. Run with `--dq-scale 0` when labels must appear live.
  Labels are for offline scoring: score time-to-detect against `impact_start_ts`, not against when the
  label landed.
- **DQ logs never reference unseen records.** A `dq_injections` row is written in the micro-batch where
  the record it describes lands (for duplicates, the first delivery).
- **Bounded stop (`max_batches`).** First, every spooled record whose event time was observed is flushed
  with its DQ-log rows (`batch-<t>-final.json`). Records and log rows for later events, such as alarms
  generated at the top of the hour for future times, are dropped together. Then the remaining ground
  truth is written. Incidents that finished but were waiting for late records are written as normal.
  Incidents still in flight are written with `is_censored = true` and clipped times. Incidents that had
  not started are dropped. Live incidents are scheduled per simulated hour, never before the stream
  start.

**Propagation.** Each incident resolves to the set of cells under its root, taken from the ancestor
columns. Each affected cell gets an onset time, an end time and a peak severity. For every KPI period,
`intensity = severity × (fraction of the period overlapping [onset, end)) × ramp`. Each effect
coefficient is scaled by this intensity and merged across incidents with `max`. Partial overlap gives
partial values: an outage that starts 5 minutes into a 15-minute period reports `availability_pct ≈ 67`.

**Alarm cascades.** The root raises a few alarms; each descendant raises symptom alarms. A router
failure, for example, produces one `NODE_DOWN` and a `GTPU_PATH_FAILURE` on the parent UPF, plus
`LINK_DOWN` on every link, `S1_NG_LINK_FAILURE` on every site and `CELL_OUT_OF_SERVICE` on every cell:
dozens of symptoms against one cause. The RCA model has to rank the root above them. Some faults are
quiet or late on purpose:
- core congestion alarms trip 4–10 minutes **after** customers notice;
- backhaul degradation flags only about 30 % of its cells;
- a dark site cannot report, so only `NE_UNREACHABLE` (raised by the OSS) appears.

**No overlapping labels.** Customer-impacting incidents never share a cell while their impact windows
(±30 min) overlap. Every degraded cell-period therefore has exactly one ground-truth cause. Real
networks do get concurrent faults; this is a deliberate simplification so the labels stay clean.

**Counterfactual guarantee.** Baseline noise, faults, alarms, sessions and DQ each draw from their own
RNG stream, seeded by `(seed, component, time chunk)`. Running with `--no-faults` therefore reproduces
the exact baseline, and the diff between the two runs is the fault impact. The propagation tests rely
on this: descendants of a failed router change, and non-descendants are bit-identical.

## Data-quality defects

Defects are applied to `kpis`, `alarms` and `sessions` after generation. Each record gets at most one
defect, duplicates are copies of clean records, and every defect is logged in `dq_injections`.

| defect | default rate | what happens | how a pipeline should catch it |
|---|---|---|---|
| `duplicate` | 0.5 % | record re-delivered 1–600 s later with the same `record_id` and payload | dedupe on `record_id` (watermark ≥ 10 min) |
| `late_arrival` | 1 % | `emitted_ts` pushed 30 min – 36 h later, so the record lands in a later `date=` partition | `emitted_ts − event_ts` > threshold. Normal lag is < 20 min in batch |
| `malformed` | 0.2 % | `bad_timestamp` (`"N/A"`, `"2026-13-45T25:61:00Z"`, …). JSON only: `type_mismatch` (`"#VALUE!"` in a numeric column) and `truncated_json` (half a line) | Auto Loader `_rescued_data` / corrupt-record handling; `try_cast` / `to_timestamp` null checks |
| `null` | 0.5 % | one mandatory field nulled (id, timestamp, or a key KPI) | `expect … IS NOT NULL` |
| `out_of_range` | 0.2 % | impossible values: success rate 100.5–160 %, PRB > 100 %, negative latency/users/bytes/duration; alarms timestamped 1970 or 2099 (`clock_skew`) | range expectations |

Rates are set with `DQConfig` or scaled with `--dq-scale`; 0 turns DQ off. Each record gets at most one
defect, so every rate must be within [0, 1] and the rates must sum to at most 1. `DQConfig` raises a
`ValueError` otherwise, and the CLI rejects a `--dq-scale` that would push the total over 1; with the
default rates (2.4 % in total) the maximum scale is about 41. The tests check that the
observed rates match the configured ones, that duplicates are exactly the repeated `record_id`s, that
truncated lines are exactly the unparseable lines, and that late records can be identified from
timestamps alone.

## Volumes and performance

Measured with the CLI on a laptop (Apple Silicon, Python 3.11, Parquet, default DQ and fault rates),
after the Australian localisation. `tiny`/`small` are 3-day runs and `large` a 2-day run,
extrapolated to 30 days. Runtime is roughly linear in days; local-time seasonality costs one vectorised
tz conversion per zone per 6-hour chunk. Expect similar figures on a serverless notebook driver. `xl`
figures are from before localisation, scaled by cell count.

| preset | sites / cells | KPI rows per day | sessions per day | alarm events per day | 30-day size | 30-day runtime | peak RAM |
|---|---|---|---|---|---|---|---|
| `tiny` | 24 / 111 | ~10.5 k | ~15 k | ~450 | ~40 MB | ~8 s | < 0.2 GB |
| `small` | 299 / 1,431 | 138 k | 90 k | ~1.3 k | ~280 MB | ~27 s | 0.4 GB |
| `large` (default) | 5,000 / 22,830 | 2.2 M | 350 k | ~17 k | **~2.2 GB** (72 MB/day) | **~4 min** (~7.5 s/day) | ~2.3 GB |
| `xl` | 20,000 / 91,803 | 8.8 M | 560 k | ~62 k | ~8 GB (275 MB/day) | ~15 min (~30 s/day) | ~5 GB |

JSON is about 9× larger than Parquet and about 1.7× slower to write.

In streaming at `large`, one 1-minute micro-batch is about 22.8 k KPI rows (~7 MB of JSON), plus
~250 sessions and a handful of alarms.

**Granularity trade-off.** A large operator has 15–30 k sites and 100 k+ cells, and modern PM can
report every minute. At full scale with 1-minute history that is about 4 billion KPI rows a month. It
is far too much to generate on a single driver, and it adds nothing to a demo. The defaults keep
**per-cell** resolution and full topology depth, but:

- **15-minute history** matches the standard 3GPP reporting period and is what trends, baselines and
  ML features are computed on.
- **1-minute streaming** gives the 5-minute detection SLA real resolution. A fault is visible within
  one or two micro-batches.
- **A ~5 k-site national footprint** keeps the default 30-day run to a few minutes and ~2 GB. `xl`
  (20 k sites) shows the same code scales by preset.
- **Sessions are a 0.25 % sample** of real xDR volume. That gives enough per-cell signal to see impact
  bursts without generating billions of rows. `estimated_impacted_subscribers` is computed from the
  full expected population, not the sample.

## Design rationale

- **Tree topology with denormalised ancestors.** Blast-radius queries ("all cells under router X")
  become a single equality filter. They are just as cheap in Spark SQL, Lakebase and the app's topology
  view.
- **Faults are root-cause objects, not KPI perturbations.** Each incident starts at a root and
  propagates through the graph with realistic per-hop delays, ramps and staggered recovery. Symptoms
  vastly outnumber causes, and some causes are quiet: core congestion alarms late, and a dark site
  stops talking. That is what makes root-cause ranking a real problem.
- **Red herrings are first-class.** Alarm storms with no impact, flapping elements, planned
  maintenance, and organic traffic surges with real impact but no faulty element all appear in the
  ground truth with `event_class` and `is_customer_impacting`. The model can therefore be trained and
  scored on not paging for them.
- **Impact is observable three ways.** Cell KPIs show degradation or silence, alarms show cascades,
  and sessions show failed or dropped subscriber sessions. Detection can be multi-signal, and its
  latency can be measured against `impact_start_ts`.
- **Raw-feed realism.** The feeds carry string timestamps, emission versus event time, partitioning by
  arrival, at-least-once duplicates, late data and corrupt lines. These defects are realistic, so the
  bronze → silver expectations have something to catch. Each defect is logged, so their precision and
  recall can be measured.
- **Determinism and isolation.** Same seed, same bytes: tested for both batch and streaming when
  `--start` is set. Independent RNG streams per component make counterfactual runs possible.
- **Minimal dependencies.** The package needs only numpy, pandas and pyarrow, and runs on any Python
  ≥ 3.10 driver, including serverless notebooks. It needs no Spark, so the generator is unit-testable
  locally in seconds.
