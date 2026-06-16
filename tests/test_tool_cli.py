from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gaia_lsp import cli
from gaia_lsp.tool import check_path, main


def test_check_path_returns_agent_json_envelope(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        """
from gaia.engine.lang import claim, register_prior
claim_obj = claim("A test claim.")
register_prior(claim_obj, 0.5, justification="Neutral external prior.")
""",
        encoding="utf-8",
    )

    payload = check_path(sample)

    assert payload["software"] == "gaia"
    assert payload["operation"] == "check"
    assert payload["ok"] is True
    assert payload["diagnostics"] == []


def test_tool_fails_on_blocking_when_requested(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "bad.py"
    sample.write_text("from gaia.engine.lang import claim\nclaim()\n", encoding="utf-8")

    exit_code = main(["check", str(sample), "--fail-on-blocking"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["diagnostics"][0]["code"] == "GAIA010"


def test_tool_check_reports_error_and_warning_severities(tmp_path: Path) -> None:
    sample = tmp_path / "mixed.py"
    sample.write_text(
        """
from gaia.engine.lang import claim

missing_content = claim()
shortcut_prior = claim("Prior shortcut remains reviewable.", prior=0.5)
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "gaia_lsp.tool",
            "check",
            str(sample),
            "--fail-on-blocking",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    payload = json.loads(result.stdout)
    severities = {item["code"]: item["severity"] for item in payload["diagnostics"]}

    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["blockingDiagnosticCount"] == 1
    assert severities["GAIA010"] == "error"
    assert severities["GAIA011"] == "warning"


def test_lint_cli_json_entrypoint(tmp_path: Path) -> None:
    sample = tmp_path / "bad.py"
    sample.write_text("PRIORS = {'x': 0.5}\n", encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    result = subprocess.run(
        [sys.executable, "-m", "gaia_lsp.cli", "lint", str(sample), "--json"],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 1
    assert json.loads(result.stdout)[0]["code"] == "GAIA033"


def test_direct_lint_cli_text_and_main_branches(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "ok.py"
    sample.write_text(
        "from gaia.engine.lang import claim\nknown = claim('Known')\n",
        encoding="utf-8",
    )

    assert cli.lint_main([str(sample)]) == 0
    assert cli.main([]) == 2
    assert cli.main(["unknown"]) == 2
    with pytest.raises(SystemExit):
        cli.lsp_main([])

    captured = capsys.readouterr()
    assert "usage:" in captured.err


def test_tool_operations_emit_expected_json(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from gaia.engine.lang import claim\nknown = claim('Known')\n",
        encoding="utf-8",
    )

    assert main(["capabilities"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "gaia-lsp"

    assert main(["rules"]) == 0
    rules = json.loads(capsys.readouterr().out)
    assert rules["upstream"]["repository"] == "SiliconEinstein/Gaia"
    assert any(item["label"] == "BetaBinomial" for item in rules["symbols"])

    assert main(["complete", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["items"]

    assert main(["context", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["symbols"][0]["name"] == "known"

    assert main(["context", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["symbols"] == []

    assert main(["hover", str(sample), "--line", "1", "--character", "9"]) == 0
    assert "probability" in json.loads(capsys.readouterr().out)["contents"].lower()

    assert main(["symbols", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["symbols"][0]["kind"] == "claim"
