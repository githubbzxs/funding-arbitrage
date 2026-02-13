# AGENTS

## 项目协作约定

- 所有注释、README、内嵌文档使用中文（UTF-8）。
- 优先修复缺陷，再扩展功能。
- 遵循 KISS 和 SOLID，避免过度设计。
- 目标是可运行、可展示、可发布的真实产品。

## Facts

- **[2026-02-13] 产品定位**：跨交易所资金费率套利系统，覆盖 Binance/OKX/Bybit/Bitget/Gate.io。
- **[2026-02-13] 技术栈**：后端 FastAPI（Python），前端 Vue3 + Vite + TypeScript。
- **[2026-02-13] 部署形态**：支持本地开发与 Docker Compose 单机部署（PostgreSQL + Redis 可选）。
- **[2026-02-13] 市场范围**：当前仅 USDT 永续合约。

## Decisions

- **[2026-02-13] 机会排序**：按名义年化差 `spread_rate_1y_nominal` 降序。
  - Why：与目标“理论收益最高套利对”直接一致。
  - Impact：`backend/app/services/arbitrage.py`，`frontend/src/api/market.ts`
- **[2026-02-13] 风控最小闭环**：重点防单边，第二腿失败时回滚第一腿并记录风险事件。
  - Why：优先避免单边裸露导致爆仓风险。
  - Impact：`backend/app/services/execution.py`
- **[2026-02-13] 杠杆探测默认关闭**：`FA_ENABLE_CCXT_MARKET_LEVERAGE=false`。
  - Why：降低网络抖动带来的连接噪音与不稳定。
  - Impact：`backend/app/exchanges/leverage.py`

## Commands

- **后端启动**：`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- **后端测试**：`cd backend && pytest -q`
- **前端启动**：`cd frontend && npm install && npm run dev`
- **前端构建**：`cd frontend && npm run build`
- **容器部署**：`docker compose up -d --build`

## Status / Next

- **[2026-02-13] 当前状态**：后端 API、5所行情聚合、套利扫描、执行接口、前端看板和交易抽屉已完成。
- **[2026-02-13] 下一步建议**：
  - 增加真实私有接口的下单后对账与重试幂等。
  - 增加 WebSocket 推送通道，减少轮询延迟。
  - 增加回测报告页（参数分组对比）。

## Known Issues

- **[2026-02-13] 区域限制**：部分交易所在美国网络/账户权限下可能限制实盘交易。
  - Verify：使用各交易所 API Key 在 `/api/execution/open` 做小额联调。
