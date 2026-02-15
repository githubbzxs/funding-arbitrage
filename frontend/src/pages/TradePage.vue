<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { convertNotionalByBinance, executeAction } from '../api/execution';
import { fetchOrders, fetchPositions } from '../api/records';
import { createTemplate, deleteTemplate, fetchTemplates, updateTemplate } from '../api/templates';
import type {
  ExecutionAction,
  ExecutionRequest,
  StrategyTemplate,
  StrategyTemplatePayload,
  SupportedExchange,
} from '../types/market';

const EXCHANGE_OPTIONS: SupportedExchange[] = ['binance', 'okx', 'bybit', 'bitget', 'gateio'];
const ACTION_OPTIONS: Array<{ label: string; value: ExecutionAction }> = [
  { label: '预览', value: 'preview' },
  { label: '开仓', value: 'open' },
  { label: '平仓', value: 'close' },
  { label: '对冲', value: 'hedge' },
  { label: '紧急全平', value: 'emergency-close' },
];

type CredentialForm = {
  apiKey: string;
  apiSecret: string;
  passphrase: string;
  testnet: boolean;
};

const route = useRoute();
const router = useRouter();

const currentAction = ref<ExecutionAction>('open');
const busy = ref(false);
const errorMessage = ref('');
const resultText = ref('');
const convertBusy = ref(false);
const convertError = ref('');
const convertMessage = ref('');
const positionsCount = ref(0);
const ordersCount = ref(0);
const useManualCredentials = ref(false);

const templatesLoading = ref(false);
const templateBusy = ref(false);
const templateError = ref('');
const templateMessage = ref('');
const templates = ref<StrategyTemplate[]>([]);
const selectedTemplateId = ref('');
const templateName = ref('');

const form = reactive({
  symbol: '',
  longExchange: '' as SupportedExchange | '',
  shortExchange: '' as SupportedExchange | '',
  hedgeExchange: '' as SupportedExchange | '',
  hedgeSide: 'sell' as 'buy' | 'sell',
  quantity: 0.001,
  notionalUsd: 1000,
  leverage: 5,
  holdHours: 8,
  positionIdsText: '',
  note: '',
});

const longCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false,
});
const shortCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false,
});
const hedgeCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false,
});

function readQueryString(name: string): string {
  const raw = route.query[name];
  if (typeof raw === 'string') {
    return raw.trim();
  }
  if (Array.isArray(raw) && typeof raw[0] === 'string') {
    return raw[0].trim();
  }
  return '';
}

function normalizeAction(value: string): ExecutionAction {
  const candidates = new Set(ACTION_OPTIONS.map((item) => item.value));
  if (candidates.has(value as ExecutionAction)) {
    return value as ExecutionAction;
  }
  return 'open';
}

function hydrateFromRoute(): void {
  currentAction.value = normalizeAction(readQueryString('action').toLowerCase());
  form.symbol = readQueryString('symbol').toUpperCase() || form.symbol;
  form.longExchange = (readQueryString('long').toLowerCase() as SupportedExchange) || form.longExchange;
  form.shortExchange = (readQueryString('short').toLowerCase() as SupportedExchange) || form.shortExchange;
  form.hedgeExchange = form.longExchange || form.shortExchange || form.hedgeExchange;
}

function hasCredential(formValue: CredentialForm): boolean {
  return Boolean(formValue.apiKey.trim() && formValue.apiSecret.trim());
}

function toCredential(formValue: CredentialForm): Record<string, unknown> {
  return {
    api_key: formValue.apiKey.trim(),
    api_secret: formValue.apiSecret.trim(),
    passphrase: formValue.passphrase.trim() || undefined,
    testnet: formValue.testnet,
  };
}

