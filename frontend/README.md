# 资金费率套利前端

本目录是资金费率套利系统的前端工程，技术栈为 `Vue 3 + Vite + TypeScript`。

## 功能概览

- 顶部筛选：`OI 阈值`、`日成交额阈值`、`结算间隔筛选`、`交易所多选`
- 高密度暗色主表，展示：
- `交易所`
- `币对`
- `未平仓额`
- `日成交额`
- `1h / 8h / 1y`
- `下次费率时间和值`
- `结算间隔`
- `最大杠杆`
- `名义年化`
- 交易抽屉支持：`预览`、`开仓`、`平仓`、`一键对冲`、`紧急全平`
- 底部工具栏：文档、社群、语言、自动刷新

## 接口约定

- 市场数据：
- `GET /api/market/snapshots`
- `GET /api/opportunities`
- 交易与记录：
- `GET /api/positions`
- `GET /api/orders`
- `POST /api/execution/preview`
- `POST /api/execution/open`
- `POST /api/execution/close`
- `POST /api/execution/hedge`
- `POST /api/execution/emergency-close`

可通过环境变量 `VITE_API_BASE` 指定后端地址，默认同源访问。

## 本地开发

```bash
npm install
npm run dev
```

默认地址：`http://localhost:5173`

## 构建与预览

```bash
npm run build
npm run preview
```
