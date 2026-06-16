import assert from "node:assert/strict";
import test from "node:test";

import {
  groupDiagnosticsByFile,
  normalizeRange,
  parseGaiaCheckOutput,
  severityName,
  summarizeCheck
} from "../src/diagnostics";

test("parses gaia-lsp-tool check payloads", () => {
  const payload = parseGaiaCheckOutput(
    JSON.stringify({
      software: "gaia",
      operation: "check",
      path: "/tmp/pkg/src/pkg/__init__.py",
      ok: false,
      blockingDiagnosticCount: 1,
      diagnosticCount: 1,
      diagnostics: [
        {
          code: "GAIA010",
          message: "claim() requires content",
          severity: "error",
          blocking: true,
          range: {
            start: { line: 2, character: 4 },
            end: { line: 2, character: 4 }
          }
        }
      ]
    })
  );

  assert.equal(payload.diagnostics.length, 1);
  assert.equal(summarizeCheck(payload), "Gaia LSP: 1 blocking / 1 total");
});

test("normalizes severity and ranges for VS Code transfer", () => {
  assert.equal(severityName("warning"), "Warning");
  assert.equal(severityName("unknown"), "Hint");
  assert.equal(severityName("info", true), "Error");

  const range = normalizeRange({
    code: "GAIA001",
    message: "syntax",
    severity: "error",
    range: {
      start: { line: 3, character: 9 },
      end: { line: 3, character: 9 }
    }
  });

  assert.deepEqual(range, {
    start: { line: 3, character: 9 },
    end: { line: 3, character: 10 }
  });
});

test("groups diagnostics by reported file with fallback path", () => {
  const payload = parseGaiaCheckOutput(
    JSON.stringify({
      software: "gaia",
      operation: "check",
      path: "/tmp/pkg",
      ok: false,
      blockingDiagnosticCount: 1,
      diagnosticCount: 2,
      diagnostics: [
        {
          code: "GAIA064",
          message: "missing gaia metadata",
          severity: "error",
          blocking: true,
          file: "/tmp/pkg/pyproject.toml",
          line: 1,
          column: 1
        },
        {
          code: "GAIA050",
          message: "unresolved reference",
          severity: "warning",
          blocking: false,
          file: "src/pkg/__init__.py",
          line: 4,
          column: 8
        }
      ]
    })
  );

  const grouped = groupDiagnosticsByFile(payload, "/tmp/pkg");

  assert.equal(grouped["/tmp/pkg/pyproject.toml"].length, 1);
  assert.equal(grouped["/tmp/pkg/src/pkg/__init__.py"].length, 1);
  assert.equal(grouped["/tmp/pkg/src/pkg/__init__.py"][0].severity, "Warning");
});
