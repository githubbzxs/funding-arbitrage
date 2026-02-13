<script setup lang="ts">
import { useVirtualizer } from '@tanstack/vue-virtual';
import { computed, ref } from 'vue';
import type { MarginSimulation, OpportunityBoardRow } from '../types/market';
import { formatLeverage, formatMoney, formatPercent } from '../utils/format';

const props = defineProps<{
  rows: OpportunityBoardRow[];
  loading: boolean;
  marginInputs: Record<string, string>;
  simulations: Record<string, MarginSimulation | null>;
}>();

const emit = defineEmits<{
  openDetail: [OpportunityBoardRow];
  openPair: [OpportunityBoardRow];
  openTrade: [OpportunityBoardRow];
  updateMargin: [{ rowId: string; value: string }];
}>();

const ROW_HEIGHT = 108;

const containerRef = ref<HTMLElement | null>(null);

const rowVirtualizer = useVirtualizer(
  computed(() => ({
    count: props.rows.length,
    getScrollElement: () => containerRef.value,
    estimateSize: () => ROW_HEIGHT,
    overscan: 8,
  }))
);

const virtualItems = computed(() => rowVirtualizer.value.getVirtualItems());

function colorClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}

function shorterSideText(side: 'long' | 'short' | null): string {
  if (side === 'long') {
    return '多腿';
  }
  if (side === 'short') {
    return '空腿';
  }
  return '-';
}

function onMarginInput(rowId: string, event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('updateMargin', { rowId, value: target.value });
}
</script>

<template>
  <section class="table-shell">
    <header class="table-head">
      <span>币对</span>
      <span>套利方向</span>
      <span>资金费率(原始)</span>
      <span>结算间隔</span>
      <span>价差(1h/8h/年化)</span>
      <span>杠杆后年化</span>
      <span>保证金模拟(24h)</span>
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

            <div>{{ rows[virtualRow.index].longExchange }} -> {{ rows[virtualRow.index].shortExchange }}</div>

            <div class="funding-cell">
              <span :class="colorClass(rows[virtualRow.index].longLeg.fundingRateRaw)">
                L {{ formatPercent(rows[virtualRow.index].longLeg.fundingRateRaw, 4) }}
              </span>
              <span :class="colorClass(rows[virtualRow.index].shortLeg.fundingRateRaw)">
                S {{ formatPercent(rows[virtualRow.index].shortLeg.fundingRateRaw, 4) }}
              </span>
            </div>

            <div class="interval-cell">
              <span>L {{ rows[virtualRow.index].longLeg.settlementInterval }}</span>
              <span>S {{ rows[virtualRow.index].shortLeg.settlementInterval }}</span>
              <span v-if="rows[virtualRow.index].intervalMismatch" class="hint warn">
                间隔不一致，短间隔: {{ shorterSideText(rows[virtualRow.index].shorterIntervalSide) }}
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
              <div>{{ formatPercent(rows[virtualRow.index].leveragedSpreadRate1yNominal, 2) }}</div>
              <div class="leverage">杠杆 {{ formatLeverage(rows[virtualRow.index].maxUsableLeverage) }}</div>
            </div>

            <div class="sim-cell">
              <label class="sim-input-wrap">
                <span>保证金(USDT)</span>
                <input
                  type="number"
                  min="0"
                  step="10"
                  placeholder="输入保证金"
                  :value="marginInputs[rows[virtualRow.index].id] ?? ''"
                  @input="onMarginInput(rows[virtualRow.index].id, $event)"
                />
              </label>
              <div v-if="simulations[rows[virtualRow.index].id]" class="sim-result">
                <span class="strong" :class="colorClass(simulations[rows[virtualRow.index].id]!.expectedPnlUsd)">
                  ≈ {{ formatMoney(simulations[rows[virtualRow.index].id]!.expectedPnlUsd) }}
                </span>
                <span class="hint">
                  名义仓位 {{ formatMoney(simulations[rows[virtualRow.index].id]!.notionalUsd) }} ({{ formatLeverage(simulations[rows[virtualRow.index].id]!.leverage) }})
                </span>
                <span
                  class="hint"
                  :class="simulations[rows[virtualRow.index].id]!.intervalMismatch ? 'warn' : ''"
                >
                  {{
                    simulations[rows[virtualRow.index].id]!.intervalMismatch
                      ? `短间隔单边 ${shorterSideText(simulations[rows[virtualRow.index].id]!.shorterIntervalSide)}: ${formatPercent(
                          simulations[rows[virtualRow.index].id]!.singleSideRate,
                          4
                        )}`
                      : `纯对冲收益: ${formatPercent(simulations[rows[virtualRow.index].id]!.hedgedRate, 4)}`
                  }}
                </span>
              </div>
              <span v-else class="hint">输入保证金后显示 24h 预期收益</span>
            </div>

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
  min-height: 460px;
  display: grid;
  grid-template-rows: auto 1fr;
}

.table-head {
  display: grid;
  grid-template-columns: 110px 150px 180px 180px 270px 140px 260px 200px;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-soft);
  color: var(--text-dim);
  font-size: 12px;
  background: #0e141f;
}

.table-body {
  height: calc(100vh - 340px);
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
  height: 108px;
  padding: 8px 12px;
  display: grid;
  align-items: center;
  grid-template-columns: 110px 150px 180px 180px 270px 140px 260px 200px;
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

.funding-cell {
  display: grid;
  gap: 3px;
}

.interval-cell {
  display: grid;
  gap: 3px;
}

.sim-cell {
  display: grid;
  gap: 4px;
}

.sim-input-wrap {
  display: grid;
  gap: 2px;
}

.sim-input-wrap span {
  font-size: 11px;
  color: var(--text-dim);
}

.sim-input-wrap input {
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  height: 28px;
  background: #101722;
  color: var(--text-main);
  padding: 0 8px;
  outline: none;
}

.sim-input-wrap input:focus {
  border-color: var(--accent);
}

.sim-result {
  display: grid;
  gap: 2px;
}

.hint {
  color: var(--text-dim);
  font-size: 11px;
}

.hint.warn {
  color: #ffb9b9;
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

.leverage {
  color: var(--text-dim);
  font-size: 11px;
  margin-top: 2px;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}
</style>
