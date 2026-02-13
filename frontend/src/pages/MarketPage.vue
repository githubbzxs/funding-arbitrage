<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { fetchOpportunities, fetchSnapshots } from '../api/market';
import BottomToolbar from '../components/BottomToolbar.vue';
import MarketTable from '../components/MarketTable.vue';
import TopFilters from '../components/TopFilters.vue';
import type {
  FilterState,
  MarketFetchError,
  MarketMeta,
  MarketRow,
  OpportunityLegInfo,
  OpportunityPairRow
} from '../types/market';

const EXCHANGE_OPTIONS = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;

const router = useRouter();
const marketLoading = ref(false);
const marketError = ref('');
const lastUpdated = ref('');
const snapshots = ref<MarketRow[]>([]);
const opportunities = ref<MarketRow[]>([]);
const snapshotErrors = ref<MarketFetchError[]>([]);
const marketMeta = ref<MarketMeta | null>(null);

const filters = reactive<FilterState>({
  exchanges: []
});

const autoRefresh = ref(true);
const refreshSeconds = ref(10);
let timerId: number | undefined;

function rowScore(row: OpportunityPairRow): number {
  const leveraged = row.leveragedSpreadRate1yNominal;
  if (typeof leveraged === 'number' && Number.isFinite(leveraged)) {
    return leveraged;
  }
  if (Number.isFinite(row.spreadRate1yNominal)) {
    return row.spreadRate1yNominal;
  }
  return Number.NEGATIVE_INFINITY;
}

function buildSnapshotKey(exchange: string, symbol: string): string {
  return `${exchange.toLowerCase()}::${symbol.toLowerCase()}`;
}

function normalizeExchange(value: string): string {
  return value.trim().toLowerCase();
}

function annualizedFrom8h(rate8h: number | null): number | null {
  if (typeof rate8h !== 'number' || !Number.isFinite(rate8h)) {
    return null;
  }
  return rate8h * 3 * 365;
}

function resolveSpread1h(spreadRate8h: number | null): number | null {
  if (typeof spreadRate8h !== 'number' || !Number.isFinite(spreadRate8h)) {
    return null;
  }
  return spreadRate8h / 8;
}

function buildEmptyLeg(exchange: string): OpportunityLegInfo {
  return {
    exchange,
    openInterestUsd: null,
    volume24hUsd: null,
    fundingRateRaw: null,
    fundingRate1h: null,
    fundingRate8h: null,
    fundingRate1y: null,
    nextFundingTime: '',
    settlementInterval: '-',
    maxLeverage: null,
    leveragedNominalApr: null
  };
}

function buildLegInfo(
  exchange: string,
  symbol: string,
  fallback: {
    fundingRateRaw: number | null;
    fundingRate8h: number | null;
    nextFundingTime: string;
    maxLeverage: number | null;
  },
  snapshotMap: Map<string, MarketRow>
): OpportunityLegInfo {
  const snapshot = snapshotMap.get(buildSnapshotKey(exchange, symbol));
  if (snapshot) {
    return {
      exchange,
      openInterestUsd: Number.isFinite(snapshot.openInterestUsd) ? snapshot.openInterestUsd : null,
      volume24hUsd: Number.isFinite(snapshot.volume24hUsd) ? snapshot.volume24hUsd : null,
      fundingRateRaw: snapshot.nextFundingRate,
      fundingRate1h: snapshot.fundingRate1h,
      fundingRate8h: snapshot.fundingRate8h,
      fundingRate1y: snapshot.fundingRate1y,
      nextFundingTime: snapshot.nextFundingTime,
      settlementInterval: snapshot.settlementInterval || '-',
      maxLeverage: snapshot.maxLeverage,
      leveragedNominalApr: snapshot.leveragedNominalApr
    };
  }

  const fundingRate1h = resolveSpread1h(fallback.fundingRate8h);
  const fundingRate1y = annualizedFrom8h(fallback.fundingRate8h);
  const leveragedNominalApr =
    fundingRate1y !== null && fallback.maxLeverage !== null ? fundingRate1y * fallback.maxLeverage : null;

  return {
    ...buildEmptyLeg(exchange),
    fundingRateRaw: fallback.fundingRateRaw,
    fundingRate1h,
    fundingRate8h: fallback.fundingRate8h,
    fundingRate1y,
    nextFundingTime: fallback.nextFundingTime,
    maxLeverage: fallback.maxLeverage,
    leveragedNominalApr
  };
}

