# 资金费率套利系统（Funding Arbitrage）

这是一个可运行的跨交易所资金费率套利系统，支持：

- Binance
- OKX
- Bybit
- Bitget
- Gate.io

系统能力：

- 实时抓取 5 所 USDT 永续资金费率与关键字段
- 统一口径展示：未平仓额、日成交额、1h/8h/1y、下次费率时间、结算间隔、最大杠杆、名义年化
- 自动扫描套利机会并按理论收益排序
- Web UI 高密度暗色终端风看板
- 一键执行：预览 / 开仓 / 平仓 / 对冲 / 紧急全平
- 基础防单边风控（单腿失败记录风险事件与回滚尝试）

## 目录结构

```text
backend/   FastAPI 服务、交易所适配器、执行与风控、测试
frontend/  Vue3 看板与交易面板
```

## 本地启动

## 1) 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认后端地址：`http://127.0.0.1:8000`  
文档地址：`http://127.0.0.1:8000/docs`

## 2) 前端

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`

## 一键容器部署

```bash
docker compose up -d --build
```

启动后：

- 前端：`http://localhost`
- 后端：`http://localhost:8000`

## 配置说明

复制 `.env.example` 后按需修改：

- 后端变量前缀：`FA_`
- 前端变量：`VITE_API_BASE`

关键变量：

- `FA_DATABASE_URL`：数据库连接（默认 SQLite，可切 PostgreSQL）
- `FA_REDIS_URL`：Redis 地址（用于短期缓存）
- `FA_CORS_ORIGINS`：允许跨域来源
- `FA_ENABLE_CCXT_MARKET_LEVERAGE`：是否启用 ccxt 公共杠杆探测

## 执行接口说明

- `POST /api/execution/preview`
- `POST /api/execution/open`
- `POST /api/execution/close`
- `POST /api/execution/hedge`
- `POST /api/execution/emergency-close`

自动模式下，请在请求体 `credentials` 提供对应交易所 API 凭据：

```json
{
  "binance": {
    "api_key": "...",
    "api_secret": "...",
    "passphrase": null,
    "testnet": false
  }
}
```

## 测试

```bash
cd backend
pytest -q
```

## 注意事项

- 本项目默认仅覆盖 USDT 永续。
- 不同地区/账号的交易权限会影响实盘可用性。
- 建议先使用手动模式或小资金验证后再启用自动模式。
