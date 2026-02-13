from app.exchanges.leverage import _parse_binance_public_brackets


def test_parse_binance_public_brackets() -> None:
    payload = {
        "code": "000000",
        "data": {
            "brackets": [
                {
                    "symbol": "BTCUSDT",
                    "riskBrackets": [
                        {"maxOpenPosLeverage": 125},
                        {"maxOpenPosLeverage": 50},
                    ],
                },
                {
                    "symbol": "ETHUSDT",
                    "maxLeverage": 75,
                    "riskBrackets": [],
                },
                {
                    "symbol": "BTCUSD",
                    "riskBrackets": [{"maxOpenPosLeverage": 100}],
                },
            ]
        },
    }

    leverage_map = _parse_binance_public_brackets(payload)
    assert leverage_map["BTCUSDT"] == 125
    assert leverage_map["ETHUSDT"] == 75
    assert "BTCUSD" not in leverage_map
