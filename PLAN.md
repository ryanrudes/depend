Implementation Plan: depend Python Library + mypy Plugin

1. Project goal

Build depend, a Python library that provides practical dependent-style typing through:

1. ordinary Python type hints;
2. typing.Annotated refinements;
3. symbolic dimensions and value-indexed constraints;
4. runtime validation;
5. proof objects;
6. @checked function contracts;
7. dataclass validation;
8. shape-safe NumPy annotations;
9. optional mypy plugin support for static narrowing and proof of structured constraints.

The goal is not to pretend Python has native dependent types. The goal is to make dependent-style programming feel idiomatic in Python:

from depend import checked, refined, Sized
PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")
@checked
def repeat(text: str, n: PositiveInt) -> str:
    return text * n
@checked
def dot(
    a: Sized[list[float], "n"],
    b: Sized[list[float], "n"],
) -> float:
    return sum(x * y for x, y in zip(a, b))

Runtime validation should always work. The mypy plugin should prove the subset of constraints that are statically tractable.

2. High-level architecture

The project has four layers:

Runtime library:
  validates values, function arguments, returns, dataclasses, arrays, symbols
Static metadata:
  represents predicates, symbolic expressions, constraints, shape specs
mypy plugin:
  understands known metadata forms, narrows ensure(...), tracks symbols
Codegen/stubs, optional:
  emits overloads for value-indexed APIs that need exact static relationships

The runtime must be useful without the plugin.

The plugin must improve static feedback without being required for correctness.

3. Package layout

Create this package structure:

depend/
  __init__.py
  annotations.py
  checked.py
  constraints.py
  context.py
  dataclasses.py
  errors.py
  expressions.py
  predicates.py
  proofs.py
  refined.py
  registry.py
  sized.py
  validate.py
  numpy/
    __init__.py
    dtype.py
    ndarray.py
    shape.py
  mypy_plugin/
    __init__.py
    plugin.py
    analyze.py
    metadata.py
    narrow.py
    sized.py
    numpy.py
    registry.py
tests/
  runtime/
    test_refined.py
    test_checked.py
    test_sized.py
    test_context.py
    test_errors.py
    test_dataclasses.py
    test_proofs.py
    test_registry.py
    test_numpy.py
  mypy/
    cases/
      refined_success.py
      refined_failure.py
      ensure_narrowing.py
      sized_success.py
      sized_failure.py
      numpy_shape_success.py
      numpy_shape_failure.py
      registry_success.py
      registry_failure.py
    test_mypy_plugin.py
docs/
  index.md
  refinements.md
  checked-functions.md
  sized-collections.md
  numpy-shapes.md
  proofs.md
  registries.md
  mypy-plugin.md
  limitations.md

4. Public API

Expose from depend.__init__:

from depend.checked import checked
from depend.dataclasses import checked_dataclass, dependent_dataclass
from depend.predicates import Predicate, predicate, where
from depend.refined import refined
from depend.sized import Sized
from depend.validate import validate, ensure, is_valid
from depend.proofs import Proof, prove, RequiresProof
from depend.registry import register, parent_of, label_of, children_of

Expose from depend.numpy:

from depend.numpy.ndarray import NDArray
from depend.numpy.shape import Shape, AnyDim
from depend.numpy.dtype import DType, Float32, Float64, Int32, Int64

5. Runtime core

5.1 Predicate

Implement Predicate as the core refinement object.

@dataclass(frozen=True, slots=True)
class Predicate:
    fn: Callable[..., bool]
    name: str
    message: str | None = None
    dependencies: tuple[str, ...] = ()
    static_kind: str | None = None
    static_args: tuple[Any, ...] = ()
    def validate(self, value: Any, ctx: Context) -> None:
        ...

Responsibilities:

* call the predicate function;
* resolve dependency values from Context;
* raise a structured ValidationError on failure;
* expose static metadata for the mypy plugin when possible.

