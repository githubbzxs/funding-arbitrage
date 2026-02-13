import asyncio
import time
from datetime import datetime

import httpx

from app.core.config import get_settings
from app.exchanges.base import BaseExchangeFetcher
from app.exchanges.leverage import get_leverage_map
from app.exchanges.utils import build_snapshot, normalize_usdt_symbol, parse_exchange_timestamp, safe_float
from app.models.schemas import MarketSnapshot


class OkxFetcher(BaseExchangeFetcher):
    exchange = "okx"

    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        instruments_task = self._request_json(
            client,
            "https://www.okx.com/api/v5/public/instruments",
            params={"instType": "SWAP"},
        )
        tickers_task = self._request_json(
            client,
            "https://www.okx.com/api/v5/market/tickers",
            params={"instType": "SWAP"},
        )
        open_interest_task = self._request_json(
            client,
            "https://www.okx.com/api/v5/public/open-interest",
            params={"instType": "SWAP"},
        )

        instruments_resp, tickers_resp, open_interest_resp = await asyncio.gather(
            instruments_task,
            tickers_task,
            open_interest_task,
        )
        instruments = instruments_resp.get("data", [])
        tickers = tickers_resp.get("data", [])
        open_interests = open_interest_resp.get("data", [])

        usdt_swaps = [
            item
            for item in instruments
            if item.get("instType") == "SWAP"
            and item.get("settleCcy") == "USDT"
            and item.get("state") == "live"
        ]
        inst_ids = [item["instId"] for item in usdt_swaps if item.get("instId")]
        funding_map = await self._fetch_funding_rates(client, inst_ids)
        leverage_map = await get_leverage_map(self.exchange)

        ticker_map = {row.get("instId"): row for row in tickers if row.get("instId")}
        oi_map = {row.get("instId"): row for row in open_interests if row.get("instId")}

        snapshots: list[MarketSnapshot] = []
        for item in usdt_swaps:
            inst_id = item.get("instId")
            if not inst_id:
                continue

            funding = funding_map.get(inst_id, {})
            ticker = ticker_map.get(inst_id, {})
            oi = oi_map.get(inst_id, {})

            last_price = safe_float(ticker.get("last"))
            vol_ccy = safe_float(ticker.get("volCcy24h"))
            vol24h_usd = None
            if last_price is not None and vol_ccy is not None:
                vol24h_usd = last_price * vol_ccy

            funding_interval_hours = _infer_okx_funding_interval(
                parse_exchange_timestamp(funding.get("fundingTime"), unit="ms"),
                parse_exchange_timestamp(funding.get("nextFundingTime"), unit="ms"),
            )
            normalized_symbol = normalize_usdt_symbol(inst_id)
            max_leverage = safe_float(item.get("lever"))
            if max_leverage is None and normalized_symbol:
                max_leverage = leverage_map.get(normalized_symbol)

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=inst_id,
                oi_usd=safe_float(oi.get("oiUsd")),
                vol24h_usd=vol24h_usd,
                funding_rate_raw=safe_float(funding.get("fundingRate")),
                funding_interval_hours=funding_interval_hours,
                next_funding_time=parse_exchange_timestamp(funding.get("nextFundingTime"), unit="ms"),
                max_leverage=max_leverage,
                mark_price=last_price,
            )
            if snapshot:
                snapshots.append(snapshot)

        return snapshots

    async def _fetch_funding_rates(
        self,
        client: httpx.AsyncClient,
        inst_ids: list[str],
    ) -> dict[str, dict]:
        settings = get_settings()
        concurrency = max(4, settings.max_concurrency_per_exchange)
        semaphore = asyncio.Semaphore(concurrency)
        budget_seconds = max(0.5, settings.okx_funding_fetch_budget_seconds)
        started_at = time.monotonic()
        result: dict[str, dict] = {}

        async def worker(inst_id: str) -> None:
            # OKX funding-rate 需要逐合约请求，合约数较多时会显著拖慢整次快照。
            # 这里做一个总体时间预算：超时后直接降级返回部分 funding-rate，
            # 避免前端 Nginx 等待超时导致 504。
            if time.monotonic() - started_at > budget_seconds:
                return
            async with semaphore:
                if time.monotonic() - started_at > budget_seconds:
                    return
                try:
                    payload = await self._request_json(
                        client,
                        "https://www.okx.com/api/v5/public/funding-rate",
                        params={"instId": inst_id},
                    )
                except Exception:
                    return

                rows = payload.get("data", [])
                if rows:
                    result[inst_id] = rows[0]

        batch_size = concurrency * 3
        for offset in range(0, len(inst_ids), batch_size):
            if time.monotonic() - started_at > budget_seconds:
                break
            batch = inst_ids[offset : offset + batch_size]
            await asyncio.gather(*(worker(inst_id) for inst_id in batch))
        return result


def _infer_okx_funding_interval(
    funding_time: datetime | None,
    next_funding_time: datetime | None,
) -> float:
    if funding_time and next_funding_time:
        diff_hours = (next_funding_time - funding_time).total_seconds() / 3600
        if diff_hours > 0:
            return diff_hours
    return 8.0
