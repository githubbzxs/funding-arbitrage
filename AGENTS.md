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

## Memory Updates

- **[2026-02-13] 前端主视图切换为机会对并支持一键打开双交易所页面**：币对点击会按多腿/空腿交易所自动新开两个交易页；主表改为两腿完整信息+系统差值展示。
  - Why：降低手动切换交易页面的操作成本，统一 1h/4h/8h 在年化口径下比较。
  - Impact：`frontend/src/App.vue`，`frontend/src/components/MarketTable.vue`，`frontend/src/components/TopFilters.vue`，`frontend/src/components/BottomToolbar.vue`，`frontend/src/api/market.ts`，`frontend/src/types/market.ts`，`frontend/src/utils/exchangeLinks.ts`
  - Verify：`cd frontend && npm run build`；`cd backend && pytest -q`

- **[2026-02-13] 交易所筛选固定常驻 5 所，移除结算间隔筛选并扩展刷新频率**：筛选项固定 `binance/okx/bybit/bitget/gateio`，结算间隔仅展示不参与筛选，刷新预设改为 `2/5/10/20/30/60` 秒。
  - Why：避免因单所临时无数据导致筛选缺项，并减少无效筛选维度。
  - Impact：`frontend/src/App.vue`，`frontend/src/components/TopFilters.vue`，`frontend/src/components/BottomToolbar.vue`
  - Verify：前端页面手动检查筛选栏与底部工具栏选项。

- **[2026-02-13] 行情抓取切换为 ccxt 统一 provider 并增加接口元信息**：5 所行情统一走 `CcxtMarketProvider`，`/api/market/snapshots` 增加 `meta`（耗时/缓存命中/成功失败交易所）。
  - Why：降低多实现维护成本，并提升抓取链路可观测性。
  - Impact：`backend/app/exchanges/providers/ccxt_market.py`，`backend/app/services/market_data.py`，`backend/app/models/schemas.py`
  - Verify：`cd backend && pytest -q`；调用 `GET /api/market/snapshots` 检查 `meta` 字段。

- **[2026-02-13] 前端拆分为三页路由并修复双交易所跳转**：新增 `/` 行情页、`/trade` 交易页、`/settings/api` 凭据页、`/trade/redirect` 中转页；币对点击经中转页一键打开双交易所。
  - Why：降低单页信息密度，修复“只打开一个交易所”问题并提升可操作性。
  - Impact：`frontend/src/router.ts`，`frontend/src/pages/MarketPage.vue`，`frontend/src/pages/TradePage.vue`，`frontend/src/pages/ApiSettingsPage.vue`，`frontend/src/pages/TradeRedirectPage.vue`
  - Verify：`cd frontend && npm run build`；手动点击币对验证中转页与双链接。

- **[2026-02-13] 移除前端 OI/成交额阈值筛选与主表冗余展示**：主表去掉未平仓合约和交易量展示，筛选仅保留交易所维度。
  - Why：聚焦套利决策核心指标，减少信息噪音。
  - Impact：`frontend/src/components/TopFilters.vue`，`frontend/src/components/MarketTable.vue`，`frontend/src/types/market.ts`
  - Verify：前端页面确认无 OI/成交额阈值输入且主表不显示 OI/交易量。

- **[2026-02-13] 杠杆后年化与可用杠杆恢复并补齐 Gate.io 容错**：Binance 杠杆优先走公共档位接口，Gate.io 在 ccxt 空结果时回退原生 REST，市场聚合把“空结果”视为失败并使用短期 stale 快照兜底，同时默认开启 `FA_ENABLE_CCXT_MARKET_LEVERAGE`。
  - Why：修复“杠杆后年化/可用杠杆缺失”与“Gate.io 间歇缺失”导致的机会列表不稳定问题。
  - Impact：`backend/app/exchanges/leverage.py`，`backend/app/exchanges/providers/ccxt_market.py`，`backend/app/services/market_data.py`，`frontend/src/api/market.ts`，`frontend/src/types/market.ts`，`frontend/src/pages/MarketPage.vue`，`docker-compose.yml`，`docker-compose.vps.yml`
  - Verify：`cd backend && pytest -q`，`cd frontend && npm run build`，调用 `GET /api/market/snapshots` 检查 `meta.exchange_sources` 与 `meta.exchange_counts`。
