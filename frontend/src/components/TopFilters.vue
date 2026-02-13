<script setup lang="ts">
import { computed } from 'vue';
import type { FilterState } from '../types/market';

const props = defineProps<{
  modelValue: FilterState;
  exchangeOptions: string[];
  updatedAt: string;
  statusLine?: string;
  refreshing?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [FilterState];
  refresh: [];
}>();

const modelValue = computed(() => props.modelValue);

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
    exchanges: []
  });
}
</script>

<template>
  <section class="filters-panel">
    <div class="filters-grid">
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
      <div class="meta">
        <div>上次刷新：{{ updatedAt || '-' }}</div>
        <div v-if="statusLine">{{ statusLine }}</div>
      </div>
      <button type="button" class="ghost" :disabled="refreshing" @click="$emit('refresh')">
        {{ refreshing ? '刷新中...' : '立即刷新' }}
      </button>
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
  grid-template-columns: minmax(0, 1fr);
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
  display: grid;
  gap: 2px;
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

.ghost:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  border-color: var(--line-soft);
}

@media (max-width: 720px) {
  .filter-actions {
    flex-wrap: wrap;
  }

  .meta {
    width: 100%;
  }
}
</style>
