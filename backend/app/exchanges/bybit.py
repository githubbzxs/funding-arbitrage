from typing import Any

import httpx

from app.exchanges.base import BaseExchangeFetcher
from app.exchanges.leverage import get_leverage_map
from app.exchanges.utils import build_snapshot, parse_exchange_timestamp, safe_float
from app.models.schemas import MarketSnapshot


class BybitFetcher(BaseExchangeFetcher):
    exchange = "bybit"

    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        tickers_resp = await self._request_json(
            client,
            "https://api.bybit.com/v5/market/tickers",
            params={"category": "linear"},
        )
        tickers = tickers_resp.get("result", {}).get("list", [])

        instruments = await self._fetch_instruments(client)
        instrument_map = {row.get("symbol"): row for row in instruments if row.get("symbol")}
        leverage_map = await get_leverage_map(self.exchange)

        snapshots: list[MarketSnapshot] = []
        for row in tickers:
            symbol = str(row.get("symbol", ""))
            if not symbol.endswith("USDT"):
                continue

            instrument = instrument_map.get(symbol, {})
            funding_interval_hours = safe_float(row.get("fundingIntervalHour"))
            if funding_interval_hours is None:
                funding_interval_minutes = safe_float(instrument.get("fundingInterval"))
                if funding_interval_minutes is not None:
                    funding_interval_hours = funding_interval_minutes / 60
            if funding_interval_hours is None:
                funding_interval_hours = 8.0

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=symbol,
                oi_usd=safe_float(row.get("openInterestValue")),
                vol24h_usd=safe_float(row.get("turnover24h")),
                funding_rate_raw=safe_float(row.get("fundingRate")),
                funding_interval_hours=funding_interval_hours,
                next_funding_time=parse_exchange_timestamp(row.get("nextFundingTime"), unit="ms"),
                max_leverage=safe_float(instrument.get("leverageFilter", {}).get("maxLeverage"))
                or leverage_map.get(symbol),
                mark_price=safe_float(row.get("markPrice")),
            )
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

    async def _fetch_instruments(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        all_rows: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"category": "linear", "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            resp = await self._request_json(
                client,
                "https://api.bybit.com/v5/market/instruments-info",
                params=params,
            )
            result = resp.get("result", {})
            rows = result.get("list", [])
            if not rows:
                break
            all_rows.extend(rows)
            cursor = result.get("nextPageCursor")
            if not cursor:
                break
        return all_rows

