<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { fetchOrders, fetchPositions, fetchRiskEvents, resolveRiskEvent } from '../api/records';
import type { OrderRecord, PositionRecord, RiskEventRecord } from '../types/market';

const refreshSeconds = ref(5);
const autoRefresh = ref(true);
const loading = ref(false);
const errorMessage = ref('');
const noticeMessage = ref('');
const positions = ref<PositionRecord[]>([]);
const orders = ref<OrderRecord[]>([]);
const riskEvents = ref<RiskEventRecord[]>([]);
const resolvedFilter = ref<'all' | 'unresolved'>('unresolved');

let timer: number | null = null;

function fmtDate(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('zh-CN');
}

const riskExposedPositions = computed(() =>
  positions.value.filter((item) => ['risk_exposed', 'open_failed', 'close_failed'].includes(item.status))
);

const unresolvedRiskEvents = computed(() => riskEvents.value.filter((item) => !item.resolved));

const alertLevel = computed<'danger' | 'warn' | 'ok'>(() => {
  if (riskExposedPositions.value.length > 0) {
    return 'danger';
  }
  const hasCritical = unresolvedRiskEvents.value.some((item) => item.severity === 'critical');
  if (hasCritical || unresolvedRiskEvents.value.length > 0) {
    return 'warn';
  }
  return 'ok';
});

const alertText = computed(() => {
  if (alertLevel.value === 'danger') {
    return `检测到 ${riskExposedPositions.value.length} 个高风险仓位（risk_exposed/open_failed/close_failed），请优先处理。`;
  }
  if (alertLevel.value === 'warn') {
    return `存在 ${unresolvedRiskEvents.value.length} 条未处理风险事件，请尽快确认。`;
  }
  return '当前未发现未处理高风险事件。';
});

const visibleRiskEvents = computed(() => {
  if (resolvedFilter.value === 'unresolved') {
    return riskEvents.value.filter((item) => !item.resolved);
  }
  return riskEvents.value;
});

async function loadMonitorData(): Promise<void> {
  loading.value = true;
  errorMessage.value = '';
  noticeMessage.value = '';
  try {
    const [nextPositions, nextOrders, nextRiskEvents] = await Promise.all([
      fetchPositions(500),
      fetchOrders(800),
      fetchRiskEvents({ limit: 500 }),
    ]);
    positions.value = nextPositions;
    orders.value = nextOrders;
    riskEvents.value = nextRiskEvents;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载监控数据失败';
  } finally {
    loading.value = false;
  }
}

function clearTimer(): void {
  if (timer !== null && typeof window !== 'undefined') {
    window.clearInterval(timer);
  }
  timer = null;
}

function setupTimer(): void {
  clearTimer();
  if (!autoRefresh.value || typeof window === 'undefined') {
    return;
  }
  timer = window.setInterval(() => {
    void loadMonitorData();
  }, refreshSeconds.value * 1000);
}

async function markRiskEventResolved(eventId: string): Promise<void> {
  noticeMessage.value = '';
  errorMessage.value = '';
  try {
    await resolveRiskEvent(eventId);
    await loadMonitorData();
    noticeMessage.value = '风险事件已标记为已处理。';
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '标记失败';
  }
}

watch([autoRefresh, refreshSeconds], () => {
  setupTimer();
});

onMounted(async () => {
  await loadMonitorData();
  setupTimer();
});

onBeforeUnmount(() => {
  clearTimer();
});
</script>

