from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import utc_now

SupportedExchange = Literal["binance", "okx", "bybit", "bitget", "gateio"]


class FetchError(BaseModel):
    """单交易所抓取失败信息。"""

    exchange: SupportedExchange
    message: str


class MarketSnapshot(BaseModel):
    """统一后的市场快照字段。"""

    exchange: SupportedExchange
    symbol: str
    oi_usd: float | None = None
    vol24h_usd: float | None = None
    funding_rate_raw: float | None = None
    funding_interval_hours: float | None = None
    next_funding_time: datetime | None = None
    max_leverage: float | None = None
    rate_1h: float | None = None
    rate_8h: float | None = None
    rate_1y: float | None = None
    nominal_rate_1y: float | None = None
    mark_price: float | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class MarketSnapshotsResponse(BaseModel):
    """市场快照接口响应。"""

    as_of: datetime = Field(default_factory=utc_now)
    snapshots: list[MarketSnapshot] = Field(default_factory=list)
    errors: list[FetchError] = Field(default_factory=list)


class Opportunity(BaseModel):
    """套利机会。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    long_nominal_rate_1y: float
    short_nominal_rate_1y: float
    spread_rate_1y_nominal: float
    long_rate_8h: float | None = None
    short_rate_8h: float | None = None
    long_funding_rate_raw: float | None = None
    short_funding_rate_raw: float | None = None
    long_next_funding_time: datetime | None = None
    short_next_funding_time: datetime | None = None


class OpportunitiesResponse(BaseModel):
    """套利机会列表响应。"""

    as_of: datetime = Field(default_factory=utc_now)
    total: int
    opportunities: list[Opportunity]
    errors: list[FetchError] = Field(default_factory=list)


class ExecutionMode(str, Enum):
    """执行模式。"""

    manual = "manual"
    auto = "auto"


class ExchangeCredential(BaseModel):
    """交易所 API 认证信息。"""

    api_key: str
    api_secret: str
    passphrase: str | None = None
    testnet: bool = False


class ExecutionPreviewRequest(BaseModel):
    """开仓预估请求。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    notional_usd: float = Field(gt=0)
    hold_hours: float = Field(default=8.0, gt=0)
    taker_fee_bps: float = Field(default=6.0, ge=0)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class ExecutionPreviewResponse(BaseModel):
    """开仓预估响应。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    spread_rate_1y_nominal: float | None = None
    expected_pnl_usd: float | None = None
    estimated_fee_usd: float
    hold_hours: float
    details: dict[str, Any] = Field(default_factory=dict)


class OpenPositionRequest(BaseModel):
    """开仓请求。"""

    mode: ExecutionMode = ExecutionMode.manual
    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    quantity: float = Field(gt=0)
    leverage: float | None = Field(default=None, gt=0)
    notional_usd: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class ClosePositionRequest(BaseModel):
    """平仓请求。"""

    mode: ExecutionMode = ExecutionMode.manual
    position_id: str | None = None
    symbol: str | None = None
    long_exchange: SupportedExchange | None = None
    short_exchange: SupportedExchange | None = None
    long_quantity: float | None = Field(default=None, gt=0)
    short_quantity: float | None = Field(default=None, gt=0)
    leverage: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    note: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ClosePositionRequest":
        if self.position_id:
            return self
        required = [self.symbol, self.long_exchange, self.short_exchange, self.long_quantity, self.short_quantity]
        if any(value is None for value in required):
            raise ValueError("未提供 position_id 时，必须提供 symbol/long_exchange/short_exchange/long_quantity/short_quantity")
        self.symbol = self.symbol.upper()
        return self


class HedgeRequest(BaseModel):
    """对冲请求。"""

    mode: ExecutionMode = ExecutionMode.manual
    symbol: str
    exchange: SupportedExchange
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    leverage: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    reason: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class EmergencyCloseRequest(BaseModel):
    """紧急全平请求。"""

    mode: ExecutionMode = ExecutionMode.manual
    position_ids: list[str] | None = None
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)


class ExecutionLegResult(BaseModel):
    """单腿执行结果。"""

    exchange: SupportedExchange
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    status: str
    order_id: str | None = None
    filled_qty: float | None = None
    avg_price: float | None = None
    message: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ExecutionActionResponse(BaseModel):
    """执行接口统一返回。"""

    success: bool
    action: str
    mode: ExecutionMode
    position_id: str | None = None
    legs: list[ExecutionLegResult] = Field(default_factory=list)
    risk_event_id: str | None = None
    message: str
    timestamp: datetime = Field(default_factory=utc_now)


class OrderRead(BaseModel):
    """订单读取模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    position_id: str | None = None
    action: str
    mode: str
    status: str
    exchange: str
    symbol: str
    side: str
    quantity: float
    filled_qty: float | None = None
    avg_price: float | None = None
    exchange_order_id: str | None = None
    note: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PositionRead(BaseModel):
    """仓位读取模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    long_exchange: str
    short_exchange: str
    long_qty: float
    short_qty: float
    mode: str
    status: str
    entry_spread_rate: float | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class OrdersResponse(BaseModel):
    """订单列表响应。"""

    total: int
    items: list[OrderRead]


class PositionsResponse(BaseModel):
    """仓位列表响应。"""

    total: int
    items: list[PositionRead]

