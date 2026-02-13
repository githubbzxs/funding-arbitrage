<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { executeAction } from './api/execution';
import { fetchOpportunities, fetchOrders, fetchPositions, fetchSnapshots } from './api/market';
import BottomToolbar from './components/BottomToolbar.vue';
import MarketTable from './components/MarketTable.vue';
import TopFilters from './components/TopFilters.vue';
import TradeDrawer from './components/TradeDrawer.vue';
import type { ExecutionAction, ExecutionRequest, FilterState, MarketRow, TradingRecord } from './types/market';

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
  intervals: [],
  exchanges: []
});

const drawerOpen = ref(false);
const drawerAction = ref<ExecutionAction>('preview');
const selectedMarket = ref<MarketRow | null>(null);
const executionBusy = ref(false);
const executionError = ref('');
const executionResult = ref('');

const autoRefresh = ref(true);
const refreshSeconds = ref(10);
const language = ref<'zh-CN' | 'en-US'>('zh-CN');

let timerId: number | undefined;

function buildKey(row: MarketRow): string {
  return `${row.exchange.toLowerCase()}::${row.symbol.toLowerCase()}::${row.source}`;
}

const mergedRows = computed<MarketRow[]>(() => {
  const mergedMap = new Map<string, MarketRow>();

  snapshots.value.forEach((row) => {
    mergedMap.set(buildKey(row), row);
  });
  opportunities.value.forEach((row) => {
    mergedMap.set(buildKey(row), row);
  });

  return [...mergedMap.values()].sort((a, b) => b.nominalApr - a.nominalApr);
});

const exchangeOptions = computed(() => {
  const base = new Set<string>();
  snapshots.value.forEach((row) => base.add(row.exchange));
  return [...base].sort((a, b) => a.localeCompare(b));
});

const intervalOptions = computed(() => {
  const values = new Set<string>();
  snapshots.value.forEach((row) => {
    if (row.settlementInterval) {
      values.add(row.settlementInterval);
    }
  });
  return values.size > 0 ? [...values].sort((a, b) => a.localeCompare(b)) : ['1h', '4h', '8h'];
});

const filteredRows = computed(() =>
  mergedRows.value.filter((row) => {
    if (row.openInterestUsd < filters.oiThreshold) {
      return false;
    }
    if (row.volume24hUsd < filters.volumeThreshold) {
      return false;
    }
    if (filters.intervals.length > 0 && row.source === 'snapshot' && !filters.intervals.includes(row.settlementInterval)) {
      return false;
    }
    if (filters.exchanges.length > 0) {
      if (row.source === 'snapshot' && !filters.exchanges.includes(row.exchange)) {
        return false;
      }
      if (row.source === 'opportunity') {
        const longOk = row.longExchange ? filters.exchanges.includes(row.longExchange) : false;
        const shortOk = row.shortExchange ? filters.exchanges.includes(row.shortExchange) : false;
        if (!longOk && !shortOk) {
          return false;
        }
      }
    }
    return true;
  })
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
    lastUpdated.value = new Date().toLocaleString(language.value);
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
  filters.intervals = nextFilters.intervals;
  filters.exchanges = nextFilters.exchanges;
}

function onLanguageUpdate(value: string): void {
  language.value = value === 'en-US' ? 'en-US' : 'zh-CN';
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
      :interval-options="intervalOptions"
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
    :language="language"
    @update:auto-refresh="autoRefresh = $event"
    @update:refresh-seconds="refreshSeconds = $event"
    @update:language="onLanguageUpdate"
    @refresh="refreshAll"
  />

  <div v-if="tradeLoading" class="trade-loading">仓位与订单同步中...</div>
</template>