<template>
  <section class="monitor-page">
    <section class="toolbar">
      <div class="left">
        <h2>监控终端</h2>
        <p>仓位、订单、风险事件实时轮询</p>
      </div>
      <div class="right">
        <label class="switch">
          <input v-model="autoRefresh" type="checkbox" />
          <span>自动刷新</span>
        </label>
        <label class="field">
          <span>间隔</span>
          <select v-model.number="refreshSeconds" :disabled="!autoRefresh">
            <option :value="5">5 秒</option>
            <option :value="10">10 秒</option>
            <option :value="30">30 秒</option>
            <option :value="60">60 秒</option>
          </select>
        </label>
        <button type="button" class="ghost" :disabled="loading" @click="loadMonitorData">
          {{ loading ? '刷新中...' : '立即刷新' }}
        </button>
      </div>
    </section>

    <p class="alert" :class="alertLevel">{{ alertText }}</p>
    <p v-if="noticeMessage" class="notice ok">{{ noticeMessage }}</p>
    <p v-if="errorMessage" class="notice error">{{ errorMessage }}</p>

    <section class="grid">
      <article class="panel">
        <header class="panel-head">
          <h3>仓位 ({{ positions.length }})</h3>
        </header>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>币对</th>
                <th>套利腿</th>
                <th>状态</th>
                <th>模式</th>
                <th>开仓时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="positions.length === 0">
                <td colspan="6" class="empty">暂无仓位</td>
              </tr>
              <tr v-for="item in positions" :key="item.id">
                <td class="mono">{{ item.id }}</td>
                <td>{{ item.symbol }}</td>
                <td>{{ item.long_exchange }}/{{ item.short_exchange }}</td>
                <td>
                  <span class="status" :class="item.status">{{ item.status }}</span>
                </td>
                <td>{{ item.mode }}</td>
                <td>{{ fmtDate(item.opened_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel">
        <header class="panel-head">
          <h3>订单 ({{ orders.length }})</h3>
        </header>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>动作</th>
                <th>交易所</th>
                <th>币对</th>
                <th>方向</th>
                <th>状态</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="orders.length === 0">
                <td colspan="7" class="empty">暂无订单</td>
              </tr>
              <tr v-for="item in orders" :key="item.id">
                <td class="mono">{{ item.id }}</td>
                <td>{{ item.action }}</td>
                <td>{{ item.exchange }}</td>
                <td>{{ item.symbol }}</td>
                <td>{{ item.side }}</td>
                <td>
                  <span class="status" :class="item.status">{{ item.status }}</span>
                </td>
                <td>{{ fmtDate(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <article class="panel">
      <header class="panel-head risk-head">
        <h3>风险事件 ({{ visibleRiskEvents.length }})</h3>
        <label class="switch">
          <input
            :checked="resolvedFilter === 'all'"
            type="checkbox"
            @change="resolvedFilter = resolvedFilter === 'all' ? 'unresolved' : 'all'"
          />
          <span>显示已处理</span>
        </label>
      </header>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>类型</th>
              <th>级别</th>
              <th>消息</th>
              <th>状态</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="visibleRiskEvents.length === 0">
              <td colspan="7" class="empty">暂无风险事件</td>
            </tr>
            <tr v-for="item in visibleRiskEvents" :key="item.id">
              <td class="mono">{{ item.id }}</td>
              <td>{{ item.event_type }}</td>
              <td>
                <span class="severity" :class="item.severity">{{ item.severity }}</span>
              </td>
              <td>{{ item.message }}</td>
              <td>{{ item.resolved ? '已处理' : '未处理' }}</td>
              <td>{{ fmtDate(item.created_at) }}</td>
              <td>
                <button
                  v-if="!item.resolved"
                  type="button"
                  class="mini"
                  @click="markRiskEventResolved(item.id)"
                >
                  标记已处理
                </button>
                <span v-else class="resolved">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.monitor-page {
  display: grid;
  gap: 10px;
}

.toolbar {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  padding: 12px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.left h2 {
  margin: 0;
  font-size: 16px;
}

.left p {
  margin: 4px 0 0;
  color: var(--text-dim);
  font-size: 12px;
}

.right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field {
  display: grid;
  gap: 4px;
}

.field span {
  font-size: 12px;
  color: var(--text-dim);
}

.field select {
  border: 1px solid var(--line-soft);
  background: #111927;
  color: var(--text-main);
  height: 30px;
  padding: 0 8px;
  border-radius: 2px;
}

.ghost {
  border: 1px solid var(--line-soft);
  background: #131c28;
  color: var(--text-main);
  height: 30px;
  padding: 0 10px;
  border-radius: 2px;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}

.alert {
  margin: 0;
  border: 1px solid var(--line-soft);
  padding: 10px;
  font-size: 12px;
}

.alert.danger {
  border-color: rgba(239, 68, 68, 0.7);
  background: rgba(239, 68, 68, 0.12);
  color: #ffd3d3;
}

.alert.warn {
  border-color: rgba(245, 158, 11, 0.7);
  background: rgba(245, 158, 11, 0.12);
  color: #ffdfa6;
}

.alert.ok {
  border-color: rgba(16, 185, 129, 0.65);
  background: rgba(16, 185, 129, 0.1);
  color: #baf7dd;
}

.notice {
  margin: 0;
  border: 1px solid var(--line-soft);
  padding: 10px;
  font-size: 12px;
}

.notice.ok {
  border-color: rgba(16, 185, 129, 0.65);
  background: rgba(16, 185, 129, 0.1);
  color: #baf7dd;
}

.notice.error {
  border-color: rgba(239, 68, 68, 0.6);
  background: rgba(239, 68, 68, 0.1);
  color: #ffd3d3;
}

.grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.panel {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  overflow: hidden;
}

.panel-head {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line-soft);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-head h3 {
  margin: 0;
  font-size: 14px;
}

.table-wrap {
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 760px;
}

th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-soft);
  font-size: 12px;
  text-align: left;
  white-space: nowrap;
}

th {
  color: var(--text-dim);
  font-weight: 500;
}

.empty {
  color: var(--text-dim);
  text-align: center;
}

.mono {
  font-family: 'JetBrains Mono', 'Consolas', 'Menlo', monospace;
}

.status {
  padding: 2px 6px;
  border: 1px solid var(--line-soft);
  border-radius: 2px;
}

.status.risk_exposed,
.status.open_failed,
.status.close_failed,
.severity.critical {
  border-color: rgba(239, 68, 68, 0.7);
  color: #ffc6c6;
  background: rgba(239, 68, 68, 0.14);
}

.severity.high {
  border-color: rgba(245, 158, 11, 0.7);
  color: #ffdfa6;
  background: rgba(245, 158, 11, 0.14);
}

.mini {
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  height: 26px;
  padding: 0 8px;
  border-radius: 2px;
  font-size: 12px;
}

.resolved {
  color: var(--text-dim);
}

@media (max-width: 1024px) {
  .toolbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .right {
    flex-wrap: wrap;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
