<script setup lang="ts">
import { computed, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { buildPairTradeTargets, type PairTradeTarget } from '../utils/exchangeLinks';
import { openPairTargetsInNewTabs } from '../utils/popupOpen';

const route = useRoute();
const statusMessage = ref('该页面为手动跳转工具（备用），不会在主流程自动触发。');
const blockedCount = ref(0);
const tried = ref(false);

function readQueryString(name: string): string {
  const raw = route.query[name];
  if (typeof raw === 'string') {
    return raw.trim();
  }
  if (Array.isArray(raw) && typeof raw[0] === 'string') {
    return raw[0].trim();
  }
  return '';
}

const symbol = computed(() => readQueryString('symbol').toUpperCase());
const longExchange = computed(() => readQueryString('long').toLowerCase());
const shortExchange = computed(() => readQueryString('short').toLowerCase());

const targetResult = computed(() => buildPairTradeTargets(longExchange.value, shortExchange.value, symbol.value));
const targets = computed<PairTradeTarget[]>(() => targetResult.value.targets);

function openAllTargets(): void {
  tried.value = true;
  blockedCount.value = 0;
  if (targets.value.length === 0) {
    statusMessage.value = '未找到可用的交易所跳转链接，请检查参数。';
    return;
  }

  const result = openPairTargetsInNewTabs(targets.value);
  blockedCount.value = result.requested - result.opened;
  if (blockedCount.value > 0) {
    statusMessage.value = `浏览器拦截了 ${blockedCount.value} 个新标签页，请先允许本站弹窗与重定向后重试。`;
    return;
  }
  statusMessage.value = '已尝试打开全部交易所页面。';
}
</script>

<template>
  <section class="panel">
    <h2>交易所手动跳转工具（备用）</h2>
    <p class="desc">
      币对：<strong>{{ symbol || '-' }}</strong> | 多腿：<strong>{{ longExchange || '-' }}</strong> | 空腿：<strong>{{ shortExchange || '-' }}</strong>
    </p>
    <p class="desc">{{ statusMessage }}</p>

    <div class="actions">
      <button type="button" class="accent" @click="openAllTargets">一键重试打开</button>
      <RouterLink class="ghost" to="/">返回行情页</RouterLink>
      <RouterLink
        class="ghost"
        :to="{ path: '/trade', query: { action: 'open', symbol, long: longExchange, short: shortExchange } }"
      >
        去交易页
      </RouterLink>
    </div>

    <div v-if="targets.length > 0" class="manual-list">
      <h3>手动打开</h3>
      <a
        v-for="target in targets"
        :key="`${target.leg}-${target.exchange}`"
        class="link"
        :href="target.url"
        target="_blank"
        rel="noopener noreferrer"
      >
        打开 {{ target.exchange }}
      </a>
    </div>

    <p v-if="tried && targets.length === 0" class="error">未能生成跳转链接，请检查交易所与币对参数。</p>
  </section>
</template>

<style scoped>
.panel {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 16px;
  display: grid;
  gap: 10px;
}

.panel h2 {
  margin: 0;
  font-size: 16px;
}

.desc {
  margin: 0;
  color: var(--text-dim);
  font-size: 13px;
}

.desc strong {
  color: var(--text-main);
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.accent,
.ghost {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 2px;
  border: 1px solid var(--line-soft);
  text-decoration: none;
  font-size: 12px;
}

.accent {
  border-color: rgba(0, 199, 166, 0.8);
  background: rgba(0, 199, 166, 0.9);
  color: #022018;
}

.ghost {
  background: #101722;
  color: var(--text-main);
}

.ghost:hover {
  border-color: var(--accent);
}

.manual-list {
  border: 1px solid var(--line-soft);
  background: #0d141e;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.manual-list h3 {
  margin: 0;
  font-size: 13px;
}

.link {
  color: var(--accent-soft);
  text-decoration: underline;
  font-size: 13px;
}

.error {
  margin: 0;
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  color: #ffd3d3;
  font-size: 12px;
  padding: 8px;
}
</style>
