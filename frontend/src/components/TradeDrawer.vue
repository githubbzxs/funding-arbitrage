<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import type { ExecutionAction, ExecutionRequest, MarketRow } from '../types/market';
import { formatPercent } from '../utils/format';
import { deleteCredential, fetchCredentialStatuses, upsertCredential, type CredentialStatus } from '../api/credentials';

const props = defineProps<{
  open: boolean;
  market: MarketRow | null;
  initialAction: ExecutionAction;
  exchanges: string[];
  positionsCount: number;
  ordersCount: number;
  busy: boolean;
  errorMessage: string;
  resultText: string;
}>();

const emit = defineEmits<{
  close: [];
  execute: [ExecutionRequest];
}>();

type CredentialForm = {
  apiKey: string;
  apiSecret: string;
  passphrase: string;
  testnet: boolean;
};

type StoredCredentialForm = {
  exchange: string;
  configured: boolean;
  apiKeyMasked: string;
  updatedAt: string;
  apiKey: string;
  apiSecret: string;
  passphrase: string;
  testnet: boolean;
  saving: boolean;
  error: string;
};

const actionOptions: Array<{ label: string; value: ExecutionAction }> = [
  { label: '预览', value: 'preview' },
  { label: '开仓', value: 'open' },
  { label: '平仓', value: 'close' },
  { label: '一键对冲', value: 'hedge' },
  { label: '紧急全平', value: 'emergency-close' }
];

const currentAction = ref<ExecutionAction>(props.initialAction);
const form = reactive({
  mode: 'manual' as 'manual' | 'auto',
  symbol: '',
  longExchange: '',
  shortExchange: '',
  hedgeExchange: '',
  hedgeSide: 'sell' as 'buy' | 'sell',
  quantity: 1,
  notionalUsd: 1000,
  leverage: 5,
  holdHours: 8,
  positionIdsText: '',
  note: ''
});

const longCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false
});
const shortCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false
});
const hedgeCredential = reactive<CredentialForm>({
  apiKey: '',
  apiSecret: '',
  passphrase: '',
  testnet: false
});

const selectedPairHint = computed(() => {
  if (!props.market?.longExchange || !props.market?.shortExchange) {
    return '当前行不是套利对，请先在表格中选中一条套利机会。';
  }
  return `${props.market.longExchange} / ${props.market.shortExchange}`;
});

const usableExchanges = computed(() => props.exchanges.filter((item) => item && !item.includes('/')));

const storedError = ref('');
const storedForms = ref<StoredCredentialForm[]>([]);

function ensureStoredForms(): void {
  const existing = new Map(storedForms.value.map((item) => [item.exchange, item]));
  storedForms.value = usableExchanges.value.map((exchange) => {
    const prev = existing.get(exchange);
    if (prev) {
      return prev;
    }
    return {
      exchange,
      configured: false,
      apiKeyMasked: '-',
      updatedAt: '',
      apiKey: '',
      apiSecret: '',
      passphrase: '',
      testnet: false,
      saving: false,
      error: ''
    };
  });
}

function applyStatuses(statuses: CredentialStatus[]): void {
  const map = new Map(statuses.filter((item) => item.exchange).map((item) => [item.exchange, item]));
  storedForms.value.forEach((form) => {
    const status = map.get(form.exchange);
    if (!status) {
      form.configured = false;
      form.apiKeyMasked = '-';
      form.updatedAt = '';
      return;
    }
    form.configured = Boolean(status.configured);
    form.apiKeyMasked = status.api_key_masked ?? '-';
    form.updatedAt = status.updated_at ?? '';
    if (typeof status.testnet === 'boolean') {
      form.testnet = status.testnet;
    }
  });
}

async function refreshStoredStatuses(): Promise<void> {
  storedError.value = '';
  try {
    const statuses = await fetchCredentialStatuses();
    applyStatuses(statuses);
  } catch (error) {
    storedError.value = error instanceof Error ? error.message : '加载托管凭据失败';
  }
}

async function saveStored(formValue: StoredCredentialForm): Promise<void> {
  formValue.error = '';
  const apiKey = formValue.apiKey.trim();
  const apiSecret = formValue.apiSecret.trim();
  const passphrase = formValue.passphrase.trim();

  if (!apiKey || !apiSecret) {
    formValue.error = '请填写 API Key 与 API Secret';
    return;
  }

  formValue.saving = true;
  try {
    await upsertCredential(formValue.exchange, {
      api_key: apiKey,
      api_secret: apiSecret,
      passphrase: passphrase || undefined,
      testnet: formValue.testnet
    });
    formValue.apiKey = '';
    formValue.apiSecret = '';
    formValue.passphrase = '';
    await refreshStoredStatuses();
  } catch (error) {
    formValue.error = error instanceof Error ? error.message : '保存失败';
  } finally {
    formValue.saving = false;
  }
}

