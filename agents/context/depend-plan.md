# depend Project Plan

## Mission

Build an idiomatic Python library and mypy plugin for gradual dependent-style typing.

## Feature milestones

1. Runtime refinements
   - `Predicate`
   - `where`
   - `refined`
   - `validate`
   - `ensure`
   - `ValidationError`

2. Checked functions
   - `@checked`
   - argument validation
   - return validation
   - async support
   - disabled checks

3. Symbolic expressions and `Sized`
   - restricted expression parser
   - symbol binding context
   - collection length constraints
   - dependent return validation

4. Dataclasses and proofs
   - `checked_dataclass`
   - `dependent_dataclass`
   - `Proof`
   - `prove`
   - `RequiresProof`

5. NumPy support
   - `Shape`
   - `DType`
   - `NDArray`
   - dtype aliases

6. Registry metadata
   - `register`
   - `parent_of`
   - `children_of`
   - `label_of`

7. mypy plugin MVP
   - plugin entry point
   - `ensure` narrowing
   - known predicate literal checks

8. mypy `Sized` support
   - length metadata
   - literal length checks
   - symbol equality checks

9. mypy NumPy shape support
   - shape metadata
   - rank/dimension checks
   - dtype checks where known

10. Docs and examples

## Design mantra

Runtime first. Static assistance second. Honest limitations always.
