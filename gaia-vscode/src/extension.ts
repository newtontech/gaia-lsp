import * as childProcess from "node:child_process";
import * as path from "node:path";
import * as vscode from "vscode";

import {
  DiagnosticSeverityName,
  DiagnosticTransfer,
  groupDiagnosticsByFile,
  importInsertionLine,
  parseGaiaCheckOutput,
  suggestedGaiaImport,
  summarizeCheck
} from "./diagnostics";
import {
  GaiaCompletionItem,
  GaiaHoverResult,
  GaiaLocationItem,
  GaiaSymbol,
  parseCompletionOutput,
  parseExplainOutput,
  parseHoverOutput,
  parseLocationsOutput,
  parseSymbolsOutput
} from "./language";

interface ExtensionSettings {
  toolPath: string;
  toolArgs: string[];
  checkOnSave: boolean;
  checkOnOpen: boolean;
  failOnBlocking: boolean;
  maxBuffer: number;
  trace: "off" | "messages";
}

interface ToolResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

let diagnostics: vscode.DiagnosticCollection;
let output: vscode.OutputChannel;
let statusBar: vscode.StatusBarItem;
let lastDiagnosticUris = new Set<string>();
const gaiaDocumentSelector: vscode.DocumentSelector = [{ language: "python", scheme: "file" }];

export function activate(context: vscode.ExtensionContext): void {
  diagnostics = vscode.languages.createDiagnosticCollection("gaia-lsp");
  output = vscode.window.createOutputChannel("Gaia LSP");
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 25);
  statusBar.name = "Gaia LSP";
  statusBar.command = "gaia.lsp.checkFile";
  statusBar.text = "$(beaker) Gaia";
  statusBar.tooltip = "Run Gaia LSP diagnostics";
  statusBar.show();

  context.subscriptions.push(
    diagnostics,
    output,
    statusBar,
    vscode.commands.registerCommand("gaia.lsp.checkFile", checkCurrentFile),
    vscode.commands.registerCommand("gaia.lsp.checkWorkspace", checkWorkspace),
    vscode.commands.registerCommand("gaia.lsp.showContext", showAuthoringContext),
    vscode.commands.registerCommand("gaia.lsp.showManual", showLanguageManual),
    vscode.commands.registerCommand("gaia.lsp.showRules", showRuleCatalog),
    vscode.languages.registerCompletionItemProvider(
      gaiaDocumentSelector,
      {
        provideCompletionItems: provideGaiaCompletions
      },
      ".",
      "("
    ),
    vscode.languages.registerHoverProvider(gaiaDocumentSelector, {
      provideHover: provideGaiaHover
    }),
    vscode.languages.registerDefinitionProvider(gaiaDocumentSelector, {
      provideDefinition: provideGaiaDefinition
    }),
    vscode.languages.registerReferenceProvider(gaiaDocumentSelector, {
      provideReferences: provideGaiaReferences
    }),
    vscode.languages.registerSignatureHelpProvider(
      gaiaDocumentSelector,
      {
        provideSignatureHelp: provideGaiaSignatureHelp
      },
      "(",
      ","
    ),
    vscode.languages.registerCodeActionsProvider(
      gaiaDocumentSelector,
      {
        provideCodeActions: provideGaiaCodeActions
      },
      {
        providedCodeActionKinds: [vscode.CodeActionKind.QuickFix]
      }
    ),
    vscode.languages.registerDocumentSymbolProvider(gaiaDocumentSelector, {
      provideDocumentSymbols: provideGaiaDocumentSymbols
    }),
    vscode.workspace.onDidSaveTextDocument((document) => {
      if (readSettings().checkOnSave && isGaiaCandidate(document)) {
        void checkDocument(document);
      }
    }),
    vscode.workspace.onDidOpenTextDocument((document) => {
      if (readSettings().checkOnOpen && isGaiaCandidate(document)) {
        void checkDocument(document);
      }
    })
  );

  for (const document of vscode.workspace.textDocuments) {
    if (readSettings().checkOnOpen && isGaiaCandidate(document)) {
      void checkDocument(document);
    }
  }
}

export function deactivate(): void {
  lastDiagnosticUris = new Set<string>();
}