async function removeStored(formValue: StoredCredentialForm): Promise<void> {
  formValue.error = '';
  formValue.saving = true;
  try {
    await deleteCredential(formValue.exchange);
    await refreshStoredStatuses();
  } catch (error) {
    formValue.error = error instanceof Error ? error.message : '删除失败';
  } finally {
    formValue.saving = false;
  }
}

watch(
  () => props.initialAction,
  (next) => {
    currentAction.value = next;
  }
);

watch(
  () => props.market,
  (market) => {
    if (!market) {
      return;
    }
    form.symbol = market.symbol || form.symbol;
    form.longExchange = market.longExchange || form.longExchange;
    form.shortExchange = market.shortExchange || form.shortExchange;
    form.hedgeExchange = market.longExchange || market.shortExchange || form.hedgeExchange;
    form.notionalUsd = Math.max(100, Math.floor(market.volume24hUsd / 10000) * 100 || form.notionalUsd);
    const maxLev = market.maxUsableLeverage ?? market.maxLeverage;
    if (typeof maxLev === 'number' && Number.isFinite(maxLev) && maxLev > 0) {
      form.leverage = Math.max(1, Math.min(Math.floor(maxLev), form.leverage));
    }
  },
  { immediate: true }
);

function selectAction(action: ExecutionAction): void {
  currentAction.value = action;
}

function hasCredential(formValue: CredentialForm): boolean {
  return Boolean(formValue.apiKey.trim() && formValue.apiSecret.trim());
}

function toCredential(formValue: CredentialForm): Record<string, unknown> {
  return {
    api_key: formValue.apiKey.trim(),
    api_secret: formValue.apiSecret.trim(),
    passphrase: formValue.passphrase.trim() || undefined,
    testnet: formValue.testnet
  };
}

function buildCredentialMap(action: ExecutionAction): Record<string, unknown> {
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
      taker_fee_bps: 6
    };
  }

  if (action === 'open') {
    return {
      mode: form.mode,
      symbol: form.symbol,
      long_exchange: form.longExchange,
      short_exchange: form.shortExchange,
      quantity: form.quantity,
      leverage: form.leverage,
      notional_usd: form.notionalUsd,
      credentials,
      note: form.note || undefined
    };
  }

  if (action === 'close') {
    return {
      mode: form.mode,
      symbol: form.symbol,
      long_exchange: form.longExchange,
      short_exchange: form.shortExchange,
      long_quantity: form.quantity,
      short_quantity: form.quantity,
      credentials,
      note: form.note || undefined
    };
  }

  if (action === 'hedge') {
    return {
      mode: form.mode,
      symbol: form.symbol,
      exchange: form.hedgeExchange,
      side: form.hedgeSide,
      quantity: form.quantity,
      leverage: form.leverage,
      credentials,
      reason: form.note || undefined
    };
  }

  return {
    mode: form.mode,
    position_ids: parsePositionIds(),
    credentials: buildCredentialMap('hedge')
  };
}

function onSubmit(): void {
  emit('execute', {
    action: currentAction.value,
    payload: buildPayload()
  });
}

watch(usableExchanges, ensureStoredForms, { immediate: true });
watch(
  () => props.open,
  (open) => {
    if (open) {
      ensureStoredForms();
      void refreshStoredStatuses();
    }
  },
  { immediate: true }
);
</script>

