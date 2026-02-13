<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  exchangeOptions: string[];
  exchanges: string[];
  symbol: string;
  limit: number;
  minNextCycleScore: number;
  autoRefresh: boolean;
  refreshSeconds: number;
  refreshing: boolean;
  updatedAt: string;
  total: number;
  statusLine: string;
}>();

const emit = defineEmits<{
  'update:exchanges': [string[]];
  'update:symbol': [string];
  'update:limit': [number];
  'update:minNextCycleScore': [number];
  'update:autoRefresh': [boolean];
  'update:refreshSeconds': [number];
  refresh: [];
}>();

const selected = computed(() => new Set(props.exchanges.map((item) => item.toLowerCase())));

function toggleExchange(exchange: string): void {
  const normalized = exchange.toLowerCase();
  const next = selected.value.has(normalized)
    ? props.exchanges.filter((item) => item.toLowerCase() !== normalized)
    : [...props.exchanges, normalized];
  emit('update:exchanges', next);
}

function onSymbolChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('update:symbol', target.value.toUpperCase().trim());
}

function onLimitChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  const parsed = Number(target.value);
  if (Number.isFinite(parsed) && parsed > 0) {
    emit('update:limit', Math.min(5000, Math.max(100, Math.round(parsed))));
  }
}

function onMinNextCycleScoreChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  const parsed = Number(target.value);
  emit('update:minNextCycleScore', Number.isFinite(parsed) ? parsed : 0);
}

function onRefreshSecondsChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const parsed = Number(target.value);
  if (Number.isFinite(parsed) && parsed > 0) {
    emit('update:refreshSeconds', parsed);
  }
}
</script>

<template>
  <section class="toolbar">
    <div class="toolbar-row">
      <label class="field">
        <span>币对搜索</span>
        <input :value="symbol" placeholder="例如 BTCUSDT" @input="onSymbolChange" />
      </label>

      <label class="field">
        <span>最小统一指标(%)</span>
        <input :value="minNextCycleScore" type="number" step="1" @input="onMinNextCycleScoreChange" />
      </label>

      <label class="field">
        <span>拉取上限</span>
        <input :value="limit" type="number" min="100" max="5000" step="100" @input="onLimitChange" />
      </label>

      <label class="field small">
        <span>自动刷新</span>
        <button type="button" class="ghost" :class="{ active: autoRefresh }" @click="emit('update:autoRefresh', !autoRefresh)">
          {{ autoRefresh ? '开启' : '关闭' }}
        </button>
      </label>

      <label class="field small">
        <span>刷新间隔</span>
        <select :value="refreshSeconds" :disabled="!autoRefresh" @change="onRefreshSecondsChange">
          <option :value="15">15秒</option>
          <option :value="30">30秒</option>
          <option :value="60">60秒</option>
          <option :value="120">120秒</option>
          <option :value="300">300秒</option>
        </select>
      </label>
    </div>

    <div class="chip-row">
      <button
        v-for="exchange in exchangeOptions"
        :key="exchange"
        type="button"
        class="chip"
        :class="{ active: selected.has(exchange.toLowerCase()) }"
        @click="toggleExchange(exchange)"
      >
        {{ exchange }}
      </button>
    </div>

    <div class="meta-row">
      <div class="meta-text">
        <div>总机会数: {{ total }}</div>
        <div>最近更新: {{ updatedAt || '-' }}</div>
        <div v-if="statusLine">{{ statusLine }}</div>
      </div>
      <button type="button" class="refresh" :disabled="refreshing" @click="emit('refresh')">
        {{ refreshing ? '刷新中...' : '立即刷新' }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.toolbar {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: grid;
  gap: 10px;
}

.toolbar-row {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.field {
  display: grid;
  gap: 6px;
}

.field.small {
  max-width: 140px;
}

.field span {
  font-size: 12px;
  color: var(--text-dim);
}

.field input,
.field select {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  height: 34px;
  padding: 0 10px;
  border-radius: 4px;
  outline: none;
  font-family: inherit;
}

.field input:focus,
.field select:focus {
  border-color: var(--accent);
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  border: 1px solid var(--line-soft);
  background: #0e1521;
  color: var(--text-dim);
  padding: 0 12px;
  height: 30px;
  border-radius: 99px;
  font-size: 12px;
}

.chip.active {
  border-color: var(--accent);
  color: var(--accent-soft);
  background: rgba(0, 199, 166, 0.1);
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.meta-text {
  color: var(--text-dim);
  font-size: 12px;
  display: grid;
  gap: 2px;
}

.refresh,
.ghost {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  height: 34px;
  padding: 0 12px;
  border-radius: 4px;
}

.ghost.active {
  border-color: var(--accent);
  color: var(--accent-soft);
}

.refresh:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

@media (max-width: 1200px) {
  .toolbar-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .toolbar-row {
    grid-template-columns: 1fr;
  }

  .meta-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