static_kind is critical. Runtime lambdas are opaque to mypy. Known predicate constructors should produce structured metadata:

GreaterThan(0) -> Predicate(static_kind="gt", static_args=(0,))
Between(0, 1) -> Predicate(static_kind="between", static_args=(0, 1))
NonEmpty -> Predicate(static_kind="non_empty")

Arbitrary lambda predicates are runtime-only unless the plugin later learns to parse simple AST patterns. Do not make AST proving a v1 requirement. That way lies unpaid grief.

5.2 where(...)

Implement:

def where(
    fn: Callable[..., bool],
    message: str | None = None,
    *,
    name: str | None = None,
    dependencies: tuple[str, ...] = (),
) -> Predicate:
    ...

Example:

PositiveInt = Annotated[int, where(lambda x: x > 0, "must be positive")]

5.3 Built-in known predicates

Add first-class known predicates. These are plugin-friendly.

GreaterThan[x]
GreaterEqual[x]
LessThan[x]
LessEqual[x]
Between[lo, hi]
NonEmpty
Finite
Probability
StrictlyIncreasing

Use objects or factory functions, whichever is easier to type.

Example:

PositiveInt = Annotated[int, GreaterThan[0]]
ProbabilityFloat = Annotated[float, Between[0.0, 1.0]]

Runtime validates them. Plugin understands them.

5.4 refined(...)

Implement:

def refined(
    base: type[Any],
    predicate: Callable[[Any], bool] | Predicate,
    *,
    name: str | None = None,
    message: str | None = None,
) -> Any:
    ...

Return:

Annotated[base, Predicate(...)]

Example:

PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

If the predicate is already a Predicate, preserve its structured metadata.

5.5 Context

Implement validation context:

@dataclass
class Context:
    values: dict[str, Any]
    symbols: dict[str, int]
    symbol_sources: dict[str, str]
    proofs: dict[tuple[str, int, str], Proof]
    path: tuple[str, ...]
    def child(self, name: str) -> Context: ...
    def bind_value(self, name: str, value: Any) -> None: ...
    def bind_symbol(self, name: str, value: int, source: str) -> None: ...
    def resolve_expr(self, expr: Expr) -> int: ...

Symbol rules:

* First occurrence binds the symbol.
* Later occurrence checks equality.
* If values differ, raise ValidationError.

Example:

def dot(a: Sized[list[float], "n"], b: Sized[list[float], "n"]) -> float:
    ...

Validation sequence:

validate a -> bind n = len(a)
validate b -> check len(b) == n

6. Symbolic expressions

6.1 Expression model

Implement a small symbolic arithmetic language.

Supported:

n
m
n + m
n - 1
n * 2
2 * n

Do not support arbitrary Python expressions.

Core classes:

class Expr: ...
@dataclass(frozen=True, slots=True)
class SymbolExpr(Expr):
    name: str
@dataclass(frozen=True, slots=True)
class ConstExpr(Expr):
    value: int
@dataclass(frozen=True, slots=True)
class BinaryExpr(Expr):
    op: Literal["+", "-", "*"]
    left: Expr
    right: Expr

6.2 Parser

Implement:

def parse_expr(value: str | int | Expr) -> Expr:
    ...

Requirements:

* parse integer constants;
* parse symbol names matching [A-Za-z_][A-Za-z0-9_]*;
* parse +, -, *;
* reject function calls, attribute access, indexing, imports, comprehensions, and everything else that would turn a type annotation into a tiny crime scene.

Use Python ast.parse(..., mode="eval"), but whitelist only:

* ast.Name
* ast.Constant for ints
* ast.BinOp with Add, Sub, Mult

Reject all other nodes.

6.3 Expression evaluation

Implement:

def eval_expr(expr: Expr, symbols: Mapping[str, int]) -> int:
    ...

If a symbol is missing, raise a validation-internal error that gets rendered as a ValidationError.

