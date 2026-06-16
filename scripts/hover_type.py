#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEPEND_CALLS = {"ensure", "validate"}
REFINED_CALLS = {"refined"}


@dataclass(frozen=True, slots=True)
class Binding:
    name: str
    display: str
    kind: str
    line: int
    column: int
    detail: str | None = None


@dataclass(slots=True)
class Scope:
    kind: str
    start: tuple[int, int]
    end: tuple[int, int]
    parent: Scope | None = None
    bindings: dict[str, list[Binding]] = field(default_factory=dict)
    children: list[Scope] = field(default_factory=list)

    def add_binding(self, binding: Binding) -> None:
        self.bindings.setdefault(binding.name, []).append(binding)

    def contains(self, line: int, column: int) -> bool:
        return _pos_le(self.start, (line, column)) and _pos_lt((line, column), self.end)


@dataclass(frozen=True, slots=True)
class HoverInfo:
    symbol: str
    computed_type: str
    kind: str
    detail: str | None = None
    base_type: str | None = None
    expression: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "computed_type": self.computed_type,
            "kind": self.kind,
            "detail": self.detail,
            "base_type": self.base_type,
            "expression": self.expression,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute a depend-aware hover type for a Python symbol.")
    parser.add_argument("--serve", action="store_true", help="Run as a long-lived JSONL hover server.")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--line", type=int, help="1-based line number.")
    parser.add_argument("--column", type=int, help="1-based column number.")
    parser.add_argument("--mypy-config", type=Path, default=None)
    parser.add_argument("--include-base", action="store_true", help="Attach a mypy-revealed base type when possible.")
    args = parser.parse_args()

    if args.serve:
        return serve()

    if args.file is None or args.line is None or args.column is None:
        parser.error("--file, --line, and --column are required unless --serve is used")

    source = args.file.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(args.file), type_comments=True)
    analysis = _analyze(tree, source)
    hover = hover_info(
        analysis,
        source,
        args.line,
        max(args.column - 1, 0),
        args.file,
        args.mypy_config,
        args.include_base,
    )
    print(json.dumps(_hover_response(hover), separators=(",", ":")))
    return 0


@dataclass(slots=True)
class FileSnapshot:
    fingerprint: tuple[int, int]
    source: str
    analysis: Analysis


class HoverServer:
    def __init__(self) -> None:
        self._snapshots: dict[Path, FileSnapshot] = {}
        self._responses: dict[tuple[str, tuple[int, int], int, int, str, bool], dict[str, Any]] = {}

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        try:
            file = Path(request["file"])
            line = int(request["line"])
            column = max(int(request["column"]) - 1, 0)
            mypy_config_raw = request.get("mypy_config")
            mypy_config = Path(mypy_config_raw) if mypy_config_raw else None
            include_base = bool(request.get("include_base"))
        except (KeyError, TypeError, ValueError) as exc:
            return {"id": request_id, "ok": False, "reason": f"invalid hover request: {exc}"}

        try:
            snapshot = self._load_snapshot(file)
        except OSError as exc:
            return {"id": request_id, "ok": False, "reason": f"failed to read file: {exc}"}

        cache_key = (
            str(file.resolve()),
            snapshot.fingerprint,
            line,
            column,
            str(mypy_config.resolve()) if mypy_config is not None else "",
            include_base,
        )
        cached = self._responses.get(cache_key)
        if cached is not None:
            return {"id": request_id, **cached}

        hover = hover_info(
            snapshot.analysis,
            snapshot.source,
            line,
            column,
            file,
            mypy_config,
            include_base,
        )
        response = _hover_response(hover)
        self._responses[cache_key] = response
        return {"id": request_id, **response}

    def _load_snapshot(self, file: Path) -> FileSnapshot:
        resolved = file.resolve()
        stat_result = resolved.stat()
        fingerprint = (stat_result.st_mtime_ns, stat_result.st_size)
        cached = self._snapshots.get(resolved)
        if cached is not None and cached.fingerprint == fingerprint:
            return cached
        if cached is not None:
            resolved_key = str(resolved)
            self._responses = {
                key: value
                for key, value in self._responses.items()
                if key[0] != resolved_key
            }

        source = resolved.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(resolved), type_comments=True)
        analysis = _analyze(tree, source)
        snapshot = FileSnapshot(fingerprint=fingerprint, source=source, analysis=analysis)
        self._snapshots[resolved] = snapshot
        return snapshot


def serve() -> int:
    server = HoverServer()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"ok": False, "reason": f"invalid JSON: {exc}"}
        else:
            try:
                response = server.handle_request(request)
            except Exception as exc:  # noqa: BLE001
                response = {"id": request.get("id") if isinstance(request, dict) else None, "ok": False, "reason": str(exc)}

        print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


