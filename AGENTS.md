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

- **[2026-02-13] 行情页改为缓存优先+五分钟刷新并修复双交易所跳转**：进入页面优先读取本地缓存，不再立即发起网络请求；统一改为 5 分钟自动刷新 + 顶部单一手动刷新按钮；币对点击改为用户手势内直接打开双交易所，失败时回退中转页手动打开。
  - Why：解决“点击后只开一个交易所”“立即刷新无体感”“进入页面即刷导致等待”的体验问题。
  - Impact：`frontend/src/pages/MarketPage.vue`，`frontend/src/components/TopFilters.vue`，`frontend/src/pages/TradeRedirectPage.vue`，`frontend/src/utils/exchangeLinks.ts`，`frontend/src/components/MarketCardList.vue`
  - Verify：手动点击币对应能同时打开两所；刷新按钮显示“刷新中”；新开页面在有缓存时立即展示，5 分钟后自动刷新。

- **[2026-02-13] 抓取失败回退升级为全交易所 ccxt->REST->stale**：统一 provider 在 ccxt 失败或空结果时回退到各交易所原生 REST 抓取，最终仍可回退 stale 数据，接口支持 `force_refresh` 跳过缓存。
  - Why：避免单一 ccxt 链路波动导致多个交易所同时缺失。
  - Impact：`backend/app/exchanges/providers/ccxt_market.py`，`backend/app/services/market_data.py`，`backend/app/api/market.py`，`backend/app/api/opportunities.py`，`backend/tests/test_gateio_fallback.py`，`backend/tests/test_market_force_refresh.py`
  - Verify：`GET /api/market/snapshots?force_refresh=1` 检查 `meta.exchange_sources`；`cd backend && pytest -q`。

- **[2026-02-13] 双交易所直开链路改为强同步双开并取消主流程中转页回退**：主流程点击币对时改为同步尝试打开两个新标签，若被拦截则在行情页内强提示开启本站弹窗权限；中转页降级为手动工具页。
  - Why：彻底消除“点击后自动跳转中转页且只打开一个交易所”的主流程干扰，让行为可预测。
  - Impact：`frontend/src/utils/exchangeLinks.ts`，`frontend/src/utils/popupOpen.ts`，`frontend/src/pages/MarketPage.vue`，`frontend/src/components/MarketTable.vue`，`frontend/src/components/MarketCardList.vue`，`frontend/src/pages/TradeRedirectPage.vue`，`frontend/src/App.vue`，`frontend/package.json`，`frontend/src/utils/exchangeLinks.test.ts`，`frontend/src/utils/popupOpen.test.ts`
  - Verify：`cd frontend && npm run test`，`cd frontend && npm run build`，手动点击币对验证不再自动跳转 `/trade/redirect` 且拦截时出现权限提示。

- **[2026-02-13] 扫描页改为 board 聚合接口 + 查询缓存 + 虚拟滚动**：前端主入口重构为 `/scanner` 与 `/scanner/:symbol/:long/:short`，数据改走 `/api/market/board`；桌面端使用虚拟列表，移动端使用分页卡片；后端新增 `symbol` 过滤并补齐 board 行 `id` 与腿部 `exchange` 字段。
  - Why：降低前端二次拼装和全量渲染开销，解决中大数据量下卡顿。
  - Impact：`backend/app/api/market.py`，`backend/app/services/market_board.py`，`backend/app/models/schemas.py`，`backend/tests/test_market_board.py`，`frontend/src/pages/ScannerPage.vue`，`frontend/src/pages/PairDetailPage.vue`，`frontend/src/components/ScannerTableVirtual.vue`，`frontend/src/components/ScannerMobileCards.vue`，`frontend/src/components/ScannerToolbar.vue`，`frontend/src/composables/useScannerQuery.ts`，`frontend/src/api/market.ts`，`frontend/src/router.ts`，`frontend/src/main.ts`
  - Verify：`cd backend && pytest -q`；`cd frontend && npm run test`；`cd frontend && npm run build`

- **[2026-02-13] 扫描页补齐交易所筛选修复 + Gate.io WS兜底 + 间隔差异收益模拟**：后端 board 筛选改为“单选包含、多选双腿都命中”；Gate.io 抓取链路升级为 `ccxt -> REST -> WS -> stale`；前端新增“保证金模拟(24h)”并按“同间隔正常算、异间隔拆分短间隔单边”展示预估收益。
  - Why：修复筛选体验与 Gate.io 间歇缺失，且把不同收费间隔下的真实收益结构直观展示出来。
  - Impact：`backend/app/exchanges/providers/ccxt_market.py`，`backend/app/services/market_board.py`，`backend/app/models/schemas.py`，`backend/tests/test_gateio_fallback.py`，`backend/tests/test_market_board.py`，`frontend/src/api/market.ts`，`frontend/src/types/market.ts`，`frontend/src/utils/marginSim.ts`，`frontend/src/pages/ScannerPage.vue`，`frontend/src/components/ScannerTableVirtual.vue`，`frontend/src/components/ScannerMobileCards.vue`
  - Verify：`cd backend && pytest -q`，`cd frontend && npm run test`，`cd frontend && npm run build`

