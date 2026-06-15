from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .proofs import Proof

from .errors import ValidationError, summarize_value
from .expressions import Expr, eval_expr


@dataclass(slots=True)
class Context:
    values: dict[str, Any] = field(default_factory=dict)
    symbols: dict[str, int] = field(default_factory=dict)
    symbol_sources: dict[str, str] = field(default_factory=dict)
    proofs: dict[tuple[str, int, str], Proof] = field(default_factory=dict)
    path: tuple[str, ...] = ()

    def child(self, name: str) -> Context:
        return Context(
            values=self.values,
            symbols=self.symbols,
            symbol_sources=self.symbol_sources,
            proofs=self.proofs,
            path=self.path + (name,),
        )

    def fork(self) -> Context:
        return Context(
            values=self.values.copy(),
            symbols=self.symbols.copy(),
            symbol_sources=self.symbol_sources.copy(),
            proofs=self.proofs.copy(),
            path=self.path,
        )

    def bind_value(self, name: str, value: Any) -> None:
        self.values[name] = value

    def bind_symbol(self, name: str, value: int, source: str) -> None:
        if name not in self.symbols:
            self.symbols[name] = value
            self.symbol_sources[name] = source
            return

        existing = self.symbols[name]
        if existing != value:
            existing_source = self.symbol_sources.get(name, "previous binding")
            raise ValidationError(
                path=self.path,
                expected=f"{name} = {existing}",
                actual=f"{name} = {value}",
                details=f"where {name} = {existing} from {existing_source}",
                context=dict(self.symbols),
            )

    def resolve_expr(self, expr: Expr) -> int:
        try:
            return eval_expr(expr, self.symbols)
        except KeyError as exc:
            missing = exc.args[0]
            raise ValidationError(
                path=self.path,
                expected=str(expr),
                actual=f"unbound symbol {missing}",
                details=f"symbol {missing} must be bound before evaluating {expr}",
                context=dict(self.symbols),
            ) from exc
