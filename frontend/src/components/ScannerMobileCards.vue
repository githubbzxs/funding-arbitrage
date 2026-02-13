<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { OpportunityBoardRow } from '../types/market';
import { formatLeverage, formatPercent } from '../utils/format';

const props = defineProps<{
  rows: OpportunityBoardRow[];
  loading: boolean;
}>();

const emit = defineEmits<{
  openDetail: [OpportunityBoardRow];
  openPair: [OpportunityBoardRow];
  openTrade: [OpportunityBoardRow];
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
</script>

<template>
  <section class="mobile-list">
    <p v-if="loading && rows.length === 0" class="state">数据加载中...</p>
    <p v-else-if="rows.length === 0" class="state">暂无满足条件的数据</p>

    <article v-for="row in pageRows" :key="row.id" class="card">
      <header>
        <button type="button" class="symbol" @click="emit('openDetail', row)">{{ row.symbol }}</button>
        <p>{{ row.longExchange }} → {{ row.shortExchange }}</p>
      </header>

      <div class="metrics">
        <div>
          <span>多腿8h</span>
          <strong :class="colorClass(row.longLeg.fundingRate8h)">{{ formatPercent(row.longLeg.fundingRate8h, 4) }}</strong>
        </div>
        <div>
          <span>空腿8h</span>
          <strong :class="colorClass(row.shortLeg.fundingRate8h)">{{ formatPercent(row.shortLeg.fundingRate8h, 4) }}</strong>
        </div>
        <div>
          <span>价差年化</span>
          <strong :class="colorClass(row.spreadRate1yNominal)">{{ formatPercent(row.spreadRate1yNominal, 2) }}</strong>
        </div>
        <div>
          <span>杠杆后年化</span>
          <strong :class="colorClass(row.leveragedSpreadRate1yNominal)">
            {{ formatPercent(row.leveragedSpreadRate1yNominal, 2) }}
          </strong>
        </div>
        <div>
          <span>可用杠杆</span>
          <strong>{{ formatLeverage(row.maxUsableLeverage) }}</strong>
        </div>
      </div>

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

.metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.metrics div {
  border: 1px solid var(--line-soft);
  background: #0d141f;
  padding: 8px;
  display: grid;
  gap: 4px;
}

.metrics span {
  color: var(--text-dim);
  font-size: 11px;
}

.metrics strong {
  font-size: 13px;
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

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}
</style>
