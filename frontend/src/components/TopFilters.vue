<script setup lang="ts">
import { computed } from 'vue';
import type { FilterState } from '../types/market';

const props = defineProps<{
  modelValue: FilterState;
  exchangeOptions: string[];
  updatedAt: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [FilterState];
  refresh: [];
}>();

const modelValue = computed(() => props.modelValue);

const oiThreshold = computed({
  get: () => props.modelValue.oiThreshold,
  set: (value: number) => {
    emit('update:modelValue', { ...props.modelValue, oiThreshold: value });
  }
});

const volumeThreshold = computed({
  get: () => props.modelValue.volumeThreshold,
  set: (value: number) => {
    emit('update:modelValue', { ...props.modelValue, volumeThreshold: value });
  }
});

function toggleFromList(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function toggleExchange(exchange: string): void {
  emit('update:modelValue', {
    ...props.modelValue,
    exchanges: toggleFromList(props.modelValue.exchanges, exchange)
  });
}

function resetFilters(): void {
  emit('update:modelValue', {
    oiThreshold: 0,
    volumeThreshold: 0,
    exchanges: []
  });
}

function onNumberChange(event: Event, key: 'oiThreshold' | 'volumeThreshold'): void {
  const target = event.target as HTMLInputElement;
  const value = Number(target.value);
  if (key === 'oiThreshold') {
    oiThreshold.value = Number.isFinite(value) ? value : 0;
    return;
  }
  volumeThreshold.value = Number.isFinite(value) ? value : 0;
}
</script>

<template>
  <section class="filters-panel">
    <div class="filters-grid">
      <label class="field">
        <span>OI 阈值 (USD)</span>
        <input type="number" min="0" step="10000" :value="oiThreshold" @input="onNumberChange($event, 'oiThreshold')" />
      </label>

      <label class="field">
        <span>日成交额阈值 (USD)</span>
        <input
          type="number"
          min="0"
          step="10000"
          :value="volumeThreshold"
          @input="onNumberChange($event, 'volumeThreshold')"
        />
      </label>

      <div class="field wide">
        <span>交易所筛选</span>
        <div class="chip-list">
          <button
            v-for="exchange in exchangeOptions"
            :key="exchange"
            type="button"
            class="chip"
            :class="{ active: modelValue.exchanges.includes(exchange) }"
            @click="toggleExchange(exchange)"
          >
            {{ exchange }}
          </button>
        </div>
      </div>
    </div>

    <div class="filter-actions">
      <div class="meta">上次刷新：{{ updatedAt || '-' }}</div>
      <button type="button" class="ghost" @click="$emit('refresh')">立即刷新</button>
      <button type="button" class="ghost" @click="resetFilters">重置筛选</button>
    </div>
  </section>
</template>

<style scoped>
.filters-panel {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 10px;
  display: grid;
  gap: 10px;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.field {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}

.field span {
  color: var(--text-main);
}

.field.wide {
  grid-column: span 1;
}

.field input {
  height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  background: var(--control-bg);
  color: var(--text-main);
  border-radius: 2px;
  outline: none;
}

.field input:focus {
  border-color: var(--accent);
}

.chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  border: 1px solid var(--line-soft);
  background: #0d131c;
  color: var(--text-dim);
  height: 28px;
  padding: 0 10px;
  font-size: 12px;
  border-radius: 2px;
}

.chip.active {
  border-color: var(--accent);
  color: var(--accent-soft);
  background: rgba(0, 199, 166, 0.08);
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.meta {
  margin-right: auto;
  color: var(--text-dim);
  font-size: 12px;
}

.ghost {
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  background: transparent;
  color: var(--text-main);
  border-radius: 2px;
}

.ghost:hover {
  border-color: var(--accent);
}

@media (max-width: 1024px) {
  .filters-grid {
    grid-template-columns: 1fr 1fr;
  }

  .field.wide {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .filters-grid {
    grid-template-columns: 1fr;
  }

  .field.wide {
    grid-column: span 1;
  }

  .filter-actions {
    flex-wrap: wrap;
  }

  .meta {
    width: 100%;
  }
}
</style>
