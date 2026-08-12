"""Unit tests for GraphState's checkpoint-safety.

AsyncPostgresSaver checkpoints the full GraphState dict to PostgreSQL on every
node transition. A live Langfuse SDK trace object is not something that
should ever be put in that dict — it isn't reliably serialisable, and even if
it were, deserialising it after a restart would produce a stale, unusable
handle. This test guards against that field ever coming back.
"""
import sys
from pathlib import Path
from typing import get_type_hints

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "rag" / "agentic-rag" / "src"))

from state import GraphState  # noqa: E402

# state.py uses `from __future__ import annotations`, so GraphState.__annotations__
# holds unresolved forward-reference strings — resolve them via get_type_hints()
# to compare against actual types.
_hints = get_type_hints(GraphState)


def test_graph_state_has_no_live_trace_object_field():
    assert "lf_trace" not in _hints


def test_graph_state_trace_id_is_a_plain_string():
    assert _hints["trace_id"] is str


def test_graph_state_hitl_fields_present():
    assert _hints["hitl_approved"] is bool
    assert _hints["thread_id"] is str


def test_graph_state_does_not_use_langgraph_reserved_channel_names():
    # LangGraph reserves "checkpoint_id" as an internal channel name (part of
    # its own checkpoint-tuple config schema) and raises
    # ValueError("Channel name 'checkpoint_id' is reserved") at graph.compile()
    # time if a state schema field uses it. The public API's response field
    # is still called checkpoint_id — only the internal GraphState key must
    # avoid it.
    assert "checkpoint_id" not in _hints
