<script setup lang="ts">
import type { MarketRow } from '../types/market';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';

defineProps<{
  rows: MarketRow[];
  loading: boolean;
}>();

defineEmits<{
  preview: [MarketRow];
  open: [MarketRow];
}>();

function rateClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}
</script>

<template>
  <section class="table-shell">
    <div class="table-scroll">
      <table class="market-table">
        <thead>
          <tr>
            <th>交易所</th>
            <th>币对</th>
            <th>未平仓额</th>
            <th>日成交额</th>
            <th>1h</th>
            <th>8h</th>
            <th>1y</th>
            <th>下次费率时间和值</th>
            <th>结算间隔</th>
            <th>最大杠杆</th>
            <th>名义年化(杠杆后)</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="12" class="empty-cell">数据加载中...</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td colspan="12" class="empty-cell">暂无满足条件的数据</td>
          </tr>
          <tr v-for="row in rows" :key="row.id">
            <td>
              <div class="exchange-cell">
                <span>{{ row.exchange }}</span>
                <small :class="row.source === 'opportunity' ? 'tag-op' : 'tag-snapshot'">
                  {{ row.source === 'opportunity' ? '套利' : '市场' }}
                </small>
              </div>
            </td>
            <td class="symbol">{{ row.symbol }}</td>
            <td>{{ formatMoney(row.openInterestUsd) }}</td>
            <td>{{ formatMoney(row.volume24hUsd) }}</td>
            <td :class="rateClass(row.fundingRate1h)">
              {{ formatPercent(row.fundingRate1h, 4) }}
            </td>
            <td :class="rateClass(row.fundingRate8h)">
              {{ formatPercent(row.fundingRate8h, 4) }}
            </td>
            <td :class="rateClass(row.fundingRate1y)">
              {{ formatPercent(row.fundingRate1y, 2) }}
            </td>
            <td class="next-funding">
              <span>{{ formatTime(row.nextFundingTime) }}</span>
              <span :class="rateClass(row.nextFundingRate)">
                {{ formatPercent(row.nextFundingRate, 4) }}
              </span>
            </td>
            <td>{{ row.settlementInterval }}</td>
            <td>{{ formatLeverage(row.maxLeverage) }}</td>
            <td class="apr">{{ formatPercent(row.leveragedNominalApr ?? row.nominalApr, 2) }}</td>
            <td>
              <div class="action-group">
                <button type="button" class="action-button" @click="$emit('preview', row)">预览</button>
                <button type="button" class="action-button accent" @click="$emit('open', row)">开仓</button>
              </div>
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

.table-scroll {
  overflow-x: auto;
}

.market-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1280px;
}

th,
td {
  border-bottom: 1px solid var(--line-soft);
  padding: 6px 8px;
  font-size: 12px;
  line-height: 1.35;
  white-space: nowrap;
  text-align: left;
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

.exchange-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tag-op,
.tag-snapshot {
  font-size: 10px;
  border-radius: 2px;
  padding: 1px 4px;
  border: 1px solid transparent;
}

.tag-op {
  border-color: rgba(0, 199, 166, 0.7);
  color: var(--accent-soft);
}

.tag-snapshot {
  border-color: var(--line-soft);
  color: var(--text-dim);
}

.symbol {
  color: #f3f5f7;
  font-weight: 600;
}

.next-funding {
  display: grid;
  gap: 2px;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}

.apr {
  font-weight: 700;
  color: var(--accent-soft);
}

.action-group {
  display: flex;
  gap: 6px;
}

.action-button {
  height: 26px;
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