7. Validation engine

7.1 validate(...)

Implement:

def validate(value: Any, annotation: Any, ctx: Context | None = None) -> Any:
    ...

Validation should support:

* bare types: int, str, float, custom classes;
* Annotated[T, ...];
* list[T];
* tuple[T, ...];
* fixed tuples: tuple[int, str];
* dict[K, V];
* set[T];
* Union / |;
* Literal[...];
* Sized[...];
* NDArray[...];
* proof annotations;
* Any, which should always pass.

Return the original value.

Do not wrap values by default.

7.2 ensure(...)

Implement:

def ensure(value: Any, annotation: Any) -> Any:
    validate(value, annotation)
    return value

The runtime just validates and returns.

The mypy plugin narrows:

x = ensure(get_value(), PositiveInt)

into something type-compatible with PositiveInt.

7.3 is_valid(...)

Implement:

def is_valid(value: Any, annotation: Any) -> bool:
    try:
        validate(value, annotation)
        return True
    except ValidationError:
        return False

7.4 Error model

Implement rich validation errors:

class ValidationError(TypeError):
    path: tuple[str, ...]
    expected: str
    actual: str
    details: str | None
    context: Mapping[str, Any]

Rendering should produce:

ValidationError in dot argument b:
  expected len(b) == n
  where n = 3 from argument a
  got len(b) = 2

For predicates:

ValidationError for port:
  expected Port: must be between 0 and 65535
  got 70000

Requirements:

* errors must identify the failing function argument or dataclass field;
* errors must include bound symbols when relevant;
* errors must avoid dumping huge arrays or giant lists;
* implement compact value summaries.

8. Sized

8.1 API

Support:

Sized[list[int], "n"]
Sized[list[int], "n + 1"]
Sized[tuple[float, ...], 3]

Usage:

@checked
def dot(
    a: Sized[list[float], "n"],
    b: Sized[list[float], "n"],
) -> float:
    return sum(x * y for x, y in zip(a, b))

8.2 Implementation

Implement Sized using __class_getitem__.

Internal annotation:

@dataclass(frozen=True, slots=True)
class SizedAnnotation:
    container_annotation: Any
    length_expr: Expr

Validation:

1. Validate value against container_annotation.
2. Require len(value).
3. Evaluate/bind/check length_expr.

For a bare symbol:

Sized[list[int], "n"]

if n is unbound, bind n = len(value).

For an expression:

Sized[list[int], "n + 1"]

all symbols must already be bound before checking. Do not infer n from n + 1 in v1. That can come later.

8.3 Return validation

Use same context to validate return types.

@checked
def reverse(xs: Sized[list[int], "n"]) -> Sized[list[int], "n"]:
    return xs[::-1]

9. @checked

9.1 Function validation

Implement:

@checked
def f(...):
    ...

Support both bare and configured forms:

@checked
def f(...): ...
@checked(enabled=False)
def g(...): ...

Validation algorithm:

1. Inspect signature.
2. Bind arguments with defaults.
3. Create Context.
4. Bind argument names and values into context.
5. Validate parameters in signature order.
6. Call the function.
7. Validate return value if return annotation exists and is not Any.
8. Return original result.

9.2 Async functions

Detect coroutine functions and support:

@checked
async def f(...):
    ...

9.3 Performance controls

Support environment variable:

DEPEND_DISABLE_CHECKS=1

If set, @checked should call through without validation.

Also support:

@checked(validate_return=False)
def f(...): ...

for performance-sensitive cases.

10. Dataclass integration

10.1 @checked_dataclass

Support:

from dataclasses import dataclass
from depend import checked_dataclass
@checked_dataclass
@dataclass
class Config:
    port: Port
    workers: PositiveInt

Implementation:

* wrap or synthesize __post_init__;
* validate all fields using type annotations;
* call the original __post_init__ if present.

Order:

