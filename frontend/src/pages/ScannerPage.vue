<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import ScannerMobileCards from '../components/ScannerMobileCards.vue';
import ScannerTableVirtual from '../components/ScannerTableVirtual.vue';
import ScannerToolbar from '../components/ScannerToolbar.vue';
import { useScannerQuery } from '../composables/useScannerQuery';
import type { MarginSimulation, OpportunityBoardRow } from '../types/market';
import { buildPairTradeTargets } from '../utils/exchangeLinks';
import { calcMarginSimulation, parseMarginUsd } from '../utils/marginSim';
import { openPairTargetsInNewTabs } from '../utils/popupOpen';

const EXCHANGE_OPTIONS = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;
const MOBILE_QUERY = '(max-width: 960px)';

const router = useRouter();

const exchanges = ref<string[]>([]);
const symbol = ref('');
const limit = ref(1200);
const minSpreadRate1yNominal = ref(0);
const autoRefresh = ref(true);
const refreshSeconds = ref(30);
const isMobile = ref(false);
const openNotice = ref<{ kind: 'success' | 'warning'; message: string } | null>(null);
const marginInputs = ref<Record<string, string>>({});

let mediaQuery: MediaQueryList | null = null;
let mediaQueryHandler: ((event: MediaQueryListEvent) => void) | null = null;

const { query, refreshNow } = useScannerQuery({
  limit,
  minSpreadRate1yNominal,
  exchanges,
  symbol,
  autoRefresh,
  refreshSeconds
});

const rows = computed(() => query.data.value?.rows ?? []);
const total = computed(() => query.data.value?.total ?? rows.value.length);
const loading = computed(() => query.isPending.value || query.isFetching.value);
const simulationByRowId = computed<Record<string, MarginSimulation | null>>(() => {
  const output: Record<string, MarginSimulation | null> = {};
  rows.value.forEach((row) => {
    const inputValue = marginInputs.value[row.id];
    if (!inputValue) {
      output[row.id] = null;
      return;
    }
    const marginUsd = parseMarginUsd(inputValue);
    if (marginUsd === null) {
      output[row.id] = null;
      return;
    }
    output[row.id] = calcMarginSimulation(row, marginUsd, 24);
  });
  return output;
});
const errorMessage = computed(() => {
  const error = query.error.value;
  if (error instanceof Error) {
    return error.message;
  }
  return '';
});

const updatedAt = computed(() => {
  const asOf = query.data.value?.asOf;
  if (asOf) {
    const date = new Date(asOf);
    if (!Number.isNaN(date.getTime())) {
      return date.toLocaleString('zh-CN');
    }
  }
  if (query.dataUpdatedAt.value > 0) {
    return new Date(query.dataUpdatedAt.value).toLocaleString('zh-CN');
  }
  return '';
});

const statusLine = computed(() => {
  const meta = query.data.value?.meta;
  const errors = query.data.value?.errors ?? [];
  const parts: string[] = [];
  if (meta?.fetchMs !== null && typeof meta?.fetchMs === 'number') {
    parts.push(`抓取耗时 ${meta.fetchMs}ms`);
  }
  if (meta?.cacheHit) {
    parts.push('命中缓存');
  }
  if (meta?.exchangesFailed.length) {
    parts.push(`失败交易所: ${meta.exchangesFailed.join(',')}`);
  }
  if (errors.length > 0) {
    parts.push(`错误数: ${errors.length}`);
  }
  if (meta?.exchangeSources) {
    const sourceParts = Object.entries(meta.exchangeSources)
      .filter(([, source]) => source && source !== 'ccxt')
      .map(([exchange, source]) => `${exchange}:${source}`);
    if (sourceParts.length) {
      parts.push(`数据来源: ${sourceParts.join(',')}`);
    }
  }
  return parts.join(' | ');
});

function setupMobileWatcher(): void {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return;
  }
  mediaQuery = window.matchMedia(MOBILE_QUERY);
  isMobile.value = mediaQuery.matches;
  mediaQueryHandler = (event: MediaQueryListEvent) => {
    isMobile.value = event.matches;
  };
  mediaQuery.addEventListener('change', mediaQueryHandler);
}

function cleanupMobileWatcher(): void {
  if (mediaQuery && mediaQueryHandler) {
    mediaQuery.removeEventListener('change', mediaQueryHandler);
  }
  mediaQuery = null;
  mediaQueryHandler = null;
}

function openDetail(row: OpportunityBoardRow): void {
  void router.push({
    path: `/scanner/${encodeURIComponent(row.symbol)}/${encodeURIComponent(row.longExchange)}/${encodeURIComponent(row.shortExchange)}`
  });
}

