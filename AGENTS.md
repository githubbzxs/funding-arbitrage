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
- **[2026-02-13] 504 双轨修复**：后端做缓存 + 单交易所超时预算 + OKX funding 抓取预算；前端 Nginx 增加 `/api/` 代理超时兜底。
  - Why：避免外部接口慢/批量请求导致 Nginx 504。
  - Impact：`backend/app/services/market_data.py`，`backend/app/exchanges/okx.py`，`backend/app/core/config.py`，`frontend/nginx.conf`
- **[2026-02-13] 年化主展示改为杠杆后名义年化**：前端按 `leveragedNominalApr` 排序展示；后端补充 `leveraged_nominal_rate_1y` 与 `leveraged_spread_rate_1y_nominal` 字段。
  - Why：更贴近“可用杠杆放大后的名义收益”直觉口径，避免看起来过低。
  - Impact：`backend/app/exchanges/utils.py`，`backend/app/services/arbitrage.py`，`backend/app/models/schemas.py`，`frontend/src/api/market.ts`，`frontend/src/components/MarketTable.vue`
- **[2026-02-13] 统一 API 凭据后端托管**：新增 `/api/credentials`，新增 `FA_CREDENTIAL_ENCRYPTION_KEY`；加密存储表 `exchange_credentials`；自动模式缺省凭据时回退托管凭据。
  - Why：减少每次下单手填，提升可用性，并避免明文落库。
  - Impact：`backend/app/api/credentials.py`，`backend/app/services/credentials.py`，`backend/app/services/execution.py`，`frontend/src/components/TradeDrawer.vue`，`frontend/src/api/credentials.ts`

## Commands

- **后端启动**：`cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`
- **后端测试**：`cd backend && pytest -q`
- **前端启动**：`cd frontend && npm install && npm run dev`
- **前端构建**：`cd frontend && npm run build`
- **容器部署**：`docker compose up -d --build`
- **生成 Fernet Key（用于 FA_CREDENTIAL_ENCRYPTION_KEY）**：`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## Status / Next

- **[2026-02-13] 当前状态**：后端 API、5所行情聚合、套利扫描、执行接口、前端看板和交易抽屉已完成。
- **[2026-02-13] 下一步建议**：
  - 增加真实私有接口的下单后对账与重试幂等。
  - 增加 WebSocket 推送通道，减少轮询延迟。
  - 增加回测报告页（参数分组对比）。

## Known Issues

- **[2026-02-13] 区域限制**：部分交易所在美国网络/账户权限下可能限制实盘交易。
  - Verify：使用各交易所 API Key 在 `/api/execution/open` 做小额联调。
- **[2026-02-13] 托管凭据解密**：更换 `FA_CREDENTIAL_ENCRYPTION_KEY` 后历史托管凭据将无法解密。
  - Verify：调用 `GET /api/credentials` 检查 `api_key_masked` 是否可展示（缺密钥/密钥错误时可能为空）。

## Deploy Memory

- **[2026-02-13] VPS部署完成并接入域名**：应用已在服务器 `154.201.95.70` 通过 `docker compose -f docker-compose.vps.yml up -d --build` 更新到 `main` 最新提交（`dabbaeb`）。
  - Verify：`docker compose -f docker-compose.vps.yml ps` 显示 `fa-frontend/fa-backend/fa-postgres/fa-redis` 均为 `Up`。
- **[2026-02-13] 域名接入完成**：`funding.0xpsyche.me` 已解析到 `154.201.95.70`，并由系统 Nginx 反向代理到 `127.0.0.1:8080`，已签发 Let’s Encrypt 证书并启用 HTTPS。
  - Verify：`https://funding.0xpsyche.me/healthz` 返回 `{"status":"ok"}`，`https://funding.0xpsyche.me/api/market/snapshots` 返回 `200`。
- **[2026-02-13] 安全约束**：部署凭据仅用于本次会话，不写入仓库记忆文件。
