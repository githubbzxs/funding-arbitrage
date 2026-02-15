from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.time import utc_now

SupportedExchange = Literal["binance", "okx", "bybit", "bitget", "gateio"]


class FetchError(BaseModel):
    """单交易所抓取错误。"""

    exchange: SupportedExchange
    message: str


class MarketSnapshot(BaseModel):
    """统一行情快照。"""

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
    leveraged_nominal_rate_1y: float | None = None
    mark_price: float | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class MarketSnapshotsResponse(BaseModel):
    """行情快照响应。"""

    as_of: datetime = Field(default_factory=utc_now)
    snapshots: list[MarketSnapshot] = Field(default_factory=list)
    errors: list[FetchError] = Field(default_factory=list)
    meta: dict[str, Any] | None = None


class Opportunity(BaseModel):
    """套利机会。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    long_nominal_rate_1y: float
    short_nominal_rate_1y: float
    spread_rate_1y_nominal: float
    long_max_leverage: float | None = None
    short_max_leverage: float | None = None
    max_usable_leverage: float | None = None
    leveraged_spread_rate_1y_nominal: float | None = None
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


class OpportunityBoardLeg(BaseModel):
    """board 单腿字段。"""

    exchange: SupportedExchange
    funding_rate_raw: float | None = None
    rate_1h: float | None = None
    rate_8h: float | None = None
    rate_1y: float | None = None
    next_funding_time: datetime | None = None
    max_leverage: float | None = None
    leveraged_nominal_rate_1y: float | None = None
    open_interest_usd: float | None = None
    volume24h_usd: float | None = None
    settlement_interval: str = "-"
    settlement_interval_hours: float | None = None


class SettlementEvent(BaseModel):
    """结算事件。"""

    time: datetime
    kind: Literal["both", "long_only", "short_only"]
    rate: float
    leveraged_rate: float
    long_rate_raw: float | None = None
    short_rate_raw: float | None = None


class OpportunityBoardRow(BaseModel):
    """board 行。"""

    id: str
    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    long_leg: OpportunityBoardLeg
    short_leg: OpportunityBoardLeg
    interval_mismatch: bool = False
    shorter_interval_side: Literal["long", "short"] | None = None
    spread_rate_1h: float | None = None
    spread_rate_8h: float | None = None
    spread_rate_1y_nominal: float
    leveraged_spread_rate_1y_nominal: float | None = None
    max_usable_leverage: float | None = None
    next_sync_settlement_time: datetime | None = None
    window_hours_to_sync: float | None = None
    next_cycle_score: float | None = None
    next_cycle_score_unlevered: float | None = None
    settlement_events_preview: list[SettlementEvent] = Field(default_factory=list)
    single_side_event_count: int = 0
    single_side_total_rate: float | None = None
    calc_status: Literal["ok", "missing_data", "no_sync_found"] = "missing_data"


class MarketBoardResponse(BaseModel):
    """board 响应。"""

    as_of: datetime = Field(default_factory=utc_now)
    total: int
    rows: list[OpportunityBoardRow] = Field(default_factory=list)
    errors: list[FetchError] = Field(default_factory=list)
    meta: dict[str, Any] | None = None


class ExecutionMode(str, Enum):
    """执行模式（仅自动）。"""

    auto = "auto"


class ExchangeCredential(BaseModel):
    """交易所凭据。"""

    api_key: str
    api_secret: str
    passphrase: str | None = None
    testnet: bool = False


class CredentialStatus(BaseModel):
    """托管凭据状态。"""

    exchange: SupportedExchange
    configured: bool
    api_key_masked: str | None = None
    has_passphrase: bool = False
    testnet: bool | None = None
    updated_at: datetime | None = None


class CredentialsResponse(BaseModel):
    """托管凭据状态列表响应。"""

    items: list[CredentialStatus] = Field(default_factory=list)


class ExecutionPreviewRequest(BaseModel):
    """预估请求。"""

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
    """预估响应。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    spread_rate_1y_nominal: float | None = None
    expected_pnl_usd: float | None = None
    estimated_fee_usd: float
    hold_hours: float
    details: dict[str, Any] = Field(default_factory=dict)


class OpenPositionRequest(BaseModel):
    """开仓请求（按名义金额换算数量）。"""

    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    notional_usd: float = Field(gt=0)
    leverage: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class ClosePositionRequest(BaseModel):
    """平仓请求。"""

    position_id: str | None = None
    symbol: str | None = None
    long_exchange: SupportedExchange | None = None
    short_exchange: SupportedExchange | None = None
    notional_usd: float | None = Field(default=None, gt=0)
    leverage: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    note: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ClosePositionRequest":
        if self.position_id:
            return self
        required = [self.symbol, self.long_exchange, self.short_exchange, self.notional_usd]
        if any(value is None for value in required):
            raise ValueError("未提供 position_id 时，必须提供 symbol/long_exchange/short_exchange/notional_usd")
        self.symbol = self.symbol.upper()
        return self


class HedgeRequest(BaseModel):
    """对冲请求（按名义金额换算数量）。"""

    symbol: str
    exchange: SupportedExchange
    side: Literal["buy", "sell"]
    notional_usd: float = Field(gt=0)
    leverage: float | None = Field(default=None, gt=0)
    credentials: dict[SupportedExchange, ExchangeCredential] = Field(default_factory=dict)
    reason: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class EmergencyCloseRequest(BaseModel):
    """紧急全平请求。"""

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
    """执行响应。"""

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


class StrategyTemplateBase(BaseModel):
    """策略模板基础字段。"""

    name: str = Field(min_length=1, max_length=80)
    symbol: str
    long_exchange: SupportedExchange
    short_exchange: SupportedExchange
    notional_usd: float | None = Field(default=None, gt=0)
    leverage: float | None = Field(default=None, gt=0)
    hold_hours: float | None = Field(default=None, gt=0)
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.upper()


class StrategyTemplateCreate(StrategyTemplateBase):
    """创建策略模板请求。"""


class StrategyTemplateUpdate(BaseModel):
    """更新策略模板请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    symbol: str | None = None
    long_exchange: SupportedExchange | None = None
    short_exchange: SupportedExchange | None = None
    notional_usd: float | None = Field(default=None, gt=0)
    leverage: float | None = Field(default=None, gt=0)
    hold_hours: float | None = Field(default=None, gt=0)
    note: str | None = None

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.upper()


class StrategyTemplateRead(BaseModel):
    """策略模板读取模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    symbol: str
    long_exchange: str
    short_exchange: str
    notional_usd: float | None = None
    leverage: float | None = None
    hold_hours: float | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class StrategyTemplatesResponse(BaseModel):
    """策略模板列表响应。"""

    total: int
    items: list[StrategyTemplateRead]


class RiskEventRead(BaseModel):
    """风险事件读取模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    event_type: str
    severity: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    resolved: bool
    created_at: datetime
    updated_at: datetime


class RiskEventsResponse(BaseModel):
    """风险事件列表响应。"""

    total: int
    items: list[RiskEventRead]
