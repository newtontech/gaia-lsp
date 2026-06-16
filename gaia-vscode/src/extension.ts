import * as childProcess from "node:child_process";
import * as path from "node:path";
import * as vscode from "vscode";

import {
  DiagnosticSeverityName,
  DiagnosticTransfer,
  groupDiagnosticsByFile,
  parseGaiaCheckOutput,
  summarizeCheck
} from "./diagnostics";

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
    vscode.commands.registerCommand("gaia.lsp.showRules", showRuleCatalog),
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
