import httpx

from app.exchanges.base import BaseExchangeFetcher
from app.exchanges.leverage import get_leverage_map
from app.exchanges.utils import build_snapshot, safe_float
from app.models.schemas import MarketSnapshot


class BitgetFetcher(BaseExchangeFetcher):
    exchange = "bitget"

    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        tickers_resp = await self._request_json(
            client,
            "https://api.bitget.com/api/v2/mix/market/tickers",
            params={"productType": "USDT-FUTURES"},
        )
        contracts_resp = await self._request_json(
            client,
            "https://api.bitget.com/api/v2/mix/market/contracts",
            params={"productType": "USDT-FUTURES"},
        )
        tickers = tickers_resp.get("data", [])
        contracts = contracts_resp.get("data", [])
        contract_map = {row.get("symbol"): row for row in contracts if row.get("symbol")}
        leverage_map = await get_leverage_map(self.exchange)

        snapshots: list[MarketSnapshot] = []
        for row in tickers:
            symbol = str(row.get("symbol", ""))
            if not symbol.endswith("USDT"):
                continue

            contract = contract_map.get(symbol, {})
            mark_price = safe_float(row.get("markPrice"))
            holding_amount = safe_float(row.get("holdingAmount"))
            oi_usd = None
            if mark_price is not None and holding_amount is not None:
                oi_usd = mark_price * holding_amount

            max_leverage = safe_float(contract.get("maxLever")) or leverage_map.get(symbol)

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=symbol,
                oi_usd=oi_usd,
                vol24h_usd=safe_float(row.get("usdtVolume")) or safe_float(row.get("quoteVolume")),
                funding_rate_raw=safe_float(row.get("fundingRate")),
                funding_interval_hours=safe_float(contract.get("fundInterval")) or 8.0,
                next_funding_time=None,
                max_leverage=max_leverage,
                mark_price=mark_price,
            )
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

