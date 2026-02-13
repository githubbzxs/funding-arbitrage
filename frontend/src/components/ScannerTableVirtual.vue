<script setup lang="ts">
import { useVirtualizer } from '@tanstack/vue-virtual';
import { computed, ref } from 'vue';
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

const ROW_HEIGHT = 56;

const containerRef = ref<HTMLElement | null>(null);

const rowVirtualizer = useVirtualizer(
  computed(() => ({
    count: props.rows.length,
    getScrollElement: () => containerRef.value,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10
  }))
);

const virtualItems = computed(() => rowVirtualizer.value.getVirtualItems());

function colorClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}
</script>

<template>
  <section class="table-shell">
    <header class="table-head">
      <span>币对</span>
      <span>套利方向</span>
      <span>资金费率(8h)</span>
      <span>价差(1h/8h/年化)</span>
      <span>杠杆后年化</span>
      <span>可用杠杆</span>
      <span>操作</span>
    </header>

    <div v-if="loading && rows.length === 0" class="state">数据加载中...</div>
    <div v-else-if="rows.length === 0" class="state">暂无满足条件的数据</div>

    <div v-else ref="containerRef" class="table-body">
      <div class="table-inner" :style="{ height: `${rowVirtualizer.getTotalSize()}px` }">
        <article
          v-for="virtualRow in virtualItems"
          :key="String(virtualRow.key)"
          class="table-row"
          :style="{ transform: `translateY(${virtualRow.start}px)` }"
        >
          <template v-if="rows[virtualRow.index]">
            <button type="button" class="symbol-link" @click="emit('openDetail', rows[virtualRow.index])">
              {{ rows[virtualRow.index].symbol }}
            </button>
            <div>{{ rows[virtualRow.index].longExchange }} → {{ rows[virtualRow.index].shortExchange }}</div>
            <div>
              <span :class="colorClass(rows[virtualRow.index].longLeg.fundingRate8h)">
                L {{ formatPercent(rows[virtualRow.index].longLeg.fundingRate8h, 4) }}
              </span>
              /
              <span :class="colorClass(rows[virtualRow.index].shortLeg.fundingRate8h)">
                S {{ formatPercent(rows[virtualRow.index].shortLeg.fundingRate8h, 4) }}
              </span>
            </div>
            <div>
              <span :class="colorClass(rows[virtualRow.index].spreadRate1h)">1h {{ formatPercent(rows[virtualRow.index].spreadRate1h, 4) }}</span>
              <span :class="colorClass(rows[virtualRow.index].spreadRate8h)"> | 8h {{ formatPercent(rows[virtualRow.index].spreadRate8h, 4) }}</span>
              <span class="strong" :class="colorClass(rows[virtualRow.index].spreadRate1yNominal)">
                | 年化 {{ formatPercent(rows[virtualRow.index].spreadRate1yNominal, 2) }}
              </span>
            </div>
            <div class="strong" :class="colorClass(rows[virtualRow.index].leveragedSpreadRate1yNominal)">
              {{ formatPercent(rows[virtualRow.index].leveragedSpreadRate1yNominal, 2) }}
            </div>
            <div>{{ formatLeverage(rows[virtualRow.index].maxUsableLeverage) }}</div>
            <div class="actions">
              <button type="button" class="ghost" @click="emit('openPair', rows[virtualRow.index])">打开双交易所</button>
              <button type="button" class="accent" @click="emit('openTrade', rows[virtualRow.index])">去交易</button>
            </div>
          </template>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.table-shell {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  min-height: 420px;
  display: grid;
  grid-template-rows: auto 1fr;
}

.table-head {
  display: grid;
  grid-template-columns: 120px 180px 220px 320px 140px 100px 220px;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-soft);
  color: var(--text-dim);
  font-size: 12px;
  background: #0e141f;
}

.table-body {
  height: calc(100vh - 320px);
  min-height: 360px;
  overflow: auto;
}

.table-inner {
  position: relative;
  width: 100%;
}

.table-row {
  position: absolute;
  left: 0;
  width: 100%;
  height: 56px;
  padding: 0 12px;
  display: grid;
  align-items: center;
  grid-template-columns: 120px 180px 220px 320px 140px 100px 220px;
  gap: 10px;
  border-bottom: 1px solid var(--line-soft);
  font-size: 12px;
}

.table-row:hover {
  background: rgba(0, 199, 166, 0.05);
}

.symbol-link {
  border: none;
  background: transparent;
  color: var(--accent-soft);
  font-weight: 700;
  text-align: left;
  padding: 0;
}

.symbol-link:hover {
  text-decoration: underline;
}

.actions {
  display: flex;
  gap: 8px;
}

.ghost,
.accent {
  height: 30px;
  padding: 0 10px;
  border-radius: 4px;
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  font-size: 12px;
}

.accent {
  border-color: rgba(0, 199, 166, 0.9);
  background: rgba(0, 199, 166, 0.88);
  color: #052019;
}

.state {
  color: var(--text-dim);
  font-size: 13px;
  padding: 16px;
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
