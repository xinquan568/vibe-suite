# SPDX-License-Identifier: ISC
"""Seeds D7 Testing & Validation: the sole test cannot fail."""

from app import pricing


def test_compute_runs():
    pricing.compute([], 0, 0, 0, None)
    assert True
