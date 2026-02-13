from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.exchanges.gateio import GateIoFetcher
from app.exchanges.leverage import CCXT_EXCHANGE_MAP, get_leverage_map
from app.exchanges.utils import build_snapshot, normalize_usdt_symbol, parse_exchange_timestamp, safe_float
from app.models.schemas import MarketSnapshot, SupportedExchange


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_ms_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = safe_float(value)
    if parsed is None:
        return _parse_iso_datetime(value)
    if parsed < 1e11:
        return parse_exchange_timestamp(int(parsed), unit="s")
    return parse_exchange_timestamp(int(parsed), unit="ms")


def _parse_interval_hours(value: object) -> float | None:
    if value in (None, ""):
        return None

    if isinstance(value, str):
        text = value.strip().lower()
        if not text:
            return None
        if text.endswith("h"):
            return safe_float(text[:-1])
        parsed = safe_float(text)
    else:
        parsed = safe_float(value)

    if parsed is None or parsed <= 0:
        return None

    # 交易所有时返回分钟/秒，做一层保守归一化。
    if parsed > 2400:
        return parsed / 3600
    if parsed > 24:
        return parsed / 60
    return parsed


def _as_row_map(payload: object) -> dict[str, dict[str, Any]]:
    if isinstance(payload, dict):
        rows: dict[str, dict[str, Any]] = {}
        for key, value in payload.items():
            if not isinstance(value, dict):
                continue
            symbol = str(value.get("symbol") or key)
            rows[symbol] = value
        return rows
    if isinstance(payload, list):
        rows = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "")
            if not symbol:
                continue
            rows[symbol] = item
        return rows
    return {}


