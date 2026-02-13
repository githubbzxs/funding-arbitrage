<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query';
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchBoard } from '../api/market';
import type { SettlementEventPreview } from '../types/market';
import { buildPairTradeTargets } from '../utils/exchangeLinks';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';
import { calcMarginSimulation, parseMarginUsd, resolveNextSettlementTime, resolveSettlementEvents, resolveSingleSideEventCount } from '../utils/marginSim';
import { openPairTargetsInNewTabs } from '../utils/popupOpen';

const route = useRoute();
const router = useRouter();
const marginInput = ref('');

function readParam(name: string): string {
  const value = route.params[name];
  if (typeof value === 'string') {
    return decodeURIComponent(value).trim();
  }
  return '';
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

function eventTitle(event: SettlementEventPreview): string {
  if (event.kind === 'single_side') {
    return `${sideText(event.side)}单边`;
  }
  if (event.kind === 'hedged') {
    return '同结算';
  }
  return '结算事件';
}

const symbol = computed(() => readParam('symbol').toUpperCase());
const longExchange = computed(() => readParam('long').toLowerCase());
const shortExchange = computed(() => readParam('short').toLowerCase());
const notice = computed(() => route.query.notice);

const detailQuery = useQuery(
  computed(() => ({
    queryKey: ['market-board-detail', symbol.value, longExchange.value, shortExchange.value] as const,
    queryFn: () =>
      fetchBoard({
        symbol: symbol.value,
        exchanges: [longExchange.value, shortExchange.value],
        limit: 500
      }),
    staleTime: 20_000,
    gcTime: 5 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false
  }))
);

const row = computed(() =>
  (detailQuery.data.value?.rows ?? []).find(
    (item) =>
      item.symbol.toUpperCase() === symbol.value &&
      item.longExchange.toLowerCase() === longExchange.value &&
      item.shortExchange.toLowerCase() === shortExchange.value
  )
);

const settlementEvents = computed(() => (row.value ? resolveSettlementEvents(row.value) : []));
const singleSideEventCount = computed(() => (row.value ? resolveSingleSideEventCount(row.value, settlementEvents.value) : 0));
const nextSettlementTime = computed(() => (row.value ? resolveNextSettlementTime(row.value, settlementEvents.value) : ''));
const simulation = computed(() => {
  if (!row.value) {
    return null;
  }
  const marginUsd = parseMarginUsd(marginInput.value);
  if (marginUsd === null) {
    return null;
  }
  return calcMarginSimulation(row.value, marginUsd);
});

const errorMessage = computed(() => {
  const error = detailQuery.error.value;
  if (error instanceof Error) {
    return error.message;
  }
  return '';
});

function openPairPages(): void {
  if (!row.value) {
    return;
  }
  const result = buildPairTradeTargets(row.value.longExchange, row.value.shortExchange, row.value.symbol);
  if (result.targets.length === 0) {
    return;
  }
  openPairTargetsInNewTabs(result.targets);
}

function openTradePage(): void {
  if (!row.value) {
    return;
  }
  void router.push({
    path: '/trade',
    query: {
      action: 'open',
      symbol: row.value.symbol,
      long: row.value.longExchange,
      short: row.value.shortExchange
    }
  });
}
</script>

<template>
  <section class="detail-page">
    <header class="detail-head">
      <div>
        <h2>{{ symbol || '-' }} 机会详情</h2>
        <p>多 {{ longExchange || '-' }} / 空 {{ shortExchange || '-' }}</p>
      </div>
      <div class="actions">
        <button type="button" class="ghost" @click="router.push('/scanner')">返回扫描页</button>
        <button type="button" class="ghost" @click="openPairPages">打开双交易所</button>
        <button type="button" class="accent" @click="openTradePage">去交易</button>
      </div>
    </header>

    <p v-if="typeof notice === 'string' && notice" class="notice">{{ notice }}</p>
    <p v-if="detailQuery.isPending.value" class="notice">加载详情中...</p>
    <p v-if="errorMessage" class="notice warn">{{ errorMessage }}</p>
    <p v-else-if="!row" class="notice warn">未找到该机会，可能已经失效或筛选条件变化。</p>

    <section v-else class="grid">
      <article class="panel">
        <h3>统一指标</h3>
        <div class="line"><span>nextCycleScore(含杠杆)</span><strong :class="colorClass(row.nextCycleScore)">{{ formatPercent(row.nextCycleScore, 2) }}</strong></div>
        <div class="line"><span>未杠杆参考</span><strong :class="colorClass(row.nextCycleScoreUnleveraged)">{{ formatPercent(row.nextCycleScoreUnleveraged, 2) }}</strong></div>
        <div class="line"><span>可用杠杆</span><strong>{{ formatLeverage(row.maxUsableLeverage) }}</strong></div>
      </article>

      <article class="panel">
        <h3>结算窗口（到下一次同结算）</h3>
        <div class="line"><span>下一次同结算</span><strong>{{ formatTime(nextSettlementTime) }}</strong></div>
        <div class="line"><span>单边结算次数</span><strong>{{ singleSideEventCount }}</strong></div>
        <details class="event-details">
          <summary>展开逐次事件列表</summary>
          <ul>
            <li v-for="event in settlementEvents" :key="event.id">
              <span>{{ formatTime(event.eventTime) }} {{ eventTitle(event) }}</span>
              <strong :class="colorClass(event.amountRate)">{{ formatPercent(event.amountRate, 4) }}</strong>
            </li>
          </ul>
        </details>
      </article>

      <article class="panel">
        <h3>腿部信息</h3>
        <div class="leg-card">
          <h4>多腿 {{ row.longLeg.exchange }}</h4>
          <div class="line"><span>资金费率(原始)</span><strong :class="colorClass(row.longLeg.fundingRateRaw)">{{ formatPercent(row.longLeg.fundingRateRaw, 4) }}</strong></div>
          <div class="line"><span>结算间隔</span><strong>{{ row.longLeg.settlementInterval }}</strong></div>
          <div class="line"><span>下次结算</span><strong>{{ formatTime(row.longLeg.nextFundingTime) }}</strong></div>
          <div class="line"><span>最大杠杆</span><strong>{{ formatLeverage(row.longLeg.maxLeverage) }}</strong></div>
          <div class="line"><span>未平仓(USD)</span><strong>{{ formatMoney(row.longLeg.openInterestUsd) }}</strong></div>
          <div class="line"><span>24h成交额</span><strong>{{ formatMoney(row.longLeg.volume24hUsd) }}</strong></div>
        </div>

        <div class="leg-card">
          <h4>空腿 {{ row.shortLeg.exchange }}</h4>
          <div class="line"><span>资金费率(原始)</span><strong :class="colorClass(row.shortLeg.fundingRateRaw)">{{ formatPercent(row.shortLeg.fundingRateRaw, 4) }}</strong></div>
          <div class="line"><span>结算间隔</span><strong>{{ row.shortLeg.settlementInterval }}</strong></div>
          <div class="line"><span>下次结算</span><strong>{{ formatTime(row.shortLeg.nextFundingTime) }}</strong></div>
          <div class="line"><span>最大杠杆</span><strong>{{ formatLeverage(row.shortLeg.maxLeverage) }}</strong></div>
          <div class="line"><span>未平仓(USD)</span><strong>{{ formatMoney(row.shortLeg.openInterestUsd) }}</strong></div>
          <div class="line"><span>24h成交额</span><strong>{{ formatMoney(row.shortLeg.volume24hUsd) }}</strong></div>
        </div>
      </article>

      <article class="panel">
        <h3>保证金模拟（同一事件列表）</h3>
        <label class="field">
          <span>保证金(USDT)</span>
          <input v-model="marginInput" type="number" min="0" step="10" placeholder="输入保证金" />
        </label>

        <div v-if="simulation" class="sim-result">
          <div class="line">
            <span>预计总收益</span>
            <strong :class="colorClass(simulation.expectedPnlUsd)">≈ {{ formatMoney(simulation.expectedPnlUsd) }}</strong>
          </div>
          <div class="line"><span>名义仓位</span><strong>{{ formatMoney(simulation.notionalUsd) }} ({{ formatLeverage(simulation.leverage) }})</strong></div>
          <div class="line"><span>单边结算次数</span><strong>{{ simulation.singleSideEventCount }}</strong></div>

          <details class="event-details">
            <summary>展开逐次金额明细</summary>
            <ul>
              <li v-for="event in simulation.events" :key="event.id">
                <span>{{ formatTime(event.eventTime) }} {{ event.summary }}</span>
                <strong :class="colorClass(event.pnlUsd)">{{ formatMoney(event.pnlUsd) }} ({{ formatPercent(event.amountRate, 4) }})</strong>
              </li>
            </ul>
          </details>
        </div>
        <p v-else class="hint">输入保证金后，按“到下一次同结算”的事件窗口计算。</p>
      </article>
    </section>
  </section>
</template>

<style scoped>
.detail-page {
  display: grid;
  gap: 10px;
}

.detail-head {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.detail-head h2 {
  margin: 0;
  font-size: 18px;
}

.detail-head p {
  margin: 4px 0 0;
  color: var(--text-dim);
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ghost,
.accent {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  border-radius: 4px;
  height: 34px;
  padding: 0 12px;
}

.accent {
  border-color: rgba(0, 199, 166, 0.9);
  background: rgba(0, 199, 166, 0.88);
  color: #052019;
}

.notice {
  margin: 0;
  border: 1px solid var(--line-soft);
  background: #0d141e;
  color: var(--text-dim);
  font-size: 12px;
  padding: 10px;
}

.notice.warn {
  border-color: rgba(255, 120, 120, 0.5);
  color: #ffb8b8;
  background: rgba(255, 120, 120, 0.1);
}

.grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: grid;
  gap: 8px;
}

.panel h3 {
  margin: 0;
  font-size: 14px;
}

.line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
}

.line span {
  color: var(--text-dim);
}

.event-details summary {
  cursor: pointer;
  color: var(--accent-soft);
  font-size: 12px;
}

.event-details ul {
  margin: 8px 0 0;
  padding-left: 14px;
  display: grid;
  gap: 4px;
}

.event-details li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.leg-card {
  border: 1px solid var(--line-soft);
  background: #0d141f;
  padding: 10px;
  display: grid;
  gap: 6px;
}

.leg-card h4 {
  margin: 0;
  font-size: 13px;
}

.field {
  display: grid;
  gap: 6px;
}

.field span {
  font-size: 12px;
  color: var(--text-dim);
}

.field input {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  border-radius: 4px;
  height: 34px;
  padding: 0 10px;
  outline: none;
}

.field input:focus {
  border-color: var(--accent);
}

.sim-result {
  display: grid;
  gap: 6px;
}

.hint {
  margin: 0;
  color: var(--text-dim);
  font-size: 12px;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}

@media (max-width: 1024px) {
  .detail-head {
    flex-direction: column;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
