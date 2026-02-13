<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { MarginSimulation, OpportunityBoardRow, SettlementEventPreview } from '../types/market';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';
import { resolveNextSettlementTime, resolveSingleSideEventCount } from '../utils/marginSim';

const props = defineProps<{
  rows: OpportunityBoardRow[];
  loading: boolean;
  marginInputs: Record<string, string>;
  settlementEventsByRowId: Record<string, SettlementEventPreview[]>;
  simulations: Record<string, MarginSimulation | null>;
}>();

const emit = defineEmits<{
  openDetail: [OpportunityBoardRow];
  openPair: [OpportunityBoardRow];
  openTrade: [OpportunityBoardRow];
  updateMargin: [{ rowId: string; value: string }];
}>();

const PAGE_SIZE = 20;
const page = ref(1);

const totalPages = computed(() => {
  const total = Math.ceil(props.rows.length / PAGE_SIZE);
  return total > 0 ? total : 1;
});

const pageRows = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE;
  return props.rows.slice(start, start + PAGE_SIZE);
});

watch(
  () => props.rows.length,
  () => {
    if (page.value > totalPages.value) {
      page.value = totalPages.value;
    }
  }
);

function nextPage(): void {
  page.value = Math.min(totalPages.value, page.value + 1);
}

function prevPage(): void {
  page.value = Math.max(1, page.value - 1);
}

function colorClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}

function sideText(side: 'long' | 'short' | null): string {
  if (side === 'long') {
    return '多腿';
  }
  if (side === 'short') {
    return '空腿';
  }
  return '未知';
}

function onMarginInput(rowId: string, event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('updateMargin', { rowId, value: target.value });
}

function rowEvents(row: OpportunityBoardRow): SettlementEventPreview[] {
  return props.settlementEventsByRowId[row.id] ?? [];
}

function singleSideCount(row: OpportunityBoardRow, events: SettlementEventPreview[]): number {
  return resolveSingleSideEventCount(row, events);
}

function nextSettlementText(row: OpportunityBoardRow, events: SettlementEventPreview[]): string {
  return formatTime(resolveNextSettlementTime(row, events));
}

function eventTitle(event: SettlementEventPreview): string {
  if (event.kind === 'single_side') {
    return `${sideText(event.side)}单边`;
  }
  if (event.kind === 'hedged') {
    return '同结算';
  }
  return '结算事件';
}
</script>