async function checkCurrentFile(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== "file") {
    void vscode.window.showWarningMessage("Open a Gaia Python file before running diagnostics.");
    return;
  }
  await checkDocument(editor.document);
}

async function checkWorkspace(uri?: vscode.Uri): Promise<void> {
  let target = uri;
  if (!target) {
    const folder = await selectWorkspaceFolder();
    target = folder?.uri;
  }
  if (!target) {
    void vscode.window.showWarningMessage("Open a workspace folder before running Gaia diagnostics.");
    return;
  }
  await checkTarget(target);
}

async function checkDocument(document: vscode.TextDocument): Promise<void> {
  if (document.uri.scheme !== "file") {
    return;
  }
  await checkTarget(document.uri);
}

async function checkTarget(target: vscode.Uri): Promise<void> {
  const settings = readSettings();
  setBusy(target);
  try {
    const result = await runGaiaTool(["check", target.fsPath], target, settings);
    const payload = parseGaiaCheckOutput(result.stdout);
    clearPreviousDiagnostics();
    applyDiagnostics(payload, target);

    const summary = summarizeCheck(payload);
    statusBar.text = payload.ok ? "$(pass) Gaia" : "$(error) Gaia";
    statusBar.tooltip = summary;
    trace(settings, `${summary} for ${target.fsPath}`);
    if (result.stderr.trim()) {
      trace(settings, result.stderr.trim());
    }
    if (settings.failOnBlocking && payload.blockingDiagnosticCount > 0) {
      void vscode.window.showErrorMessage(summary);
    }
  } catch (error) {
    diagnostics.delete(target);
    statusBar.text = "$(warning) Gaia";
    statusBar.tooltip = error instanceof Error ? error.message : String(error);
    output.appendLine(statusBar.tooltip);
    void vscode.window.showWarningMessage(statusBar.tooltip);
  }
}

