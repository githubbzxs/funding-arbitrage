import pytest

from app.services.rates import convert_funding_rate


def test_convert_funding_rate_basic() -> None:
    rate_1h, rate_8h, rate_1y, nominal_rate_1y = convert_funding_rate(0.0004, 8)
    assert rate_1h == 0.00005
    assert rate_8h == 0.0004
    assert nominal_rate_1y == pytest.approx(0.438)
    assert rate_1y is not None
    assert rate_1y > 0