<template>
  <section class="mobile-list">
    <p v-if="loading && rows.length === 0" class="state">数据加载中...</p>
    <p v-else-if="rows.length === 0" class="state">暂无满足条件的数据</p>

    <article v-for="row in pageRows" :key="row.id" class="card">
      <header>
        <button type="button" class="symbol" @click="emit('openDetail', row)">{{ row.symbol }}</button>
        <p>多 {{ row.longExchange }} / 空 {{ row.shortExchange }}</p>
      </header>

      <section class="metric-panel">
        <div class="line">
          <span>统一指标(含杠杆)</span>
          <strong :class="colorClass(row.nextCycleScore)">{{ formatPercent(row.nextCycleScore, 2) }}</strong>
        </div>
        <div class="line">
          <span>未杠杆参考</span>
          <strong :class="colorClass(row.nextCycleScoreUnleveraged)">{{ formatPercent(row.nextCycleScoreUnleveraged, 2) }}</strong>
        </div>
        <div class="line">
          <span>可用杠杆</span>
          <strong>{{ formatLeverage(row.maxUsableLeverage) }}</strong>
        </div>
      </section>

      <section class="settlement-panel">
        <p>
          多 {{ row.longLeg.exchange }}: {{ formatPercent(row.longLeg.fundingRateRaw, 4) }} · {{ row.longLeg.settlementInterval }} ·
          {{ formatTime(row.longLeg.nextFundingTime) }}
        </p>
        <p>
          空 {{ row.shortLeg.exchange }}: {{ formatPercent(row.shortLeg.fundingRateRaw, 4) }} · {{ row.shortLeg.settlementInterval }} ·
          {{ formatTime(row.shortLeg.nextFundingTime) }}
        </p>
        <p class="hint">下一次同结算: {{ nextSettlementText(row, rowEvents(row)) }}</p>
        <p class="hint">单边结算次数: {{ singleSideCount(row, rowEvents(row)) }}</p>

        <details v-if="singleSideCount(row, rowEvents(row)) > 0" class="event-details">
          <summary>展开逐次事件摘要</summary>
          <ul>
            <li v-for="event in rowEvents(row)" :key="event.id">
              <span>{{ formatTime(event.eventTime) }} {{ eventTitle(event) }}</span>
              <strong :class="colorClass(event.amountRate)">{{ formatPercent(event.amountRate, 4) }}</strong>
            </li>
          </ul>
        </details>
      </section>

      <section class="sim-panel">
        <label>
          <span>保证金模拟（到下一次同结算）</span>
          <input
            type="number"
            min="0"
            step="10"
            placeholder="输入保证金 USDT"
            :value="marginInputs[row.id] ?? ''"
            @input="onMarginInput(row.id, $event)"
          />
        </label>
        <div v-if="simulations[row.id]" class="sim-result">
          <strong :class="colorClass(simulations[row.id]!.expectedPnlUsd)">≈ {{ formatMoney(simulations[row.id]!.expectedPnlUsd) }}</strong>
          <p>名义仓位 {{ formatMoney(simulations[row.id]!.notionalUsd) }} ({{ formatLeverage(simulations[row.id]!.leverage) }})</p>
          <p>单边结算 {{ simulations[row.id]!.singleSideEventCount }} 次</p>

          <details class="event-details">
            <summary>展开逐次金额明细</summary>
            <ul>
              <li v-for="event in simulations[row.id]!.events" :key="event.id">
                <span>{{ formatTime(event.eventTime) }} {{ event.summary }}</span>
                <strong :class="colorClass(event.pnlUsd)">{{ formatMoney(event.pnlUsd) }} ({{ formatPercent(event.amountRate, 4) }})</strong>
              </li>
            </ul>
          </details>
        </div>
        <p v-else>输入保证金后按结算事件窗口模拟</p>
      </section>

      <div class="actions">
        <button type="button" class="ghost" @click="emit('openPair', row)">打开双交易所</button>
        <button type="button" class="accent" @click="emit('openTrade', row)">去交易</button>
      </div>
    </article>

    <div v-if="rows.length > 0" class="pager">
      <button type="button" class="ghost" :disabled="page <= 1" @click="prevPage">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button type="button" class="ghost" :disabled="page >= totalPages" @click="nextPage">下一页</button>
    </div>
  </section>
</template>

<style scoped>
.mobile-list {
  display: grid;
  gap: 10px;
}

.state {
  margin: 0;
  border: 1px solid var(--line-soft);
  background: var(--panel-bg);
  color: var(--text-dim);
  font-size: 12px;
  padding: 12px;
}

.card {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: grid;
  gap: 10px;
}

header {
  display: grid;
  gap: 4px;
}

header p {
  margin: 0;
  color: var(--text-dim);
  font-size: 12px;
}

.symbol {
  border: none;
  background: transparent;
  color: var(--accent-soft);
  font-size: 16px;
  font-weight: 700;
  text-align: left;
  padding: 0;
}

.metric-panel,
.settlement-panel,
.sim-panel {
  border: 1px solid var(--line-soft);
  background: #0d141f;
  padding: 8px;
  display: grid;
  gap: 6px;
}

.line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.line span {
  color: var(--text-dim);
  font-size: 11px;
}

.settlement-panel p,
.sim-panel p {
  margin: 0;
  font-size: 11px;
  color: var(--text-dim);
}

.sim-panel label {
  display: grid;
  gap: 4px;
}

.sim-panel span {
  color: var(--text-dim);
  font-size: 11px;
}

.sim-panel input {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  border-radius: 4px;
  height: 32px;
  padding: 0 8px;
  outline: none;
}

.sim-panel input:focus {
  border-color: var(--accent);
}

.sim-result {
  display: grid;
  gap: 4px;
}

.event-details summary {
  cursor: pointer;
  color: var(--accent-soft);
  font-size: 11px;
}

.event-details ul {
  margin: 6px 0 0;
  padding-left: 14px;
  display: grid;
  gap: 4px;
}

.event-details li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.ghost,
.accent {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  border-radius: 4px;
  height: 32px;
  font-size: 12px;
}

.accent {
  border-color: rgba(0, 199, 166, 0.9);
  background: rgba(0, 199, 166, 0.88);
  color: #052019;
}

.pager {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  color: var(--text-dim);
  font-size: 12px;
}

.ghost:disabled {
  opacity: 0.65;
}

.hint {
  color: var(--text-dim);
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}
</style>