- **[2026-02-13] 扫描页统一指标切换为“下一次同结算窗口”并修复桌面比例**：后端新增 `next_cycle_score`、`next_sync_settlement_time` 与结算事件预览；前端移除“套利方向”，将“资金费率+结算间隔+下次结算”合并展示，并将保证金模拟改为按同一事件列表逐次计算。
  - Why：解决“页面撑开后信息看不全”与“多指标口径分散”问题，把不同结算间隔下的单边机会和每次金额统一到可对比口径。
  - Impact：`backend/app/api/market.py`，`backend/app/models/schemas.py`，`backend/app/services/market_board.py`，`backend/tests/test_market_board.py`，`frontend/src/api/market.ts`，`frontend/src/types/market.ts`，`frontend/src/utils/marginSim.ts`，`frontend/src/utils/marginSim.test.ts`，`frontend/src/pages/ScannerPage.vue`，`frontend/src/components/ScannerToolbar.vue`，`frontend/src/components/ScannerTableVirtual.vue`，`frontend/src/components/ScannerMobileCards.vue`，`frontend/src/pages/PairDetailPage.vue`，`frontend/src/composables/useScannerQuery.ts`
  - Verify：`cd backend && pytest -q`，`cd frontend && npm run test`，`cd frontend && npm run build`

- **[2026-02-13] 扫描页首屏改为“持久化缓存优先 + 5分钟策略对齐”**：`useScannerQuery` 新增 localStorage 持久缓存并注入 `initialData`，后端默认 `market_cache_ttl_seconds` 调整为 `300`，扫描页默认自动刷新间隔改为 `300` 秒并在工具栏增加 `300` 秒选项。
  - Why：修复“进入页面仍需等待网络返回”的体验问题，确保尽量先出上次数据，再后台更新。
  - Impact：`frontend/src/composables/useScannerQuery.ts`，`frontend/src/pages/ScannerPage.vue`，`frontend/src/components/ScannerToolbar.vue`，`backend/app/core/config.py`
  - Verify：`cd frontend && npm run test`，`cd frontend && npm run build`，`cd backend && pytest -q`，`https://funding.0xpsyche.me/healthz`

- **[2026-02-15] 系统主入口改造为“套利执行 + 监控终端”并移除行情扫描链路**：前端删除 `/scanner` 及详情页、虚拟表格、行情查询与相关工具模块，路由改为 `/trade`、`/monitor`、`/settings/api`；后端移除 `/api/market/*` 与 `/api/opportunities`，新增策略模板 API（`/api/templates`）与风险事件 API（`/api/risk-events`），交易页支持模板创建/更新/删除与一键回填，监控页支持仓位/订单/风险事件轮询与页内告警条。
  - Why：按需求彻底去除行情页面，收敛为执行与风控监控闭环，减少页面切换与冗余链路。
  - Impact：`frontend/src/router.ts`，`frontend/src/App.vue`，`frontend/src/pages/TradePage.vue`，`frontend/src/pages/MonitorPage.vue`，`frontend/src/pages/ApiSettingsPage.vue`，`frontend/src/api/records.ts`，`frontend/src/api/templates.ts`，`frontend/src/types/market.ts`，`backend/app/main.py`，`backend/app/models/orm.py`，`backend/app/models/schemas.py`，`backend/app/api/templates.py`，`backend/app/api/risk_events.py`，`backend/tests/test_templates_api.py`，`backend/tests/test_risk_events_api.py`。
  - Verify：`cd backend && pytest -q`，`cd frontend && npm run test`，`cd frontend && npm run build`。

- **[2026-02-15] Binance 统一账户下单新增 `portfolioMargin` 自动重试兜底**：当 Binance 首次下单返回 `-2015 Invalid API-key, IP, or permissions` 时，执行网关会自动以 `portfolioMargin=true` 再试一次（走 PAPI 路由），并在设置杠杆时同步携带该参数。
  - Why：统一账户（Portfolio Margin）与普通 U 本位账户路由不同，避免因路由不匹配导致“Key 正确但下单失败”。
  - Impact：`backend/app/services/execution.py`，`backend/tests/test_execution_binance_portfolio_margin.py`
  - Verify：`cd backend && pytest -q`

