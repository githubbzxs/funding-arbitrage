import asyncio
import time

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

        for exchange, snapshots, error in results:
            merged_snapshots.extend(snapshots)
            if error:
                errors.append(error)
                exchanges_failed.append(exchange)
            else:
                exchanges_ok.append(exchange)

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
            },
        )
        await cache_set_json(cache_key, response.model_dump(mode="json"), self._settings.market_cache_ttl_seconds)
        async with self._local_cache_lock:
            self._local_cache_payload = response
            self._local_cache_expires_at_ts = time.monotonic() + self._settings.market_cache_ttl_seconds
        return response

    async def _fetch_single(
        self,
        fetcher,
    ) -> tuple[SupportedExchange, list[MarketSnapshot], FetchError | None]:
        try:
            data = await asyncio.wait_for(
                fetcher.fetch_snapshots(),
                timeout=self._settings.exchange_fetch_timeout_seconds,
            )
            return fetcher.exchange, data, None
        except asyncio.TimeoutError:
            return fetcher.exchange, [], FetchError(exchange=fetcher.exchange, message="抓取超时")
        except Exception as exc:
            return fetcher.exchange, [], FetchError(exchange=fetcher.exchange, message=str(exc))