def _hover_response(hover: HoverInfo | None) -> dict[str, Any]:
    if hover is None:
        return {"ok": False, "reason": "no hover target found"}
    return {"ok": True, **hover.to_json()}


@dataclass(slots=True)
class Analysis:
    tree: ast.AST
    root: Scope
    parents: dict[ast.AST, ast.AST | None]


def hover_info(
    analysis: Analysis,
    source: str,
    line: int,
    column: int,
    file: Path,
    mypy_config: Path | None,
    include_base: bool,
) -> HoverInfo | None:
    node = _find_smallest_node(analysis.tree, line, column)
    if node is None:
        return None

    hover_node = _hover_expression_node(node, analysis.parents)
    symbol = _symbol_name(hover_node, source)
    if symbol is None:
        symbol = _symbol_name(node, source)
    if symbol is None:
        return None

    binding = _binding_for_symbol(analysis.root, line, column, symbol)
    inspected_type = _dmypy_inspected_type(hover_node, file, mypy_config)
    if inspected_type is None:
        inspected_type = _mypy_revealed_type(source, file, hover_node, mypy_config, analysis.parents)
    expression = _source_segment(source, hover_node)

    if binding is not None and binding.kind == "type_alias":
        base_type = inspected_type if include_base and inspected_type and inspected_type != binding.display else None
        return HoverInfo(
            symbol=symbol,
            computed_type=binding.display,
            kind=binding.kind,
            detail=binding.detail,
            base_type=base_type,
            expression=expression,
        )

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.arg)) and binding is not None:
        base_type = inspected_type if include_base and inspected_type and inspected_type != binding.display else None
        return HoverInfo(
            symbol=symbol,
            computed_type=binding.display,
            kind=binding.kind,
            detail=binding.detail,
            base_type=base_type,
            expression=expression,
        )

    if inspected_type is not None and inspected_type != "Any":
        base_type = binding.display if include_base and binding is not None and binding.display != inspected_type else None
        return HoverInfo(
            symbol=symbol,
            computed_type=inspected_type,
            kind="mypy",
            detail=None,
            base_type=base_type,
            expression=expression,
        )

    if binding is None:
        return None
    return HoverInfo(
        symbol=symbol,
        computed_type=binding.display,
        kind=binding.kind,
        detail=binding.detail,
        base_type=None,
        expression=expression,
    )


def _analyze(tree: ast.AST, source: str) -> Analysis:
    end_line = len(source.splitlines()) or 1
    last_line = source.splitlines()[-1] if source.splitlines() else ""
    root = Scope(kind="module", start=(1, 0), end=(end_line, len(last_line)))
    parents = _build_parent_map(tree)

    def visit(node: ast.AST, scope: Scope) -> None:

        if isinstance(node, ast.Module):
            _scan_block(node.body, scope, source, visit)
            return

        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _register_function(node, scope, source)
            fn_scope = Scope(
                kind="function",
                start=(node.lineno, node.col_offset),
                end=_node_end(node),
                parent=scope,
            )
            scope.children.append(fn_scope)
            _register_parameters(node.args, fn_scope, source)
            _scan_block(node.body, fn_scope, source, visit)
            return

        if isinstance(node, ast.ClassDef):
            _register_class(node, scope, source)
            class_scope = Scope(
                kind="class",
                start=(node.lineno, node.col_offset),
                end=_node_end(node),
                parent=scope,
            )
            scope.children.append(class_scope)
            _scan_block(node.body, class_scope, source, visit)
            return

        if isinstance(node, ast.If):
            _scan_block(node.body, scope, source, visit)
            _scan_block(node.orelse, scope, source, visit)
            return

        if isinstance(node, ast.For | ast.AsyncFor | ast.While):
            _scan_block(node.body, scope, source, visit)
            _scan_block(node.orelse, scope, source, visit)
            return

        if isinstance(node, ast.With | ast.AsyncWith):
            _scan_block(node.body, scope, source, visit)
            return

        if isinstance(node, ast.Try):
            _scan_block(node.body, scope, source, visit)
            for handler in node.handlers:
                _scan_block(handler.body, scope, source, visit)
            _scan_block(node.orelse, scope, source, visit)
            _scan_block(node.finalbody, scope, source, visit)
            return

        if isinstance(node, ast.Match):
            for case in node.cases:
                _scan_block(case.body, scope, source, visit)
            return

    visit(tree, root)
    return Analysis(tree=tree, root=root, parents=parents)


