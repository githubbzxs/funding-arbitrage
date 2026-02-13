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

function normalizedExchanges(value: string[]): string[] {
  return [...value]
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .sort();
}

export function useScannerQuery(options: UseScannerQueryOptions) {
  const forceRefreshToken = ref(0);

  const query = useQuery(
    computed(() => ({
      queryKey: [
        'market-board',
        options.limit.value,
        options.minNextCycleScore.value,
        options.symbol.value.trim().toUpperCase(),
        normalizedExchanges(options.exchanges.value).join(',')
      ] as const,
      queryFn: async (): Promise<MarketBoardResult> => {
        const shouldForceRefresh = forceRefreshToken.value > 0;
        if (shouldForceRefresh) {
          forceRefreshToken.value = 0;
        }
        return fetchBoard({
          limit: options.limit.value,
          minNextCycleScore: options.minNextCycleScore.value,
          symbol: options.symbol.value.trim() || undefined,
          exchanges: normalizedExchanges(options.exchanges.value),
          forceRefresh: shouldForceRefresh
        });
      },
      staleTime: 20_000,
      gcTime: 5 * 60_000,
      retry: 1,
      refetchOnWindowFocus: false,
      refetchInterval: options.autoRefresh.value ? Math.max(10, options.refreshSeconds.value) * 1000 : false
    }))
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
