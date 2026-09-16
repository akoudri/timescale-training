import numpy as np

from mistral_gen.rng import rng_pour


def test_reproductible():
    a = rng_pour(20260315, "vent", 3).normal(size=100)
    b = rng_pour(20260315, "vent", 3).normal(size=100)
    assert np.array_equal(a, b)


def test_volets_independants():
    a = rng_pour(20260315, "vent", 3).normal(size=100)
    b = rng_pour(20260315, "vent", 4).normal(size=100)
    c = rng_pour(20260315, "trous", 3).normal(size=100)
    assert not np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_sensible_a_la_graine():
    a = rng_pour(20260315, "vent").normal(size=10)
    b = rng_pour(20260316, "vent").normal(size=10)
    assert not np.array_equal(a, b)
