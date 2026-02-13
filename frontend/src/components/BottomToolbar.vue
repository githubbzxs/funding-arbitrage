<script setup lang="ts">
const props = defineProps<{
  autoRefresh: boolean;
  refreshSeconds: number;
  language: string;
}>();

const emit = defineEmits<{
  'update:autoRefresh': [boolean];
  'update:refreshSeconds': [number];
  'update:language': [string];
  refresh: [];
}>();

function toggleAutoRefresh(): void {
  emit('update:autoRefresh', !props.autoRefresh);
}

function onRefreshSecondsChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  emit('update:refreshSeconds', Number(target.value));
}

function onLanguageChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  emit('update:language', target.value);
}
</script>

<template>
  <footer class="bottom-toolbar">
    <a href="https://developers.binance.com/docs/derivatives" target="_blank" rel="noreferrer">文档</a>
    <a href="https://t.me/" target="_blank" rel="noreferrer">电报群</a>
    <a href="#" target="_blank" rel="noreferrer">浏览器插件</a>

    <label>
      <span>语言</span>
      <select :value="language" @change="onLanguageChange">
        <option value="zh-CN">简体中文</option>
        <option value="en-US">English</option>
      </select>
    </label>

    <label>
      <span>刷新频率</span>
      <select :value="refreshSeconds" @change="onRefreshSecondsChange">
        <option :value="5">5秒</option>
        <option :value="10">10秒</option>
        <option :value="15">15秒</option>
        <option :value="30">30秒</option>
      </select>
    </label>

    <button type="button" class="toggle" :class="{ active: autoRefresh }" @click="toggleAutoRefresh">
      {{ autoRefresh ? '自动刷新: 开' : '自动刷新: 关' }}
    </button>
    <button type="button" class="toggle" @click="$emit('refresh')">立即刷新</button>
  </footer>
</template>

<style scoped>
.bottom-toolbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  border-top: 1px solid var(--line-strong);
  background: #070c13;
  min-height: 42px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  z-index: 25;
  overflow-x: auto;
}

.bottom-toolbar a {
  color: var(--text-dim);
  text-decoration: none;
  font-size: 12px;
  white-space: nowrap;
}

.bottom-toolbar a:hover {
  color: var(--accent-soft);
}

label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
  font-size: 12px;
  white-space: nowrap;
}

select {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  border-radius: 2px;
  height: 26px;
  padding: 0 8px;
}

.toggle {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  height: 26px;
  border-radius: 2px;
  font-size: 12px;
  padding: 0 10px;
  white-space: nowrap;
}

.toggle.active {
  border-color: var(--accent);
  color: var(--accent-soft);
}
</style>