const exchangeOptions = computed<string[]>(() => [...EXCHANGE_OPTIONS]);

const snapshotIndex = computed(() => {
  const index = new Map<string, MarketRow>();
  snapshots.value.forEach((row) => {
    index.set(buildSnapshotKey(row.exchange, row.symbol), row);
  });
  return index;
});

const opportunityPairs = computed<OpportunityPairRow[]>(() => {
  return opportunities.value
    .filter((row) => row.source === 'opportunity')
    .map((row) => {
      const defaultLong = row.exchange.split('/')[0] ?? '';
      const defaultShort = row.exchange.split('/')[1] ?? '';
      const longExchange = normalizeExchange(row.longExchange || defaultLong);
      const shortExchange = normalizeExchange(row.shortExchange || defaultShort);

      const longLeg = buildLegInfo(
        longExchange,
        row.symbol,
        {
          fundingRateRaw: row.longFundingRateRaw ?? null,
          fundingRate8h: row.longRate8h ?? null,
          nextFundingTime: row.longNextFundingTime || row.nextFundingTime,
          maxLeverage: row.longMaxLeverage ?? row.maxUsableLeverage ?? null
        },
        snapshotIndex.value
      );

      const shortLeg = buildLegInfo(
        shortExchange,
        row.symbol,
        {
          fundingRateRaw: row.shortFundingRateRaw ?? null,
          fundingRate8h: row.shortRate8h ?? null,
          nextFundingTime: row.shortNextFundingTime || row.nextFundingTime,
          maxLeverage: row.shortMaxLeverage ?? row.maxUsableLeverage ?? null
        },
        snapshotIndex.value
      );

      const spreadRate8h =
        typeof longLeg.fundingRate8h === 'number' && typeof shortLeg.fundingRate8h === 'number'
          ? shortLeg.fundingRate8h - longLeg.fundingRate8h
          : row.spreadRate8h ?? row.fundingRate8h;

      const spreadRate1h =
        typeof longLeg.fundingRate1h === 'number' && typeof shortLeg.fundingRate1h === 'number'
          ? shortLeg.fundingRate1h - longLeg.fundingRate1h
          : row.spreadRate1h ?? row.fundingRate1h;

      const spreadRate1yNominal = row.spreadRate1yNominal ?? row.nominalApr ?? row.fundingRate1y ?? 0;

      const maxUsableLeverage =
        row.maxUsableLeverage ??
        (typeof longLeg.maxLeverage === 'number' && typeof shortLeg.maxLeverage === 'number'
          ? Math.min(longLeg.maxLeverage, shortLeg.maxLeverage)
          : null);

      const leveragedSpreadRate1yNominal =
        row.leveragedNominalApr ??
        (typeof maxUsableLeverage === 'number' ? spreadRate1yNominal * maxUsableLeverage : null);

      return {
        id: row.id,
        symbol: row.symbol,
        longExchange,
        shortExchange,
        longLeg,
        shortLeg,
        spreadRate1h,
        spreadRate8h,
        spreadRate1yNominal,
        leveragedSpreadRate1yNominal,
        rawOpportunity: row
      };
    })
    .sort((a, b) => {
      const left = rowScore(a);
      const right = rowScore(b);
      if (left === right) {
        return 0;
      }
      return right > left ? 1 : -1;
    });
});

