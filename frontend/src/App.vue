<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { executeAction } from './api/execution';
import { fetchOpportunities, fetchOrders, fetchPositions, fetchSnapshots } from './api/market';
import BottomToolbar from './components/BottomToolbar.vue';
import MarketTable from './components/MarketTable.vue';
import TopFilters from './components/TopFilters.vue';
import TradeDrawer from './components/TradeDrawer.vue';
import type {
  ExecutionAction,
  ExecutionRequest,
  FilterState,
  MarketRow,
  OpportunityLegInfo,
  OpportunityPairRow,
  TradingRecord,
} from './types/market';
import { buildPairTradeUrls } from './utils/exchangeLinks';

const EXCHANGE_OPTIONS = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;

const marketLoading = ref(false);
const tradeLoading = ref(false);
const marketError = ref('');
const lastUpdated = ref('');

const snapshots = ref<MarketRow[]>([]);
const opportunities = ref<MarketRow[]>([]);
const positions = ref<TradingRecord[]>([]);
const orders = ref<TradingRecord[]>([]);

const filters = reactive<FilterState>({
  oiThreshold: 0,
  volumeThreshold: 0,
  exchanges: [],
});

const drawerOpen = ref(false);
const drawerAction = ref<ExecutionAction>('preview');
const selectedMarket = ref<MarketRow | null>(null);
const executionBusy = ref(false);
const executionError = ref('');
const executionResult = ref('');

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
    leveragedNominalApr: null,
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
  snapshotMap: Map<string, MarketRow>,
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
      leveragedNominalApr: snapshot.leveragedNominalApr,
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
    leveragedNominalApr,
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
          maxLeverage: row.longMaxLeverage ?? row.maxUsableLeverage ?? null,
        },
        snapshotIndex.value,
      );

      const shortLeg = buildLegInfo(
        shortExchange,
        row.symbol,
        {
          fundingRateRaw: row.shortFundingRateRaw ?? null,
          fundingRate8h: row.shortRate8h ?? null,
          nextFundingTime: row.shortNextFundingTime || row.nextFundingTime,
          maxLeverage: row.shortMaxLeverage ?? row.maxUsableLeverage ?? null,
        },
        snapshotIndex.value,
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
        rawOpportunity: row,
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
    const longOi = row.longLeg.openInterestUsd ?? 0;
    const shortOi = row.shortLeg.openInterestUsd ?? 0;
    if (longOi < filters.oiThreshold || shortOi < filters.oiThreshold) {
      return false;
    }

    const longVol = row.longLeg.volume24hUsd ?? 0;
    const shortVol = row.shortLeg.volume24hUsd ?? 0;
    if (longVol < filters.volumeThreshold || shortVol < filters.volumeThreshold) {
      return false;
    }

    if (filters.exchanges.length > 0) {
      const selected = new Set(filters.exchanges.map((item) => item.toLowerCase()));
      if (!selected.has(row.longExchange.toLowerCase()) && !selected.has(row.shortExchange.toLowerCase())) {
        return false;
      }
    }

    return true;
  }),
);

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
    const [snapshotRows, opportunityRows] = await Promise.all([fetchSnapshots(), fetchOpportunities()]);
    snapshots.value = snapshotRows;
    opportunities.value = opportunityRows;
    lastUpdated.value = new Date().toLocaleString('zh-CN');
  } catch (error) {
    marketError.value = error instanceof Error ? error.message : '拉取市场数据失败';
  } finally {
    marketLoading.value = false;
  }
}

async function refreshTradeData(): Promise<void> {
  tradeLoading.value = true;
  try {
    const [positionRows, orderRows] = await Promise.all([fetchPositions(), fetchOrders()]);
    positions.value = positionRows;
    orders.value = orderRows;
  } catch {
    positions.value = [];
    orders.value = [];
  } finally {
    tradeLoading.value = false;
  }
}

async function refreshAll(): Promise<void> {
  await Promise.all([refreshMarketData(), refreshTradeData()]);
}

function openDrawer(action: ExecutionAction, row?: MarketRow): void {
  if (row) {
    selectedMarket.value = row;
  }
  drawerAction.value = action;
  executionError.value = '';
  executionResult.value = '';
  drawerOpen.value = true;
}

function closeDrawer(): void {
  drawerOpen.value = false;
}

function onFilterChange(nextFilters: FilterState): void {
  filters.oiThreshold = nextFilters.oiThreshold;
  filters.volumeThreshold = nextFilters.volumeThreshold;
  filters.exchanges = nextFilters.exchanges;
}

function openPairPages(row: OpportunityPairRow): void {
  marketError.value = '';
  const urls = buildPairTradeUrls(row.longExchange, row.shortExchange, row.symbol);
  if (urls.length === 0) {
    marketError.value = '未找到可用的交易所跳转链接';
    return;
  }

  let blockedCount = 0;
  urls.forEach((url) => {
    const popup = window.open(url, '_blank', 'noopener,noreferrer');
    if (!popup) {
      blockedCount += 1;
    }
  });

  if (blockedCount > 0) {
    marketError.value = '浏览器拦截了新标签页，请允许本站弹窗后重试';
  }
}

async function onExecute(request: ExecutionRequest): Promise<void> {
  executionBusy.value = true;
  executionError.value = '';
  executionResult.value = '';
  try {
    const result = await executeAction(request.action, request.payload);
    executionResult.value = JSON.stringify(result, null, 2);
    if (request.action !== 'preview') {
      await refreshAll();
    }
  } catch (error) {
    executionError.value = error instanceof Error ? error.message : '执行失败';
  } finally {
    executionBusy.value = false;
  }
}

watch([autoRefresh, refreshSeconds], setupTimer);

onMounted(async () => {
  await refreshAll();
  setupTimer();
});

onBeforeUnmount(() => {
  clearTimer();
});
</script>

<template>
  <div class="app-shell">
    <header class="top-header">
      <div class="title-group">
        <h1>Funding Arbitrage Terminal</h1>
        <p>资金费率套利监控面板</p>
      </div>

      <div class="header-actions">
        <span class="status" :class="{ running: autoRefresh }">
          {{ autoRefresh ? `自动刷新 ${refreshSeconds}s` : '自动刷新已关闭' }}
        </span>
        <button type="button" class="start-trade" @click="openDrawer('preview', selectedMarket || undefined)">
          开始交易
        </button>
      </div>
    </header>

    <TopFilters
      :model-value="filters"
      :exchange-options="exchangeOptions"
      :updated-at="lastUpdated"
      @update:model-value="onFilterChange"
      @refresh="refreshAll"
    />

    <p v-if="marketError" class="error-tip">{{ marketError }}</p>

    <MarketTable
      :rows="filteredRows"
      :loading="marketLoading"
      @preview="openDrawer('preview', $event)"
      @open="openDrawer('open', $event)"
      @visit-symbol="openPairPages"
    />
  </div>

  <TradeDrawer
    :open="drawerOpen"
    :market="selectedMarket"
    :initial-action="drawerAction"
    :exchanges="exchangeOptions"
    :positions-count="positions.length"
    :orders-count="orders.length"
    :busy="executionBusy"
    :error-message="executionError"
    :result-text="executionResult"
    @close="closeDrawer"
    @execute="onExecute"
  />

  <BottomToolbar
    :auto-refresh="autoRefresh"
    :refresh-seconds="refreshSeconds"
    @update:auto-refresh="autoRefresh = $event"
    @update:refresh-seconds="refreshSeconds = $event"
    @refresh="refreshAll"
  />

  <div v-if="tradeLoading" class="trade-loading">仓位与订单同步中...</div>
</template>