- **[2026-02-15] 执行链路改为仅名义金额下单并移除手动模式**：`open/close/hedge` 请求移除数量参数，统一使用 `notional_usd`，由后端按交易所 `mark_price` 换算数量；执行模式固定为 `auto`，前端交易页移除“执行模式/数量”输入。
  - Why：减少手工换算误差，统一下单口径并收敛交互复杂度。
  - Impact：`backend/app/models/schemas.py`，`backend/app/services/execution.py`，`backend/app/api/execution.py`，`backend/app/exchanges/providers/ccxt_market.py`，`frontend/src/pages/TradePage.vue`，`frontend/src/types/market.ts`，`frontend/src/api/templates.ts`
  - Verify：`cd backend && pytest -q`，`cd frontend && npm test`，`cd frontend && npm run build`

- **[2026-02-15] 执行改回数量下单并新增 Binance 统一换算工具**：`open/close/hedge` 重新使用 `quantity` 入参；新增 `POST /api/execution/convert`，按 Binance 标记价格将 `notional_usd` 换算为数量；交易页新增“名义金额换算（Binance）”区块并支持一键回填数量；策略模板恢复 `quantity` 字段读写。
  - Why：避免因单所标记价缺失导致下单失败，同时保留名义金额快速换算的便利性。
  - Impact：`backend/app/models/schemas.py`，`backend/app/services/execution.py`，`backend/app/api/execution.py`，`backend/app/api/templates.py`，`backend/tests/test_execution_notional_flow.py`，`backend/tests/test_templates_api.py`，`frontend/src/pages/TradePage.vue`，`frontend/src/api/execution.ts`，`frontend/src/types/market.ts`，`frontend/src/api/templates.ts`，`frontend/src/api/templates.test.ts`
  - Verify：`cd backend && pytest -q`，`cd frontend && npm test`，`cd frontend && npm run build`

- **[2026-02-15] 测试 VPS 已完成本次发布（commit: `0e26783`）**：香港测试机 `103.52.152.92` 已执行 `git pull --ff-only origin main` 与 `docker-compose -f docker-compose.vps.yml up -d --build`，`fa-backend/fa-frontend/fa-postgres/fa-redis` 均为 `Up`。
  - Verify：`curl -i http://127.0.0.1:8080/healthz` 返回 `200`，响应体包含 `{"status":"ok"}`。

- **[2026-02-15] Binance 下单默认走统一账户参数**：执行网关在 Binance 下单时始终携带 `portfolioMargin=true`，并在设置杠杆时同步走该参数，不再先走普通路由后重试。
  - Why：统一账户场景下减少路由不匹配导致的 `-2015` 鉴权误判。
  - Impact：`backend/app/services/execution.py`，`backend/tests/test_execution_binance_portfolio_margin.py`
  - Verify：`cd backend && pytest -q`

- **[2026-02-15] 修复 Binance `-4061` 持仓方向不匹配**：执行网关新增 `position_side` 透传；开/平/回滚/对冲时按腿方向显式设置 `LONG/SHORT`；当 Binance 返回 `-4061` 时自动回退重试为 `positionSide=BOTH`（兼容单向持仓设置）。
  - Why：统一账户下用户可能开启双向持仓；若参数与账户持仓模式不匹配会直接拒单。
  - Impact：`backend/app/services/execution.py`，`backend/tests/test_execution_binance_portfolio_margin.py`，`backend/tests/test_execution_notional_flow.py`
  - Verify：`cd backend && pytest -q`

- **[2026-02-15] 修复 OKX `51000 Parameter posSide error`**：OKX 下单默认按策略腿方向透传 `posSide=long/short`；若返回 `posSide` 参数错误，自动回退重试 `posSide=net`（并在平仓场景附带 `reduceOnly`）。
  - Why：OKX 账户可能配置为双向或单向持仓，不同模式对 `posSide/reduceOnly` 组合要求不同。
  - Impact：`backend/app/services/execution.py`，`backend/tests/test_execution_binance_portfolio_margin.py`
  - Verify：`cd backend && pytest -q`

- **[2026-02-15] 修复跨交易所数量口径不一致导致名义额度偏差**：执行网关下单前按交易所 `contractSize` 将“基础币数量”换算为各所下单单位（合约张数），并在回写成交数量时统一换回基础币数量；同时 Binance/OKX 设置杠杆失败时直接报错中止，避免“杠杆未生效但继续下单”。
  - Why：不同交易所合约下单单位不同（如 OKX 多为张数），直接复用同一 quantity 会造成实际名义金额偏差。
  - Impact：`backend/app/services/execution.py`，`backend/tests/test_execution_binance_portfolio_margin.py`
  - Verify：`cd backend && pytest -q`