const filteredRows = computed<OpportunityPairRow[]>(() =>
  opportunityPairs.value.filter((row) => {
    if (filters.exchanges.length > 0) {
      const selected = new Set(filters.exchanges.map((item) => item.toLowerCase()));
      if (!selected.has(row.longExchange.toLowerCase()) && !selected.has(row.shortExchange.toLowerCase())) {
        return false;
      }
    }
    return true;
  })
);

const statusLine = computed(() => {
  const parts: string[] = [];
  if (marketMeta.value?.fetchMs !== null && typeof marketMeta.value?.fetchMs === 'number') {
    parts.push(`抓取耗时 ${marketMeta.value.fetchMs}ms`);
  }
  if (marketMeta.value?.cacheHit) {
    parts.push('命中缓存');
  }
  if (marketMeta.value?.exchangesFailed?.length) {
    parts.push(`失败: ${marketMeta.value.exchangesFailed.join(',')}`);
  }
  return parts.join(' | ');
});

function clearTimer(): void {
  if (timerId !== undefined) {
    window.clearInterval(timerId);
    timerId = undefined;
  }
}

function setupTimer(): void {
  clearTimer();
  if (!autoRefresh.value) {
    return;
  }
  timerId = window.setInterval(() => {
    void refreshMarketData();
  }, refreshSeconds.value * 1000);
}

async function refreshMarketData(): Promise<void> {
  marketLoading.value = true;
  marketError.value = '';
  try {
    const [snapshotResult, opportunityRows] = await Promise.all([fetchSnapshots(), fetchOpportunities()]);
    snapshots.value = snapshotResult.rows;
    opportunities.value = opportunityRows;
    snapshotErrors.value = snapshotResult.errors;
    marketMeta.value = snapshotResult.meta;
    lastUpdated.value = new Date().toLocaleString('zh-CN');
  } catch (error) {
    marketError.value = error instanceof Error ? error.message : '拉取市场数据失败';
  } finally {
    marketLoading.value = false;
  }
}

function onFilterChange(nextFilters: FilterState): void {
  filters.exchanges = nextFilters.exchanges;
}

function openPairPages(row: OpportunityPairRow): void {
  void router.push({
    path: '/trade/redirect',
    query: {
      symbol: row.symbol,
      long: row.longExchange,
      short: row.shortExchange
    }
  });
}

function openTrade(row: OpportunityPairRow): void {
  void router.push({
    path: '/trade',
    query: {
      action: 'open',
      symbol: row.symbol,
      long: row.longExchange,
      short: row.shortExchange
    }
  });
}

watch([autoRefresh, refreshSeconds], setupTimer);

onMounted(async () => {
  await refreshMarketData();
  setupTimer();
});

onBeforeUnmount(() => {
  clearTimer();
});
</script>

<template>
  <div class="page-grid">
    <TopFilters
      :model-value="filters"
      :exchange-options="exchangeOptions"
      :updated-at="lastUpdated"
      :status-line="statusLine"
      @update:model-value="onFilterChange"
      @refresh="refreshMarketData"
    />

    <p v-if="marketError" class="error-tip">{{ marketError }}</p>
    <p v-else-if="snapshotErrors.length > 0" class="warn-tip">
      部分交易所抓取失败：{{
        snapshotErrors.map((item) => `${item.exchange}: ${item.message}`).join(' | ')
      }}
    </p>

    <MarketTable :rows="filteredRows" :loading="marketLoading" @trade="openTrade" @visit-symbol="openPairPages" />

    <BottomToolbar
      :auto-refresh="autoRefresh"
      :refresh-seconds="refreshSeconds"
      @update:auto-refresh="autoRefresh = $event"
      @update:refresh-seconds="refreshSeconds = $event"
      @refresh="refreshMarketData"
    />
  </div>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 10px;
  padding-bottom: 56px;
}

.warn-tip {
  margin: 0;
  border: 1px solid rgba(255, 190, 102, 0.4);
  background: rgba(255, 190, 102, 0.08);
  color: #ffd9a1;
  padding: 8px 10px;
  font-size: 12px;
}
</style>
