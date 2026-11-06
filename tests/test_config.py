import pytest

from tuition_synth.config import BASE_VOLUMES, Config


def test_full_scale_matches_statement():
    cfg = Config()
    assert cfg.seed == 20261022
    assert cfg.volume("students") == 10_000
    assert cfg.volume("programs") == 20
    assert cfg.volume("invoices") == 30_000
    assert cfg.volume("scholarships") == 15_000
    assert cfg.volume("payments") == 50_000


def test_scale_applies_but_programs_stay_fixed():
    cfg = Config(scale=0.02)
    assert cfg.volume("students") == 200
    assert cfg.volume("payments") == 1_000
    assert cfg.volume("programs") == BASE_VOLUMES["programs"]


def test_invalid_scale_rejected():
    with pytest.raises(ValueError):
        Config(scale=0)