<template>
  <div class="drawer-wrapper" :class="{ open }">
    <div class="mask" @click="$emit('close')" />
    <aside class="drawer">
      <header class="drawer-header">
        <div>
          <h2>交易控制台</h2>
          <p>仓位：{{ positionsCount }} ｜ 订单：{{ ordersCount }}</p>
        </div>
        <button type="button" class="close-button" @click="$emit('close')">关闭</button>
      </header>

      <section class="selected-card">
        <div class="row">
          <span>当前币对</span>
          <strong>{{ market?.symbol || '-' }}</strong>
        </div>
        <div class="row">
          <span>套利腿</span>
          <strong>{{ selectedPairHint }}</strong>
        </div>
        <div class="row">
          <span>名义年化(杠杆后)</span>
          <strong>{{ formatPercent(market?.leveragedNominalApr ?? market?.nominalApr, 2) }}</strong>
        </div>
      </section>

      <section class="actions-panel">
        <div class="action-tabs">
          <button
            v-for="option in actionOptions"
            :key="option.value"
            type="button"
            class="tab"
            :class="{ active: option.value === currentAction }"
            @click="selectAction(option.value)"
          >
            {{ option.label }}
          </button>
        </div>

        <div class="form-grid">
          <label>
            <span>执行模式</span>
            <select v-model="form.mode">
              <option value="manual">手动确认</option>
              <option value="auto">自动执行</option>
            </select>
          </label>

          <label>
            <span>币对</span>
            <input v-model.trim="form.symbol" placeholder="例如 BTCUSDT" />
          </label>

          <label v-if="currentAction !== 'hedge'">
            <span>多头交易所</span>
            <select v-model="form.longExchange">
              <option value="">请选择</option>
              <option v-for="exchange in usableExchanges" :key="exchange" :value="exchange">
                {{ exchange }}
              </option>
            </select>
          </label>

          <label v-if="currentAction !== 'hedge'">
            <span>空头交易所</span>
            <select v-model="form.shortExchange">
              <option value="">请选择</option>
              <option v-for="exchange in usableExchanges" :key="exchange" :value="exchange">
                {{ exchange }}
              </option>
            </select>
          </label>

          <label v-if="currentAction === 'hedge'">
            <span>对冲交易所</span>
            <select v-model="form.hedgeExchange">
              <option value="">请选择</option>
              <option v-for="exchange in usableExchanges" :key="exchange" :value="exchange">
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

          <label v-if="currentAction === 'preview' || currentAction === 'open'">
            <span>名义金额 (USD)</span>
            <input v-model.number="form.notionalUsd" type="number" min="10" step="10" />
          </label>

          <label v-if="currentAction !== 'preview' && currentAction !== 'emergency-close'">
            <span>数量</span>
            <input v-model.number="form.quantity" type="number" min="0.001" step="0.001" />
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
            <span>指定仓位ID（逗号分隔，可空）</span>
            <input v-model.trim="form.positionIdsText" placeholder="如：id1,id2,id3" />
          </label>

          <label class="full">
            <span>备注</span>
            <textarea v-model.trim="form.note" rows="2" placeholder="可选" />
          </label>
        </div>

        <details class="credential-card">
          <summary>统一 API 凭据管理（后端加密托管）</summary>
          <p class="credential-tip">
            保存后会加密存储在后端数据库中，页面不会展示 Secret 明文；自动模式下可以不填写“本次覆盖”直接下单。
          </p>
          <p v-if="storedError" class="feedback error">{{ storedError }}</p>

          <div class="credential-grid">
            <div v-for="item in storedForms" :key="item.exchange" class="credential-item">
              <div class="credential-head">
                <h4>{{ item.exchange }}</h4>
                <small class="status" :class="{ ok: item.configured }">
                  {{ item.configured ? `已配置 ${item.apiKeyMasked}` : '未配置' }}
                </small>
              </div>

              <input v-model.trim="item.apiKey" placeholder="API Key" />
              <input v-model.trim="item.apiSecret" type="password" placeholder="API Secret" />
              <input v-model.trim="item.passphrase" type="password" placeholder="Passphrase（如有）" />
              <label class="checkbox">
                <input v-model="item.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>

              <div class="credential-actions">
                <button type="button" class="mini" :disabled="item.saving" @click="saveStored(item)">
                  {{ item.saving ? '保存中...' : '保存' }}
                </button>
                <button
                  type="button"
                  class="mini danger"
                  :disabled="item.saving || !item.configured"
                  @click="removeStored(item)"
                >
                  删除
                </button>
              </div>

              <p v-if="item.error" class="feedback error">{{ item.error }}</p>
            </div>
          </div>
        </details>

        <details class="credential-card">
          <summary>本次请求覆盖凭据（可选，优先于后端托管）</summary>
          <div class="credential-grid">
            <div class="credential-item">
              <h4>多头交易所凭据</h4>
              <input v-model.trim="longCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="longCredential.apiSecret" placeholder="API Secret" />
              <input v-model.trim="longCredential.passphrase" placeholder="Passphrase（如有）" />
              <label class="checkbox">
                <input v-model="longCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
            <div class="credential-item">
              <h4>空头交易所凭据</h4>
              <input v-model.trim="shortCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="shortCredential.apiSecret" placeholder="API Secret" />
              <input v-model.trim="shortCredential.passphrase" placeholder="Passphrase（如有）" />
              <label class="checkbox">
                <input v-model="shortCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
            <div class="credential-item">
              <h4>对冲交易所凭据</h4>
              <input v-model.trim="hedgeCredential.apiKey" placeholder="API Key" />
              <input v-model.trim="hedgeCredential.apiSecret" placeholder="API Secret" />
              <input v-model.trim="hedgeCredential.passphrase" placeholder="Passphrase（如有）" />
              <label class="checkbox">
                <input v-model="hedgeCredential.testnet" type="checkbox" />
                <span>Testnet</span>
              </label>
            </div>
          </div>
        </details>

        <button type="button" class="submit" :disabled="busy" @click="onSubmit">
          {{ busy ? '执行中...' : '执行动作' }}
        </button>
        <p v-if="errorMessage" class="feedback error">{{ errorMessage }}</p>
        <pre v-if="resultText" class="feedback result">{{ resultText }}</pre>
      </section>
    </aside>
  </div>
