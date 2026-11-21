"""The demo generator runs the real rules end to end, and can't touch dues.db."""
from pathlib import Path

import pytest

from app import clock
from app.demo_seed import generate


def test_generates_a_small_demo_shop(tmp_path):
    counts = generate(customers=8, days=45, seed=1, verbose=False, path=tmp_path / "demo-test.db")
    assert counts["entries"] > 0 and counts["payments"] > 0
    assert (tmp_path / "demo-test.db").exists()
    clock.reset()


def test_refuses_to_overwrite_the_real_database(tmp_path):
    with pytest.raises(ValueError):
        generate(customers=1, days=1, verbose=False, path=tmp_path / "dues.db")