def _scan_block(
    body: list[ast.stmt],
    scope: Scope,
    source: str,
    visit: Any,
) -> None:
    for stmt in body:
        _scan_stmt(stmt, scope, source, visit)


def _scan_stmt(
    stmt: ast.stmt,
    scope: Scope,
    source: str,
    visit: Any,
) -> None:
    if isinstance(stmt, ast.TypeAlias):
        display = _source_segment(source, stmt.value)
        detail = None
        scope.add_binding(Binding(stmt.name.id, display, "type_alias", stmt.lineno, stmt.col_offset, detail=detail))
        return

    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
        display = _source_segment(source, stmt.annotation)
        scope.add_binding(Binding(stmt.target.id, display, "annotation", stmt.lineno, stmt.col_offset, detail=None))
        if stmt.value is not None:
            visit(stmt.value, scope)
        return

    if isinstance(stmt, ast.Assign):
        display, kind, detail = _assign_binding_info(stmt.value, source)
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                binding_display = target.id if kind == "refined" else display
                scope.add_binding(Binding(target.id, binding_display, kind, stmt.lineno, stmt.col_offset, detail=detail))
        visit(stmt.value, scope)
        return

    if isinstance(stmt, ast.FunctionDef | ast.AsyncFunctionDef):
        visit(stmt, scope)
        return

    if isinstance(stmt, ast.ClassDef):
        visit(stmt, scope)
        return

    visit(stmt, scope)


def _register_function(node: ast.FunctionDef | ast.AsyncFunctionDef, scope: Scope, source: str) -> None:
    return_annotation = _source_segment(source, node.returns) if node.returns is not None else "None"
    params = ", ".join(_parameter_text(arg, source) for arg in node.args.args)
    if node.args.vararg is not None:
        params = ", ".join([params, f"*{_parameter_text(node.args.vararg, source)}" if params else f"*{_parameter_text(node.args.vararg, source)}"])
    if node.args.kwonlyargs:
        kwonly = ", ".join(_parameter_text(arg, source) for arg in node.args.kwonlyargs)
        params = ", ".join([params, kwonly]) if params else kwonly
    display = f"def {node.name}({params}) -> {return_annotation}"
    scope.add_binding(Binding(node.name, display, "function", node.lineno, node.col_offset))


def _register_class(node: ast.ClassDef, scope: Scope, source: str) -> None:
    bases = ", ".join(_source_segment(source, base) for base in node.bases) if node.bases else ""
    display = f"class {node.name}"
    if bases:
        display = f"{display}({bases})"
    scope.add_binding(Binding(node.name, display, "class", node.lineno, node.col_offset))


def _register_parameters(args: ast.arguments, scope: Scope, source: str) -> None:
    for arg in list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs):
        if arg.annotation is None:
            continue
        scope.add_binding(
            Binding(
                arg.arg,
                _source_segment(source, arg.annotation),
                "parameter",
                arg.lineno,
                arg.col_offset,
            )
        )
    if args.vararg is not None and args.vararg.annotation is not None:
        scope.add_binding(
            Binding(
                args.vararg.arg,
                _source_segment(source, args.vararg.annotation),
                "parameter",
                args.vararg.lineno,
                args.vararg.col_offset,
            )
        )
    if args.kwarg is not None and args.kwarg.annotation is not None:
        scope.add_binding(
            Binding(
                args.kwarg.arg,
                _source_segment(source, args.kwarg.annotation),
                "parameter",
                args.kwarg.lineno,
                args.kwarg.col_offset,
            )
        )


def _parameter_text(arg: ast.arg, source: str) -> str:
    if arg.annotation is None:
        return arg.arg
    return f"{arg.arg}: {_source_segment(source, arg.annotation)}"


def _assign_binding_info(value: ast.AST, source: str) -> tuple[str, str, str | None]:
    if isinstance(value, ast.Call):
        call_name = _call_name(value.func)
        if call_name in DEPEND_CALLS:
            annotation = _call_annotation(value, source)
            if annotation is not None:
                return annotation, "ensure", f"from {call_name}(...)"
        if call_name in REFINED_CALLS:
            return "refined type", "refined", _source_segment(source, value)
    return _source_segment(source, value), "assignment", None


def _call_annotation(call: ast.Call, source: str) -> str | None:
    if len(call.args) >= 2:
        return _source_segment(source, call.args[1])
    for keyword in call.keywords:
        if keyword.arg in {"annotation", "type"} and keyword.value is not None:
            return _source_segment(source, keyword.value)
    return None


