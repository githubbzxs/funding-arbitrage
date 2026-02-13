from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.models.schemas import MarketSnapshot, SupportedExchange


class BaseExchangeFetcher(ABC):
    """交易所公共行情抓取器基类。"""

    exchange: SupportedExchange

    @abstractmethod
    async def fetch_snapshots(self, client: httpx.AsyncClient) -> list[MarketSnapshot]:
        """抓取并返回统一后的快照列表。"""

    async def _request_json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