1. dataclass initializes fields.
2. original __post_init__ runs.
3. validation runs.

Or make order configurable:

@checked_dataclass(validate_before_post_init=True)

Default should be after __post_init__, because post-init often normalizes fields.

10.2 @dependent_dataclass

Convenience decorator:

@dependent_dataclass
class Config:
    port: Port
    workers: PositiveInt

Equivalent to:

@checked_dataclass
@dataclass
class Config:
    ...

11. Proof objects

11.1 Proof

Implement:

@dataclass(frozen=True, slots=True)
class Proof:
    value_id: int
    annotation_fingerprint: str
    predicate_name: str

Proof should be tied to a particular runtime object identity and annotation fingerprint.

11.2 prove(...)

def prove(value: Any, annotation: Any) -> Proof:
    validate(value, annotation)
    return Proof(...)

11.3 RequiresProof

Support proof-requiring checked functions:

@checked
def divide(
    x: float,
    y: float,
    proof: RequiresProof["y", NonZeroFloat],
) -> float:
    return x / y

Runtime validates that:

* proof applies to argument "y";
* proof’s value identity matches id(y);
* proof’s annotation fingerprint matches NonZeroFloat.

11.4 ensured(...) context manager

Implement:

with ensured(y, PositiveInt):
    ...

Runtime validates on entry.

The mypy plugin can optionally narrow inside the block. This is harder. Treat as v2 unless simple support is feasible.

12. NumPy support

12.1 Shape

Support:

Shape["T", 3]
Shape["batch", "features"]
Shape["m", "n"]
Shape["m", "n + 1"]

Internal:

@dataclass(frozen=True, slots=True)
class ShapeAnnotation:
    dims: tuple[Expr | AnyDimType, ...]

12.2 AnyDim

Support wildcard dimensions:

Shape["T", AnyDim]

12.3 DType

Support:

DType[np.float64]
DType[np.int64]

Also aliases:

Float32
Float64
Int32
Int64
Bool

12.4 NDArray

Support:

NDArray[Shape["T", 3], Float64]
NDArray[Shape["T"], DType[np.float64]]

Validation:

1. import NumPy lazily;
2. check isinstance(value, np.ndarray);
3. check rank;
4. bind/check symbolic shape dimensions;
5. check dtype if specified.

Example:

@checked
def normalize_rows(
    x: NDArray[Shape["N", 3], Float64],
) -> NDArray[Shape["N", 3], Float64]:
    ...

13. Registry support

13.1 Purpose

Provide runtime metadata for hierarchical/value-indexed domains.

Example:

@register(to=MySubjects.SUBJECT_A)
class SubjectASegments(SegmentId):
    SEGMENT_1 = "segment1"
    SEGMENT_2 = "segment2"

Runtime metadata:

label_of(SubjectASegments.SEGMENT_1) == "subjectA:segment1"
parent_of(SubjectASegments.SEGMENT_1) == MySubjects.SUBJECT_A
children_of(MySubjects.SUBJECT_A)

13.2 Implementation

Global registry:

@dataclass
class Registry:
    parent_by_child: dict[Any, Any]
    children_by_parent: dict[Any, set[Any]]
    label_by_item: dict[Any, str]

APIs:

def register(*, to: Any) -> Callable[[type[T]], type[T]]: ...
def parent_of(item: Any) -> Any | None: ...
def children_of(parent: Any) -> tuple[Any, ...]: ...
def label_of(item: Any) -> str: ...

Do not mutate enum .value.

13.3 Static note

The mypy plugin may support structured registry declarations later, but runtime decorators alone are not a reliable static source. For static proof, prefer generated stubs or explicit metadata.

14. mypy plugin

14.1 Setup

Expose plugin entry point:

# depend/mypy_plugin/plugin.py
from mypy.plugin import Plugin
class DependPlugin(Plugin):
    ...
    
