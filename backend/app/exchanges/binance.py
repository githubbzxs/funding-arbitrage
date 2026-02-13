import asyncio

import httpx

from app.core.config import get_settings
from app.exchanges.base import BaseExchangeFetcher
from app.exchanges.leverage import get_leverage_map
from app.exchanges.utils import build_snapshot, parse_exchange_timestamp, safe_float
from app.models.schemas import MarketSnapshot


class BinanceFetcher(BaseExchangeFetcher):
    exchange = "binance"

    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        premium_task = self._request_json(client, "https://fapi.binance.com/fapi/v1/premiumIndex")
        ticker_task = self._request_json(client, "https://fapi.binance.com/fapi/v1/ticker/24hr")
        exchange_info_task = self._request_json(client, "https://fapi.binance.com/fapi/v1/exchangeInfo")

        premium_list, ticker_list, exchange_info = await asyncio.gather(
            premium_task,
            ticker_task,
            exchange_info_task,
        )
        symbols_meta = exchange_info.get("symbols", [])
        usdt_perp_symbols = [
            row.get("symbol")
            for row in symbols_meta
            if row.get("quoteAsset") == "USDT"
            and row.get("contractType") == "PERPETUAL"
            and row.get("status") == "TRADING"
        ]
        usdt_perp_symbols = [symbol for symbol in usdt_perp_symbols if symbol]

        premium_map = {row.get("symbol"): row for row in premium_list if row.get("symbol")}
        volume_map = {row.get("symbol"): safe_float(row.get("quoteVolume")) for row in ticker_list if row.get("symbol")}
        leverage_map = await get_leverage_map(self.exchange)
        oi_map = await self._fetch_open_interest_map(client, usdt_perp_symbols)

        snapshots: list[MarketSnapshot] = []
        for symbol in usdt_perp_symbols:
            premium = premium_map.get(symbol, {})
            mark_price = safe_float(premium.get("markPrice"))
            oi_qty = oi_map.get(symbol)
            oi_usd = None
            if oi_qty is not None and mark_price is not None:
                oi_usd = oi_qty * mark_price

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=symbol,
                oi_usd=oi_usd,
                vol24h_usd=volume_map.get(symbol),
                funding_rate_raw=safe_float(premium.get("lastFundingRate")),
                funding_interval_hours=8.0,
                next_funding_time=parse_exchange_timestamp(premium.get("nextFundingTime"), unit="ms"),
                max_leverage=leverage_map.get(symbol),
                mark_price=mark_price,
            )
            if snapshot:
                snapshots.append(snapshot)

        return snapshots

    async def _fetch_open_interest_map(
        self,
        client: httpx.AsyncClient,
        symbols: list[str],
    ) -> dict[str, float]:
        settings = get_settings()
        semaphore = asyncio.Semaphore(max(4, settings.max_concurrency_per_exchange))
        oi_map: dict[str, float] = {}

        async def worker(symbol: str) -> None:
            async with semaphore:
                try:
                    payload = await self._request_json(
                        client,
                        "https://fapi.binance.com/fapi/v1/openInterest",
                        params={"symbol": symbol},
                    )
                except Exception:
                    return
                value = safe_float(payload.get("openInterest"))
                if value is not None:
                    oi_map[symbol] = value

        await asyncio.gather(*(worker(symbol) for symbol in symbols))
        return oi_map

