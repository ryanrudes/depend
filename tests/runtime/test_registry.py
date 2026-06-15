from __future__ import annotations

from enum import Enum

from depend import children_of, label_of, parent_of, register


class Subjects(Enum):
    SUBJECT_A = "subjectA"
    SUBJECT_B = "subjectB"


@register(to=Subjects.SUBJECT_A)
class SubjectASegments:
    SEGMENT_1 = "segment1"
    SEGMENT_2 = "segment2"


def test_registry_metadata() -> None:
    assert label_of(Subjects.SUBJECT_A) == "subjectA"
    assert label_of(SubjectASegments.SEGMENT_1) == "subjectA:segment1"
    assert parent_of(SubjectASegments.SEGMENT_1) == Subjects.SUBJECT_A
    assert set(children_of(Subjects.SUBJECT_A)) == {"segment1", "segment2"}
    assert Subjects.SUBJECT_A.value == "subjectA"
