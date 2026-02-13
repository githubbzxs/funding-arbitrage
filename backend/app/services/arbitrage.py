from itertools import combinations

from app.models.schemas import MarketSnapshot, Opportunity


def scan_opportunities(
    snapshots: list[MarketSnapshot],
    *,
    min_spread_rate_1y_nominal: float = 0.0,
) -> list[Opportunity]:
    """
    同一 symbol 在不同交易所两两配对，按名义年化利差降序输出。
    默认方向：做多低费率交易所，做空高费率交易所。
    """

    symbol_groups: dict[str, list[MarketSnapshot]] = {}
    for item in snapshots:
        if item.nominal_rate_1y is None:
            continue
        symbol_groups.setdefault(item.symbol, []).append(item)

    opportunities: list[Opportunity] = []
    for symbol, items in symbol_groups.items():
        if len(items) < 2:
            continue
        for left, right in combinations(items, 2):
            if left.exchange == right.exchange:
                continue
            left_rate = left.nominal_rate_1y
            right_rate = right.nominal_rate_1y
            if left_rate is None or right_rate is None:
                continue

            if left_rate <= right_rate:
                long_leg = left
                short_leg = right
            else:
                long_leg = right
                short_leg = left

            spread = (short_leg.nominal_rate_1y or 0.0) - (long_leg.nominal_rate_1y or 0.0)
            if spread < min_spread_rate_1y_nominal:
                continue

            opportunities.append(
                Opportunity(
                    symbol=symbol,
                    long_exchange=long_leg.exchange,
                    short_exchange=short_leg.exchange,
                    long_nominal_rate_1y=long_leg.nominal_rate_1y or 0.0,
                    short_nominal_rate_1y=short_leg.nominal_rate_1y or 0.0,
                    spread_rate_1y_nominal=spread,
                    long_rate_8h=long_leg.rate_8h,
                    short_rate_8h=short_leg.rate_8h,
                    long_funding_rate_raw=long_leg.funding_rate_raw,
                    short_funding_rate_raw=short_leg.funding_rate_raw,
                    long_next_funding_time=long_leg.next_funding_time,
                    short_next_funding_time=short_leg.next_funding_time,
                )
            )

    opportunities.sort(key=lambda item: item.spread_rate_1y_nominal, reverse=True)
    return opportunities

