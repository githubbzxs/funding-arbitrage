import { createRouter, createWebHistory } from 'vue-router';
import ApiSettingsPage from './pages/ApiSettingsPage.vue';
import PairDetailPage from './pages/PairDetailPage.vue';
import ScannerPage from './pages/ScannerPage.vue';
import TradePage from './pages/TradePage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/scanner'
    },
    {
      path: '/scanner',
      name: 'scanner',
      component: ScannerPage
    },
    {
      path: '/scanner/:symbol/:long/:short',
      name: 'scanner-detail',
      component: PairDetailPage
    },
    {
      path: '/trade',
      name: 'trade',
      component: TradePage
    },
    {
      path: '/settings/api',
      name: 'settings-api',
      component: ApiSettingsPage
    }
  ]
});

export default router;