function buildCredentialMap(action: ExecutionAction): Record<string, unknown> {
  if (!useManualCredentials.value) {
    return {};
  }
  const credentials: Record<string, unknown> = {};
  if (action === 'open' || action === 'close' || action === 'preview') {
    if (form.longExchange && hasCredential(longCredential)) {
      credentials[form.longExchange] = toCredential(longCredential);
    }
    if (form.shortExchange && hasCredential(shortCredential)) {
      credentials[form.shortExchange] = toCredential(shortCredential);
    }
    return credentials;
  }
  if (action === 'hedge' && form.hedgeExchange && hasCredential(hedgeCredential)) {
    credentials[form.hedgeExchange] = toCredential(hedgeCredential);
  }
  return credentials;
}

function parsePositionIds(): string[] | undefined {
  const list = form.positionIdsText
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
  return list.length > 0 ? list : undefined;
}

function buildPayload(): Record<string, unknown> {
  const action = currentAction.value;
  const credentials = buildCredentialMap(action);

  if (action === 'preview') {
    return {
      symbol: form.symbol,
      long_exchange: form.longExchange,
      short_exchange: form.shortExchange,
      notional_usd: form.notionalUsd,
      hold_hours: form.holdHours,
      taker_fee_bps: 6,
    };
  }

  if (action === 'open') {
    return {
      symbol: form.symbol,
      long_exchange: form.longExchange,
      short_exchange: form.shortExchange,
      quantity: form.quantity,
      leverage: form.leverage,
      credentials,
      note: form.note || undefined,
    };
  }

  if (action === 'close') {
    return {
      symbol: form.symbol,
      long_exchange: form.longExchange,
      short_exchange: form.shortExchange,
      quantity: form.quantity,
      leverage: form.leverage,
      credentials,
      note: form.note || undefined,
    };
  }

  if (action === 'hedge') {
    return {
      symbol: form.symbol,
      exchange: form.hedgeExchange,
      side: form.hedgeSide,
      quantity: form.quantity,
      leverage: form.leverage,
      credentials,
      reason: form.note || undefined,
    };
  }

  return {
    position_ids: parsePositionIds(),
    credentials,
  };
}

function applyTemplate(template: StrategyTemplate): void {
  form.symbol = template.symbol;
  form.longExchange = template.long_exchange;
  form.shortExchange = template.short_exchange;
  form.hedgeExchange = template.long_exchange;
  if (typeof template.quantity === 'number' && Number.isFinite(template.quantity)) {
    form.quantity = template.quantity;
  }
  if (typeof template.notional_usd === 'number' && Number.isFinite(template.notional_usd)) {
    form.notionalUsd = template.notional_usd;
  }
  if (typeof template.leverage === 'number' && Number.isFinite(template.leverage)) {
    form.leverage = template.leverage;
  }
  if (typeof template.hold_hours === 'number' && Number.isFinite(template.hold_hours)) {
    form.holdHours = template.hold_hours;
  }
  form.note = template.note ?? '';
  templateName.value = template.name;
}

function buildTemplatePayload(): StrategyTemplatePayload {
  const name = templateName.value.trim();
  if (!name) {
    throw new Error('请先填写模板名称');
  }
  if (!form.symbol.trim()) {
    throw new Error('请先填写币对后再保存模板');
  }
  if (!form.longExchange || !form.shortExchange) {
    throw new Error('请先选择多头与空头交易所后再保存模板');
  }

  return {
    name,
    symbol: form.symbol.toUpperCase(),
    long_exchange: form.longExchange,
    short_exchange: form.shortExchange,
    quantity: form.quantity,
    notional_usd: form.notionalUsd,
    leverage: form.leverage,
    hold_hours: form.holdHours,
    note: form.note || null,
  };
}

async function loadTemplates(): Promise<void> {
  templatesLoading.value = true;
  templateError.value = '';
  try {
    const next = await fetchTemplates();
    templates.value = next;

    if (selectedTemplateId.value) {
      const current = next.find((item) => item.id === selectedTemplateId.value);
      if (!current) {
        selectedTemplateId.value = '';
      }
    }
  } catch (error) {
    templateError.value = error instanceof Error ? error.message : '加载模板失败';
  } finally {
    templatesLoading.value = false;
  }
}

