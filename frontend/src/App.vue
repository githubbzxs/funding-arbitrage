<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

const route = useRoute();

const navItems = [
  { label: '行情机会', to: '/' },
  { label: '交易执行', to: '/trade' },
  { label: 'API 配置', to: '/settings/api' }
];

const pageHint = computed(() => {
  if (route.path.startsWith('/trade/redirect')) {
    return '正在跳转到交易所页面';
  }
  if (route.path.startsWith('/trade')) {
    return '交易执行与风控动作';
  }
  if (route.path.startsWith('/settings/api')) {
    return '后端托管 API 凭据配置';
  }
  return '跨交易所资金费率套利监控';
});
</script>

<template>
  <div class="app-shell">
    <header class="top-header">
      <div class="title-group">
        <h1>Funding Arbitrage Terminal</h1>
        <p>{{ pageHint }}</p>
      </div>

      <nav class="top-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: route.path === item.to }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </header>

    <main class="page-shell">
      <RouterView />
    </main>
  </div>
</template>