</template>

<style scoped>
.drawer-wrapper {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 30;
}

.drawer-wrapper.open {
  pointer-events: auto;
}

.mask {
  position: absolute;
  inset: 0;
  background: rgba(3, 7, 11, 0);
  transition: background 0.24s ease;
}

.drawer-wrapper.open .mask {
  background: rgba(3, 7, 11, 0.65);
}

.drawer {
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  width: 480px;
  max-width: 100%;
  background: #0a1119;
  border-left: 1px solid var(--line-strong);
  transform: translateX(105%);
  transition: transform 0.24s ease;
  display: grid;
  grid-template-rows: auto auto 1fr;
}

.drawer-wrapper.open .drawer {
  transform: translateX(0);
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--line-soft);
  padding: 14px;
}

.drawer-header h2 {
  margin: 0;
  font-size: 16px;
}

.drawer-header p {
  margin: 4px 0 0;
  color: var(--text-dim);
  font-size: 12px;
}

.close-button {
  align-self: start;
  border: 1px solid var(--line-soft);
  background: #131c28;
  color: var(--text-main);
  height: 28px;
  border-radius: 2px;
  padding: 0 10px;
}

.close-button:hover {
  border-color: var(--accent);
}

.selected-card {
  border-bottom: 1px solid var(--line-soft);
  padding: 14px;
  display: grid;
  gap: 8px;
}

.selected-card .row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  gap: 12px;
}

.selected-card span {
  color: var(--text-dim);
}

.selected-card strong {
  color: var(--text-main);
  text-align: right;
}

.actions-panel {
  overflow-y: auto;
  padding: 14px;
  display: grid;
  gap: 12px;
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
  grid-template-columns: 1fr 1fr;
}

.form-grid label {
  display: grid;
  gap: 6px;
}

.form-grid span {
  font-size: 12px;
  color: var(--text-dim);
}

.form-grid input,
.form-grid select,
.form-grid textarea {
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
.form-grid textarea:focus {
  border-color: var(--accent);
}

.full {
  grid-column: 1 / -1;
}

.credential-card {
  border: 1px solid var(--line-soft);
  border-radius: 2px;
  padding: 8px;
  background: #0d141e;
}

.credential-card summary {
  cursor: pointer;
  color: var(--text-main);
  font-size: 12px;
}

.credential-tip {
  margin: 8px 0 0;
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.4;
}

.credential-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.status {
  font-size: 11px;
  color: var(--text-dim);
}

.status.ok {
  color: var(--success);
}

.credential-actions {
  display: flex;
  gap: 8px;
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

.mini:hover {
  border-color: var(--accent);
}

.mini.danger {
  border-color: rgba(239, 68, 68, 0.6);
  background: rgba(239, 68, 68, 0.08);
  color: #ffd0d0;
}

.mini.danger:hover {
  border-color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.12);
}

.credential-grid {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.credential-item {
  border: 1px solid var(--line-soft);
  background: #101722;
  padding: 10px;
  display: grid;
  gap: 8px;
}

.credential-item h4 {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
  font-weight: 500;
}

.checkbox {
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-dim);
}

.checkbox input {
  width: 14px;
  height: 14px;
  margin: 0;
}

.submit {
  height: 34px;
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

.feedback {
  margin: 0;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-word;
}

.feedback.error {
  color: var(--danger);
}

.feedback.result {
  background: #09111a;
  border: 1px solid var(--line-soft);
  border-radius: 2px;
  padding: 8px;
  max-height: 180px;
  overflow: auto;
}

@media (max-width: 720px) {
  .drawer {
    width: 100%;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
