import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query';
import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './styles.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false
    }
  }
});

createApp(App).use(router).use(VueQueryPlugin, { queryClient }).mount('#app');
