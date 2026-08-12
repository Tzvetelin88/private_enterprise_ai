"""Unit tests for the GradeResult Pydantic model and its parsers.

These tests verify that grade_documents always returns a validated
'relevant' or 'irrelevant' string — never freeform LLM text.

nodes.py's primary parsing path is PydanticOutputParser(GradeResult) against
a real LangChain LLM call; _parse_grade is the lenient regex/keyword fallback
used only if PydanticOutputParser fails on every retry. Both are inlined here
(copied from nodes.py) so we can test them independently without needing the
full service context (relative imports, settings, an actual Ollama server, etc.).
"""
import json
import re
import logging
from typing import Literal

import pytest
from pydantic import BaseModel, Field
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser


# ── Inline copy of the Pydantic model and parser from nodes.py ───────────────
# This lets us unit-test the core logic without loading the full service module.

class GradeResult(BaseModel):
    """Validated LLM grading output — grade is always 'relevant' or 'irrelevant'."""
    grade: Literal["relevant", "irrelevant"] = Field(
        ...,
        description="Whether the retrieved documents are relevant to the question.",
    )


logger = logging.getLogger(__name__)


def _parse_grade(raw: str, retries_left: int = 2) -> str:
    """Parse LLM output into a validated GradeResult grade."""
    json_match = re.search(r'\{[^}]*"grade"[^}]*\}', raw, re.IGNORECASE)
    if json_match:
        try:
            data = json.loads(json_match.group())
            result = GradeResult(**data)
            return result.grade
        except Exception:
            pass

    lower = raw.strip().lower()
    if lower in ("relevant", "irrelevant"):
        return lower
    if "irrelevant" in lower:
        return "irrelevant"
    if "relevant" in lower:
        return "relevant"

    if retries_left > 0:
        logger.debug("Grade parse failed on '%s', %d retries left — returning relevant", raw, retries_left)
    else:
        logger.warning("Grade parse exhausted retries on '%s' — defaulting to relevant", raw)
    return "relevant"


class TestGradeResult:
    """GradeResult Pydantic model validation."""

    def test_valid_relevant(self):
        result = GradeResult(grade="relevant")
        assert result.grade == "relevant"

    def test_valid_irrelevant(self):
        result = GradeResult(grade="irrelevant")
        assert result.grade == "irrelevant"

    def test_invalid_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GradeResult(grade="yes")

    def test_invalid_case_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GradeResult(grade="RELEVANT")

    def test_invalid_freeform_raises(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            GradeResult(grade="The documents are relevant to the question.")


class TestParseGrade:
    """_parse_grade() — multi-strategy parser with retry/default logic."""

    def test_exact_relevant(self):
        assert _parse_grade("relevant") == "relevant"

    def test_exact_irrelevant(self):
        assert _parse_grade("irrelevant") == "irrelevant"

    def test_json_relevant(self):
        assert _parse_grade('{"grade": "relevant"}') == "relevant"

    def test_json_irrelevant(self):
        assert _parse_grade('{"grade": "irrelevant"}') == "irrelevant"

    def test_json_embedded_in_prose(self):
        assert _parse_grade('Here is my answer: {"grade": "irrelevant"} end.') == "irrelevant"

    def test_keyword_relevant_in_sentence(self):
        assert _parse_grade("These documents are relevant.") == "relevant"

    def test_keyword_irrelevant_in_sentence(self):
        assert _parse_grade("The docs are irrelevant to the question.") == "irrelevant"

    def test_case_insensitive_keyword(self):
        # After .lower() the word "IRRELEVANT" becomes "irrelevant" in the check
        assert _parse_grade("IRRELEVANT") == "irrelevant"

    def test_case_insensitive_relevant(self):
        assert _parse_grade("RELEVANT") == "relevant"

    def test_malformed_json_falls_through_to_keyword(self):
        # Malformed JSON but contains the keyword
        assert _parse_grade('{"grade": relevant}') == "relevant"

    def test_unknown_output_defaults_to_relevant(self):
        # "YES" contains neither keyword → default to relevant
        assert _parse_grade("YES") == "relevant"

    def test_empty_string_defaults_to_relevant(self):
        assert _parse_grade("") == "relevant"

    def test_numeric_string_defaults_to_relevant(self):
        assert _parse_grade("1") == "relevant"

    def test_irrelevant_takes_precedence_over_relevant(self):
        # If both keywords appear, "irrelevant" contains "relevant" so it should still
        # return "irrelevant" (checked first)
        assert _parse_grade("irrelevant") == "irrelevant"

    def test_retries_left_parameter_does_not_change_logic(self):
        # retries_left only affects log output, not the parsed result
        assert _parse_grade("YES", retries_left=0) == "relevant"
        assert _parse_grade("YES", retries_left=2) == "relevant"


class TestPydanticOutputParserPrimaryPath:
    """The primary parse path used by grade_documents: a real
    PydanticOutputParser(GradeResult) against the LLM's raw text output —
    not the lenient _parse_grade heuristic. Confirms it accepts well-formed
    output and raises (triggering the retry/fallback path in nodes.py) on
    malformed output, exactly as grade_documents relies on.
    """

    parser = PydanticOutputParser(pydantic_object=GradeResult)

    def test_format_instructions_mention_grade_field(self):
        assert "grade" in self.parser.get_format_instructions().lower()

    def test_parses_clean_json(self):
        result = self.parser.parse('{"grade": "relevant"}')
        assert result.grade == "relevant"

    def test_parses_json_wrapped_in_markdown_fence(self):
        result = self.parser.parse('```json\n{"grade": "irrelevant"}\n```')
        assert result.grade == "irrelevant"

    def test_raises_on_invalid_enum_value(self):
        with pytest.raises(OutputParserException):
            self.parser.parse('{"grade": "YES"}')

    def test_raises_on_freeform_text(self):
        with pytest.raises(OutputParserException):
            self.parser.parse("The documents look relevant to me.")

    def test_raises_on_empty_string(self):
        with pytest.raises(OutputParserException):
            self.parser.parse("")
