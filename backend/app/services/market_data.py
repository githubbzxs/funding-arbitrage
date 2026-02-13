import asyncio
import time
from typing import Any

from pydantic import TypeAdapter

from app.core.cache import cache_get_json, cache_set_json
from app.core.config import get_settings
from app.exchanges.providers import CcxtMarketProvider
from app.models.schemas import FetchError, MarketSnapshot, MarketSnapshotsResponse, SupportedExchange


_snapshot_list_adapter = TypeAdapter(list[MarketSnapshot])
_error_list_adapter = TypeAdapter(list[FetchError])


class MarketDataService:
    """聚合 5 所公共行情并统一结构。"""

    def __init__(self) -> None:
        self._fetchers = [
            CcxtMarketProvider("binance"),
            CcxtMarketProvider("okx"),
            CcxtMarketProvider("bybit"),
            CcxtMarketProvider("bitget"),
            CcxtMarketProvider("gateio"),
        ]
        self._settings = get_settings()
        self._local_cache_lock = asyncio.Lock()
        self._local_cache_expires_at_ts = 0.0
        self._local_cache_payload: MarketSnapshotsResponse | None = None
        self._last_success_snapshots: dict[SupportedExchange, list[MarketSnapshot]] = {}
        self._last_success_at_ts: dict[SupportedExchange, float] = {}
        self._stale_fallback_max_age_seconds = max(30, self._settings.market_cache_ttl_seconds * 6)

    async def fetch_snapshots(self) -> MarketSnapshotsResponse:
        now = time.monotonic()
        cached_local = self._local_cache_payload
        if cached_local is not None and self._local_cache_expires_at_ts > now:
            meta = dict(cached_local.meta or {})
            meta["cache_hit"] = True
            return cached_local.model_copy(update={"meta": meta, "as_of": cached_local.as_of})

        cache_key = "fa:market:snapshots:v2"
        cached = await cache_get_json(cache_key)
        if isinstance(cached, dict):
            snapshots_raw = cached.get("snapshots", [])
            errors_raw = cached.get("errors", [])
            meta_raw = cached.get("meta")
            try:
                snapshots = _snapshot_list_adapter.validate_python(snapshots_raw)
                errors = _error_list_adapter.validate_python(errors_raw)
                self._record_last_success_batch(snapshots)
                meta = meta_raw if isinstance(meta_raw, dict) else {}
                meta["cache_hit"] = True
                payload = MarketSnapshotsResponse(snapshots=snapshots, errors=errors, meta=meta)
                async with self._local_cache_lock:
                    self._local_cache_payload = payload
                    self._local_cache_expires_at_ts = time.monotonic() + self._settings.market_cache_ttl_seconds
                return payload
            except Exception:
                pass

        started_at = time.perf_counter()
        tasks = [self._fetch_single(fetcher) for fetcher in self._fetchers]
        results = await asyncio.gather(*tasks)

        merged_snapshots: list[MarketSnapshot] = []
        errors: list[FetchError] = []
        exchanges_ok: list[SupportedExchange] = []
        exchanges_failed: list[SupportedExchange] = []
        exchange_sources: dict[str, str] = {fetcher.exchange: "pending" for fetcher in self._fetchers}
        exchange_counts: dict[str, int] = {fetcher.exchange: 0 for fetcher in self._fetchers}

        for exchange, snapshots, error, source in results:
            if error is None:
                merged_snapshots.extend(snapshots)
                self._record_last_success(exchange, snapshots)
                exchanges_ok.append(exchange)
                exchange_sources[exchange] = source
                exchange_counts[exchange] = len(snapshots)
                continue

            errors.append(error)
            exchanges_failed.append(exchange)
            stale_snapshots = self._get_stale_snapshots(exchange)
            if stale_snapshots:
                merged_snapshots.extend(stale_snapshots)
                exchange_sources[exchange] = "stale"
                exchange_counts[exchange] = len(stale_snapshots)
            else:
                exchange_sources[exchange] = "failed"
                exchange_counts[exchange] = 0

        # 保留同交易所同 symbol 的最新一条数据。
        dedup: dict[tuple[str, str], MarketSnapshot] = {}
        for item in merged_snapshots:
            dedup[(item.exchange, item.symbol)] = item

        snapshots = sorted(dedup.values(), key=lambda row: (row.symbol, row.exchange))
        response = MarketSnapshotsResponse(
            snapshots=snapshots,
            errors=errors,
            meta={
                "fetch_ms": int((time.perf_counter() - started_at) * 1000),
                "cache_hit": False,
                "exchanges_ok": exchanges_ok,
                "exchanges_failed": exchanges_failed,
                "exchange_sources": exchange_sources,
                "exchange_counts": exchange_counts,
            },
        )
        await cache_set_json(cache_key, response.model_dump(mode="json"), self._settings.market_cache_ttl_seconds)
        async with self._local_cache_lock:
            self._local_cache_payload = response
            self._local_cache_expires_at_ts = time.monotonic() + self._settings.market_cache_ttl_seconds
        return response

    async def _fetch_single(
        self,
        fetcher: Any,
    ) -> tuple[SupportedExchange, list[MarketSnapshot], FetchError | None, str]:
        source = "ccxt"
        try:
            if hasattr(fetcher, "fetch_snapshots_with_source"):
                data, source = await asyncio.wait_for(
                    fetcher.fetch_snapshots_with_source(),
                    timeout=self._settings.exchange_fetch_timeout_seconds,
                )
            else:
                data = await asyncio.wait_for(
                    fetcher.fetch_snapshots(),
                    timeout=self._settings.exchange_fetch_timeout_seconds,
                )

            if not data:
                return fetcher.exchange, [], FetchError(exchange=fetcher.exchange, message="抓取结果为空"), source
            return fetcher.exchange, data, None, source
        except asyncio.TimeoutError:
            return fetcher.exchange, [], FetchError(exchange=fetcher.exchange, message="抓取超时"), "failed"
        except Exception as exc:
            return fetcher.exchange, [], FetchError(exchange=fetcher.exchange, message=str(exc)), "failed"

    def _record_last_success(self, exchange: SupportedExchange, snapshots: list[MarketSnapshot]) -> None:
        self._last_success_snapshots[exchange] = list(snapshots)
        self._last_success_at_ts[exchange] = time.monotonic()

    def _record_last_success_batch(self, snapshots: list[MarketSnapshot]) -> None:
        grouped: dict[SupportedExchange, list[MarketSnapshot]] = {}
        for row in snapshots:
            grouped.setdefault(row.exchange, []).append(row)
        for exchange, items in grouped.items():
            self._record_last_success(exchange, items)

    def _get_stale_snapshots(self, exchange: SupportedExchange) -> list[MarketSnapshot] | None:
        snapshots = self._last_success_snapshots.get(exchange)
        if not snapshots:
            return None
        ts = self._last_success_at_ts.get(exchange)
        if ts is None:
            return None
        if time.monotonic() - ts > self._stale_fallback_max_age_seconds:
            return None
        return list(snapshots)
