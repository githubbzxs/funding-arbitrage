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
  <section class="card-list">
    <p class="open-tip">点击币对会尝试在新标签打开双交易所；若只打开一个，请先允许本站弹窗与重定向。</p>
    <p v-if="loading && rows.length === 0" class="state-tip">数据加载中...</p>
    <p v-else-if="rows.length === 0" class="state-tip">暂无满足条件的数据</p>

    <article v-for="row in rows" :key="row.id" class="pair-card">
      <header class="card-head">
        <button type="button" class="symbol-link" @click="$emit('visitSymbol', row)">
          {{ row.symbol }}
        </button>
        <span class="path-text">{{ row.longExchange }} → {{ row.shortExchange }}</span>
      </header>

      <dl class="card-grid">
        <div>
          <dt>多腿 8h</dt>
          <dd :class="rateClass(row.longLeg.fundingRate8h)">{{ formatPercent(row.longLeg.fundingRate8h, 4) }}</dd>
        </div>
        <div>
          <dt>空腿 8h</dt>
          <dd :class="rateClass(row.shortLeg.fundingRate8h)">{{ formatPercent(row.shortLeg.fundingRate8h, 4) }}</dd>
        </div>
        <div>
          <dt>价差 1h</dt>
          <dd :class="rateClass(row.spreadRate1h)">{{ formatPercent(row.spreadRate1h, 4) }}</dd>
        </div>
        <div>
          <dt>价差 8h</dt>
          <dd :class="rateClass(row.spreadRate8h)">{{ formatPercent(row.spreadRate8h, 4) }}</dd>
        </div>
        <div>
          <dt>价差年化</dt>
          <dd :class="['strong', rateClass(row.spreadRate1yNominal)]">{{ formatPercent(row.spreadRate1yNominal, 2) }}</dd>
        </div>
        <div>
          <dt>杠杆后年化</dt>
          <dd :class="['strong', rateClass(row.leveragedSpreadRate1yNominal)]">
            {{ formatPercent(row.leveragedSpreadRate1yNominal, 2) }}
          </dd>
        </div>
        <div>
          <dt>可用杠杆</dt>
          <dd>{{ formatLeverage(usableLeverage(row)) }}</dd>
        </div>
      </dl>

      <div class="card-actions">
        <button type="button" class="action-button" @click="$emit('visitSymbol', row)">新标签打开双交易所</button>
        <button type="button" class="action-button accent" @click="$emit('trade', row)">去交易</button>
      </div>
    </article>
  </section>
</template>

<style scoped>
.card-list {
  display: grid;
  gap: 10px;
}

.open-tip {
  margin: 0;
  border: 1px solid var(--line-soft);
  background: #0d141e;
  color: var(--text-dim);
  padding: 10px;
  font-size: 12px;
}

.state-tip {
  margin: 0;
  border: 1px solid var(--line-soft);
  background: var(--panel-bg);
  color: var(--text-dim);
  padding: 12px;
  font-size: 12px;
}

.pair-card {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: grid;
  gap: 10px;
}

.card-head {
  display: grid;
  gap: 4px;
}

.symbol-link {
  border: none;
  background: transparent;
  color: #77f5de;
  font-weight: 700;
  font-size: 16px;
  padding: 0;
  text-align: left;
}

.symbol-link:hover {
  text-decoration: underline;
}

.path-text {
  color: var(--text-dim);
  font-size: 12px;
}

.card-grid {
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 10px;
}

.card-grid div {
  border: 1px solid var(--line-soft);
  background: #0d141e;
  padding: 8px;
  display: grid;
  gap: 4px;
}

dt {
  color: var(--text-dim);
  font-size: 11px;
}

dd {
  margin: 0;
  color: var(--text-main);
  font-size: 13px;
  font-weight: 600;
}

.card-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.action-button {
  height: 34px;
  border: 1px solid var(--line-soft);
  color: var(--text-main);
  background: #101722;
  font-size: 12px;
  border-radius: 4px;
}

.action-button.accent {
  border-color: rgba(0, 199, 166, 0.8);
  color: #032621;
  background: rgba(0, 199, 166, 0.88);
  font-weight: 600;
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
</style>
