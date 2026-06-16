from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from gaia_lsp.analyzer import analyze_path

ROOT = Path(__file__).resolve().parents[1]
GALILEO_FIXTURE = ROOT / "tests" / "fixtures" / "upstream" / "galileo-v0-5-gaia"


def test_real_upstream_galileo_fixture_has_no_static_lsp_diagnostics() -> None:
    diagnostics = analyze_path(GALILEO_FIXTURE)

    assert diagnostics == []


def test_gaia_lsp_tool_checks_real_upstream_fixture_as_agent_gate() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gaia_lsp.tool",
            "check",
            str(GALILEO_FIXTURE),
            "--fail-on-blocking",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["ok"] is True
    assert payload["diagnosticCount"] == 0
    assert payload["path"] == str(GALILEO_FIXTURE.resolve())
