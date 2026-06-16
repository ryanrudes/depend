const cp = require("child_process");
const path = require("path");
const vscode = require("vscode");

const HOVER_WORD_PATTERN = /[A-Za-z_][A-Za-z0-9_.\[\]]*/;
const HOVER_PREFETCH_DELAY_MS = 25;
const HOVER_PREFETCH_WAIT_MS = 100;
const hoverCacheByUri = new Map();
const hoverSessionsByKey = new Map();
const hoverPrefetchTimersByKey = new Map();


function activate(context) {
  const provider = vscode.languages.registerHoverProvider("python", {
    provideHover(document, position) {
      return provideDependHover(document, position);
    },
  });
  context.subscriptions.push(provider);
  context.subscriptions.push(
    vscode.window.onDidChangeActiveTextEditor((editor) => {
      if (editor) {
        scheduleHoverPrefetch(editor.document, editor.selection.active);
      }
    }),
  );
  context.subscriptions.push(
    vscode.window.onDidChangeTextEditorSelection((event) => {
      const selection = event.selections[0];
      if (selection) {
        scheduleHoverPrefetch(event.textEditor.document, selection.active);
      }
    }),
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((event) => {
      const activeEditor = vscode.window.activeTextEditor;
      if (activeEditor && activeEditor.document.uri.toString() === event.document.uri.toString()) {
        clearHoverPrefetchTimers(activeEditor.document.uri.toString());
        scheduleHoverPrefetch(activeEditor.document, activeEditor.selection.active);
      }
    }),
  );
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((document) => {
      if (document.uri.scheme === "file") {
        clearHoverPrefetchTimers(document.uri.toString());
        hoverCacheByUri.delete(document.uri.toString());
      }
    }),
  );
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("dependHover")) {
        disposeHoverState();
      }
    }),
  );
  context.subscriptions.push({ dispose: disposeHoverState });

  const activeEditor = vscode.window.activeTextEditor;
  if (activeEditor) {
    scheduleHoverPrefetch(activeEditor.document, activeEditor.selection.active);
  }
}


async function provideDependHover(document, position) {
  const env = resolveHoverEnvironment(document);
  if (env === null) {
    return undefined;
  }
  const diagnostics = collectRelevantDiagnostics(document, position);
  const cache = getDocumentHoverCache(document);
  const cacheKey = buildHoverCacheKey(document, position, env.pythonCommand, env.mypyConfig, env.scriptPath);
  const existingEntry = cache.entries.get(cacheKey);
  const payloadPromise = primeHoverPayload(
    document,
    position,
    env.pythonCommand,
    env.timeoutMs,
    env.workspaceFolderPath,
    env.scriptPath,
    env.mypyConfig,
  );
  let payload = existingEntry && existingEntry.ready ? existingEntry.payload : undefined;

  if (!payload && diagnostics.length === 0) {
    if (existingEntry && existingEntry.promise) {
      payload = await existingEntry.promise;
    } else {
      payload = await waitForHoverPayload(payloadPromise, HOVER_PREFETCH_WAIT_MS);
    }
  }

  const hover = new vscode.MarkdownString(undefined, true);
  let hasContent = false;

  if (payload && payload.ok && payload.computed_type) {
    hover.appendMarkdown("**depend computed type**\n\n");
    hover.appendCodeblock(payload.computed_type, "python");
    if (payload.kind) {
      hover.appendMarkdown(`\n\nKind: \`${escapeMarkdown(payload.kind)}\``);
    }
    if (payload.detail) {
      hover.appendMarkdown(`\n\n${escapeMarkdown(payload.detail)}`);
    }
    if (payload.base_type && payload.base_type !== payload.computed_type) {
      hover.appendMarkdown(`\n\nBase: \`${escapeMarkdown(payload.base_type)}\``);
    }
    hasContent = true;
  }

  if (diagnostics.length > 0) {
    if (hasContent) {
      hover.appendMarkdown("\n\n");
    }
    hover.appendMarkdown(`**${diagnostics.length === 1 ? "Problem" : "Problems"}**\n`);
    for (const diagnostic of diagnostics) {
      const message = escapeMarkdown(normalizeWhitespace(diagnostic.message));
      const severity = diagnosticSeverityLabel(diagnostic.severity);
      const source = diagnostic.source ? ` (${escapeMarkdown(diagnostic.source)})` : "";
      hover.appendMarkdown(`\n- ${severity}${source}: ${message}`);
    }
    hasContent = true;
  }

  if (!hasContent) {
    return undefined;
  }

  return new vscode.Hover(hover);
}


