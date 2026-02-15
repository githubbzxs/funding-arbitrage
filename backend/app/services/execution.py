from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.exchanges.leverage import CCXT_EXCHANGE_MAP
from app.models.orm import Order, Position, RiskEvent
from app.models.schemas import (
    ClosePositionRequest,
    EmergencyCloseRequest,
    ExchangeCredential,
    ExecutionActionResponse,
    ExecutionLegResult,
    ExecutionMode,
    ExecutionPreviewRequest,
    ExecutionPreviewResponse,
    HedgeRequest,
    MarketSnapshot,
    OpenPositionRequest,
    QuantityConvertRequest,
    QuantityConvertResponse,
    SupportedExchange,
)
from app.services.arbitrage import scan_opportunities
from app.services.credentials import CredentialService
from app.services.market_data import MarketDataService


def _to_ccxt_symbol(symbol: str) -> str:
    normalized = symbol.upper()
    if not normalized.endswith("USDT"):
        raise ValueError(f"不支持的 symbol: {symbol}")
    base = normalized[: -len("USDT")]
    return f"{base}/USDT:USDT"


@dataclass
class GatewayResult:
    success: bool
    order_id: str | None
    filled_qty: float | None
    avg_price: float | None
    message: str
    raw: dict[str, Any]


class CcxtExecutionGateway:
    """ccxt 下单网关，封装自动执行细节。"""

    async def place_market_order(
        self,
        *,
        exchange: SupportedExchange,
        symbol: str,
        side: str,
        quantity: float,
        credential: ExchangeCredential,
        leverage: float | None = None,
        reduce_only: bool = False,
        position_side: str | None = None,
    ) -> GatewayResult:
        try:
            import ccxt.async_support as ccxt_async  # type: ignore
        except Exception as exc:  # pragma: no cover
            return GatewayResult(
                success=False,
                order_id=None,
                filled_qty=None,
                avg_price=None,
                message=f"ccxt 不可用: {exc}",
                raw={},
            )

        exchange_id = CCXT_EXCHANGE_MAP[exchange]
        exchange_cls = getattr(ccxt_async, exchange_id, None)
        if exchange_cls is None:
            return GatewayResult(
                success=False,
                order_id=None,
                filled_qty=None,
                avg_price=None,
                message=f"ccxt 不支持交易所: {exchange}",
                raw={},
            )

        client = exchange_cls(
            {
                "apiKey": credential.api_key,
                "secret": credential.api_secret,
                "password": credential.passphrase,
                "enableRateLimit": True,
                "options": {"defaultType": "swap"},
            }
        )
        if credential.testnet:
            try:
                client.set_sandbox_mode(True)
            except Exception:
                pass

        ccxt_symbol = _to_ccxt_symbol(symbol)
        params: dict[str, Any] = {}
        if exchange == "binance":
            params["portfolioMargin"] = True
            if position_side in {"LONG", "SHORT", "BOTH"}:
                params["positionSide"] = position_side
        if reduce_only and not (exchange == "binance" and position_side in {"LONG", "SHORT"}):
            params["reduceOnly"] = True

        try:
            if leverage is not None:
                try:
                    if exchange == "binance":
                        await client.set_leverage(leverage, ccxt_symbol, {"portfolioMargin": True})
                    else:
                        await client.set_leverage(leverage, ccxt_symbol)
                except Exception:
                    # 某些交易所不支持动态设杠杆，不阻断下单。
                    pass

            order = await client.create_order(
                symbol=ccxt_symbol,
                type="market",
                side=side,
                amount=quantity,
                params=params,
            )
            return GatewayResult(
                success=True,
                order_id=str(order.get("id")) if order.get("id") is not None else None,
                filled_qty=_safe_float(order.get("filled")) or quantity,
                avg_price=_safe_float(order.get("average")),
                message="下单成功",
                raw=_as_dict(order),
            )
        except Exception as exc:
            if exchange == "binance" and _is_binance_position_side_mismatch(exc):
                retry_params = dict(params)
                if retry_params.get("positionSide") in {"LONG", "SHORT"}:
                    retry_params["positionSide"] = "BOTH"
                    if reduce_only:
                        retry_params["reduceOnly"] = True
                    try:
                        order = await client.create_order(
                            symbol=ccxt_symbol,
                            type="market",
                            side=side,
                            amount=quantity,
                            params=retry_params,
                        )
                        return GatewayResult(
                            success=True,
                            order_id=str(order.get("id")) if order.get("id") is not None else None,
                            filled_qty=_safe_float(order.get("filled")) or quantity,
                            avg_price=_safe_float(order.get("average")),
                            message="下单成功",
                            raw=_as_dict(order),
                        )
                    except Exception as retry_exc:
                        return GatewayResult(
                            success=False,
                            order_id=None,
                            filled_qty=None,
                            avg_price=None,
                            message=f"{exc}; positionSide retry failed: {retry_exc}",
                            raw={},
                        )
            return GatewayResult(
                success=False,
                order_id=None,
                filled_qty=None,
                avg_price=None,
                message=str(exc),
                raw={},
            )
        finally:
            try:
                await client.close()
            except Exception:
                pass


