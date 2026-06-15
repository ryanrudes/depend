from __future__ import annotations

import pytest

from depend import Proof, RequiresProof, ValidationError, ensured, prove, checked, refined


PositiveInt = refined(int, lambda x: x > 0, name="PositiveInt")
NonNegativeInt = refined(int, lambda x: x >= 0, name="NonNegativeInt")


def test_prove_returns_runtime_certificate() -> None:
    value = 4
    proof = prove(value, PositiveInt)

    assert isinstance(proof, Proof)
    assert proof.value_id == id(value)
    assert proof.predicate_name == "PositiveInt"
    assert proof.annotation_fingerprint


def test_requires_proof_validates_argument_identity_and_annotation() -> None:
    @checked
    def divide(x: float, y: PositiveInt, proof: RequiresProof["y", PositiveInt]) -> float:
        return x / y

    y = 4
    proof = prove(y, PositiveInt)
    assert divide(12.0, y, proof) == 3.0

    with pytest.raises(ValidationError):
        divide(12.0, y, prove(5, PositiveInt))

    with pytest.raises(ValidationError):
        divide(12.0, y, prove(y, NonNegativeInt))


def test_ensured_context_manager_validates_on_entry() -> None:
    with ensured(3, PositiveInt) as value:
        assert value == 3

    with pytest.raises(ValidationError):
        with ensured(-1, PositiveInt):
            pass
