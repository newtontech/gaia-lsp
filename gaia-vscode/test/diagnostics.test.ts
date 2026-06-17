import assert from "node:assert/strict";
import test from "node:test";

import {
  groupDiagnosticsByFile,
  importInsertionLine,
  normalizeRange,
  parseGaiaCheckOutput,
  severityName,
  suggestedGaiaImport,
  summarizeCheck
} from "../src/diagnostics";
import {
  parseCompletionOutput,
  parseLocationsOutput,
  parseExplainOutput,
  parseHoverOutput,
  parseSymbolsOutput
} from "../src/language";

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

test("parses language capability payloads from gaia-lsp-tool", () => {
  const completions = parseCompletionOutput(
    JSON.stringify({
      software: "gaia",
      operation: "complete",
      items: [
        {
          label: "from gaia.engine.lang import claim, note, question",
          detail: "Core Gaia knowledge import",
          documentation: "Import claim(), note(), and question().",
          insertText: "from gaia.engine.lang import claim, note, question",
          kind: "snippet",
          sortText: "000"
        },
        { label: "claim", detail: "claim(content)", kind: "function" }
      ]
    })
  );
  const hover = parseHoverOutput(
    JSON.stringify({
      software: "gaia",
      operation: "hover",
      contents: "Declare a falsifiable Gaia claim."
    })
  );
  const symbols = parseSymbolsOutput(
    JSON.stringify({
      software: "gaia",
      operation: "symbols",
      symbols: [{ name: "aristotle_model", kind: "claim", line: 20, column: 1 }]
    })
  );

  assert.equal(completions[0].label, "from gaia.engine.lang import claim, note, question");
  assert.equal(completions[0].insertText, "from gaia.engine.lang import claim, note, question");
  assert.equal(completions[0].kind, "snippet");
  assert.equal(completions[1].label, "claim");
  assert.equal(hover?.contents, "Declare a falsifiable Gaia claim.");
  assert.equal(symbols[0].name, "aristotle_model");
});

test("parses explain payloads for signature help", () => {
  const explain = parseExplainOutput(
    JSON.stringify({
      operation: "explain",
      kind: "symbol",
      symbol: {
        label: "claim",
        detail: "claim(content, proposition=None)",
        documentation: "Declare a falsifiable Gaia claim."
      }
    })
  );

  assert.equal(explain.kind, "symbol");
  assert.equal(explain.symbol?.label, "claim");
  assert.equal(explain.symbol?.detail, "claim(content, proposition=None)");
});

test("extracts GAIA015 import quick fixes", () => {
  const diagnostic = {
    code: "GAIA015",
    message: "claim() looks like Gaia DSL but is not imported; add `from gaia.engine.lang import claim`.",
    severity: "error"
  };

  assert.equal(suggestedGaiaImport(diagnostic), "from gaia.engine.lang import claim");
  assert.equal(
    importInsertionLine([
      '"""Module docs."""',
      "",
      "import os",
      "from gaia.engine.lang import note",
      "",
      "claim('Missing import')"
    ].join("\n")),
    4
  );
  assert.equal(importInsertionLine("claim('Missing import')\n"), 0);
});

test("parses definition and references location payloads", () => {
  const locations = parseLocationsOutput(
    JSON.stringify({
      operation: "definition",
      definitions: [
        {
          name: "daily_observation",
          file: "/tmp/pkg/src/pkg/__init__.py",
          line: 4,
          column: 1,
          endLine: 4,
          endColumn: 18
        }
      ]
    }),
    "definitions"
  );

  assert.equal(locations[0].name, "daily_observation");
  assert.equal(locations[0].file, "/tmp/pkg/src/pkg/__init__.py");
  assert.equal(locations[0].line, 4);
});
