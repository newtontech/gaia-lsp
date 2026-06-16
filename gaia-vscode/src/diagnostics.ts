import * as path from "node:path";

export interface GaiaPosition {
  line: number;
  character: number;
}

export interface GaiaRange {
  start: GaiaPosition;
  end: GaiaPosition;
}

export interface GaiaDiagnostic {
  code: string;
  message: string;
  severity: string;
  source?: string;
  blocking?: boolean;
  file?: string;
  range?: GaiaRange;
  line?: number;
  column?: number;
}

export interface GaiaCheckResult {
  software: string;
  operation: string;
  path: string;
  ok: boolean;
  blockingDiagnosticCount: number;
  diagnosticCount: number;
  diagnostics: GaiaDiagnostic[];
}

export type DiagnosticSeverityName = "Error" | "Warning" | "Information" | "Hint";

export interface DiagnosticTransfer {
  filePath: string;
  code: string;
  message: string;
  severity: DiagnosticSeverityName;
  source: string;
  range: GaiaRange;
  blocking: boolean;
}

export function parseGaiaCheckOutput(stdout: string): GaiaCheckResult {
  const payload = JSON.parse(stdout) as Partial<GaiaCheckResult>;
  if (payload.software !== "gaia" || payload.operation !== "check") {
    throw new Error("gaia-lsp-tool returned a non-check payload");
  }
  if (!Array.isArray(payload.diagnostics)) {
    throw new Error("gaia-lsp-tool payload is missing diagnostics");
  }
  return {
    software: payload.software,
    operation: payload.operation,
    path: String(payload.path ?? ""),
    ok: Boolean(payload.ok),
    blockingDiagnosticCount: Number(payload.blockingDiagnosticCount ?? 0),
    diagnosticCount: Number(payload.diagnosticCount ?? payload.diagnostics.length),
    diagnostics: payload.diagnostics
  };
}

export function severityName(severity: string, blocking = false): DiagnosticSeverityName {
  const normalized = severity.toLowerCase();
  if (normalized === "error" || blocking) {
    return "Error";
  }
  if (normalized === "warning" || normalized === "warn") {
    return "Warning";
  }
  if (normalized === "info" || normalized === "information") {
    return "Information";
  }
  return "Hint";
}

export function normalizeRange(diagnostic: GaiaDiagnostic): GaiaRange {
  if (diagnostic.range) {
    return clampRange(diagnostic.range);
  }
  const line = Math.max(Number(diagnostic.line ?? 1) - 1, 0);
  const character = Math.max(Number(diagnostic.column ?? 1) - 1, 0);
  return {
    start: { line, character },
    end: { line, character: character + 1 }
  };
}

export function resolveDiagnosticFile(diagnostic: GaiaDiagnostic, fallbackPath: string): string {
  const candidate = diagnostic.file || fallbackPath;
  if (!candidate) {
    return fallbackPath;
  }
  if (path.isAbsolute(candidate)) {
    return path.normalize(candidate);
  }
  const basePath = fallbackPath && path.extname(fallbackPath) ? path.dirname(fallbackPath) : fallbackPath;
  return path.normalize(path.resolve(basePath || process.cwd(), candidate));
}

export function groupDiagnosticsByFile(
  payload: GaiaCheckResult,
  fallbackPath = payload.path
): Record<string, DiagnosticTransfer[]> {
  const grouped: Record<string, DiagnosticTransfer[]> = {};
  for (const diagnostic of payload.diagnostics) {
    const filePath = resolveDiagnosticFile(diagnostic, fallbackPath);
    const item: DiagnosticTransfer = {
      filePath,
      code: diagnostic.code,
      message: diagnostic.message,
      severity: severityName(diagnostic.severity, diagnostic.blocking),
      source: diagnostic.source || "gaia-lsp",
      range: normalizeRange(diagnostic),
      blocking: Boolean(diagnostic.blocking)
    };
    grouped[filePath] = grouped[filePath] || [];
    grouped[filePath].push(item);
  }
  return grouped;
}

export function summarizeCheck(payload: GaiaCheckResult): string {
  const blocking = payload.blockingDiagnosticCount;
  const total = payload.diagnosticCount;
  if (total === 0) {
    return "Gaia LSP: no diagnostics";
  }
  if (blocking > 0) {
    return `Gaia LSP: ${blocking} blocking / ${total} total`;
  }
  return `Gaia LSP: ${total} non-blocking diagnostics`;
}

function clampRange(range: GaiaRange): GaiaRange {
  const start = {
    line: Math.max(Number(range.start.line), 0),
    character: Math.max(Number(range.start.character), 0)
  };
  const end = {
    line: Math.max(Number(range.end.line), start.line),
    character: Math.max(Number(range.end.character), 0)
  };
  if (end.line === start.line && end.character <= start.character) {
    end.character = start.character + 1;
  }
  return { start, end };
}
