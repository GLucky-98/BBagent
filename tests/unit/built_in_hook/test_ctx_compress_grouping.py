"""Tests for single-threshold turn grouping in compress and memory subsystems."""

import pytest

from bbagent.built_in_hook.ctx_compress_hook import _group_turns_for_compress
from bbagent.built_in_hook.memory.memory_hook import _group_turns_for_extraction
from bbagent.core.message import Turn


class DummyLogger:
    def debug(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def span(self, _name):
        class Span:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return Span()

    def set_trace_id(self, *_args, **_kwargs):
        pass

    def clear_trace_id(self):
        pass


def make_turn(token_count: int, index: int = 0) -> Turn:
    """Create a minimal Turn with a specific token count."""
    t = Turn()
    t.token_count = token_count
    return t


def token_sums(groups):
    """Return list of total tokens per group."""
    return [sum(turn.token_count for turn in group) for group in groups]


def turn_counts(groups):
    """Return list of turn counts per group."""
    return [len(group) for group in groups]


# ── compress grouping ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tokens, mt, expected_groups, expected_sums",
    [
        # all small turns accumulate
        ([4000, 4000, 4000, 4000, 4000], 20000, 1, [20000]),
        # trigger new group
        ([4000, 4000, 4000, 4000, 4000, 4000], 20000, 2, [20000, 4000]),
        # single oversized turn
        ([25000], 20000, 1, [25000]),
        # oversized turn in the middle
        ([4000, 25000, 4000], 20000, 3, [4000, 25000, 4000]),
        # boundary exactly equal to merge_threshold
        ([20000, 1], 20000, 2, [20000, 1]),
        # empty input
        ([], 20000, 0, []),
        # single turn exactly at merge_threshold
        ([20000], 20000, 1, [20000]),
        # two turns each exactly half
        ([10000, 10000], 20000, 1, [20000]),
        # fit three + one leftover
        ([7000, 6000, 7000, 3000], 20000, 2, [20000, 3000]),
        # oversized + many small
        ([30000, 1000, 1000, 1000, 1000], 20000, 2, [30000, 4000]),
    ],
)
def test_compress_grouping(tokens, mt, expected_groups, expected_sums):
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_compress(turns, mt, logger=DummyLogger())
    assert len(groups) == expected_groups
    assert token_sums(groups) == expected_sums


def test_compress_grouping_warns_on_oversized():
    warnings = []

    class CaptureLogger(DummyLogger):
        def warning(self, msg, *args, **kwargs):
            warnings.append(msg)

    turns = [make_turn(25000)]
    _group_turns_for_compress(turns, 20000, logger=CaptureLogger())
    assert len(warnings) == 1
    assert "25000" in warnings[0]
    assert "20000" in warnings[0]


def test_compress_grouping_infos_on_many_turns_in_group():
    infos = []

    class CaptureLogger(DummyLogger):
        def info(self, msg, *args, **kwargs):
            infos.append(msg)

    turns = [make_turn(3000) for _ in range(7)]  # 7 turns x 3000 = 21000 → 1 group of 6 + 1 leftover
    _group_turns_for_compress(turns, 20000, logger=CaptureLogger())
    assert any("6 turns" in m for m in infos)


# ── memory extract grouping ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tokens, mt, expected_groups, expected_sums",
    [
        ([4000, 4000, 4000, 4000, 4000], 20000, 1, [20000]),
        ([4000, 4000, 4000, 4000, 4000, 4000], 20000, 2, [20000, 4000]),
        ([25000], 20000, 1, [25000]),
        ([4000, 25000, 4000], 20000, 3, [4000, 25000, 4000]),
        ([20000, 1], 20000, 2, [20000, 1]),
        ([], 20000, 0, []),
        ([20000], 20000, 1, [20000]),
    ],
)
def test_extract_grouping(tokens, mt, expected_groups, expected_sums):
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_extraction(turns, mt)
    assert len(groups) == expected_groups
    assert token_sums(groups) == expected_sums


def test_both_functions_produce_identical_results():
    """After unification, both grouping functions should behave identically."""
    turns = [make_turn(t) for t in [4000, 5000, 6000, 25000, 3000, 2000]]
    compress_groups = _group_turns_for_compress(turns, 20000, logger=DummyLogger())
    extract_groups = _group_turns_for_extraction(turns, 20000)
    assert token_sums(compress_groups) == token_sums(extract_groups)
    assert turn_counts(compress_groups) == turn_counts(extract_groups)


