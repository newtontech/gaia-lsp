export interface GaiaCompletionItem {
  label: string;
  detail?: string;
  documentation?: string;
}

export interface GaiaHoverResult {
  contents: string;
}

export interface GaiaSymbol {
  name: string;
  kind: string;
  line: number;
  column: number;
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
      documentation: candidate.documentation
    };
  });
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
