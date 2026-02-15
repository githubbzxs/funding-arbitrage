from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.exchanges.binance import BinanceFetcher
from app.exchanges.bitget import BitgetFetcher
from app.exchanges.bybit import BybitFetcher
from app.exchanges.gateio import GateIoFetcher
from app.exchanges.leverage import CCXT_EXCHANGE_MAP, get_leverage_map
from app.exchanges.okx import OkxFetcher
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

    # 兼容部分交易所返回分钟/秒的情况，统一折算为小时。
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


def _build_rest_fallback_fetcher(exchange: SupportedExchange):
    if exchange == "binance":
        return BinanceFetcher()
    if exchange == "okx":
        return OkxFetcher()
    if exchange == "bybit":
        return BybitFetcher()
    if exchange == "bitget":
        return BitgetFetcher()
    return GateIoFetcher()


class CcxtMarketProvider:
    """基于 ccxt 的统一行情抓取器。"""

    def __init__(self, exchange: SupportedExchange) -> None:
        self.exchange = exchange
        self._settings = get_settings()
        self._ccxt_id = CCXT_EXCHANGE_MAP[exchange]
        self._rest_fallback_fetcher = _build_rest_fallback_fetcher(exchange)

    async def fetch_snapshots(self) -> list[MarketSnapshot]:
        snapshots, _ = await self.fetch_snapshots_with_source()
        return snapshots

    async def fetch_snapshots_with_source(self) -> tuple[list[MarketSnapshot], str]:
        ccxt_error: Exception | None = None
        rest_error: Exception | None = None
        ws_error: Exception | None = None

        ccxt_snapshots: list[MarketSnapshot] = []
        try:
            ccxt_snapshots = await self._fetch_ccxt_snapshots()
        except Exception as exc:
            ccxt_error = exc

        if ccxt_snapshots:
            return ccxt_snapshots, "ccxt"

        rest_snapshots: list[MarketSnapshot] = []
        try:
            rest_snapshots = await self._fetch_rest_fallback()
        except Exception as exc:
            rest_error = exc

        if rest_snapshots:
            return rest_snapshots, "legacy_rest"

        ws_snapshots: list[MarketSnapshot] = []
        try:
            ws_snapshots = await self._fetch_ws_fallback()
        except Exception as exc:
            ws_error = exc

        if ws_snapshots:
            return ws_snapshots, "ws_fallback"

        parts = [
            f"ccxt={ccxt_error}" if ccxt_error is not None else None,
            f"rest={rest_error}" if rest_error is not None else None,
            f"ws={ws_error}" if ws_error is not None else None,
        ]
        detail = ", ".join(part for part in parts if part) or "all_empty"
        if ccxt_error is not None:
            raise RuntimeError(f"{self.exchange} ccxt 抓取失败且 REST/WS 兜底为空: {detail}") from ccxt_error
        raise RuntimeError(f"{self.exchange} ccxt 抓取为空且 REST/WS 兜底为空: {detail}")

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

        # 不同交易所在 ccxt 的市场路由选项有差异，统一指向 USDT 永续。
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

                snapshot = build_snapshot(
                    exchange=self.exchange,
                    symbol=raw_symbol,
                    funding_rate_raw=self._resolve_funding_rate(row),
                    funding_interval_hours=self._resolve_interval_hours(row),
                    next_funding_time=self._resolve_next_funding_time(row),
                    oi_usd=None,
                    vol24h_usd=None,
                    max_leverage=leverage_map.get(canonical) or _resolve_row_leverage(row),
                    mark_price=self._resolve_mark_price(row),
                )
                if snapshot:
                    snapshots.append(snapshot)
            return snapshots
        finally:
            try:
                await client.close()
            except Exception:
                pass

    async def _fetch_rest_fallback(self) -> list[MarketSnapshot]:
        if self._rest_fallback_fetcher is None:
            return []

        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            return await self._rest_fallback_fetcher.fetch_snapshots(client)

    async def _fetch_ws_fallback(self) -> list[MarketSnapshot]:
        if self.exchange != "gateio":
            return []

        contract_rows = await self._load_gateio_contract_rows_for_ws()
        if not contract_rows:
            return []

        try:
            import websockets
        except Exception:
            return []

        timeout_seconds = min(8.0, max(3.0, self._settings.request_timeout_seconds))
        started_at = time.perf_counter()
        subscribe_payload = {
            "time": int(time.time()),
            "channel": "futures.tickers",
            "event": "subscribe",
            "payload": ["!all"],
        }
        unsubscribe_payload = {
            "time": int(time.time()),
            "channel": "futures.tickers",
            "event": "unsubscribe",
            "payload": ["!all"],
        }
        ticker_rows: dict[str, dict[str, Any]] = {}
        target_count = min(max(80, len(contract_rows) // 2), len(contract_rows))

        async with websockets.connect(
            "wss://fx-ws.gateio.ws/v4/ws/usdt",
            open_timeout=timeout_seconds,
            close_timeout=1.0,
            max_size=2_000_000,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            await ws.send(json.dumps(subscribe_payload))
            while time.perf_counter() - started_at < timeout_seconds:
                remaining = timeout_seconds - (time.perf_counter() - started_at)
                if remaining <= 0:
                    break
                try:
                    raw_message = await asyncio.wait_for(ws.recv(), timeout=remaining)
                except asyncio.TimeoutError:
                    break

                updates = self._parse_gateio_ws_tickers_message(raw_message)
                if not updates:
                    continue

                for contract, row in updates.items():
                    if contract in contract_rows:
                        ticker_rows[contract] = row

                if len(ticker_rows) >= target_count:
                    break

            try:
                await ws.send(json.dumps(unsubscribe_payload))
            except Exception:
                pass

        return await self._build_gateio_ws_snapshots(contract_rows=contract_rows, ticker_rows=ticker_rows)

    async def _load_gateio_contract_rows_for_ws(self) -> dict[str, dict[str, Any]]:
        timeout = httpx.Timeout(self._settings.request_timeout_seconds)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            response = await client.get("https://api.gateio.ws/api/v4/futures/usdt/contracts")
            response.raise_for_status()
            payload = response.json()

        if not isinstance(payload, list):
            return {}

        rows: dict[str, dict[str, Any]] = {}
        for item in payload:
            if not isinstance(item, dict):
                continue
            contract = str(item.get("name") or "")
            if not contract.endswith("_USDT"):
                continue
            if str(item.get("status", "")).lower() != "trading":
                continue
            rows[contract] = item
        return rows

    def _parse_gateio_ws_tickers_message(self, raw_message: object) -> dict[str, dict[str, Any]]:
        if isinstance(raw_message, bytes):
            try:
                text = raw_message.decode("utf-8", errors="ignore")
            except Exception:
                return {}
        elif isinstance(raw_message, str):
            text = raw_message
        else:
            return {}

        try:
            payload = json.loads(text)
        except Exception:
            return {}

        if not isinstance(payload, dict):
            return {}
        if payload.get("channel") != "futures.tickers":
            return {}
        if payload.get("event") != "update":
            return {}

        result = payload.get("result")
        if isinstance(result, dict):
            result_rows = [result]
        elif isinstance(result, list):
            result_rows = [item for item in result if isinstance(item, dict)]
        else:
            return {}

        rows: dict[str, dict[str, Any]] = {}
        for item in result_rows:
            contract = str(item.get("contract") or item.get("name") or "")
            if contract:
                rows[contract] = item
        return rows

    async def _build_gateio_ws_snapshots(
        self,
        *,
        contract_rows: dict[str, dict[str, Any]],
        ticker_rows: dict[str, dict[str, Any]],
    ) -> list[MarketSnapshot]:
        if not contract_rows:
            return []

        leverage_map = await get_leverage_map(self.exchange)
        snapshots: list[MarketSnapshot] = []
        for contract, contract_row in contract_rows.items():
            ticker = ticker_rows.get(contract, {})

            funding_interval_hours = 8.0
            funding_interval_sec = safe_float(contract_row.get("funding_interval"))
            if funding_interval_sec is not None and funding_interval_sec > 0:
                funding_interval_hours = funding_interval_sec / 3600

            mark_price = safe_float(ticker.get("mark_price")) or safe_float(contract_row.get("mark_price"))
            total_size = safe_float(ticker.get("total_size"))
            multiplier = safe_float(contract_row.get("quanto_multiplier")) or 1.0
            oi_usd = None
            if mark_price is not None and total_size is not None:
                oi_usd = mark_price * total_size * multiplier

            next_funding_raw = ticker.get("funding_next_apply")
            if next_funding_raw in (None, ""):
                next_funding_raw = contract_row.get("funding_next_apply")

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=contract,
                oi_usd=oi_usd,
                vol24h_usd=safe_float(ticker.get("volume_24h_quote")) or safe_float(ticker.get("volume_24h_settle")),
                funding_rate_raw=safe_float(ticker.get("funding_rate")) or safe_float(contract_row.get("funding_rate")),
                funding_interval_hours=funding_interval_hours,
                next_funding_time=parse_exchange_timestamp(next_funding_raw, unit="s"),
                max_leverage=safe_float(contract_row.get("leverage_max")) or leverage_map.get(contract.replace("_", "")),
                mark_price=mark_price,
            )
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

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
            if symbol:
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
        for key in ("nextFundingTimestamp", "nextFundingTime", "fundingTimestamp", "timestamp"):
            parsed = _to_ms_datetime(row.get(key))
            if parsed is not None:
                return parsed
        for key in ("nextFundingTime", "nextFundingTimestamp", "fundingTime", "fundingTimestamp", "next_funding_time"):
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

        for key in ("fundingIntervalHour", "fundingIntervalHours", "fundingInterval", "fundInterval", "funding_interval", "fundingRateInterval"):
            parsed = _parse_interval_hours(info_dict.get(key))
            if parsed is not None:
                return parsed

        return 8.0

    def _resolve_mark_price(self, row: dict[str, Any]) -> float | None:
        info = row.get("info")
        info_dict = info if isinstance(info, dict) else {}

        for key in ("markPrice", "mark_price", "lastPrice", "indexPrice", "price"):
            parsed = safe_float(row.get(key))
            if parsed is not None and parsed > 0:
                return parsed

        for key in ("markPrice", "mark_price", "lastPrice", "indexPrice", "price"):
            parsed = safe_float(info_dict.get(key))
            if parsed is not None and parsed > 0:
                return parsed

        return None