async function saveAsTemplate(): Promise<void> {
  templateError.value = '';
  templateMessage.value = '';
  templateBusy.value = true;
  try {
    const payload = buildTemplatePayload();
    const created = await createTemplate(payload);
    selectedTemplateId.value = created.id;
    await loadTemplates();
    templateMessage.value = '模板已创建';
  } catch (error) {
    templateError.value = error instanceof Error ? error.message : '创建模板失败';
  } finally {
    templateBusy.value = false;
  }
}

async function updateCurrentTemplate(): Promise<void> {
  if (!selectedTemplateId.value) {
    templateError.value = '请先选择一个模板再更新';
    return;
  }
  templateError.value = '';
  templateMessage.value = '';
  templateBusy.value = true;
  try {
    const payload = buildTemplatePayload();
    const updated = await updateTemplate(selectedTemplateId.value, payload);
    selectedTemplateId.value = updated.id;
    await loadTemplates();
    templateMessage.value = '模板已更新';
  } catch (error) {
    templateError.value = error instanceof Error ? error.message : '更新模板失败';
  } finally {
    templateBusy.value = false;
  }
}

async function removeCurrentTemplate(): Promise<void> {
  if (!selectedTemplateId.value) {
    templateError.value = '请先选择一个模板再删除';
    return;
  }
  templateError.value = '';
  templateMessage.value = '';
  templateBusy.value = true;
  try {
    await deleteTemplate(selectedTemplateId.value);
    selectedTemplateId.value = '';
    templateName.value = '';
    await loadTemplates();
    templateMessage.value = '模板已删除';
  } catch (error) {
    templateError.value = error instanceof Error ? error.message : '删除模板失败';
  } finally {
    templateBusy.value = false;
  }
}

function onTemplateSelect(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const templateId = target.value;
  selectedTemplateId.value = templateId;
  const template = templates.value.find((item) => item.id === templateId);
  if (template) {
    applyTemplate(template);
  }
}

async function refreshTradeData(): Promise<void> {
  try {
    const [positions, orders] = await Promise.all([fetchPositions(), fetchOrders()]);
    positionsCount.value = positions.length;
    ordersCount.value = orders.length;
  } catch {
    positionsCount.value = 0;
    ordersCount.value = 0;
  }
}

async function convertQuantityByBinance(): Promise<void> {
  convertError.value = '';
  convertMessage.value = '';

  const symbol = form.symbol.trim().toUpperCase();
  if (!symbol) {
    convertError.value = '请先填写币对后再换算';
    return;
  }
  if (!Number.isFinite(form.notionalUsd) || form.notionalUsd <= 0) {
    convertError.value = '请输入有效的名义金额';
    return;
  }

  convertBusy.value = true;
  try {
    const result = await convertNotionalByBinance(symbol, form.notionalUsd);
    form.quantity = result.quantity;
    convertMessage.value = `已按 Binance 标记价 ${result.mark_price.toFixed(6)} 换算，数量 ${result.quantity.toFixed(8)}`;
  } catch (error) {
    convertError.value = error instanceof Error ? error.message : '换算失败';
  } finally {
    convertBusy.value = false;
  }
}

async function onSubmit(): Promise<void> {
  errorMessage.value = '';
  resultText.value = '';
  busy.value = true;
  const request: ExecutionRequest = {
    action: currentAction.value,
    payload: buildPayload(),
  };
  try {
    const result = await executeAction(request.action, request.payload);
    resultText.value = JSON.stringify(result, null, 2);
    await refreshTradeData();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '执行失败';
  } finally {
    busy.value = false;
  }
}

const selectedPairHint = computed(() => {
  if (!form.longExchange || !form.shortExchange) {
    return '-';
  }
  return `${form.longExchange} / ${form.shortExchange}`;
});

watch(
  () => route.fullPath,
  () => {
    hydrateFromRoute();
  },
  { immediate: true }
);

onMounted(async () => {
  await Promise.all([refreshTradeData(), loadTemplates()]);
});
</script>

