<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

const route = useRoute();

const navItems = [
  { label: '扫描看板', to: '/scanner' },
  { label: '交易执行', to: '/trade' },
  { label: 'API设置', to: '/settings/api' }
];

const pageHint = computed(() => {
  if (route.path.startsWith('/scanner/')) {
    return '机会详情与交易入口';
  }
  if (route.path.startsWith('/scanner')) {
    return '跨交易所资金费率机会扫描';
  }
  if (route.path.startsWith('/trade')) {
    return '下单执行与风险控制';
  }
  if (route.path.startsWith('/settings/api')) {
    return '后端托管 API 凭据管理';
  }
  return 'Funding Arbitrage Terminal';
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
          :class="{ active: route.path === item.to || route.path.startsWith(`${item.to}/`) }"
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
