from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gaia_lsp import cli
from gaia_lsp.tool import check_path, main


def write_minimal_gaia_package(root: Path) -> Path:
    package = root / "src" / "sample_v0_5"
    package.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """
[project]
name = "sample-v0-5-gaia"
version = "0.1.0"

[tool.gaia]
type = "knowledge-package"
""",
        encoding="utf-8",
    )
    init_py = package / "__init__.py"
    init_py.write_text(
        "from gaia.engine.lang import claim\nknown = claim('Known')\n",
        encoding="utf-8",
    )
    (package / "priors.py").write_text("from gaia.engine.lang import register_prior\n")
    return init_py


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
    assert any(item["code"] == "GAIA010" for item in rules["diagnostics"])

    assert main(["complete", str(sample)]) == 0
    completions = json.loads(capsys.readouterr().out)["items"]
    assert any(
        item["label"] == "from gaia.engine.lang import claim, note, question"
        for item in completions
    )

    assert main(["context", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["symbols"][0]["name"] == "known"

    package_root = tmp_path / "sample-v0-5-gaia"
    init_py = write_minimal_gaia_package(package_root)

    assert main(["context", str(package_root)]) == 0
    context = json.loads(capsys.readouterr().out)
    assert context["package"]["importName"] == "sample_v0_5"
    assert context["query"] == ""
    assert context["symbols"][0]["name"] == "known"
    assert any(item["label"] == "from .priors import *" for item in context["completionItems"])

    assert main(["context", str(package_root), "--query", "register_prior"]) == 0
    focused_context = json.loads(capsys.readouterr().out)
    assert focused_context["query"] == "register_prior"
    assert [item["label"] for item in focused_context["completionItems"]] == ["register_prior"]
    assert focused_context["symbols"] == []
    assert focused_context["explanations"][0]["kind"] == "symbol"
    assert focused_context["explanations"][0]["symbol"]["label"] == "register_prior"

    assert main(["context", str(init_py)]) == 0
    assert json.loads(capsys.readouterr().out)["package"]["projectName"] == "sample-v0-5-gaia"

    assert main(["hover", str(sample), "--line", "1", "--character", "9"]) == 0
    assert "probability" in json.loads(capsys.readouterr().out)["contents"].lower()

    assert main(["symbols", str(sample)]) == 0
    assert json.loads(capsys.readouterr().out)["symbols"][0]["kind"] == "claim"

    assert main(["definition", str(init_py), "--line", "1", "--character", "1"]) == 0
    definition_payload = json.loads(capsys.readouterr().out)
    assert definition_payload["operation"] == "definition"
    assert definition_payload["definitions"][0]["name"] == "known"

    assert main(["references", str(init_py), "--line", "1", "--character", "1"]) == 0
    references_payload = json.loads(capsys.readouterr().out)
    assert references_payload["operation"] == "references"
    assert references_payload["references"]

    assert main(["workspace-symbols", str(package_root), "--query", "known"]) == 0
    workspace_payload = json.loads(capsys.readouterr().out)
    assert workspace_payload["operation"] == "workspace-symbols"
    assert workspace_payload["symbols"][0]["name"] == "known"

    assert main(["folding", str(init_py)]) == 0
    assert json.loads(capsys.readouterr().out)["operation"] == "folding"

    assert main(["links", str(init_py)]) == 0
    assert json.loads(capsys.readouterr().out)["operation"] == "links"

    assert main(["rename", str(init_py), "renamed_known", "--line", "1", "--character", "1"]) == 0
    rename_payload = json.loads(capsys.readouterr().out)
    assert rename_payload["operation"] == "rename"
    assert rename_payload["newName"] == "renamed_known"

    assert main(["semantic-tokens", str(init_py)]) == 0
    semantic_payload = json.loads(capsys.readouterr().out)
    assert semantic_payload["operation"] == "semantic-tokens"
    assert semantic_payload["tokens"]


def test_tool_manual_and_explain_commands_emit_language_reference(
    tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from gaia.engine.lang import claim\nknown = claim('Known')\n",
        encoding="utf-8",
    )

    assert main(["manual"]) == 0
    manual = capsys.readouterr().out
    assert "# Gaia LSP Language Manual" in manual
    assert "## Authoring Surface" in manual
    assert "gaia-lsp-tool hover" in manual
    assert "GAIA010" in manual

    assert main(["manual", "--format", "json", "--section", "diagnostics"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "manual"
    assert [section["id"] for section in payload["sections"]] == ["diagnostics"]

    assert main(["explain", "claim"]) == 0
    claim_payload = json.loads(capsys.readouterr().out)
    assert claim_payload["operation"] == "explain"
    assert claim_payload["kind"] == "symbol"
    assert claim_payload["symbol"]["label"] == "claim"

    assert main(["explain", "GAIA010"]) == 0
    diagnostic_payload = json.loads(capsys.readouterr().out)
    assert diagnostic_payload["kind"] == "diagnostic"
    assert diagnostic_payload["diagnostic"]["severity"] == "error"

    assert main(["hover", str(sample), "--line", "1", "--character", "9"]) == 0
    assert "claim(content" in json.loads(capsys.readouterr().out)["contents"]


def test_check_missing_file_emits_machine_readable_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "absent.py"

    exit_code = main(["check", str(missing)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["operation"] == "check"
    assert payload["ok"] is False
    assert payload["toolVersion"]
    assert payload["error"]["kind"] == "missing_file"
    assert payload["error"]["message"]
    assert str(missing) in payload["path"]


def test_hover_missing_file_emits_machine_readable_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    missing = tmp_path / "absent.py"

    exit_code = main(["hover", str(missing), "--line", "2", "--character", "3"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error"]["kind"] == "missing_file"
    assert payload["line"] == 2
    assert payload["character"] == 3


def test_file_only_operation_on_directory_emits_not_a_file(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(["hover", str(tmp_path), "--line", "0", "--character", "0"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error"]["kind"] == "not_a_file"


def test_non_utf8_file_emits_encoding_error(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    binary = tmp_path / "binary.py"
    binary.write_bytes(b"\xff\xfe not valid utf-8 \x00\x00")

    exit_code = main(["hover", str(binary), "--line", "1", "--character", "1"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["error"]["kind"] == "encoding_error"


def test_check_non_utf8_file_remains_machine_readable(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    binary = tmp_path / "binary.py"
    binary.write_bytes(b"\xff\xfe not valid utf-8 \x00\x00")

    exit_code = main(["check", str(binary), "--fail-on-blocking"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"]["kind"] in {"encoding_error", "io_error"}


def test_explain_unknown_topic_emits_machine_readable_error(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(["explain", "NotARealSymbol"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["operation"] == "explain"
    assert payload["ok"] is False
    assert payload["error"]["kind"] == "unknown_topic"


def test_success_envelopes_carry_ok_and_tool_version(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from gaia.engine.lang import claim\nknown = claim('Known')\n",
        encoding="utf-8",
    )
    operations = [
        ["check", str(sample)],
        ["context", str(sample)],
        ["complete", str(sample)],
        ["symbols", str(sample)],
        ["hover", str(sample), "--line", "1", "--character", "9"],
        ["rules"],
        ["manual", "--format", "json"],
        ["explain", "claim"],
    ]

    for argv in operations:
        assert main(argv) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload.get("ok") is True, argv
        assert payload.get("toolVersion"), argv