def _binding_for_symbol(scope: Scope, line: int, column: int, symbol: str) -> Binding | None:
    current: Scope | None = _innermost_scope(scope, line, column)
    while current is not None:
        binding = _latest_preceding_binding(current, symbol, line, column)
        if binding is not None:
            return binding
        binding = _any_binding(current, symbol)
        if binding is not None:
            return binding
        current = current.parent
    return None


def _latest_preceding_binding(scope: Scope, symbol: str, line: int, column: int) -> Binding | None:
    candidates = scope.bindings.get(symbol, [])
    for binding in reversed(candidates):
        if _pos_le((binding.line, binding.column), (line, column)):
            return binding
    return None


def _any_binding(scope: Scope, symbol: str) -> Binding | None:
    candidates = scope.bindings.get(symbol, [])
    if candidates:
        return candidates[-1]
    return None


def _innermost_scope(scope: Scope, line: int, column: int) -> Scope:
    best = scope
    for child in scope.children:
        if child.contains(line, column):
            nested = _innermost_scope(child, line, column)
            if _scope_span(nested) <= _scope_span(best):
                best = nested
    return best


def _scope_span(scope: Scope) -> tuple[int, int, int, int]:
    return scope.end[0] - scope.start[0], scope.end[1] - scope.start[1], scope.start[0], scope.start[1]


def _find_smallest_node(tree: ast.AST, line: int, column: int) -> ast.AST | None:
    candidates: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            continue
        if _node_contains(node, line, column):
            candidates.append(node)
    if not candidates:
        return None
    candidates.sort(key=_node_area)
    return candidates[0]


def _node_contains(node: ast.AST, line: int, column: int) -> bool:
    start = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
    end = (getattr(node, "end_lineno", 0), getattr(node, "end_col_offset", 0))
    point = (line, column)
    return _pos_le(start, point) and _pos_lt(point, end)


def _node_area(node: ast.AST) -> tuple[int, int, int, int]:
    start = (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))
    end = (getattr(node, "end_lineno", 0), getattr(node, "end_col_offset", 0))
    return end[0] - start[0], end[1] - start[1], start[0], start[1]


def _node_span(node: ast.AST) -> tuple[int, int, int, int] | None:
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        return None
    start_line = getattr(node, "lineno", 1)
    start_col = getattr(node, "col_offset", 0) + 1
    end_line = getattr(node, "end_lineno", start_line)
    end_col = getattr(node, "end_col_offset", getattr(node, "col_offset", 0) + 1)
    if end_line == start_line and end_col < start_col:
        end_col = start_col
    return start_line, start_col, end_line, end_col


def _symbol_name(node: ast.AST, source: str) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _source_segment(source, node)
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return node.name
    if isinstance(node, ast.TypeAlias):
        return node.name.id
    if isinstance(node, ast.Subscript):
        return _source_segment(source, node)
    return None


def _call_name(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def _source_segment(source: str, node: ast.AST | None) -> str:
    if node is None:
        return ""
    segment = ast.get_source_segment(source, node)
    if segment is not None:
        return segment
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", start + 1) - 1
    if start == end:
        line = lines[start] if 0 <= start < len(lines) else ""
        return line[getattr(node, "col_offset", 0) : getattr(node, "end_col_offset", len(line))]
    first = lines[start][getattr(node, "col_offset", 0) :] if 0 <= start < len(lines) else ""
    middle = lines[start + 1 : end]
    last = lines[end][: getattr(node, "end_col_offset", len(lines[end]))] if 0 <= end < len(lines) else ""
    return "\n".join([first, *middle, last])


def _dmypy_inspected_type(node: ast.AST, file: Path, mypy_config: Path | None) -> str | None:
    span = _node_span(node)
    if span is None:
        return None
    return _run_dmypy_inspect(file, span, mypy_config)


def _mypy_revealed_type(
    source: str,
    file: Path,
    node: ast.AST,
    mypy_config: Path | None,
    parents: dict[ast.AST, ast.AST | None],
) -> str | None:
    expr = _source_segment(source, node)
    if not expr:
        return None

    stmt = _nearest_stmt(node, parents)
    if stmt is None:
        return None

    lines = source.splitlines()
    insert_line = getattr(stmt, "end_lineno", getattr(stmt, "lineno", 1))
    if insert_line < 1 or insert_line > len(lines):
        return None

    indent = _line_indent(lines[insert_line - 1])
    temp_source = _insert_reveal_type(lines, insert_line, indent, expr)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp:
        temp.write(temp_source)
        temp_path = Path(temp.name)

    try:
        cmd = [sys.executable, "-m", "mypy"]
        cmd.append("--no-incremental")
        if mypy_config is not None:
            cmd.extend(["--config-file", str(mypy_config)])
        cmd.extend(["--shadow-file", str(file), str(temp_path), str(file)])
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            cwd=str(Path.cwd()),
        )
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass

    for line in result.stdout.splitlines():
        marker = "Revealed type is "
        if marker in line:
            _, _, tail = line.partition(marker)
            return tail.strip().strip('"')
    return None