<template>
  <section class="terminal">
    <header class="panel-head">
      <div>
        <h2>套利执行终端</h2>
        <p>集中输入关键参数，执行与反馈同屏闭环</p>
      </div>
      <div class="head-actions">
        <button type="button" class="ghost" @click="router.push('/monitor')">监控页</button>
        <button type="button" class="ghost" @click="router.push('/settings/api')">API 设置</button>
      </div>
    </header>

    <div class="terminal-grid">
      <section class="main-pane">
        <article class="card action-card">
          <div class="action-tabs">
            <button
              v-for="option in ACTION_OPTIONS"
              :key="option.value"
              type="button"
              class="tab"
              :class="{ active: option.value === currentAction }"
              @click="currentAction = option.value"
            >
              {{ option.label }}
            </button>
          </div>

          <div class="form-grid">
            <label>
              <span>币对</span>
              <input v-model.trim="form.symbol" placeholder="例如 BTCUSDT" />
            </label>

            <label v-if="currentAction !== 'hedge'">
              <span>多头交易所</span>
              <select v-model="form.longExchange">
                <option value="">请选择</option>
                <option v-for="exchange in EXCHANGE_OPTIONS" :key="exchange" :value="exchange">
                  {{ exchange }}
                </option>
              </select>
            </label>

            <label v-if="currentAction !== 'hedge'">
              <span>空头交易所</span>
              <select v-model="form.shortExchange">
                <option value="">请选择</option>
                <option v-for="exchange in EXCHANGE_OPTIONS" :key="exchange" :value="exchange">
                  {{ exchange }}
                </option>
              </select>
            </label>

            <label v-if="currentAction === 'hedge'">
              <span>对冲交易所</span>
              <select v-model="form.hedgeExchange">
                <option value="">请选择</option>
                <option v-for="exchange in EXCHANGE_OPTIONS" :key="exchange" :value="exchange">
                  {{ exchange }}
                </option>
              </select>
            </label>

            <label v-if="currentAction === 'hedge'">
              <span>方向</span>
              <select v-model="form.hedgeSide">
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
            </label>

            <label v-if="currentAction !== 'preview' && currentAction !== 'emergency-close'">
              <span>数量</span>
              <input v-model.number="form.quantity" type="number" min="0.000001" step="0.000001" />
            </label>

            <label v-if="currentAction === 'preview'">
              <span>名义金额 (USD)</span>
              <input v-model.number="form.notionalUsd" type="number" min="10" step="10" />
            </label>

            <label v-if="currentAction === 'preview'">
              <span>持仓小时</span>
              <input v-model.number="form.holdHours" type="number" min="1" step="1" />
            </label>

            <label v-if="currentAction !== 'emergency-close'">
              <span>杠杆</span>
              <input v-model.number="form.leverage" type="number" min="1" step="1" />
            </label>

            <label v-if="currentAction === 'emergency-close'" class="full">
              <span>指定仓位 ID（逗号分隔，可空）</span>
              <input v-model.trim="form.positionIdsText" placeholder="例如 id1,id2,id3" />
            </label>

            <label class="full">
              <span>备注</span>
              <textarea v-model.trim="form.note" rows="2" placeholder="可选" />
            </label>
          </div>

          <div v-if="currentAction !== 'preview' && currentAction !== 'emergency-close'" class="convert-box">
            <p class="convert-title">名义金额换算（统一使用 Binance 标记价格）</p>
            <div class="convert-grid">
              <label>
                <span>名义金额 (USD)</span>
                <input v-model.number="form.notionalUsd" type="number" min="10" step="10" />
              </label>
              <button type="button" class="mini" :disabled="convertBusy" @click="convertQuantityByBinance">
                {{ convertBusy ? '换算中...' : '换算为数量' }}
              </button>
            </div>
            <p v-if="convertError" class="feedback error">{{ convertError }}</p>
            <p v-if="convertMessage" class="feedback ok">{{ convertMessage }}</p>
          </div>

          <button type="button" class="submit" :disabled="busy" @click="onSubmit">
            {{ busy ? '执行中...' : '执行动作' }}
          </button>

          <p v-if="errorMessage" class="feedback error">{{ errorMessage }}</p>
          <pre v-if="resultText" class="feedback result">{{ resultText }}</pre>
        </article>
      </section>

      <aside class="side-pane">
        <article class="card summary-card">
          <div class="summary-row">
            <span>仓位</span>
            <strong>{{ positionsCount }}</strong>
          </div>
          <div class="summary-row">
            <span>订单</span>
            <strong>{{ ordersCount }}</strong>
          </div>
          <div class="summary-row">
            <span>当前币对</span>
            <strong>{{ form.symbol || '-' }}</strong>
          </div>
          <div class="summary-row">
            <span>套利腿</span>
            <strong>{{ selectedPairHint }}</strong>
          </div>
          <div class="summary-row">
            <span>凭据来源</span>
            <strong>{{ useManualCredentials ? '手动覆盖' : '后端托管' }}</strong>
          </div>
        </article>

        <article class="card template-card">
          <div class="template-head">
            <h3>策略模板</h3>
            <button type="button" class="ghost" :disabled="templatesLoading" @click="loadTemplates">
              {{ templatesLoading ? '刷新中...' : '刷新' }}
            </button>
          </div>

          <div class="template-grid">
            <label>
              <span>选择模板</span>
              <select :value="selectedTemplateId" @change="onTemplateSelect">
                <option value="">请选择模板</option>
                <option v-for="item in templates" :key="item.id" :value="item.id">
                  {{ item.name }} ({{ item.symbol }} | {{ item.long_exchange }}/{{ item.short_exchange }})
                </option>
              </select>
            </label>

            <label>
              <span>模板名称</span>
              <input v-model.trim="templateName" placeholder="例如 BTC_跨所_8h" />
            </label>
          </div>

          <div class="template-actions">
            <button type="button" class="mini" :disabled="templateBusy" @click="saveAsTemplate">另存</button>
            <button type="button" class="mini" :disabled="templateBusy || !selectedTemplateId" @click="updateCurrentTemplate">更新</button>
            <button type="button" class="mini danger" :disabled="templateBusy || !selectedTemplateId" @click="removeCurrentTemplate">删除</button>
          </div>

          <p v-if="templateError" class="feedback error">{{ templateError }}</p>
          <p v-if="templateMessage" class="feedback ok">{{ templateMessage }}</p>
        </article>

        <article class="card credential-card">
          <div class="row-inline">
            <h3>本次手动凭据（可选）</h3>
            <label class="switch">
              <input v-model="useManualCredentials" type="checkbox" />
              <span>启用</span>
            </label>
          </div>
          <p class="credential-tip">默认使用后端托管凭据；启用后优先使用本次填写的凭据覆盖。</p>

          <div v-if="useManualCredentials" class="credential-grid">
            <div class="credential-item">
              <h4>多头交易所</h4>
              <input v-model.trim="longCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="longCredential.apiSecret" type="password" placeholder="API Secret" />
              <input v-model.trim="longCredential.passphrase" type="password" placeholder="Passphrase（如有）" />
              <label class="switch">
                <input v-model="longCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
            <div class="credential-item">
              <h4>空头交易所</h4>
              <input v-model.trim="shortCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="shortCredential.apiSecret" type="password" placeholder="API Secret" />
              <input v-model.trim="shortCredential.passphrase" type="password" placeholder="Passphrase（如有）" />
              <label class="switch">
                <input v-model="shortCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
            <div class="credential-item">
              <h4>对冲交易所</h4>
              <input v-model.trim="hedgeCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="hedgeCredential.apiSecret" type="password" placeholder="API Secret" />
              <input v-model.trim="hedgeCredential.passphrase" type="password" placeholder="Passphrase（如有）" />
              <label class="switch">
                <input v-model="hedgeCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
          </div>
        </article>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.terminal {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--line-soft);
  padding: 12px;
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
}

