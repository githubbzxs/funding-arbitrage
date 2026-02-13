import asyncio

import httpx
from pydantic import TypeAdapter

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import get_settings
from app.exchanges.binance import BinanceFetcher
from app.exchanges.bitget import BitgetFetcher
from app.exchanges.bybit import BybitFetcher
from app.exchanges.gateio import GateIoFetcher
from app.exchanges.okx import OkxFetcher
from app.models.schemas import FetchError, MarketSnapshot, MarketSnapshotsResponse


_snapshot_list_adapter = TypeAdapter(list[MarketSnapshot])
_error_list_adapter = TypeAdapter(list[FetchError])


class MarketDataService:
    """聚合 5 所公共行情并统一结构。"""

    def __init__(self) -> None:
        self._fetchers = [
            BinanceFetcher(),
            OkxFetcher(),
            BybitFetcher(),
            BitgetFetcher(),
            GateIoFetcher(),
        ]
        self._settings = get_settings()

    async def fetch_snapshots(self) -> MarketSnapshotsResponse:
        cache_key = "fa:market:snapshots:v1"
        cached = await cache_get_json(cache_key)
        if isinstance(cached, dict):
            snapshots_raw = cached.get("snapshots", [])
            errors_raw = cached.get("errors", [])
            try:
                snapshots = _snapshot_list_adapter.validate_python(snapshots_raw)
                errors = _error_list_adapter.validate_python(errors_raw)
                return MarketSnapshotsResponse(snapshots=snapshots, errors=errors)
            except Exception:
                pass

        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        limits = httpx.Limits(max_connections=200, max_keepalive_connections=50)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            tasks = [self._fetch_single(fetcher, client) for fetcher in self._fetchers]
            results = await asyncio.gather(*tasks)

        merged_snapshots: list[MarketSnapshot] = []
        errors: list[FetchError] = []

        for snapshots, error in results:
            merged_snapshots.extend(snapshots)
            if error:
                errors.append(error)

        # 保留同交易所同 symbol 的最新一条数据。
        dedup: dict[tuple[str, str], MarketSnapshot] = {}
        for item in merged_snapshots:
            dedup[(item.exchange, item.symbol)] = item

        snapshots = sorted(dedup.values(), key=lambda row: (row.symbol, row.exchange))
        response = MarketSnapshotsResponse(snapshots=snapshots, errors=errors)
        await cache_set_json(cache_key, response.model_dump(mode="json"), self._settings.market_cache_ttl_seconds)
        return response

    async def _fetch_single(
        self,
        fetcher,
        client: httpx.AsyncClient,
    ) -> tuple[list[MarketSnapshot], FetchError | None]:
        try:
            data = await asyncio.wait_for(
                fetcher.fetch_snapshots(client),
                timeout=self._settings.exchange_fetch_timeout_seconds,
            )
            return data, None
        except asyncio.TimeoutError:
            return [], FetchError(exchange=fetcher.exchange, message="抓取超时")
        except Exception as exc:
            return [], FetchError(exchange=fetcher.exchange, message=str(exc))
