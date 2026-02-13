<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query';
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchBoard } from '../api/market';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';
import { buildPairTradeTargets } from '../utils/exchangeLinks';
import { openPairTargetsInNewTabs } from '../utils/popupOpen';

const route = useRoute();
const router = useRouter();

function readParam(name: string): string {
  const value = route.params[name];
  if (typeof value === 'string') {
    return decodeURIComponent(value).trim();
  }
  return '';
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
        <p>{{ longExchange || '-' }} → {{ shortExchange || '-' }}</p>
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
        <h3>系统指标</h3>
        <div class="line"><span>价差 1h</span><strong>{{ formatPercent(row.spreadRate1h, 4) }}</strong></div>
        <div class="line"><span>价差 8h</span><strong>{{ formatPercent(row.spreadRate8h, 4) }}</strong></div>
        <div class="line"><span>价差年化</span><strong>{{ formatPercent(row.spreadRate1yNominal, 2) }}</strong></div>
        <div class="line"><span>杠杆后年化</span><strong>{{ formatPercent(row.leveragedSpreadRate1yNominal, 2) }}</strong></div>
        <div class="line"><span>可用杠杆</span><strong>{{ formatLeverage(row.maxUsableLeverage) }}</strong></div>
      </article>

      <article class="panel">
        <h3>多腿 {{ row.longLeg.exchange }}</h3>
        <div class="line"><span>资金费率(8h)</span><strong>{{ formatPercent(row.longLeg.fundingRate8h, 4) }}</strong></div>
        <div class="line"><span>资金费率(年化)</span><strong>{{ formatPercent(row.longLeg.fundingRate1y, 2) }}</strong></div>
        <div class="line"><span>最大杠杆</span><strong>{{ formatLeverage(row.longLeg.maxLeverage) }}</strong></div>
        <div class="line"><span>未平仓(USD)</span><strong>{{ formatMoney(row.longLeg.openInterestUsd) }}</strong></div>
        <div class="line"><span>24h成交额</span><strong>{{ formatMoney(row.longLeg.volume24hUsd) }}</strong></div>
        <div class="line"><span>下次结算</span><strong>{{ formatTime(row.longLeg.nextFundingTime) }}</strong></div>
      </article>

      <article class="panel">
        <h3>空腿 {{ row.shortLeg.exchange }}</h3>
        <div class="line"><span>资金费率(8h)</span><strong>{{ formatPercent(row.shortLeg.fundingRate8h, 4) }}</strong></div>
        <div class="line"><span>资金费率(年化)</span><strong>{{ formatPercent(row.shortLeg.fundingRate1y, 2) }}</strong></div>
        <div class="line"><span>最大杠杆</span><strong>{{ formatLeverage(row.shortLeg.maxLeverage) }}</strong></div>
        <div class="line"><span>未平仓(USD)</span><strong>{{ formatMoney(row.shortLeg.openInterestUsd) }}</strong></div>
        <div class="line"><span>24h成交额</span><strong>{{ formatMoney(row.shortLeg.volume24hUsd) }}</strong></div>
        <div class="line"><span>下次结算</span><strong>{{ formatTime(row.shortLeg.nextFundingTime) }}</strong></div>
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

@media (max-width: 1024px) {
  .detail-head {
    flex-direction: column;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