async function showRuleCatalog(): Promise<void> {
  const settings = readSettings();
  const anchor = vscode.window.activeTextEditor?.document.uri;
  try {
    const result = await runGaiaTool(["rules"], anchor, settings);
    const formatted = JSON.stringify(JSON.parse(result.stdout), null, 2);
    const document = await vscode.workspace.openTextDocument({
      content: formatted,
      language: "json"
    });
    await vscode.window.showTextDocument(document, { preview: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(message);
    void vscode.window.showWarningMessage(message);
  }
}

async function showLanguageManual(): Promise<void> {
  const settings = readSettings();
  const anchor = vscode.window.activeTextEditor?.document.uri;
  try {
    const result = await runGaiaTool(["manual", "--format", "markdown"], anchor, settings);
    await showMarkdownDocument(result.stdout);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(message);
    void vscode.window.showWarningMessage(message);
  }
}

async function showAuthoringContext(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.uri.scheme !== "file") {
    void vscode.window.showWarningMessage("Open a Gaia Python file before requesting context.");
    return;
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(["context", editor.document.uri.fsPath], editor.document.uri, settings);
    await showJsonDocument(result.stdout);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    output.appendLine(message);
    void vscode.window.showWarningMessage(message);
  }
}

async function provideGaiaCompletions(
  document: vscode.TextDocument
): Promise<vscode.CompletionItem[]> {
  if (!isGaiaCandidate(document)) {
    return [];
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(["complete", document.uri.fsPath], document.uri, settings);
    return parseCompletionOutput(result.stdout).map(toVsCodeCompletionItem);
  } catch (error) {
    trace(settings, providerErrorMessage("completion", error));
    return [];
  }
}

async function provideGaiaHover(
  document: vscode.TextDocument,
  position: vscode.Position
): Promise<vscode.Hover | null> {
  if (!isGaiaCandidate(document)) {
    return null;
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(
      [
        "hover",
        document.uri.fsPath,
        "--line",
        String(position.line),
        "--character",
        String(position.character)
      ],
      document.uri,
      settings
    );
    const hover = parseHoverOutput(result.stdout);
    return hover ? toVsCodeHover(hover) : null;
  } catch (error) {
    trace(settings, providerErrorMessage("hover", error));
    return null;
  }
}

async function provideGaiaDefinition(
  document: vscode.TextDocument,
  position: vscode.Position
): Promise<vscode.Location[]> {
  if (!isGaiaCandidate(document)) {
    return [];
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(
      [
        "definition",
        document.uri.fsPath,
        "--line",
        String(position.line),
        "--character",
        String(position.character)
      ],
      document.uri,
      settings
    );
    return parseLocationsOutput(result.stdout, "definitions").map(toVsCodeLocation);
  } catch (error) {
    trace(settings, providerErrorMessage("definition", error));
    return [];
  }
}

async function provideGaiaReferences(
  document: vscode.TextDocument,
  position: vscode.Position,
  _context: vscode.ReferenceContext
): Promise<vscode.Location[]> {
  if (!isGaiaCandidate(document)) {
    return [];
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(
      [
        "references",
        document.uri.fsPath,
        "--line",
        String(position.line),
        "--character",
        String(position.character)
      ],
      document.uri,
      settings
    );
    return parseLocationsOutput(result.stdout, "references").map(toVsCodeLocation);
  } catch (error) {
    trace(settings, providerErrorMessage("references", error));
    return [];
  }
}

async function provideGaiaSignatureHelp(
  document: vscode.TextDocument,
  position: vscode.Position
): Promise<vscode.SignatureHelp | null> {
  if (!isGaiaCandidate(document)) {
    return null;
  }
  const symbol = functionNameBeforeCall(document, position);
  if (!symbol) {
    return null;
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(["explain", symbol], document.uri, settings);
    const explain = parseExplainOutput(result.stdout);
    if (explain.kind !== "symbol" || !explain.symbol?.detail) {
      return null;
    }
    const help = new vscode.SignatureHelp();
    const signature = new vscode.SignatureInformation(
      explain.symbol.detail,
      explain.symbol.documentation
        ? new vscode.MarkdownString(explain.symbol.documentation)
        : undefined
    );
    signature.parameters = signatureParameters(explain.symbol.detail);
    help.signatures = [signature];
    help.activeSignature = 0;
    help.activeParameter = activeParameterIndex(document, position);
    return help;
  } catch (error) {
    trace(settings, providerErrorMessage("signatureHelp", error));
    return null;
  }
}

async function provideGaiaDocumentSymbols(
  document: vscode.TextDocument
): Promise<vscode.DocumentSymbol[]> {
  if (!isGaiaCandidate(document)) {
    return [];
  }
  const settings = readSettings();
  try {
    const result = await runGaiaTool(["symbols", document.uri.fsPath], document.uri, settings);
    return parseSymbolsOutput(result.stdout).map(toVsCodeDocumentSymbol);
  } catch (error) {
    trace(settings, providerErrorMessage("symbols", error));
    return [];
  }
}

async function provideGaiaCodeActions(
  document: vscode.TextDocument,
  _range: vscode.Range,
  context: vscode.CodeActionContext
): Promise<vscode.CodeAction[]> {
  if (!isGaiaCandidate(document)) {
    return [];
  }
  const actions: vscode.CodeAction[] = [];
  for (const diagnostic of context.diagnostics) {
    const importStatement = suggestedGaiaImport({
      code: String(diagnostic.code ?? ""),
      message: diagnostic.message
    });
    if (!importStatement || document.getText().includes(importStatement)) {
      continue;
    }
    const action = new vscode.CodeAction(
      `Add Gaia import: ${importStatement}`,
      vscode.CodeActionKind.QuickFix
    );
    action.diagnostics = [diagnostic];
    action.isPreferred = true;
    const edit = new vscode.WorkspaceEdit();
    const line = importInsertionLine(document.getText());
    edit.insert(document.uri, new vscode.Position(line, 0), `${importStatement}\n`);
    action.edit = edit;
    actions.push(action);
  }
  return actions;
}

function functionNameBeforeCall(document: vscode.TextDocument, position: vscode.Position): string | null {
  const currentLine = document.lineAt(position.line).text.slice(0, position.character);
  const match = currentLine.match(/([A-Za-z_][A-Za-z0-9_]*)\([^()]*$/);
  return match ? match[1] : null;
}

function signatureParameters(detail: string): vscode.ParameterInformation[] {
  const start = detail.indexOf("(");
  const end = detail.lastIndexOf(")");
  if (start < 0 || end <= start) {
    return [];
  }
  return detail
    .slice(start + 1, end)
    .split(",")
    .map((parameter) => parameter.trim())
    .filter((parameter) => parameter.length > 0)
    .map((parameter) => new vscode.ParameterInformation(parameter));
}

function activeParameterIndex(document: vscode.TextDocument, position: vscode.Position): number {
  const currentLine = document.lineAt(position.line).text.slice(0, position.character);
  const open = currentLine.lastIndexOf("(");
  if (open < 0) {
    return 0;
  }
  return currentLine.slice(open + 1).split(",").length - 1;
}

function applyDiagnostics(payload: ReturnType<typeof parseGaiaCheckOutput>, target: vscode.Uri): void {
  const grouped = groupDiagnosticsByFile(payload, payload.path || target.fsPath);
  for (const [filePath, items] of Object.entries(grouped)) {
    const uri = vscode.Uri.file(filePath);
    diagnostics.set(uri, items.map(toVsCodeDiagnostic));
    lastDiagnosticUris.add(uri.toString());
  }
  if (Object.keys(grouped).length === 0 && target.fsPath && path.extname(target.fsPath)) {
    diagnostics.delete(target);
  }
}

function toVsCodeCompletionItem(item: GaiaCompletionItem): vscode.CompletionItem {
  const completion = new vscode.CompletionItem(item.label, toVsCodeCompletionKind(item.kind));
  completion.detail = item.detail;
  completion.documentation = item.documentation
    ? new vscode.MarkdownString(item.documentation)
    : undefined;
  completion.sortText = item.sortText;
  if (item.insertText) {
    completion.insertText = item.kind === "snippet"
      ? new vscode.SnippetString(item.insertText)
      : item.insertText;
  }
  return completion;
}

function toVsCodeCompletionKind(kind: string | undefined): vscode.CompletionItemKind {
  switch (kind) {
    case "class":
      return vscode.CompletionItemKind.Class;
    case "module":
      return vscode.CompletionItemKind.Module;
    case "snippet":
      return vscode.CompletionItemKind.Snippet;
    case "variable":
      return vscode.CompletionItemKind.Variable;
    default:
      return vscode.CompletionItemKind.Function;
  }
}

function toVsCodeHover(hover: GaiaHoverResult): vscode.Hover {
  return new vscode.Hover(new vscode.MarkdownString(hover.contents));
}

function toVsCodeLocation(item: GaiaLocationItem): vscode.Location {
  const line = Math.max(item.line - 1, 0);
  const character = Math.max(item.column - 1, 0);
  const endLine = Math.max((item.endLine ?? item.line) - 1, line);
  const endCharacter = Math.max((item.endColumn ?? item.column + item.name.length) - 1, character + 1);
  return new vscode.Location(
    vscode.Uri.file(item.file),
    new vscode.Range(
      new vscode.Position(line, character),
      new vscode.Position(endLine, endCharacter)
    )
  );
}

function toVsCodeDocumentSymbol(symbol: GaiaSymbol): vscode.DocumentSymbol {
  const line = Math.max(symbol.line - 1, 0);
  const character = Math.max(symbol.column - 1, 0);
  const range = new vscode.Range(
    new vscode.Position(line, character),
    new vscode.Position(line, character + Math.max(symbol.name.length, 1))
  );
  return new vscode.DocumentSymbol(
    symbol.name,
    symbol.kind,
    toVsCodeSymbolKind(symbol.kind),
    range,
    range
  );
}

function toVsCodeSymbolKind(kind: string): vscode.SymbolKind {
  switch (kind) {
    case "claim":
      return vscode.SymbolKind.Object;
    case "note":
      return vscode.SymbolKind.String;
    case "question":
      return vscode.SymbolKind.Event;
    case "distribution":
      return vscode.SymbolKind.Number;
    case "action":
    case "relation":
      return vscode.SymbolKind.Method;
    default:
      return vscode.SymbolKind.Variable;
  }
}

function toVsCodeDiagnostic(item: DiagnosticTransfer): vscode.Diagnostic {
  const diagnostic = new vscode.Diagnostic(
    new vscode.Range(
      new vscode.Position(item.range.start.line, item.range.start.character),
      new vscode.Position(item.range.end.line, item.range.end.character)
    ),
    item.message,
    toVsCodeSeverity(item.severity)
  );
  diagnostic.code = item.code;
  diagnostic.source = item.source;
  return diagnostic;
}

async function showJsonDocument(stdout: string): Promise<void> {
  const formatted = JSON.stringify(JSON.parse(stdout), null, 2);
  const document = await vscode.workspace.openTextDocument({
    content: formatted,
    language: "json"
  });
  await vscode.window.showTextDocument(document, { preview: true });
}

async function showMarkdownDocument(stdout: string): Promise<void> {
  const document = await vscode.workspace.openTextDocument({
    content: stdout,
    language: "markdown"
  });
  await vscode.window.showTextDocument(document, { preview: true });
}

function toVsCodeSeverity(severity: DiagnosticSeverityName): vscode.DiagnosticSeverity {
  switch (severity) {
    case "Error":
      return vscode.DiagnosticSeverity.Error;
    case "Warning":
      return vscode.DiagnosticSeverity.Warning;
    case "Information":
      return vscode.DiagnosticSeverity.Information;
    case "Hint":
      return vscode.DiagnosticSeverity.Hint;
  }
}

function runGaiaTool(
  args: string[],
  target: vscode.Uri | undefined,
  settings: ExtensionSettings
): Promise<ToolResult> {
  const cwd = target ? workingDirectoryFor(target) : undefined;
  const commandArgs = [...settings.toolArgs, ...args];
  trace(settings, `$ ${settings.toolPath} ${commandArgs.join(" ")}`);

  return new Promise((resolve, reject) => {
    childProcess.execFile(
      settings.toolPath,
      commandArgs,
      { cwd, maxBuffer: settings.maxBuffer },
      (error, stdout, stderr) => {
        const exitCode = typeof error?.code === "number" ? error.code : null;
        if (error && !stdout) {
          reject(new Error(stderr.trim() || error.message));
          return;
        }
        resolve({ stdout, stderr, exitCode });
      }
    );
  });
}

function workingDirectoryFor(uri: vscode.Uri): string {
  const folder = vscode.workspace.getWorkspaceFolder(uri);
  if (folder) {
    return folder.uri.fsPath;
  }
  return path.extname(uri.fsPath) ? path.dirname(uri.fsPath) : uri.fsPath;
}

async function selectWorkspaceFolder(): Promise<vscode.WorkspaceFolder | undefined> {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return undefined;
  }
  if (folders.length === 1) {
    return folders[0];
  }
  return vscode.window.showWorkspaceFolderPick({
    placeHolder: "Select a workspace folder for Gaia diagnostics"
  });
}

function clearPreviousDiagnostics(): void {
  for (const uri of lastDiagnosticUris) {
    diagnostics.delete(vscode.Uri.parse(uri));
  }
  lastDiagnosticUris.clear();
}

function isGaiaCandidate(document: vscode.TextDocument): boolean {
  if (document.uri.scheme !== "file") {
    return false;
  }
  const basename = path.basename(document.uri.fsPath);
  return document.languageId === "python" || basename === "pyproject.toml" || basename === "references.json";
}

function readSettings(): ExtensionSettings {
  const config = vscode.workspace.getConfiguration("gaiaLsp");
  const configuredArgs = config.get<unknown[]>("toolArgs", []);
  const toolArgs = configuredArgs.filter((item): item is string => typeof item === "string");
  const maxBufferMb = Math.min(Math.max(config.get<number>("maxBufferMb", 16), 1), 256);
  const traceSetting = config.get<string>("trace", "off") === "messages" ? "messages" : "off";
  return {
    toolPath: config.get<string>("toolPath", "gaia-lsp-tool"),
    toolArgs,
    checkOnSave: config.get<boolean>("checkOnSave", true),
    checkOnOpen: config.get<boolean>("checkOnOpen", false),
    failOnBlocking: config.get<boolean>("failOnBlocking", false),
    maxBuffer: maxBufferMb * 1024 * 1024,
    trace: traceSetting
  };
}

function setBusy(target: vscode.Uri): void {
  statusBar.text = "$(sync~spin) Gaia";
  statusBar.tooltip = `Checking ${target.fsPath}`;
}

function trace(settings: ExtensionSettings, message: string): void {
  if (settings.trace === "messages") {
    output.appendLine(message);
  }
}

function providerErrorMessage(provider: string, error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  return `Gaia LSP ${provider} provider failed: ${message}`;
}
