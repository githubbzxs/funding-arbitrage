<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { fetchOpportunities, fetchSnapshots } from '../api/market';
import MarketCardList from '../components/MarketCardList.vue';
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
import { buildPairTradeTargets } from '../utils/exchangeLinks';
import { openPairTargetsInNewTabs } from '../utils/popupOpen';

const EXCHANGE_OPTIONS = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;
const LOCAL_CACHE_KEY = 'fa-market-page-cache-v1';
const REFRESH_INTERVAL_MS = 5 * 60 * 1000;
const MOBILE_QUERY = '(max-width: 960px)';

type LocalCachePayload = {
  snapshots: MarketRow[];
  opportunities: MarketRow[];
  snapshotErrors: MarketFetchError[];
  marketMeta: MarketMeta | null;
  updatedAt: string;
  cachedAt: number;
};

type OpenTabsNotice = {
  kind: 'success' | 'warning';
  message: string;
};

const router = useRouter();
const marketLoading = ref(false);
const marketError = ref('');
const lastUpdated = ref('');
const snapshots = ref<MarketRow[]>([]);
const opportunities = ref<MarketRow[]>([]);
const snapshotErrors = ref<MarketFetchError[]>([]);
const marketMeta = ref<MarketMeta | null>(null);
const refreshInProgress = ref(false);
const hasLocalCache = ref(false);
const isMobile = ref(false);
const openTabsNotice = ref<OpenTabsNotice | null>(null);

const filters = reactive<FilterState>({
  exchanges: []
});

let timerId: number | undefined;
let mediaQuery: MediaQueryList | null = null;
let mediaQueryHandler: ((event: MediaQueryListEvent) => void) | null = null;

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

function applyLocalCache(payload: LocalCachePayload): void {
  snapshots.value = payload.snapshots;
  opportunities.value = payload.opportunities;
  snapshotErrors.value = payload.snapshotErrors;
  marketMeta.value = payload.marketMeta;
  lastUpdated.value = payload.updatedAt;
}

function readLocalCache(): LocalCachePayload | null {
  if (typeof window === 'undefined') {
    return null;
  }
  const raw = window.localStorage.getItem(LOCAL_CACHE_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as Partial<LocalCachePayload>;
    if (!parsed || typeof parsed !== 'object') {
      return null;
    }
    if (!Array.isArray(parsed.snapshots) || !Array.isArray(parsed.opportunities) || !Array.isArray(parsed.snapshotErrors)) {
      return null;
    }
    return {
      snapshots: parsed.snapshots as MarketRow[],
      opportunities: parsed.opportunities as MarketRow[],
      snapshotErrors: parsed.snapshotErrors as MarketFetchError[],
      marketMeta: (parsed.marketMeta ?? null) as MarketMeta | null,
      updatedAt: typeof parsed.updatedAt === 'string' ? parsed.updatedAt : '',
      cachedAt: typeof parsed.cachedAt === 'number' ? parsed.cachedAt : Date.now()
    };
  } catch {
    return null;
  }
}

function saveLocalCache(): void {
  if (typeof window === 'undefined') {
    return;
  }
  const payload: LocalCachePayload = {
    snapshots: snapshots.value,
    opportunities: opportunities.value,
    snapshotErrors: snapshotErrors.value,
    marketMeta: marketMeta.value,
    updatedAt: lastUpdated.value,
    cachedAt: Date.now()
  };
  try {
    window.localStorage.setItem(LOCAL_CACHE_KEY, JSON.stringify(payload));
  } catch {
    // 忽略本地缓存写入异常，避免影响主流程。
  }
}

const hasAnyData = computed(() => snapshots.value.length > 0 || opportunities.value.length > 0);
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

