<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

const route = useRoute();

const navItems = [
  { label: '交易执行', to: '/trade' },
  { label: '监控终端', to: '/monitor' },
  { label: 'API 设置', to: '/settings/api' },
];

const pageHint = computed(() => {
  if (route.path.startsWith('/trade')) {
    return '模板驱动下单、风控动作与执行反馈';
  }
  if (route.path.startsWith('/monitor')) {
    return '实时查看仓位、订单与风险事件状态';
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