.panel-head p {
  margin: 4px 0 0;
  color: var(--text-dim);
  font-size: 12px;
}

.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-grid {
  display: grid;
  gap: 12px;
  padding: 12px;
  grid-template-columns: minmax(0, 1.5fr) minmax(320px, 1fr);
  align-items: start;
}

.main-pane,
.side-pane {
  display: grid;
  gap: 12px;
}

.card {
  border: 1px solid var(--line-soft);
  background: #0d1522;
  padding: 10px;
  display: grid;
  gap: 10px;
}

.ghost {
  height: 28px;
  border: 1px solid var(--line-soft);
  background: #131c28;
  color: var(--text-main);
  border-radius: 2px;
  padding: 0 10px;
}

.ghost:hover {
  border-color: var(--accent);
}

.action-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tab {
  border: 1px solid var(--line-soft);
  background: #111822;
  color: var(--text-dim);
  height: 28px;
  padding: 0 10px;
  border-radius: 2px;
  font-size: 12px;
}

.tab.active {
  border-color: var(--accent);
  color: var(--accent-soft);
}

.form-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.form-grid label,
.template-grid label {
  display: grid;
  gap: 6px;
}

.form-grid span,
.template-grid span {
  font-size: 12px;
  color: var(--text-dim);
}

.form-grid input,
.form-grid select,
.form-grid textarea,
.template-grid input,
.template-grid select,
.credential-item input {
  width: 100%;
  border: 1px solid var(--line-soft);
  background: #111927;
  color: var(--text-main);
  border-radius: 2px;
  padding: 7px 10px;
  outline: none;
  font-size: 13px;
  font-family: inherit;
}