def plugin(version: str) -> type[Plugin]:
    return DependPlugin

User config:

[tool.mypy]
plugins = ["depend.mypy_plugin.plugin"]

14.2 Plugin goals

The plugin should support:

1. recognizing refined aliases;
2. recognizing Annotated[T, Predicate] metadata where possible;
3. narrowing ensure(value, Annotation);
4. checking literal calls against known predicates;
5. tracking Sized[..., "n"] equality in function signatures;
6. tracking simple symbolic shape constraints for NDArray;
7. improving return types for value-indexed accessors if metadata/stubs are available;
8. emitting clear messages for runtime-only predicates.

14.3 Do not attempt full Python theorem proving in v1

The plugin must not try to prove arbitrary Python lambdas.

Instead:

* structured known predicates get static support;
* arbitrary predicates are runtime-only;
* plugin emits notes or warnings only when helpful.

Example message:

Predicate PositiveInt is runtime-only here; static proof unavailable.
Use depend.GreaterThan[0] or ensure(...) for static narrowing.

14.4 Refined type representation

mypy does not naturally preserve arbitrary Annotated metadata in every place the way we might want. The plugin should therefore maintain its own metadata model where possible.

Represent refined types internally as:

@dataclass(frozen=True)
class RefinedMeta:
    base_type: mypy.types.Type
    predicate_kind: str
    predicate_args: tuple[Any, ...]
    name: str

For arbitrary predicates:

predicate_kind = "runtime"

14.5 Hook: ensure(...)

Implement function hook for depend.ensure.

Example:

x = ensure(y, PositiveInt)

The hook should:

1. inspect second argument annotation;
2. determine refined type metadata;
3. return narrowed type if supported;
4. otherwise return base type with note.

For known predicates, the returned type should behave as refined.

If mypy cannot express the refined type directly, use a plugin metadata marker attached to the type or a generated nominal proxy type.

Start simple:

* for ensure(value, Annotated[T, KnownPredicate]), return T;
* emit errors when later calls require the annotation and value is not ensured;
* improve later once metadata propagation is working.

Do not get trapped trying to make mypy’s type internals beautiful. They are not furniture.

14.6 Hook: @checked

Implement decorator hook for depend.checked.

The plugin should type-check the function mostly normally, but additionally inspect annotations and issue static errors for obvious literal failures.

Example:

PositiveInt = Annotated[int, GreaterThan[0]]
@checked
def f(x: PositiveInt) -> None:
    ...
f(-1)

Static error:

Argument 1 to f violates PositiveInt: expected > 0, got Literal[-1]

For non-literal values, do not error unless the value has known incompatible refined metadata.

14.7 Hook: Sized

Implement type analysis hook for depend.Sized.

Goal:

Sized[list[int], "n"]

should be recognized as:

base = list[int]
length_expr = Symbol("n")

For mypy, the runtime type is still list[int], but plugin metadata tracks the length expression.

Static checking rules:

* Within a function signature, symbols are local to that call contract.
* If two parameters use the same symbol, plugin records equality requirement.
* If arguments are literals with known lengths, check them.
* If arguments are values previously ensured with matching Sized metadata, accept.
* Otherwise, defer to runtime validation.

Example static rejection:

@checked
def f(a: Sized[list[int], 2]) -> None:
    ...
f([1, 2, 3])

Error:

Argument a has length 3; expected length 2

Example unknown:

xs: list[int]
f(xs)

No static error. Runtime validates.

14.8 Hook: NDArray

Implement type analysis hook for depend.numpy.NDArray.

Known static support:

a: NDArray[Shape[3, 4], Float64]
b: NDArray[Shape[4, 2], Float64]

Plugin can compare shape metadata.

For runtime-produced arrays without known shape, defer.

Static checking should catch:

* rank mismatch when known;
* constant dimension mismatch;
* repeated symbol mismatch in a single call;
* dtype mismatch when known.

