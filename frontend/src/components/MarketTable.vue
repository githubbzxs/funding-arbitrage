<script setup lang="ts">
import type { OpportunityPairRow } from '../types/market';
import { formatLeverage, formatPercent } from '../utils/format';

defineProps<{
  rows: OpportunityPairRow[];
  loading: boolean;
}>();

defineEmits<{
  trade: [OpportunityPairRow];
  visitSymbol: [OpportunityPairRow];
}>();

function rateClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}

function usableLeverage(row: OpportunityPairRow): number | null {
  const left = row.longLeg.maxLeverage;
  const right = row.shortLeg.maxLeverage;
  if (typeof left === 'number' && Number.isFinite(left) && typeof right === 'number' && Number.isFinite(right)) {
    return Math.min(left, right);
  }
  return null;
}
</script>

<template>
  <section class="table-shell">
    <p class="table-tip">点击币对将尝试在新标签打开双交易所；若只打开一个，请先允许本站弹窗与重定向。</p>
    <div class="table-scroll">
      <table class="market-table">
        <thead>
          <tr>
            <th>币对</th>
            <th>套利路径</th>
            <th>多腿费率(8h)</th>
            <th>空腿费率(8h)</th>
            <th>价差(1h/8h/年化)</th>
            <th>杠杆后年化</th>
            <th>可用杠杆</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="empty-cell">数据加载中...</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td colspan="8" class="empty-cell">暂无满足条件的数据</td>
          </tr>
          <tr v-for="row in rows" :key="row.id">
            <td class="symbol-cell">
              <button type="button" class="symbol-link" title="新标签打开双交易所" @click="$emit('visitSymbol', row)">
                {{ row.symbol }}
              </button>
            </td>
            <td>{{ row.longExchange }} → {{ row.shortExchange }}</td>
            <td :class="rateClass(row.longLeg.fundingRate8h)">
              {{ formatPercent(row.longLeg.fundingRate8h, 4) }}
            </td>
            <td :class="rateClass(row.shortLeg.fundingRate8h)">
              {{ formatPercent(row.shortLeg.fundingRate8h, 4) }}
            </td>
            <td class="spread-cell">
              <div :class="rateClass(row.spreadRate1h)">1h {{ formatPercent(row.spreadRate1h, 4) }}</div>
              <div :class="rateClass(row.spreadRate8h)">8h {{ formatPercent(row.spreadRate8h, 4) }}</div>
              <div :class="['strong', rateClass(row.spreadRate1yNominal)]">年化 {{ formatPercent(row.spreadRate1yNominal, 2) }}</div>
            </td>
            <td :class="['strong', rateClass(row.leveragedSpreadRate1yNominal)]">
              {{ formatPercent(row.leveragedSpreadRate1yNominal, 2) }}
            </td>
            <td>{{ formatLeverage(usableLeverage(row)) }}</td>
            <td>
              <button type="button" class="action-button accent" @click="$emit('trade', row)">去交易</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.table-shell {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  min-height: 320px;
}

.table-tip {
  margin: 0;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-soft);
  color: var(--text-dim);
  font-size: 12px;
}

.table-scroll {
  overflow-x: auto;
}

.market-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1080px;
}

th,
td {
  border-bottom: 1px solid var(--line-soft);
  padding: 10px 8px;
  font-size: 12px;
  line-height: 1.35;
  white-space: nowrap;
  text-align: left;
  vertical-align: top;
}

thead th {
  position: sticky;
  top: 0;
  background: #0e141d;
  z-index: 1;
  color: #a9b6c4;
  font-weight: 500;
}

tbody tr:hover {
  background: rgba(0, 199, 166, 0.05);
}

.symbol-cell {
  min-width: 120px;
}

.symbol-link {
  border: none;
  background: transparent;
  color: #77f5de;
  font-weight: 700;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.symbol-link:hover {
  text-decoration: underline;
}

.spread-cell {
  display: grid;
  gap: 4px;
}

.strong {
  font-weight: 700;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}

.action-button {
  height: 28px;
  border: 1px solid var(--line-soft);
  color: var(--text-main);
  background: #101722;
  font-size: 12px;
  border-radius: 2px;
  padding: 0 10px;
}

.action-button:hover {
  border-color: var(--accent);
}

.action-button.accent {
  border-color: rgba(0, 199, 166, 0.8);
  color: #032621;
  background: rgba(0, 199, 166, 0.88);
}

.action-button.accent:hover {
  background: rgba(0, 199, 166, 1);
}

.empty-cell {
  text-align: center;
  color: var(--text-dim);
  padding: 16px 8px;
}
</style>
