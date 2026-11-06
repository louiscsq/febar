# Deployed jobs and their latest runs

Captured 2026-11-06 02:27 UTC from workspace profile `febar` by `scripts/capture_evidence_step4.py`.

Jobs deployed by the bundle (`resources/genai.jobs.yml`, `resources/rca.jobs.yml`) and the latest runs that produced
the evidence. The assistant job has a table-update trigger on `netmon_rca.open_incidents`.

| job | job_id | run_id | start_utc | state | result | minutes | params | trigger |
|---|---|---|---|---|---|---|---|---|
| banksia-genai-lakebase-check | 466782618909608 | 453131979726158 | 2026-11-06 02:25 | TERMINATED | SUCCESS | 0.9 | {} |  |
| banksia-genai-lakebase-check | 466782618909608 | 378333855503771 | 2026-11-06 02:03 | TERMINATED | SUCCESS | 1.1 | {} |  |
| banksia-genai-lakebase-check | 466782618909608 | 261122858413814 | 2026-11-06 00:55 | TERMINATED | SUCCESS | 1.7 | {} |  |
| banksia-genai-assistant | 282645727011052 | 649456465212279 | 2026-11-06 01:58 | TERMINATED | SUCCESS | 4.5 | {"force": null} | {"pause_status": "UNPAUSED", "table_update": {"condition": "ANY_UPDATED", "min_time_between_triggers_seconds": 60, "table_names": ["telco_netmon_febar_catalog.netmon_rca.open_incidents"]}} |
| banksia-genai-assistant | 282645727011052 | 147398191171624 | 2026-11-06 01:05 | TERMINATED | SUCCESS | 1.0 | {"force": null} | {"pause_status": "UNPAUSED", "table_update": {"condition": "ANY_UPDATED", "min_time_between_triggers_seconds": 60, "table_names": ["telco_netmon_febar_catalog.netmon_rca.open_incidents"]}} |
| banksia-genai-assistant | 282645727011052 | 902997043028885 | 2026-11-06 00:48 | TERMINATED | SUCCESS | 4.5 | {"force": null} | {"pause_status": "UNPAUSED", "table_update": {"condition": "ANY_UPDATED", "min_time_between_triggers_seconds": 60, "table_names": ["telco_netmon_febar_catalog.netmon_rca.open_incidents"]}} |
| banksia-genai-build-evalset | 317236717469807 | 55062596122155 | 2026-11-06 00:41 | TERMINATED | SUCCESS | 2.7 | {} |  |
| banksia-genai-build-evalset | 317236717469807 | 333277955294350 | 2026-11-06 00:26 | TERMINATED | SUCCESS | 3.0 | {} |  |
| banksia-genai-build-evalset | 317236717469807 | 170702151745464 | 2026-11-06 00:17 | TERMINATED | SUCCESS | 3.1 | {} |  |
| banksia-genai-build-evalset | 317236717469807 | 920766528334890 | 2026-11-06 00:11 | INTERNAL_ERROR | FAILED | 3.7 | {} |  |
| banksia-genai-evaluate | 834857531423871 | 92178670278783 | 2026-11-06 01:57 | TERMINATED | SUCCESS | 10.4 | {"split": "holdout", "limit": null, "judges": null, "force": null} |  |
| banksia-genai-evaluate | 834857531423871 | 194787246830308 | 2026-11-06 01:35 | TERMINATED | SUCCESS | 13.3 | {"split": "dev", "limit": null, "judges": null, "force": null} |  |
| banksia-genai-evaluate | 834857531423871 | 697469552473363 | 2026-11-06 00:58 | TERMINATED | SUCCESS | 12.7 | {"split": "dev", "limit": null, "judges": null, "force": null} |  |
| banksia-genai-evaluate | 834857531423871 | 177993460844133 | 2026-11-06 00:44 | TERMINATED | CANCELED | 14.4 | {"split": "dev", "limit": null, "judges": null, "force": null} |  |
| banksia-rca-any-alert-metric | 163263809805642 | 995856391141929 | 2026-11-05 23:43 | TERMINATED | SUCCESS | 2.2 | {} |  |

_15 row(s)_
