"""The NOC Genie space definition (netmon_pipeline.genie_space) and its generated, deployed file."""

from __future__ import annotations

import json
import re
from pathlib import Path

from netmon_pipeline import genie_space as g

ROOT = Path(__file__).resolve().parents[1]
CAT = "telco_netmon_febar_catalog"
SPACE_FILE = ROOT / "resources" / "genie" / "noc_space.geniespace.json"


def test_committed_space_file_is_up_to_date():
    assert SPACE_FILE.read_text() == g.to_json(CAT), "run python scripts/genie_build_space.py"


def test_bundle_resource_points_at_the_generated_file():
    y = (ROOT / "resources" / "genie.yml").read_text()
    assert "file_path: genie/noc_space.geniespace.json" in y
    assert "${var.warehouse_id}" in y


def test_space_has_the_contracted_content():
    s = g.build_space(CAT)
    assert s["version"] == 2
    assert len(s["config"]["sample_questions"]) >= 8
    assert len(s["instructions"]["example_question_sqls"]) >= 4
    assert len(s["benchmarks"]["questions"]) >= 10
    assert s["instructions"]["join_specs"]
    text = "".join(s["instructions"]["text_instructions"][0]["content"])
    for word in ("MTTD", "MTTR", "backhaul", "cell site", "AMF", "5 minutes"):
        assert word.lower() in text.lower(), word
    for t in s["data_sources"]["tables"]:
        assert t["description"][0].strip()


def test_ids_are_32_hex_unique_and_lists_sorted():
    s = g.build_space(CAT)
    groups = [s["config"]["sample_questions"], s["instructions"]["example_question_sqls"],
              s["instructions"]["join_specs"], s["benchmarks"]["questions"],
              *s["instructions"]["sql_snippets"].values()]
    ids = []
    for items in groups:
        got = [x["id"] for x in items]
        assert got == sorted(got)
        ids += got
    assert all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids)
    assert len(ids) == len(set(ids))
    tables = [t["identifier"] for t in s["data_sources"]["tables"]]
    assert tables == sorted(tables)


def test_governed_objects_only():
    """Operational tables are region-filtered netmon_noc views; no session (IMSI/MSISDN) or raw ground-truth table."""
    s = g.build_space(CAT)
    tables = [t["identifier"] for t in s["data_sources"]["tables"]]
    for t in tables:
        schema = t.split(".")[1]
        assert schema == "netmon_noc", t
    blob = json.dumps(s).lower()
    for bad in g.FORBIDDEN_IDENTIFIERS:
        assert bad not in blob, bad
    for pii in ("imsi", "msisdn", "subscriber_key"):
        # only mentioned in the refusal instruction, never as a table or column
        assert all(pii not in json.dumps(t).lower() for t in s["data_sources"]["tables"]), pii


def test_every_sql_references_only_space_tables():
    s = g.build_space(CAT)
    allowed = {t["identifier"] for t in s["data_sources"]["tables"]}
    sqls = ["".join(x["sql"]) for x in s["instructions"]["example_question_sqls"]]
    sqls += ["".join(x["answer"][0]["content"]) for x in s["benchmarks"]["questions"]]
    for sql in sqls:
        refs = set(re.findall(rf"{CAT}\.\w+\.\w+", sql))
        assert refs and refs <= allowed, (sql, refs - allowed)


def test_join_aliases_are_space_tables():
    s = g.build_space(CAT)
    allowed = {t["identifier"] for t in s["data_sources"]["tables"]}
    for j in s["instructions"]["join_specs"]:
        assert j["left"]["identifier"] in allowed and j["right"]["identifier"] in allowed
        assert j["sql"][1].startswith("--rt=FROM_RELATIONSHIP_TYPE_")


def test_serving_views_never_read_ground_truth_or_sessions():
    sql = (ROOT / "governance" / "sql" / "05_serving_views.sql").read_text()
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    assert "${eval_schema}" not in body and "silver_sessions" not in body
    views = re.findall(r"CREATE OR REPLACE VIEW \$\{noc_schema\}\.(\w+)", body)
    assert len(views) == 5
    # every view applies the regional row filter
    for chunk in body.split("CREATE OR REPLACE VIEW")[1:]:
        assert "${gov}.region_filter(" in chunk
