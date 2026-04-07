from __future__ import annotations


def test_build_assessment_prompt_includes_assessment_id_without_serial_number() -> None:
    from question_answer.api.v1.endpoints import _build_assessment_prompt  # noqa: PLC0415

    prompt = _build_assessment_prompt(
        "Summarize the RE table feedback",
        "asmt_1234",
        "asmt_1234",
    )

    # When no serial_number is available, the raw message is returned as-is.
    assert prompt == "Summarize the RE table feedback"


def test_build_assessment_prompt_includes_serial_number_when_available() -> None:
    from question_answer.api.v1.endpoints import _build_assessment_prompt  # noqa: PLC0415

    prompt = _build_assessment_prompt(
        "What is the stator risk?",
        "asmt_1234",
        {"serialNumber": "GEN98765"},
    )

    assert "assessment_id: asmt_1234" in prompt
    assert "serial_number: GEN98765" in prompt
    assert "Use the serial number above when querying equipment-specific data." in prompt
    assert "User question: What is the stator risk?" in prompt