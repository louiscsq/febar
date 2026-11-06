"""Write the serialized Genie space (resources/genie/noc_space.geniespace.json) from netmon_pipeline.genie_space.

    python scripts/genie_build_space.py [--catalog telco_netmon_febar_catalog] [--check]

The bundle's `genie_spaces.noc_genie` resource (resources/genie.yml) deploys that file. `--check` exits non-zero
when the committed file is stale (also asserted by tests/test_genie_space.py).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netmon_pipeline import genie_space  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "resources" / "genie" / "noc_space.geniespace.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="telco_netmon_febar_catalog")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = genie_space.to_json(a.catalog)
    if a.check:
        ok = OUT.exists() and OUT.read_text() == text
        print("up to date" if ok else f"stale: run python scripts/genie_build_space.py ({OUT})")
        return 0 if ok else 1
    OUT.write_text(text)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
