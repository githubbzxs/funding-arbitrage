import httpx

from app.exchanges.base import BaseExchangeFetcher
from app.exchanges.leverage import get_leverage_map
from app.exchanges.utils import build_snapshot, parse_exchange_timestamp, safe_float
from app.models.schemas import MarketSnapshot


class GateIoFetcher(BaseExchangeFetcher):
    exchange = "gateio"

    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        contracts = await self._request_json(client, "https://api.gateio.ws/api/v4/futures/usdt/contracts")
        tickers = await self._request_json(client, "https://api.gateio.ws/api/v4/futures/usdt/tickers")
        ticker_map = {row.get("contract"): row for row in tickers if row.get("contract")}
        leverage_map = await get_leverage_map(self.exchange)

        snapshots: list[MarketSnapshot] = []
        for contract in contracts:
            name = str(contract.get("name", ""))
            if not name.endswith("_USDT"):
                continue
            if str(contract.get("status", "")).lower() != "trading":
                continue

            ticker = ticker_map.get(name, {})
            mark_price = safe_float(ticker.get("mark_price")) or safe_float(contract.get("mark_price"))
            multiplier = safe_float(contract.get("quanto_multiplier")) or 1.0
            total_size = safe_float(ticker.get("total_size"))
            oi_usd = None
            if mark_price is not None and total_size is not None:
                oi_usd = total_size * mark_price * multiplier

            funding_interval_sec = safe_float(contract.get("funding_interval"))
            funding_interval_hours = None
            if funding_interval_sec is not None:
                funding_interval_hours = funding_interval_sec / 3600

            snapshot = build_snapshot(
                exchange=self.exchange,
                symbol=name,
                oi_usd=oi_usd,
                vol24h_usd=safe_float(ticker.get("volume_24h_quote"))
                or safe_float(ticker.get("volume_24h_settle")),
                funding_rate_raw=safe_float(ticker.get("funding_rate")) or safe_float(contract.get("funding_rate")),
                funding_interval_hours=funding_interval_hours or 8.0,
                next_funding_time=parse_exchange_timestamp(contract.get("funding_next_apply"), unit="s"),
                max_leverage=safe_float(contract.get("leverage_max")) or leverage_map.get(name.replace("_", "")),
                mark_price=mark_price,
            )
            if snapshot:
                snapshots.append(snapshot)
        return snapshots