function scheduleHoverPrefetch(document, position) {
  const env = resolveHoverEnvironment(document);
  if (env === null) {
    return;
  }

  const uriKey = document.uri.toString();
  clearHoverPrefetchTimers(uriKey);
  const timerKey = buildHoverPrefetchTimerKey(document, position, env);
  const timer = setTimeout(() => {
    hoverPrefetchTimersByKey.delete(timerKey);
    void primeHoverPayload(
      document,
      position,
      env.pythonCommand,
      env.timeoutMs,
      env.workspaceFolderPath,
      env.scriptPath,
      env.mypyConfig,
    );
  }, HOVER_PREFETCH_DELAY_MS);
  hoverPrefetchTimersByKey.set(timerKey, timer);
}


function clearHoverPrefetchTimers(uriKey) {
  if (!uriKey) {
    for (const timer of hoverPrefetchTimersByKey.values()) {
      clearTimeout(timer);
    }
    hoverPrefetchTimersByKey.clear();
    return;
  }

  for (const [timerKey, timer] of hoverPrefetchTimersByKey.entries()) {
    if (timerKey.startsWith(`${uriKey}|`)) {
      clearTimeout(timer);
      hoverPrefetchTimersByKey.delete(timerKey);
    }
  }
}


function resolveHoverEnvironment(document) {
  if (document.uri.scheme !== "file") {
    return null;
  }

  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return null;
  }

  const config = vscode.workspace.getConfiguration("dependHover", workspaceFolder.uri);
  const pythonCommand = config.get("pythonCommand", "uv");
  const timeoutMs = config.get("timeoutMs", 4000);
  const mypyConfig = resolveWorkspaceTemplate(
    config.get("mypyConfig", "${workspaceFolder}/tests/mypy.ini"),
    workspaceFolder.uri.fsPath,
  );
  const scriptPath = path.join(workspaceFolder.uri.fsPath, "scripts", "hover_type.py");
  return {
    workspaceFolderPath: workspaceFolder.uri.fsPath,
    pythonCommand,
    timeoutMs,
    mypyConfig,
    scriptPath,
  };
}


function primeHoverPayload(
  document,
  position,
  pythonCommand,
  timeoutMs,
  cwd,
  scriptPath,
  mypyConfig,
) {
  const cache = getDocumentHoverCache(document);
  const cacheKey = buildHoverCacheKey(document, position, pythonCommand, mypyConfig, scriptPath);
  const entry = getOrCreateHoverEntry(cache, cacheKey);
  if (entry.ready) {
    return Promise.resolve(entry.payload);
  }
  if (entry.promise) {
    return entry.promise;
  }

  entry.promise = getHoverPayload(document, position, pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig)
    .then((payload) => {
      entry.ready = true;
      entry.payload = payload;
      entry.promise = null;
      return payload;
    })
    .catch(() => {
      entry.ready = true;
      entry.payload = null;
      entry.promise = null;
      return null;
    });
  return entry.promise;
}


async function getHoverPayload(
  document,
  position,
  pythonCommand,
  timeoutMs,
  cwd,
  scriptPath,
  mypyConfig,
) {
  const session = getHoverSession(pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig);
  const payload = await session.request({
    file: document.uri.fsPath,
    line: position.line + 1,
    column: position.character + 1,
    mypy_config: mypyConfig,
    include_base: true,
  });
  if (payload !== undefined) {
    return payload;
  }

  return await runHoverPayloadOnce(document, position, pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig);
}


async function runHoverPayloadOnce(
  document,
  position,
  pythonCommand,
  timeoutMs,
  cwd,
  scriptPath,
  mypyConfig,
) {
  const commandInfo = buildHoverCommand(pythonCommand, scriptPath, false);
  const args = [
    "--file",
    document.uri.fsPath,
    "--line",
    String(position.line + 1),
    "--column",
    String(position.character + 1),
    "--include-base",
  ];
  if (mypyConfig) {
    args.push("--mypy-config", mypyConfig);
  }

  const output = await runCommand(commandInfo.command, [...commandInfo.args, ...args], timeoutMs, cwd);
  if (!output) {
    return null;
  }

  try {
    return JSON.parse(output);
  } catch {
    return null;
  }
}