def _run_dmypy_inspect(file: Path, span: tuple[int, int, int, int], mypy_config: Path | None) -> str | None:
    status_file = _dmypy_status_file(mypy_config)
    location = f"{file}:{span[0]}:{span[1]}:{span[2]}:{span[3]}"
    cmd = _dmypy_base_command(status_file) + ["inspect", "--force-reload", "--show", "type", location]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        cwd=str(Path.cwd()),
    )
    inspected = _parse_dmypy_type_output(result.stdout)
    if inspected is not None:
        return inspected

    if not _needs_dmypy_bootstrap(result.stdout):
        return None

    bootstrap = _dmypy_base_command(status_file) + ["run", "--"]
    if mypy_config is not None:
        bootstrap.extend(["--config-file", str(mypy_config)])
    bootstrap.append(str(file))
    subprocess.run(
        bootstrap,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        cwd=str(Path.cwd()),
    )

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
        cwd=str(Path.cwd()),
    )
    return _parse_dmypy_type_output(result.stdout)


def _dmypy_base_command(status_file: Path) -> list[str]:
    return [sys.executable, "-m", "mypy.dmypy", "--status-file", str(status_file)]


def _dmypy_status_file(mypy_config: Path | None) -> Path:
    cwd = Path.cwd().resolve()
    config = mypy_config.resolve() if mypy_config is not None else None
    basis = f"{cwd}::{config if config is not None else ''}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"depend-hover-{digest}.json"


def _parse_dmypy_type_output(output: str) -> str | None:
    for line in output.splitlines():
        if "->" not in line:
            continue
        _, _, tail = line.partition("->")
        tail = tail.strip()
        if not tail:
            continue
        try:
            return ast.literal_eval(tail)
        except Exception:  # noqa: BLE001
            continue
    return None


def _needs_dmypy_bootstrap(output: str) -> bool:
    lowered = output.lower()
    return "daemon" in lowered or "not running" in lowered or "no known type available" in lowered or "cannot find" in lowered


def _hover_expression_node(node: ast.AST, parents: dict[ast.AST, ast.AST | None]) -> ast.AST:
    current = node
    while True:
        parent = parents.get(current)
        if parent is None:
            return current
        if isinstance(parent, ast.Attribute) and current is parent.value:
            current = parent
            continue
        if isinstance(parent, ast.Subscript) and current is parent.value:
            current = parent
            continue
        if isinstance(parent, ast.Call) and current is parent.func:
            current = parent
            continue
        return current


def _is_definition_context(node: ast.AST, parents: dict[ast.AST, ast.AST | None]) -> bool:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.TypeAlias, ast.arg)):
        return True

    parent = parents.get(node)
    if isinstance(parent, ast.Assign):
        return node in parent.targets
    if isinstance(parent, ast.AnnAssign):
        return parent.target is node
    if isinstance(parent, ast.NamedExpr):
        return parent.target is node
    return False


def _nearest_stmt(node: ast.AST, parents: dict[ast.AST, ast.AST | None]) -> ast.stmt | None:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, ast.stmt):
            return current
        current = parents.get(current)
    return None


def _insert_reveal_type(lines: list[str], line_number: int, indent: str, expr: str) -> str:
    reveal = f"{indent}reveal_type({expr})"
    updated = lines[:line_number] + [reveal] + lines[line_number:]
    return "\n".join(updated) + ("\n" if lines and not lines[-1].endswith("\n") else "")


def _line_indent(line: str) -> str:
    stripped = line.lstrip(" \t")
    return line[: len(line) - len(stripped)]


def _pos_le(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[0] or (left[0] == right[0] and left[1] <= right[1])


def _pos_lt(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[0] or (left[0] == right[0] and left[1] < right[1])


def _node_end(node: ast.AST) -> tuple[int, int]:
    return (
        getattr(node, "end_lineno", getattr(node, "lineno", 1)),
        getattr(node, "end_col_offset", getattr(node, "col_offset", 0)),
    )


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST | None]:
    parents: dict[ast.AST, ast.AST | None] = {tree: None}

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            parents[child] = node
            visit(child)

    visit(tree)
    return parents


if __name__ == "__main__":
    raise SystemExit(main())
