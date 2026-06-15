const cp = require("child_process");
const path = require("path");
const vscode = require("vscode");


function activate(context) {
  const provider = vscode.languages.registerHoverProvider("python", {
    provideHover(document, position) {
      return provideDependHover(document, position);
    },
  });
  context.subscriptions.push(provider);
}


async function provideDependHover(document, position) {
  if (document.uri.scheme !== "file") {
    return undefined;
  }

  const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (!workspaceFolder) {
    return undefined;
  }

  const config = vscode.workspace.getConfiguration("dependHover", workspaceFolder.uri);
  const pythonCommand = config.get("pythonCommand", "uv");
  const timeoutMs = config.get("timeoutMs", 4000);
  const mypyConfig = resolveWorkspaceTemplate(
    config.get("mypyConfig", "${workspaceFolder}/tests/mypy.ini"),
    workspaceFolder.uri.fsPath,
  );
  const scriptPath = path.join(workspaceFolder.uri.fsPath, "scripts", "hover_type.py");

  const args = [
    "run",
    "python",
    scriptPath,
    "--file",
    document.uri.fsPath,
    "--line",
    String(position.line + 1),
    "--column",
    String(position.character + 1),
  ];
  if (mypyConfig) {
    args.push("--mypy-config", mypyConfig);
  }

  const output = await runCommand(pythonCommand, args, timeoutMs, workspaceFolder.uri.fsPath);
  if (!output) {
    return undefined;
  }

  let payload;
  try {
    payload = JSON.parse(output);
  } catch {
    return undefined;
  }

  if (!payload.ok || !payload.computed_type) {
    return undefined;
  }

  const hover = new vscode.MarkdownString(undefined, true);
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

  return new vscode.Hover(hover);
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


function deactivate() {}


module.exports = {
  activate,
  deactivate,
};