function getDocumentHoverCache(document) {
  const uriKey = document.uri.toString();
  const current = hoverCacheByUri.get(uriKey);
  if (current && current.version === document.version) {
    return current;
  }

  const next = {
    version: document.version,
    entries: new Map(),
  };
  hoverCacheByUri.set(uriKey, next);
  return next;
}


function getOrCreateHoverEntry(cache, cacheKey) {
  const cached = cache.entries.get(cacheKey);
  if (cached !== undefined) {
    return cached;
  }

  const entry = {
    ready: false,
    payload: null,
    promise: null,
  };
  cache.entries.set(cacheKey, entry);
  return entry;
}


async function waitForHoverPayload(promise, timeoutMs) {
  if (promise === null || promise === undefined) {
    return undefined;
  }

  let timer = undefined;
  const timeoutPromise = new Promise((resolve) => {
    timer = setTimeout(() => {
      resolve(undefined);
    }, timeoutMs);
  });
  try {
    return await Promise.race([
      Promise.resolve(promise).finally(() => {
        if (timer !== undefined) {
          clearTimeout(timer);
        }
      }),
      timeoutPromise,
    ]);
  } finally {
    if (timer !== undefined) {
      clearTimeout(timer);
    }
  }
}


function buildHoverPrefetchTimerKey(document, position, env) {
  const cacheKey = buildHoverCacheKey(document, position, env.pythonCommand, env.mypyConfig, env.scriptPath);
  return [
    document.uri.toString(),
    String(document.version),
    cacheKey,
  ].join("|");
}


function buildHoverCacheKey(document, position, pythonCommand, mypyConfig, scriptPath) {
  const range = document.getWordRangeAtPosition(position, HOVER_WORD_PATTERN);
  const target = range ? document.getText(range) : "";
  const rangeKey = range
    ? `${range.start.line}:${range.start.character}-${range.end.line}:${range.end.character}:${target}`
    : `${position.line}:${position.character}`;
  return [
    document.languageId,
    pythonCommand,
    mypyConfig ?? "",
    scriptPath,
    rangeKey,
  ].join("|");
}


function buildHoverSessionKey(pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig) {
  return [
    pythonCommand,
    String(timeoutMs),
    cwd,
    scriptPath,
    mypyConfig ?? "",
  ].join("|");
}


function buildHoverCommand(pythonCommand, scriptPath, serve) {
  const suffix = serve ? ["--serve"] : [];
  if (path.basename(pythonCommand).startsWith("uv")) {
    return {
      command: pythonCommand,
      args: ["run", "python", scriptPath, ...suffix],
    };
  }
  return {
    command: pythonCommand,
    args: [scriptPath, ...suffix],
  };
}


function buildHoverServerCommand(pythonCommand, scriptPath) {
  return buildHoverCommand(pythonCommand, scriptPath, true);
}


function getHoverSession(pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig) {
  const key = buildHoverSessionKey(pythonCommand, timeoutMs, cwd, scriptPath, mypyConfig);
  const cached = hoverSessionsByKey.get(key);
  if (cached !== undefined) {
    return cached;
  }

  const commandInfo = buildHoverServerCommand(pythonCommand, scriptPath);
  const session = new HoverSession(commandInfo.command, commandInfo.args, cwd, timeoutMs);
  hoverSessionsByKey.set(key, session);
  return session;
}


class HoverSession {
  constructor(command, args, cwd, timeoutMs) {
    this.command = command;
    this.args = args;
    this.cwd = cwd;
    this.timeoutMs = timeoutMs;
    this.child = null;
    this.buffer = "";
    this.pending = null;
    this.queue = Promise.resolve();
    this.disposed = false;
  }

  async request(request) {
    const next = this.queue.then(
      () => this._requestOnce(request),
      () => this._requestOnce(request),
    );
    this.queue = next.catch(() => undefined);
    return await next;
  }

  async _requestOnce(request) {
    if (this.disposed) {
      return undefined;
    }

    const child = this._ensureChild();
    if (child === null) {
      return undefined;
    }

    return await new Promise((resolve) => {
      const timer = setTimeout(() => {
        this._finishPending(undefined);
        this._restartChild();
        resolve(undefined);
      }, this.timeoutMs);

      this.pending = { resolve, timer };
      try {
        child.stdin.write(`${JSON.stringify(request)}\n`);
      } catch {
        clearTimeout(timer);
        this._finishPending(undefined);
        this._restartChild();
        resolve(undefined);
      }
    });
  }

