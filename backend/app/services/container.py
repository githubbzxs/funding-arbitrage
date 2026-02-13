from app.services.execution import ExecutionService
from app.services.market_data import MarketDataService


# 轻量级全局服务容器，保持实例复用。
market_data_service = MarketDataService()
execution_service = ExecutionService(market_data_service=market_data_service)