# ── edge cases & invariants ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "tokens, mt, expected_groups, expected_sums, expected_turn_counts",
    [
        # issue doc case: old 3 groups, new 2 groups
        ([4000, 4000, 5000, 4000, 4000], 20000, 2, [17000, 4000], [4, 1]),
        # consecutive oversized turns
        ([30000, 35000, 5000], 20000, 3, [30000, 35000, 5000], [1, 1, 1]),
        # consecutive oversized + small at end
        ([30000, 25000, 1000, 1000], 20000, 3, [30000, 25000, 2000], [1, 1, 2]),
        # very small merge_threshold
        ([100, 50, 30, 20], 100, 2, [100, 100], [1, 3]),
        # all zero-token turns
        ([0, 0, 0], 20000, 1, [0], [3]),
        # zero-token turns mixed
        ([4000, 0, 0, 6000], 20000, 1, [10000], [4]),
        # many boundary-fitting turns
        ([5000] * 4, 20000, 1, [20000], [4]),
        ([5000] * 5, 20000, 2, [20000, 5000], [4, 1]),
        # single token turns, mt=5
        ([1] * 3, 5, 1, [3], [3]),
        ([1] * 7, 5, 2, [5, 2], [5, 2]),
        # single turn exactly at mt followed by oversized
        ([20000, 25000], 20000, 2, [20000, 25000], [1, 1]),
        # just barely fits
        ([9999, 9999, 2], 20000, 1, [20000], [3]),
        # overflow by 1
        ([10000, 10000, 1], 20000, 2, [20000, 1], [2, 1]),
        # un-even distribution: 1+19000+999=20000, +1 overflows
        ([1, 19000, 999, 1], 20000, 2, [20000, 1], [3, 1]),
    ],
)
def test_compress_grouping_extended(tokens, mt, expected_groups, expected_sums, expected_turn_counts):
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_compress(turns, mt, logger=DummyLogger())
    assert len(groups) == expected_groups
    assert token_sums(groups) == expected_sums
    assert turn_counts(groups) == expected_turn_counts


def test_no_group_exceeds_merge_threshold_except_oversized_solo():
    """Invariant: every group's total ≤ merge_threshold, unless it's a single oversized turn."""
    tokens = [4000, 25000, 3000, 12000, 8000, 1, 1000, 35000, 5000]
    mt = 20000
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_compress(turns, mt, logger=DummyLogger())
    for group in groups:
        group_total = sum(t.token_count for t in group)
        if len(group) == 1 and group[0].token_count > mt:
            continue  # oversized single-turn group is allowed
        assert group_total <= mt, f"Group total {group_total} > merge_threshold {mt}"


def test_turn_order_preserved():
    """Invariant: flatten(groups) preserves original turn sequence."""
    tokens = [4000, 25000, 3000, 12000, 8000, 1, 1000, 35000, 5000]
    mt = 20000
    turns = [make_turn(t) for t in tokens]
    run_ids = [id(t) for t in turns]
    groups = _group_turns_for_compress(turns, mt, logger=DummyLogger())
    flattened = []
    for group in groups:
        flattened.extend(group)
    restored = [id(t) for t in flattened]
    assert restored == run_ids


def test_no_turns_lost_or_duplicated():
    """Invariant: total turn count across all groups equals input."""
    tokens = [4000, 25000, 3000, 12000, 8000, 1, 1000, 35000, 5000]
    mt = 20000
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_compress(turns, mt, logger=DummyLogger())
    total_grouped = sum(len(group) for group in groups)
    assert total_grouped == len(tokens)


def test_extract_invariant_no_group_exceeds_threshold():
    """Same invariant for memory extraction grouping."""
    tokens = [5000, 4000, 25000, 6000, 7000, 3000, 1000]
    mt = 20000
    turns = [make_turn(t) for t in tokens]
    groups = _group_turns_for_extraction(turns, mt)
    for group in groups:
        group_total = sum(t.token_count for t in group)
        if len(group) == 1 and group[0].token_count > mt:
            continue
        assert group_total <= mt, f"Group total {group_total} > merge_threshold {mt}"


def test_extract_order_and_count_invariants():
    """Extraction grouping also preserves order and count."""
    tokens = [5000, 4000, 25000, 6000, 7000, 3000, 1000]
    mt = 20000
    turns = [make_turn(t) for t in tokens]
    run_ids = [id(t) for t in turns]
    groups = _group_turns_for_extraction(turns, mt)
    # order preserved
    flattened = []
    for group in groups:
        flattened.extend(group)
    assert [id(t) for t in flattened] == run_ids
    # no loss
    assert sum(len(g) for g in groups) == len(tokens)


def test_warning_not_emitted_for_normal_turns():
    infos_and_warns = []

    class CaptureLogger(DummyLogger):
        def info(self, msg, *args, **kwargs):
            infos_and_warns.append(("info", msg))

        def warning(self, msg, *args, **kwargs):
            infos_and_warns.append(("warning", msg))

    turns = [make_turn(5000) for _ in range(4)]  # all fit in 20k
    _group_turns_for_compress(turns, 20000, logger=CaptureLogger())
    # 4 turns → no oversized warning, no >5 turn info
    for level, msg in infos_and_warns:
        assert level != "warning", f"Unexpected warning: {msg}"


def test_multiple_oversized_turns_all_warn():
    warnings = []

    class CaptureLogger(DummyLogger):
        def warning(self, msg, *args, **kwargs):
            warnings.append(msg)

    turns = [make_turn(25000), make_turn(30000), make_turn(35000)]
    _group_turns_for_compress(turns, 20000, logger=CaptureLogger())
    assert len(warnings) == 3