  _ensureChild() {
    if (this.child !== null && !this.child.killed) {
      return this.child;
    }

    this.buffer = "";
    try {
      const child = cp.spawn(this.command, this.args, {
        cwd: this.cwd,
        env: process.env,
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
      });
      child.stdout.on("data", (chunk) => {
        this._onStdout(chunk);
      });
      child.stderr.on("data", () => {});
      child.on("error", () => {
        this._restartChild();
      });
      child.on("close", () => {
        this._restartChild();
      });
      this.child = child;
      return child;
    } catch {
      this.child = null;
      return null;
    }
  }

  _onStdout(chunk) {
    this.buffer += chunk.toString();
    let newlineIndex = this.buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = this.buffer.slice(0, newlineIndex).trim();
      this.buffer = this.buffer.slice(newlineIndex + 1);
      newlineIndex = this.buffer.indexOf("\n");
      if (!line) {
        continue;
      }

      let payload;
      try {
        payload = JSON.parse(line);
      } catch {
        continue;
      }

      if (this.pending === null) {
        continue;
      }

      const pending = this.pending;
      this.pending = null;
      clearTimeout(pending.timer);
      pending.resolve(payload);
      break;
    }
  }

  _finishPending(value) {
    if (this.pending === null) {
      return;
    }

    const pending = this.pending;
    this.pending = null;
    clearTimeout(pending.timer);
    pending.resolve(value);
  }

  _restartChild() {
    if (this.child !== null) {
      try {
        this.child.kill();
      } catch {
        // Ignore restart shutdown errors.
      }
    }
    this.child = null;
    this.buffer = "";
    this._finishPending(undefined);
  }

  dispose() {
    this.disposed = true;
    this._finishPending(undefined);
    if (this.child !== null) {
      try {
        this.child.kill();
      } catch {
        // Ignore shutdown errors.
      }
      this.child = null;
    }
    this.buffer = "";
  }
}


function disposeHoverState() {
  clearHoverPrefetchTimers();
  for (const session of hoverSessionsByKey.values()) {
    session.dispose();
  }
  hoverSessionsByKey.clear();
  hoverCacheByUri.clear();
}


function resolveWorkspaceTemplate(value, workspaceFolderPath) {
  if (!value) {
    return value;
  }
  return String(value).replaceAll("${workspaceFolder}", workspaceFolderPath);
}


function runCommand(command, args, timeoutMs, cwd) {
  return new Promise((resolve) => {
    const child = cp.spawn(command, args, {
      cwd,
      env: process.env,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      resolve(undefined);
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", () => {
      clearTimeout(timer);
      resolve(undefined);
    });

    child.on("close", (code) => {
      clearTimeout(timer);
      if (code !== 0 && !stdout) {
        resolve(undefined);
        return;
      }
      if (stdout.trim()) {
        resolve(stdout.trim());
        return;
      }
      if (stderr.trim()) {
        resolve(undefined);
        return;
      }
      resolve(undefined);
    });
  });
}


function escapeMarkdown(text) {
  return String(text).replaceAll("`", "\\`");
}


function normalizeWhitespace(text) {
  return String(text).replace(/\s+/g, " ").trim();
}


function diagnosticSeverityLabel(severity) {
  switch (severity) {
    case vscode.DiagnosticSeverity.Error:
      return "Error";
    case vscode.DiagnosticSeverity.Warning:
      return "Warning";
    case vscode.DiagnosticSeverity.Information:
      return "Info";
    case vscode.DiagnosticSeverity.Hint:
      return "Hint";
    default:
      return "Note";
  }
}


function collectRelevantDiagnostics(document, position) {
  const diagnostics = vscode.languages.getDiagnostics(document.uri);
  const lineDiagnostics = diagnostics.filter((diagnostic) => isRelevantDiagnostic(diagnostic, position));
  const mypyDiagnostics = lineDiagnostics.filter((diagnostic) => isMypyDiagnostic(diagnostic));
  return mypyDiagnostics.length > 0 ? mypyDiagnostics : lineDiagnostics;
}


function isRelevantDiagnostic(diagnostic, position) {
  return diagnostic.range.start.line <= position.line && diagnostic.range.end.line >= position.line;
}


function isMypyDiagnostic(diagnostic) {
  const source = diagnostic.source ? String(diagnostic.source).toLowerCase() : "";
  return source.includes("mypy");
}


function deactivate() {}


module.exports = {
  activate,
  deactivate,
};