14.9 Value-indexed accessors

Support APIs where return type depends on a literal argument.

Preferred approach:

* codegen emits .pyi overloads;
* mypy already understands overloads;
* plugin optionally validates generated metadata.

Example generated stub:

class Scene:
    @overload
    def subject(self, subject: Literal[SubjectId.LEFT_SHOE]) -> SubjectView[ShoeSegmentId, ShoeMarkerId, ShoePatchId]: ...
    @overload
    def subject(self, subject: Literal[SubjectId.RIGHT_HAND]) -> SubjectView[HandSegmentId, HandMarkerId, HandPatchId]: ...

Do not make the plugin infer this from arbitrary runtime decorators in v1.

15. Code generation

15.1 Purpose

Some dependent relationships are best represented as generated overloads.

Examples:

* subject literal -> subject-specific view type;
* segment literal -> segment-specific marker/patch vocabulary;
* registry parent -> child enum type.

15.2 Generator API

Implement:

depend.codegen.generate_stubs(
    module: str,
    output: Path,
)

v1 can be minimal or left as documented future work.

For the first implementation, prioritize runtime library + mypy plugin over codegen.

16. Testing strategy

16.1 Runtime tests

Use pytest.

Test:

* refined aliases pass/fail;
* arbitrary predicates pass/fail;
* known predicates pass/fail;
* ensure;
* @checked argument validation;
* @checked return validation;
* async checked functions;
* disabled checks;
* sized symbol binding;
* sized expression checking;
* dataclass validation;
* proof validation;
* registry metadata;
* NumPy shape and dtype validation;
* error messages.

16.2 mypy plugin tests

Create test files under tests/mypy/cases.

Run mypy programmatically or through subprocess.

Each case should contain expected comments:

f(-1)  # E: Argument 1 violates PositiveInt

Test categories:

1. literal refined success/failure;
2. ensure narrowing;
3. sized literal success/failure;
4. sized unknown defers to runtime;
5. ndarray shape success/failure;
6. overload/value-indexed accessor examples;
7. runtime-only predicate warning behavior.

16.3 CI matrix

Run against:

* Python 3.11+
* latest mypy
* one previous mypy minor if practical
* NumPy optional tests only when installed

17. Implementation milestones

Milestone 1: Runtime refinements

Deliver:

* Predicate
* where
* refined
* validate
* ensure
* ValidationError
* tests

Acceptance:

PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")
validate(3, PositiveInt)
validate(-1, PositiveInt)  # raises

Milestone 2: @checked

Deliver:

* checked sync function support;
* return validation;
* good error paths;
* disabled mode;
* tests.

Acceptance:

@checked
def f(x: PositiveInt) -> PositiveInt:
    return x
f(-1)  # raises useful ValidationError

Milestone 3: Symbolic expressions and Sized

Deliver:

* expression parser;
* context symbol binding;
* Sized;
* dependent return validation.

Acceptance:

@checked
def reverse(xs: Sized[list[int], "n"]) -> Sized[list[int], "n"]:
    return xs[::-1]

and:

@checked
def bad(xs: Sized[list[int], "n"]) -> Sized[list[int], "n + 1"]:
    return xs

raises on return.

Milestone 4: Dataclasses and proofs

Deliver:

* checked_dataclass;
* dependent_dataclass;
* Proof;
* prove;
* RequiresProof.

Acceptance:

@dependent_dataclass
class Config:
    port: Port

validates on construction.

Milestone 5: NumPy support

Deliver:

* Shape;
* DType;
* NDArray;
* dtype aliases;
* tests.

Acceptance:

@checked
def f(x: NDArray[Shape["T", 3], Float64]) -> NDArray[Shape["T"], Float64]:
    ...

validates rank, shape, dtype, and symbolic T.

Milestone 6: Registry

Deliver:

* register;
* parent_of;
* children_of;
* label_of;
* tests.