const showEmptyCacheTip = computed(
  () => !hasLocalCache.value && !hasAnyData.value && !marketLoading.value && !marketError.value && !refreshInProgress.value
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
  if (marketMeta.value?.exchangeSources) {
    const sourceParts = Object.entries(marketMeta.value.exchangeSources)
      .filter(([, source]) => source && source !== 'ccxt')
      .map(([exchange, source]) => `${exchange}:${source}`);
    if (sourceParts.length > 0) {
      parts.push(`来源: ${sourceParts.join(',')}`);
    }
  }
  if (marketMeta.value?.exchangeCounts) {
    const zeroParts = Object.entries(marketMeta.value.exchangeCounts)
      .filter(([, count]) => count <= 0)
      .map(([exchange]) => exchange);
    if (zeroParts.length > 0) {
      parts.push(`0快照: ${zeroParts.join(',')}`);
    }
  }
  if (hasLocalCache.value && parts.length === 0) {
    parts.push('当前展示本地缓存数据');
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
  timerId = window.setInterval(() => {
    void refreshMarketData();
  }, REFRESH_INTERVAL_MS);
}

async function refreshMarketData(options?: { forceRefresh?: boolean }): Promise<void> {
  if (refreshInProgress.value) {
    return;
  }
  refreshInProgress.value = true;
  marketError.value = '';
  marketLoading.value = !hasAnyData.value;
  try {
    const forceRefresh = options?.forceRefresh === true;
    const [snapshotResult, opportunityRows] = await Promise.all([
      fetchSnapshots({ forceRefresh }),
      fetchOpportunities({ forceRefresh })
    ]);
    snapshots.value = snapshotResult.rows;
    opportunities.value = opportunityRows;
    snapshotErrors.value = snapshotResult.errors;
    marketMeta.value = snapshotResult.meta;
    lastUpdated.value = new Date().toLocaleString('zh-CN');
    hasLocalCache.value = true;
    saveLocalCache();
  } catch (error) {
    marketError.value = error instanceof Error ? error.message : '拉取市场数据失败';
  } finally {
    marketLoading.value = false;
    refreshInProgress.value = false;
  }
}

function onFilterChange(nextFilters: FilterState): void {
  filters.exchanges = nextFilters.exchanges;
}

function onManualRefresh(): void {
  openTabsNotice.value = null;
  void refreshMarketData({ forceRefresh: true });
}

function openPairPages(row: OpportunityPairRow): void {
  const targetResult = buildPairTradeTargets(row.longExchange, row.shortExchange, row.symbol);
  if (targetResult.targets.length === 0) {
    const reasonParts: string[] = [];
    if (targetResult.invalidExchanges.length > 0) {
      reasonParts.push(`不支持交易所：${targetResult.invalidExchanges.join(',')}`);
    }
    if (targetResult.failedExchanges.length > 0) {
      reasonParts.push(`链接生成失败：${targetResult.failedExchanges.join(',')}`);
    }
    openTabsNotice.value = {
      kind: 'warning',
      message:
        reasonParts.length > 0
          ? `无法生成双交易所链接（${reasonParts.join('；')}）。`
          : '无法生成双交易所链接，请检查交易所和币对参数。'
    };
    return;
  }

  const openResult = openPairTargetsInNewTabs(targetResult.targets);
  const issueParts: string[] = [];
  if (targetResult.invalidExchanges.length > 0) {
    issueParts.push(`不支持交易所：${targetResult.invalidExchanges.join(',')}`);
  }
  if (targetResult.failedExchanges.length > 0) {
    issueParts.push(`链接生成失败：${targetResult.failedExchanges.join(',')}`);
  }
  if (targetResult.duplicateExchanges.length > 0) {
    issueParts.push(`重复交易所：${targetResult.duplicateExchanges.join(',')}`);
  }
  if (targetResult.targets.length < 2) {
    issueParts.push(`仅识别到 ${targetResult.targets.length} 个有效交易所链接`);
  }

  if (openResult.opened < openResult.requested) {
    const blockedText =
      openResult.blockedExchanges.length > 0 ? `被拦截：${openResult.blockedExchanges.join(',')}。` : '';
    openTabsNotice.value = {
      kind: 'warning',
      message: `${blockedText}浏览器阻止了部分新标签页，请在地址栏中将本站设置为“允许弹窗和重定向”后重试。`
    };
    return;
  }

  if (issueParts.length > 0) {
    openTabsNotice.value = {
      kind: 'warning',
      message: `${issueParts.join('；')}。`
    };
    return;
  }

  openTabsNotice.value = {
    kind: 'success',
    message: '已在新标签页打开两个交易所。'
  };
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

onMounted(() => {
  setupMobileWatcher();
  const cached = readLocalCache();
  if (cached) {
    applyLocalCache(cached);
    hasLocalCache.value = true;
  }
  setupTimer();
});

onBeforeUnmount(() => {
  clearTimer();
  cleanupMobileWatcher();
});
</script>

<template>
  <div class="page-grid">
    <TopFilters
      :model-value="filters"
      :exchange-options="exchangeOptions"
      :updated-at="lastUpdated"
      :status-line="statusLine"
      :refreshing="refreshInProgress"
      @update:model-value="onFilterChange"
      @refresh="onManualRefresh"
    />

    <p
      v-if="openTabsNotice"
      :class="openTabsNotice.kind === 'warning' ? 'warn-tip open-tabs-notice' : 'info-tip open-tabs-notice'"
    >
      {{ openTabsNotice.message }}
    </p>
    <p v-if="marketError" class="error-tip">{{ marketError }}</p>
    <p v-else-if="showEmptyCacheTip" class="warn-tip">暂无缓存数据，请点击“立即刷新”加载行情。</p>
    <p v-else-if="snapshotErrors.length > 0" class="warn-tip">
      部分交易所抓取失败：{{
        snapshotErrors.map((item) => `${item.exchange}: ${item.message}`).join(' | ')
      }}
    </p>

    <MarketCardList
      v-if="isMobile"
      :rows="filteredRows"
      :loading="marketLoading"
      @trade="openTrade"
      @visit-symbol="openPairPages"
    />
    <MarketTable
      v-else
      :rows="filteredRows"
      :loading="marketLoading && filteredRows.length === 0"
      @trade="openTrade"
      @visit-symbol="openPairPages"
    />
  </div>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 10px;
}

.warn-tip {
  margin: 0;
  border: 1px solid rgba(255, 190, 102, 0.4);
  background: rgba(255, 190, 102, 0.08);
  color: #ffd9a1;
  padding: 8px 10px;
  font-size: 12px;
}

.info-tip {
  margin: 0;
  border: 1px solid rgba(0, 199, 166, 0.45);
  background: rgba(0, 199, 166, 0.1);
  color: #9cf6e7;
  padding: 8px 10px;
  font-size: 12px;
}

.open-tabs-notice {
  line-height: 1.4;
}
</style>
