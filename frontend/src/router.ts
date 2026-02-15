import { createRouter, createWebHistory } from 'vue-router';
import ApiSettingsPage from './pages/ApiSettingsPage.vue';
import MonitorPage from './pages/MonitorPage.vue';
import TradePage from './pages/TradePage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/trade',
    },
    {
      path: '/trade',
      name: 'trade',
      component: TradePage,
    },
    {
      path: '/monitor',
      name: 'monitor',
      component: MonitorPage,
    },
    {
      path: '/settings/api',
      name: 'settings-api',
      component: ApiSettingsPage,
    },
  ],
});

export default router;
