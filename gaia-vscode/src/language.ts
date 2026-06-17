export interface GaiaCompletionItem {
  label: string;
  detail?: string;
  documentation?: string;
  insertText?: string;
  kind?: string;
  sortText?: string;
}

export interface GaiaHoverResult {
  contents: string;
}

export interface GaiaExplainResult {
  kind: string;
  symbol?: GaiaCompletionItem;
}

export interface GaiaSymbol {
  name: string;
  kind: string;
  line: number;
  column: number;
}

export interface GaiaLocationItem {
  name: string;
  kind?: string;
  file: string;
  uri?: string;
  line: number;
  column: number;
  endLine?: number;
  endColumn?: number;
}

export function parseCompletionOutput(stdout: string): GaiaCompletionItem[] {
  const payload = JSON.parse(stdout) as { operation?: string; items?: unknown };
  if (payload.operation !== "complete" || !Array.isArray(payload.items)) {
    throw new Error("gaia-lsp-tool returned a non-completion payload");
  }
  return payload.items.map((item) => {
    const candidate = item as Partial<GaiaCompletionItem>;
    return {
      label: String(candidate.label ?? ""),
      detail: candidate.detail,
      documentation: candidate.documentation,
      insertText: candidate.insertText,
      kind: candidate.kind,
      sortText: candidate.sortText
    };
  });
}

export function parseExplainOutput(stdout: string): GaiaExplainResult {
  const payload = JSON.parse(stdout) as {
    operation?: string;
    kind?: unknown;
    symbol?: unknown;
  };
  if (payload.operation !== "explain") {
    throw new Error("gaia-lsp-tool returned a non-explain payload");
  }
  const result: GaiaExplainResult = {
    kind: String(payload.kind ?? "")
  };
  if (payload.symbol && typeof payload.symbol === "object") {
    const candidate = payload.symbol as Partial<GaiaCompletionItem>;
    result.symbol = {
      label: String(candidate.label ?? ""),
      detail: candidate.detail,
      documentation: candidate.documentation,
      insertText: candidate.insertText,
      kind: candidate.kind,
      sortText: candidate.sortText
    };
  }
  return result;
}

export function parseHoverOutput(stdout: string): GaiaHoverResult | null {
  const payload = JSON.parse(stdout) as { operation?: string; contents?: unknown };
  if (payload.operation !== "hover") {
    throw new Error("gaia-lsp-tool returned a non-hover payload");
  }
  if (typeof payload.contents !== "string" || payload.contents.length === 0) {
    return null;
  }
  return { contents: payload.contents };
}

export function parseLocationsOutput(
  stdout: string,
  field: "definitions" | "references"
): GaiaLocationItem[] {
  const payload = JSON.parse(stdout) as {
    operation?: string;
    definitions?: unknown;
    references?: unknown;
  };
  const expectedOperation = field === "definitions" ? "definition" : "references";
  if (payload.operation !== expectedOperation || !Array.isArray(payload[field])) {
    throw new Error(`gaia-lsp-tool returned a non-${expectedOperation} payload`);
  }
  return payload[field].map((location) => {
    const candidate = location as Partial<GaiaLocationItem>;
    return {
      name: String(candidate.name ?? ""),
      kind: candidate.kind,
      file: String(candidate.file ?? ""),
      uri: candidate.uri,
      line: Number(candidate.line ?? 1),
      column: Number(candidate.column ?? 1),
      endLine: candidate.endLine === undefined ? undefined : Number(candidate.endLine),
      endColumn: candidate.endColumn === undefined ? undefined : Number(candidate.endColumn)
    };
  });
}

export function parseSymbolsOutput(stdout: string): GaiaSymbol[] {
  const payload = JSON.parse(stdout) as { operation?: string; symbols?: unknown };
  if (payload.operation !== "symbols" || !Array.isArray(payload.symbols)) {
    throw new Error("gaia-lsp-tool returned a non-symbols payload");
  }
  return payload.symbols.map((symbol) => {
    const candidate = symbol as Partial<GaiaSymbol>;
    return {
      name: String(candidate.name ?? ""),
      kind: String(candidate.kind ?? "knowledge"),
      line: Number(candidate.line ?? 1),
      column: Number(candidate.column ?? 1)
    };
  });
}
