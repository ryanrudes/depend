# Proofs

`Proof` is a runtime certificate that a value satisfied an annotation at a specific moment. `prove(...)` constructs the certificate, `ensured(...)` validates before yielding, and `RequiresProof[...]` checks that a proof matches the value currently in scope.

## Example

```python
from depend import RequiresProof, ValidationError, checked, ensured, prove, refined

PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")

@checked
def divide(x: float, y: PositiveInt, proof: RequiresProof["y", PositiveInt]) -> float:
    return x / y

y = 4
proof = prove(y, PositiveInt)

with ensured(y, PositiveInt) as value:
    assert divide(12.0, value, proof) == 3.0

try:
    divide(12.0, y, prove(y, refined(int, lambda x: x >= 0, name="NonNegativeInt")))
except ValidationError:
    pass
```