function openTrade(row: OpportunityBoardRow): void {
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

function openPairPages(row: OpportunityBoardRow): void {
  const targetResult = buildPairTradeTargets(row.longExchange, row.shortExchange, row.symbol);
  if (targetResult.targets.length === 0) {
    openNotice.value = {
      kind: 'warning',
      message: '无法生成双交易所跳转链接，请检查交易所和币对。'
    };
    return;
  }
  const openResult = openPairTargetsInNewTabs(targetResult.targets);
  if (openResult.opened < openResult.requested) {
    const blocked = openResult.blockedExchanges.length ? `被拦截: ${openResult.blockedExchanges.join(',')}` : '浏览器拦截了新标签页';
    openNotice.value = {
      kind: 'warning',
      message: `${blocked}，请允许本站弹窗后重试。`
    };
    return;
  }
  openNotice.value = {
    kind: 'success',
    message: `已打开 ${openResult.opened} 个交易所页面。`
  };
}

async function manualRefresh(): Promise<void> {
  openNotice.value = null;
  await refreshNow();
}

function onExchangesChange(value: string[]): void {
  exchanges.value = value;
}

function onSymbolChange(value: string): void {
  symbol.value = value;
}

function onLimitChange(value: number): void {
  limit.value = value;
}

function onMinSpreadChange(value: number): void {
  minSpreadRate1yNominal.value = value;
}

function onAutoRefreshChange(value: boolean): void {
  autoRefresh.value = value;
}

function onRefreshSecondsChange(value: number): void {
  refreshSeconds.value = value;
}

function onMarginInput(payload: { rowId: string; value: string }): void {
  marginInputs.value = {
    ...marginInputs.value,
    [payload.rowId]: payload.value
  };
}

watch(
  rows,
  (nextRows) => {
    const nextIds = new Set(nextRows.map((item) => item.id));
    const nextInputs: Record<string, string> = {};
    Object.entries(marginInputs.value).forEach(([id, value]) => {
      if (nextIds.has(id)) {
        nextInputs[id] = value;
      }
    });
    marginInputs.value = nextInputs;
  },
  { immediate: true }
);

onMounted(() => {
  setupMobileWatcher();
});

onBeforeUnmount(() => {
  cleanupMobileWatcher();
});
</script>

<template>
  <section class="scanner-page">
    <ScannerToolbar
      :exchange-options="[...EXCHANGE_OPTIONS]"
      :exchanges="exchanges"
      :symbol="symbol"
      :limit="limit"
      :min-spread-rate1y-nominal="minSpreadRate1yNominal"
      :auto-refresh="autoRefresh"
      :refresh-seconds="refreshSeconds"
      :refreshing="loading"
      :updated-at="updatedAt"
      :total="total"
      :status-line="statusLine"
      @update:exchanges="onExchangesChange"
      @update:symbol="onSymbolChange"
      @update:limit="onLimitChange"
      @update:min-spread-rate1y-nominal="onMinSpreadChange"
      @update:auto-refresh="onAutoRefreshChange"
      @update:refresh-seconds="onRefreshSecondsChange"
      @refresh="manualRefresh"
    />

    <p v-if="openNotice" class="notice" :class="openNotice.kind === 'warning' ? 'warn' : 'ok'">{{ openNotice.message }}</p>
    <p v-if="errorMessage" class="notice warn">{{ errorMessage }}</p>
    <section class="sim-guide">
      <h3>保证金模拟（24h）</h3>
      <p>间隔相同：按双边对冲正常计算。</p>
      <p>间隔不同：会标记短间隔一侧，收益拆成“对冲部分 + 短间隔单边部分”。</p>
    </section>

    <ScannerMobileCards
      v-if="isMobile"
      :rows="rows"
      :loading="loading"
      :margin-inputs="marginInputs"
      :simulations="simulationByRowId"
      @open-detail="openDetail"
      @open-pair="openPairPages"
      @open-trade="openTrade"
      @update-margin="onMarginInput"
    />
    <ScannerTableVirtual
      v-else
      :rows="rows"
      :loading="loading"
      :margin-inputs="marginInputs"
      :simulations="simulationByRowId"
      @open-detail="openDetail"
      @open-pair="openPairPages"
      @open-trade="openTrade"
      @update-margin="onMarginInput"
    />
  </section>
</template>

<style scoped>
.scanner-page {
  display: grid;
  gap: 10px;
}

.sim-guide {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
}

.sim-guide h3 {
  margin: 0;
  font-size: 13px;
}

.sim-guide p {
  margin: 0;
  color: var(--text-dim);
  font-size: 12px;
}

.notice {
  margin: 0;
  font-size: 12px;
  padding: 9px 10px;
  border: 1px solid var(--line-soft);
  background: #0d141e;
}

.warn {
  border-color: rgba(255, 120, 120, 0.55);
  background: rgba(255, 120, 120, 0.12);
  color: #ffb4b4;
}

.ok {
  border-color: rgba(0, 199, 166, 0.55);
  background: rgba(0, 199, 166, 0.1);
  color: #a2f5e8;
}
</style>
