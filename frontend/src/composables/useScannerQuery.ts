import { useQuery } from '@tanstack/vue-query';
import { computed, type Ref, ref } from 'vue';
import { fetchBoard } from '../api/market';
import type { MarketBoardResult } from '../types/market';

type UseScannerQueryOptions = {
  limit: Ref<number>;
  minNextCycleScore: Ref<number>;
  exchanges: Ref<string[]>;
  symbol: Ref<string>;
  autoRefresh: Ref<boolean>;
  refreshSeconds: Ref<number>;
};

const SCANNER_BOARD_CACHE_KEY = 'fa:scanner-board-cache:v1';

type ScannerBoardCacheEntry = {
  savedAt: number;
  data: MarketBoardResult;
};

type ScannerBoardCacheStore = Record<string, ScannerBoardCacheEntry>;

function normalizedExchanges(value: string[]): string[] {
  return [...value]
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .sort();
}

function buildQuerySignature(queryKey: readonly unknown[]): string {
  return JSON.stringify(queryKey);
}

function readScannerBoardCacheStore(): ScannerBoardCacheStore {
  if (typeof window === 'undefined') {
    return {};
  }
  try {
    const raw = window.localStorage.getItem(SCANNER_BOARD_CACHE_KEY);
    if (!raw) {
      return {};
    }
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return {};
    }
    return parsed as ScannerBoardCacheStore;
  } catch {
    // 本地缓存异常时静默降级，不影响主链路
    return {};
  }
}

function readScannerBoardCache(signature: string): ScannerBoardCacheEntry | null {
  const store = readScannerBoardCacheStore();
  const entry = store[signature];
  if (!entry || typeof entry !== 'object') {
    return null;
  }
  const savedAt = (entry as { savedAt?: unknown }).savedAt;
  const data = (entry as { data?: unknown }).data;
  if (typeof savedAt !== 'number' || !Number.isFinite(savedAt)) {
    return null;
  }
  if (typeof data !== 'object' || data === null) {
    return null;
  }
  return {
    savedAt,
    data: data as MarketBoardResult
  };
}

function writeScannerBoardCache(signature: string, data: MarketBoardResult): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    const store = readScannerBoardCacheStore();
    store[signature] = {
      savedAt: Date.now(),
      data
    };
    window.localStorage.setItem(SCANNER_BOARD_CACHE_KEY, JSON.stringify(store));
  } catch {
    // 本地缓存异常时静默降级，不影响主链路
  }
}

export function useScannerQuery(options: UseScannerQueryOptions) {
  const forceRefreshToken = ref(0);

  const query = useQuery(
    computed(() => {
      const queryKey = [
        'market-board',
        options.limit.value,
        options.minNextCycleScore.value,
        options.symbol.value.trim().toUpperCase(),
        normalizedExchanges(options.exchanges.value).join(',')
      ] as const;
      const querySignature = buildQuerySignature(queryKey);
      const cacheEntry = readScannerBoardCache(querySignature);
      return {
        queryKey,
        queryFn: async (): Promise<MarketBoardResult> => {
          const shouldForceRefresh = forceRefreshToken.value > 0;
          if (shouldForceRefresh) {
            forceRefreshToken.value = 0;
          }
          const data = await fetchBoard({
            limit: options.limit.value,
            minNextCycleScore: options.minNextCycleScore.value,
            symbol: options.symbol.value.trim() || undefined,
            exchanges: normalizedExchanges(options.exchanges.value),
            forceRefresh: shouldForceRefresh
          });
          writeScannerBoardCache(querySignature, data);
          return data;
        },
        initialData: cacheEntry?.data,
        initialDataUpdatedAt: cacheEntry?.savedAt,
        staleTime: 5 * 60_000,
        gcTime: 5 * 60_000,
        retry: 1,
        refetchOnWindowFocus: false,
        refetchInterval: options.autoRefresh.value ? Math.max(10, options.refreshSeconds.value) * 1000 : false
      };
    })
  );

  async function refreshNow(): Promise<void> {
    forceRefreshToken.value = Date.now();
    await query.refetch();
  }

  return {
    query,
    refreshNow
  };
}