Acceptance:

@register(to=Subject.A)
class Segments(SegmentId):
    ARM = "arm"
label_of(Segments.ARM) == "A:arm"

Milestone 7: mypy plugin MVP

Deliver:

* plugin entry point;
* hook for ensure;
* hook/check for known predicates;
* static literal rejection for obvious failures.

Acceptance:

f(-1)

produces mypy error when f expects Annotated[int, GreaterThan[0]].

Milestone 8: mypy Sized support

Deliver:

* type metadata for Sized;
* checking literal lengths;
* tracking equality of symbols in function calls where possible.

Acceptance:

dot([1.0, 2.0], [3.0])  # mypy error if literals are visible

Milestone 9: mypy NumPy shape support

Deliver:

* shape metadata;
* constant dimension mismatch checks;
* repeated symbol checks.

Acceptance:

matmul(a_3x4, b_5x2)  # mypy error

when annotations expose constant shapes.

Milestone 10: docs and examples

Deliver docs for:

* refinements;
* checked functions;
* sized collections;
* NumPy arrays;
* proofs;
* registry metadata;
* mypy plugin setup;
* limitations.

Include a clear limitations page. Do not bury the “not a complete theorem prover” bit in a footnote like a villain.

18. Important limitations to document

The library cannot statically prove arbitrary Python predicates.

Runtime-only:

where(lambda x: expensive_arbitrary_python(x))

Plugin-supported:

GreaterThan[0]
Between[0, 1]
Sized[list[int], "n"]
NDArray[Shape["T", 3], Float64]

The plugin should be an incomplete but useful prover over structured metadata.

Do not promise full soundness for all Python.

19. Example user experience

19.1 Refined scalar

from typing import Annotated
from depend import checked, GreaterThan
PositiveInt = Annotated[int, GreaterThan[0]]
@checked
def sqrt_int(x: PositiveInt) -> float:
    return x ** 0.5

19.2 Sized collections

from depend import checked, Sized
@checked
def dot(
    a: Sized[list[float], "n"],
    b: Sized[list[float], "n"],
) -> float:
    return sum(x * y for x, y in zip(a, b))

19.3 NumPy shapes

from depend import checked
from depend.numpy import NDArray, Shape, Float64
@checked
def matmul(
    a: NDArray[Shape["m", "n"], Float64],
    b: NDArray[Shape["n", "p"], Float64],
) -> NDArray[Shape["m", "p"], Float64]:
    return a @ b

19.4 Runtime registry

from depend import register, label_of
@register(to=SubjectId.LEFT_SHOE)
class ShoeSegments(SegmentId):
    SHOE = "shoe"
assert label_of(ShoeSegments.SHOE) == "left_shoe:shoe"

20. Definition of done

The project is complete when:

1. runtime validation works for refinements, checked functions, sized values, dataclasses, proofs, registries, and NumPy arrays;
2. error messages are clear and tested;
3. mypy plugin catches obvious violations for known predicates;
4. mypy plugin narrows ensure(...) for supported refinements;
5. mypy plugin supports basic Sized and NDArray metadata;
6. docs clearly explain supported static versus runtime-only behavior;
7. tests cover both runtime and mypy behavior;
8. the public API feels like normal Python annotations, not like a cursed embedded language.

21. Guiding rule for the coding agent

Prefer boring, composable pieces.

Do not build a grand theorem prover first.

Build:

Predicate
Context
validate
checked
Sized
NDArray
mypy support

in that order.

Every feature must work at runtime before it gets static support.

Every static feature must degrade gracefully to runtime validation when proof is unavailable.

Every error must explain what failed, where it failed, what was expected, and what was received.

That is how this becomes a useful library instead of a very impressive way to lose a month.

The plan is intentionally scoped as runtime-first, plugin-assisted. That’s the version that can actually ship without needing to reimplement half of Idris while mypy quietly judges everyone involved.