class ExecutionService:
    """执行服务：预估、开仓、平仓、对冲、紧急全平。"""

    def __init__(
        self,
        market_data_service: MarketDataService,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.market_data_service = market_data_service
        self.gateway = CcxtExecutionGateway()
        self.credential_service = credential_service or CredentialService()

    async def preview(self, request: ExecutionPreviewRequest) -> ExecutionPreviewResponse:
        snapshots_resp = await self.market_data_service.fetch_snapshots()
        opportunities = scan_opportunities(snapshots_resp.snapshots)

        spread = None
        for item in opportunities:
            if (
                item.symbol == request.symbol
                and item.long_exchange == request.long_exchange
                and item.short_exchange == request.short_exchange
            ):
                spread = item.spread_rate_1y_nominal
                break

        expected_pnl = None
        if spread is not None:
            expected_pnl = request.notional_usd * spread * (request.hold_hours / (24 * 365))
        estimated_fee = request.notional_usd * 2 * (request.taker_fee_bps / 10000)

        return ExecutionPreviewResponse(
            symbol=request.symbol,
            long_exchange=request.long_exchange,
            short_exchange=request.short_exchange,
            spread_rate_1y_nominal=spread,
            expected_pnl_usd=expected_pnl,
            estimated_fee_usd=estimated_fee,
            hold_hours=request.hold_hours,
            details={"snapshot_errors": [error.model_dump() for error in snapshots_resp.errors]},
        )

    async def open_position(
        self,
        session: AsyncSession,
        request: OpenPositionRequest,
    ) -> ExecutionActionResponse:
        long_qty = request.quantity
        short_qty = request.quantity

        position = Position(
            symbol=request.symbol,
            long_exchange=request.long_exchange,
            short_exchange=request.short_exchange,
            long_qty=long_qty,
            short_qty=short_qty,
            mode=ExecutionMode.auto.value,
            status="opening",
            entry_spread_rate=await self._resolve_spread(request.symbol, request.long_exchange, request.short_exchange),
            opened_at=utc_now(),
            extra={"quantity": request.quantity, "note": request.note},
        )
        session.add(position)
        await session.flush()

        long_leg = await self._execute_leg(
            session=session,
            action="open",
            position_id=position.id,
            exchange=request.long_exchange,
            symbol=request.symbol,
            side="buy",
            quantity=long_qty,
            leverage=request.leverage,
            credentials=request.credentials,
            position_side="LONG",
        )

        if long_leg.status == "failed":
            risk_event_id = await self._create_risk_event(
                session,
                event_type="open_single_leg_failed",
                severity="high",
                message=f"开仓第一腿失败: {long_leg.message}",
                context={"position_id": position.id, "leg": long_leg.model_dump()},
            )
            position.status = "open_failed"
            await session.commit()
            return ExecutionActionResponse(
                success=False,
                action="open",
                mode=ExecutionMode.auto,
                position_id=position.id,
                legs=[long_leg],
                risk_event_id=risk_event_id,
                message="开仓失败：第一腿下单失败",
            )

        short_leg = await self._execute_leg(
            session=session,
            action="open",
            position_id=position.id,
            exchange=request.short_exchange,
            symbol=request.symbol,
            side="sell",
            quantity=short_qty,
            leverage=request.leverage,
            credentials=request.credentials,
            position_side="SHORT",
        )

        legs = [long_leg, short_leg]
        if short_leg.status == "failed":
            risk_event_id = await self._create_risk_event(
                session,
                event_type="open_second_leg_failed",
                severity="critical",
                message=f"开仓第二腿失败，触发回滚: {short_leg.message}",
                context={"position_id": position.id, "legs": [leg.model_dump() for leg in legs]},
            )
            rollback_leg = await self._execute_leg(
                session=session,
                action="rollback",
                position_id=position.id,
                exchange=request.long_exchange,
                symbol=request.symbol,
                side="sell",
                quantity=long_qty,
                leverage=request.leverage,
                credentials=request.credentials,
                reduce_only=True,
                position_side="LONG",
            )
            legs.append(rollback_leg)
            if rollback_leg.status == "ok":
                position.status = "rolled_back"
                message = "开仓第二腿失败，已尝试回滚第一腿"
            else:
                position.status = "risk_exposed"
                message = "开仓第二腿失败，回滚失败，存在单边风险"
            await session.commit()
            return ExecutionActionResponse(
                success=False,
                action="open",
                mode=ExecutionMode.auto,
                position_id=position.id,
                legs=legs,
                risk_event_id=risk_event_id,
                message=message,
            )

        position.status = "open"
        await session.commit()
        return ExecutionActionResponse(
            success=True,
            action="open",
            mode=ExecutionMode.auto,
            position_id=position.id,
            legs=legs,
            message="开仓成功",
        )

    async def close_position(
        self,
        session: AsyncSession,
        request: ClosePositionRequest,
    ) -> ExecutionActionResponse:
        plan = await self._resolve_close_plan(session, request)
        position = plan["position"]
        symbol = plan["symbol"]
        long_exchange = plan["long_exchange"]
        short_exchange = plan["short_exchange"]
        long_qty = plan["long_qty"]
        short_qty = plan["short_qty"]

        long_leg = await self._execute_leg(
            session=session,
            action="close",
            position_id=position.id if position else None,
            exchange=long_exchange,
            symbol=symbol,
            side="sell",
            quantity=long_qty,
            leverage=request.leverage,
            credentials=request.credentials,
            reduce_only=True,
            position_side="LONG",
        )
        if long_leg.status == "failed":
            risk_event_id = await self._create_risk_event(
                session,
                event_type="close_single_leg_failed",
                severity="high",
                message=f"平仓第一腿失败: {long_leg.message}",
                context={"position_id": position.id if position else None, "leg": long_leg.model_dump()},
            )
            if position:
                position.status = "close_failed"
            await session.commit()
            return ExecutionActionResponse(
                success=False,
                action="close",
                mode=ExecutionMode.auto,
                position_id=position.id if position else None,
                legs=[long_leg],
                risk_event_id=risk_event_id,
                message="平仓失败：第一腿下单失败",
            )

        short_leg = await self._execute_leg(
            session=session,
            action="close",
            position_id=position.id if position else None,
            exchange=short_exchange,
            symbol=symbol,
            side="buy",
            quantity=short_qty,
            leverage=request.leverage,
            credentials=request.credentials,
            reduce_only=True,
            position_side="SHORT",
        )
        legs = [long_leg, short_leg]

        if short_leg.status == "failed":
            risk_event_id = await self._create_risk_event(
                session,
                event_type="close_second_leg_failed",
                severity="critical",
                message=f"平仓第二腿失败，触发回滚: {short_leg.message}",
                context={"position_id": position.id if position else None, "legs": [leg.model_dump() for leg in legs]},
            )
            rollback_leg = await self._execute_leg(
                session=session,
                action="rollback",
                position_id=position.id if position else None,
                exchange=long_exchange,
                symbol=symbol,
                side="buy",
                quantity=long_qty,
                leverage=request.leverage,
                credentials=request.credentials,
                position_side="LONG",
            )
            legs.append(rollback_leg)
            if position:
                position.status = "risk_exposed" if rollback_leg.status == "failed" else "open"
            await session.commit()
            return ExecutionActionResponse(
                success=False,
                action="close",
                mode=ExecutionMode.auto,
                position_id=position.id if position else None,
                legs=legs,
                risk_event_id=risk_event_id,
                message="平仓第二腿失败，已执行回滚对冲尝试",
            )

        if position:
            position.status = "closed"
            position.closed_at = utc_now()
        await session.commit()
        return ExecutionActionResponse(
            success=True,
            action="close",
            mode=ExecutionMode.auto,
            position_id=position.id if position else None,
            legs=legs,
            message="平仓执行完成",
        )

    async def hedge(
        self,
        session: AsyncSession,
        request: HedgeRequest,
    ) -> ExecutionActionResponse:
        quantity = request.quantity

        leg = await self._execute_leg(
            session=session,
            action="hedge",
            position_id=None,
            exchange=request.exchange,
            symbol=request.symbol,
            side=request.side,
            quantity=quantity,
            leverage=request.leverage,
            credentials=request.credentials,
            reduce_only=False,
            position_side="LONG" if request.side == "buy" else "SHORT",
            note=request.reason,
        )
        risk_event_id = None
        success = leg.status != "failed"
        if not success:
            risk_event_id = await self._create_risk_event(
                session,
                event_type="hedge_failed",
                severity="high",
                message=f"对冲下单失败: {leg.message}",
                context={"leg": leg.model_dump()},
            )
        await session.commit()
        return ExecutionActionResponse(
            success=success,
            action="hedge",
            mode=ExecutionMode.auto,
            legs=[leg],
            risk_event_id=risk_event_id,
            message="对冲执行完成" if success else "对冲失败",
        )

    async def convert_notional_to_quantity(self, request: QuantityConvertRequest) -> QuantityConvertResponse:
        snapshots = await self._fetch_pricing_snapshots()
        mark_price = self._find_mark_price(snapshots=snapshots, exchange="binance", symbol=request.symbol)
        if mark_price is None or mark_price <= 0:
            raise ValueError(f"无法根据名义金额换算数量：binance {request.symbol} 缺少有效标记价格")

        quantity = request.notional_usd / mark_price
        if quantity <= 0:
            raise ValueError(f"换算后的下单数量无效：binance {request.symbol}")

        timestamp = utc_now()
        for row in snapshots:
            if row.exchange == "binance" and row.symbol == request.symbol:
                timestamp = row.updated_at
                break

        return QuantityConvertResponse(
            symbol=request.symbol,
            exchange="binance",
            notional_usd=request.notional_usd,
            mark_price=mark_price,
            quantity=quantity,
            timestamp=timestamp,
        )

    async def emergency_close(
        self,
        session: AsyncSession,
        request: EmergencyCloseRequest,
    ) -> ExecutionActionResponse:
        stmt = select(Position).where(Position.status != "closed")
        if request.position_ids:
            stmt = stmt.where(Position.id.in_(request.position_ids))
        positions = list((await session.scalars(stmt)).all())

        all_legs: list[ExecutionLegResult] = []
        failed = 0
        for position in positions:
            close_result = await self.close_position(
                session,
                ClosePositionRequest(
                    position_id=position.id,
                    credentials=request.credentials,
                ),
            )
            all_legs.extend(close_result.legs)
            if not close_result.success:
                failed += 1

        return ExecutionActionResponse(
            success=failed == 0,
            action="emergency-close",
            mode=ExecutionMode.auto,
            legs=all_legs,
            message=f"紧急全平完成，总仓位 {len(positions)}，失败 {failed}",
        )

    async def _execute_leg(
        self,
        *,
        session: AsyncSession,
        action: str,
        position_id: str | None,
        exchange: SupportedExchange,
        symbol: str,
        side: str,
        quantity: float,
        leverage: float | None,
        credentials: dict[SupportedExchange, ExchangeCredential],
        reduce_only: bool = False,
        position_side: str | None = None,
        note: str | None = None,
    ) -> ExecutionLegResult:
        credential = credentials.get(exchange)
        if credential is None:
            try:
                credential = await self.credential_service.get_credential(session, exchange)
            except ValueError:
                credential = None

        if credential is None:
            result = ExecutionLegResult(
                exchange=exchange,
                symbol=symbol,
                side=side,  # type: ignore[arg-type]
                quantity=quantity,
                status="failed",
                message=f"缺少 {exchange} 凭据，自动模式无法下单",
            )
            await self._create_order(
                session=session,
                position_id=position_id,
                action=action,
                status=result.status,
                exchange=exchange,
                symbol=symbol,
                side=side,
                quantity=quantity,
                filled_qty=None,
                avg_price=None,
                exchange_order_id=None,
                note=note,
                extra={"reduce_only": reduce_only},
            )
            return result

        gateway_result = await self.gateway.place_market_order(
            exchange=exchange,
            symbol=symbol,
            side=side,
            quantity=quantity,
            credential=credential,
            leverage=leverage,
            reduce_only=reduce_only,
            position_side=position_side,
        )

        status = "ok" if gateway_result.success else "failed"
        result = ExecutionLegResult(
            exchange=exchange,
            symbol=symbol,
            side=side,  # type: ignore[arg-type]
            quantity=quantity,
            status=status,
            order_id=gateway_result.order_id,
            filled_qty=gateway_result.filled_qty,
            avg_price=gateway_result.avg_price,
            message=gateway_result.message,
            raw=gateway_result.raw,
        )

        await self._create_order(
            session=session,
            position_id=position_id,
            action=action,
            status=status,
            exchange=exchange,
            symbol=symbol,
            side=side,
            quantity=quantity,
            filled_qty=gateway_result.filled_qty,
            avg_price=gateway_result.avg_price,
            exchange_order_id=gateway_result.order_id,
            note=note,
            extra={"reduce_only": reduce_only, "raw": gateway_result.raw},
        )
        return result

    async def _create_order(
        self,
        *,
        session: AsyncSession,
        position_id: str | None,
        action: str,
        status: str,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        filled_qty: float | None,
        avg_price: float | None,
        exchange_order_id: str | None,
        note: str | None,
        extra: dict[str, Any],
    ) -> None:
        order = Order(
            position_id=position_id,
            action=action,
            mode=ExecutionMode.auto.value,
            status=status,
            exchange=exchange,
            symbol=symbol,
            side=side,
            quantity=quantity,
            filled_qty=filled_qty,
            avg_price=avg_price,
            exchange_order_id=exchange_order_id,
            note=note,
            extra=extra,
        )
        session.add(order)
        await session.flush()

    async def _create_risk_event(
        self,
        session: AsyncSession,
        *,
        event_type: str,
        severity: str,
        message: str,
        context: dict[str, Any],
    ) -> str:
        event = RiskEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            context=context,
        )
        session.add(event)
        await session.flush()
        return event.id

    async def _resolve_spread(
        self,
        symbol: str,
        long_exchange: SupportedExchange,
        short_exchange: SupportedExchange,
    ) -> float | None:
        snapshots_resp = await self.market_data_service.fetch_snapshots()
        opportunities = scan_opportunities(snapshots_resp.snapshots)
        for item in opportunities:
            if (
                item.symbol == symbol
                and item.long_exchange == long_exchange
                and item.short_exchange == short_exchange
            ):
                return item.spread_rate_1y_nominal
        return None

    async def _resolve_close_plan(
        self,
        session: AsyncSession,
        request: ClosePositionRequest,
    ) -> dict[str, Any]:
        if request.position_id:
            position = await session.get(Position, request.position_id)
            if position is None:
                raise ValueError(f"未找到仓位: {request.position_id}")
            return {
                "position": position,
                "symbol": position.symbol,
                "long_exchange": position.long_exchange,
                "short_exchange": position.short_exchange,
                "long_qty": position.long_qty,
                "short_qty": position.short_qty,
            }

        assert request.symbol is not None
        assert request.long_exchange is not None
        assert request.short_exchange is not None
        assert request.long_quantity is not None
        assert request.short_quantity is not None

        return {
            "position": None,
            "symbol": request.symbol,
            "long_exchange": request.long_exchange,
            "short_exchange": request.short_exchange,
            "long_qty": request.long_quantity,
            "short_qty": request.short_quantity,
        }

    async def _fetch_pricing_snapshots(self) -> list[MarketSnapshot]:
        snapshots_resp = await self.market_data_service.fetch_snapshots()
        return snapshots_resp.snapshots

    def _find_mark_price(
        self,
        *,
        snapshots: list[MarketSnapshot],
        exchange: SupportedExchange,
        symbol: str,
    ) -> float | None:
        target_symbol = symbol.upper()
        for row in snapshots:
            if row.exchange != exchange:
                continue
            if row.symbol != target_symbol:
                continue
            price = _safe_float(row.mark_price)
            if price is not None and price > 0:
                return price
        return None


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"value": value}


def _is_binance_position_side_mismatch(exc: Exception) -> bool:
    text = str(exc).lower()
    return "-4061" in text and "position side" in text
