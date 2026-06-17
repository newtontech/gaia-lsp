from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gaia_lsp.analyzer import analyze_path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_FIXTURES = [
    ROOT / "tests" / "fixtures" / "upstream" / "galileo-v0-5-gaia",
    ROOT / "tests" / "fixtures" / "upstream" / "mendel-v0-5-gaia",
]


def test_real_upstream_fixtures_have_no_static_lsp_diagnostics() -> None:
    diagnostics_by_fixture = {
        fixture.name: [item.to_json() for item in analyze_path(fixture)]
        for fixture in UPSTREAM_FIXTURES
    }

    assert diagnostics_by_fixture == {fixture.name: [] for fixture in UPSTREAM_FIXTURES}


def test_gaia_lsp_tool_checks_real_upstream_fixtures_as_agent_gate() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")

    for fixture in UPSTREAM_FIXTURES:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "gaia_lsp.tool",
                "check",
                str(fixture),
                "--fail-on-blocking",
            ],
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )

        payload = json.loads(result.stdout)
        assert result.returncode == 0, result.stdout + result.stderr
        assert payload["ok"] is True
        assert payload["diagnosticCount"] == 0
        assert payload["path"] == str(fixture.resolve())
