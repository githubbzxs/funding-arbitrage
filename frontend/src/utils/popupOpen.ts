import type { PairTradeTarget } from './exchangeLinks';

export type PopupWindowLike = {
  opener?: unknown;
  location: {
    replace: (url: string) => void;
  };
  close?: () => void;
};

export type OpenWindowFn = (url?: string, target?: string, features?: string) => PopupWindowLike | null;

export type OpenPairTargetsResult = {
  requested: number;
  opened: number;
  blockedExchanges: string[];
  openedExchanges: string[];
};

function defaultOpenWindow(url?: string, target?: string, features?: string): PopupWindowLike | null {
  if (typeof window === 'undefined' || typeof window.open !== 'function') {
    return null;
  }
  return window.open(url, target, features) as unknown as PopupWindowLike | null;
}

export function openPairTargetsInNewTabs(
  targets: PairTradeTarget[],
  options?: { openWindow?: OpenWindowFn; features?: string }
): OpenPairTargetsResult {
  const openWindow = options?.openWindow ?? defaultOpenWindow;
  const features = options?.features;
  let opened = 0;
  const blockedExchanges: string[] = [];
  const openedExchanges: string[] = [];

  targets.forEach((target) => {
    const popup = openWindow('about:blank', '_blank', features);
    if (!popup) {
      blockedExchanges.push(target.exchange);
      return;
    }

    try {
      popup.opener = null;
    } catch {
      // 忽略浏览器对 opener 的限制。
    }

    try {
      popup.location.replace(target.url);
      opened += 1;
      openedExchanges.push(target.exchange);
    } catch {
      blockedExchanges.push(target.exchange);
      try {
        popup.close?.();
      } catch {
        // 忽略关闭失败，避免影响主流程。
      }
    }
  });

  return {
    requested: targets.length,
    opened,
    blockedExchanges,
    openedExchanges
  };
}