def _resolve_row_leverage(row: dict[str, Any]) -> float | None:
    info = row.get("info")
    info_dict = info if isinstance(info, dict) else {}
    for key in ("maxLeverage", "maxLever", "leverage", "leverage_max", "leverageMax"):
        parsed = safe_float(row.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    for key in ("maxLeverage", "maxLever", "lever", "leverage", "leverage_max", "leverageMax"):
        parsed = safe_float(info_dict.get(key))
        if parsed is not None and parsed > 0:
            return parsed
    return None


class CcxtMarketProvider:
    """基于 ccxt 的统一行情抓取器。"""

    def __init__(self, exchange: SupportedExchange) -> None:
        self.exchange = exchange
        self._settings = get_settings()
        self._ccxt_id = CCXT_EXCHANGE_MAP[exchange]
        self._gateio_fallback_fetcher = GateIoFetcher() if exchange == "gateio" else None

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        snapshots, _ = await self.fetch_snapshots_with_source()
        return snapshots

    async def fetch_snapshots_with_source(self) -> tuple[list[MarketSnapshot], str]:
        if self.exchange != "gateio":
            snapshots = await self._fetch_ccxt_snapshots()
            return snapshots, "ccxt"

        ccxt_error: Exception | None = None
        ccxt_snapshots: list[MarketSnapshot] = []
        try:
            ccxt_snapshots = await self._fetch_ccxt_snapshots()
        except Exception as exc:
            ccxt_error = exc

        if ccxt_snapshots:
            return ccxt_snapshots, "ccxt"

        fallback_snapshots = await self._fetch_gateio_fallback()
        if fallback_snapshots:
            return fallback_snapshots, "legacy_rest"

        if ccxt_error is not None:
            raise RuntimeError(f"gateio ccxt 抓取失败且原生兜底为空: {ccxt_error}") from ccxt_error
        raise RuntimeError("gateio ccxt 抓取为空且原生兜底为空")

    async def _fetch_ccxt_snapshots(self) -> list[MarketSnapshot]:
        try:
            import ccxt.async_support as ccxt_async  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"ccxt 导入失败: {exc}") from exc

        exchange_cls = getattr(ccxt_async, self._ccxt_id, None)
        if exchange_cls is None:
            raise RuntimeError(f"ccxt 不支持交易所: {self.exchange}")

        client = exchange_cls(
            {
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )

        # 不同交易所在 ccxt 的市场路由选项有细微差异，统一设置保证抓到 USDT 永续。
        if self.exchange == "binance":
            client.options["defaultSubType"] = "linear"
        if self.exchange == "okx":
            client.options["defaultInstType"] = "SWAP"
        if self.exchange == "bybit":
            client.options["defaultSubType"] = "linear"

        try:
            funding_map = await self._fetch_funding_rows(client)
            if not funding_map:
                return []

            leverage_map = await get_leverage_map(self.exchange)
            snapshots: list[MarketSnapshot] = []
            for raw_symbol, row in funding_map.items():
                canonical = normalize_usdt_symbol(raw_symbol)
                if canonical is None:
                    continue

                funding_rate_raw = self._resolve_funding_rate(row)
                next_funding_time = self._resolve_next_funding_time(row)
                interval_hours = self._resolve_interval_hours(row)
                max_leverage = leverage_map.get(canonical) or _resolve_row_leverage(row)
                snapshot = build_snapshot(
                    exchange=self.exchange,
                    symbol=raw_symbol,
                    funding_rate_raw=funding_rate_raw,
                    funding_interval_hours=interval_hours,
                    next_funding_time=next_funding_time,
                    oi_usd=None,
                    vol24h_usd=None,
                    max_leverage=max_leverage,
                    mark_price=None,
                )
                if snapshot:
                    snapshots.append(snapshot)
            return snapshots
        finally:
            try:
                await client.close()
            except Exception:
                pass

    async def _fetch_gateio_fallback(self) -> list[MarketSnapshot]:
        if self.exchange != "gateio" or self._gateio_fallback_fetcher is None:
            return []

        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            return await self._gateio_fallback_fetcher.fetch_snapshots(client)

    async def _fetch_funding_rows(self, client: Any) -> dict[str, dict[str, Any]]:
        has = getattr(client, "has", {}) or {}
        rows: dict[str, dict[str, Any]] = {}

        if has.get("fetchFundingRates"):
            try:
                payload = await client.fetch_funding_rates()
                rows = _as_row_map(payload)
                if rows:
                    return rows
            except Exception:
                pass

        if not has.get("fetchFundingRate"):
            return rows

        symbols = await self._discover_symbols(client)
        if not symbols:
            return rows

        budget_seconds = max(1.0, self._settings.ccxt_funding_fetch_budget_seconds)
        started_at = time.perf_counter()
        semaphore = asyncio.Semaphore(max(2, min(self._settings.max_concurrency_per_exchange, 12)))

        async def worker(symbol: str) -> tuple[str, dict[str, Any] | None]:
            if time.perf_counter() - started_at > budget_seconds:
                return symbol, None
            async with semaphore:
                if time.perf_counter() - started_at > budget_seconds:
                    return symbol, None
                try:
                    payload = await client.fetch_funding_rate(symbol)
                except Exception:
                    return symbol, None
                if isinstance(payload, dict):
                    return symbol, payload
                return symbol, None

        results = await asyncio.gather(*(worker(symbol) for symbol in symbols))
        for symbol, payload in results:
            if payload is None:
                continue
            key = str(payload.get("symbol") or symbol)
            rows[key] = payload
        return rows

    async def _discover_symbols(self, client: Any) -> list[str]:
        try:
            if self.exchange == "bybit":
                await client.load_markets(params={"type": "swap"})
            else:
                await client.load_markets()
        except Exception:
            return []

        symbols: list[str] = []
        for market in client.markets.values():
            if not isinstance(market, dict):
                continue
            if not market.get("swap"):
                continue
            if str(market.get("quote", "")).upper() != "USDT":
                continue
            if market.get("active") is False:
                continue
            symbol = str(market.get("symbol") or "")
            if not symbol:
                continue
            symbols.append(symbol)
        return symbols

    def _resolve_funding_rate(self, row: dict[str, Any]) -> float | None:
        info = row.get("info")
        info_dict = info if isinstance(info, dict) else {}
        for key in ("fundingRate", "lastFundingRate", "nextFundingRate", "funding_rate"):
            parsed = safe_float(row.get(key))
            if parsed is not None:
                return parsed
        for key in ("fundingRate", "lastFundingRate", "nextFundingRate", "funding_rate"):
            parsed = safe_float(info_dict.get(key))
            if parsed is not None:
                return parsed
        return None

    def _resolve_next_funding_time(self, row: dict[str, Any]) -> datetime | None:
        info = row.get("info")
        info_dict = info if isinstance(info, dict) else {}
        for key in (
            "nextFundingTimestamp",
            "nextFundingTime",
            "fundingTimestamp",
            "timestamp",
        ):
            parsed = _to_ms_datetime(row.get(key))
            if parsed is not None:
                return parsed
        for key in (
            "nextFundingTime",
            "nextFundingTimestamp",
            "fundingTime",
            "fundingTimestamp",
            "next_funding_time",
        ):
            parsed = _to_ms_datetime(info_dict.get(key))
            if parsed is not None:
                return parsed
        return None

    def _resolve_interval_hours(self, row: dict[str, Any]) -> float:
        info = row.get("info")
        info_dict = info if isinstance(info, dict) else {}

        for key in ("interval", "fundingInterval", "fundingIntervalHours", "funding_interval"):
            parsed = _parse_interval_hours(row.get(key))
            if parsed is not None:
                return parsed

        for key in (
            "fundingIntervalHour",
            "fundingIntervalHours",
            "fundingInterval",
            "fundInterval",
            "funding_interval",
            "fundingRateInterval",
        ):
            parsed = _parse_interval_hours(info_dict.get(key))
            if parsed is not None:
                return parsed

        return 8.0
