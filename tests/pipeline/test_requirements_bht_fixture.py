import json
from pathlib import Path


def test_bht_requirements_counts():
    """
    Guardrail: the BHT fixture must retain formal requirements with IDs and at least one table-derived requirement.

    - Expect at least 10 REQ-BHT-* items (lines with 'shall' and req id)
    - Expect at least 1 table-derived requirement
    """

    out_dir = Path("data/results/export_trial8/07_requirements_miner/json_output")
    req_path = out_dir / "07_requirements.json"
    assert req_path.exists(), "requirements output missing; run pipeline to populate export_trial8"

    data = json.loads(req_path.read_text())
    reqs = data.get("requirements", [])
    assert reqs, "no requirements found"

    with_ids = [r for r in reqs if str(r.get("requirement_id") or "").startswith("REQ-BHT-")]
    table_reqs = [r for r in reqs if r.get("from") == "table"]

    assert len(with_ids) >= 10, f"expected >=10 REQ-BHT-* requirements, found {len(with_ids)}"
    assert len(table_reqs) >= 1, "expected at least one table-derived requirement"