.form-grid input:focus,
.form-grid select:focus,
.form-grid textarea:focus,
.template-grid input:focus,
.template-grid select:focus,
.credential-item input:focus {
  border-color: var(--accent);
}

.full {
  grid-column: 1 / -1;
}

.convert-box {
  border: 1px solid var(--line-soft);
  background: #101823;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.convert-title {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}

.convert-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
}

.submit {
  height: 36px;
  border: 1px solid rgba(0, 199, 166, 0.9);
  background: rgba(0, 199, 166, 0.94);
  color: #052119;
  border-radius: 2px;
  font-size: 13px;
  font-weight: 700;
}

.submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.summary-card {
  gap: 8px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  font-size: 12px;
}

.summary-row span {
  color: var(--text-dim);
}

.summary-row strong {
  text-align: right;
}

.template-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.template-head h3 {
  margin: 0;
  font-size: 14px;
}

.template-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr;
}

.template-actions {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.mini {
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  background: #131c28;
  color: var(--text-main);
  border-radius: 2px;
  font-size: 12px;
}

.mini.danger {
  border-color: rgba(239, 68, 68, 0.6);
  background: rgba(239, 68, 68, 0.08);
  color: #ffd0d0;
}

.row-inline {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.row-inline h3 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.credential-tip {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}

.credential-grid {
  display: grid;
  gap: 8px;
}

.credential-item {
  border: 1px solid var(--line-soft);
  background: #101722;
  padding: 8px;
  display: grid;
  gap: 8px;
}

.credential-item h4 {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
  font-weight: 500;
}

.switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}

.switch input {
  width: 14px;
  height: 14px;
  margin: 0;
}

.feedback {
  margin: 0;
  border: 1px solid var(--line-soft);
  background: #0d141e;
  padding: 8px 10px;
  font-size: 12px;
  overflow-x: auto;
}

.feedback.error {
  border-color: rgba(239, 68, 68, 0.6);
  background: rgba(239, 68, 68, 0.1);
  color: #ffd3d3;
}

.feedback.ok {
  border-color: rgba(16, 185, 129, 0.65);
  background: rgba(16, 185, 129, 0.12);
  color: #baf7dd;
}

.feedback.result {
  color: #b8f5e8;
}

@media (max-width: 1250px) {
  .terminal-grid {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .template-actions {
    grid-template-columns: 1fr;
  }

  .convert-grid {
    grid-template-columns: 1fr;
  }
}
</style>
