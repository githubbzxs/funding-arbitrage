import { createRouter, createWebHistory } from 'vue-router';
import ApiSettingsPage from './pages/ApiSettingsPage.vue';
import MarketPage from './pages/MarketPage.vue';
import TradePage from './pages/TradePage.vue';
import TradeRedirectPage from './pages/TradeRedirectPage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'market',
      component: MarketPage
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
    },
    {
      path: '/trade/redirect',
      name: 'trade-redirect',
      component: TradeRedirectPage
    }
  ]
});

export default router;
