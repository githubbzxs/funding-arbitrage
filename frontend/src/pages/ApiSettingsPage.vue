<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { deleteCredential, fetchCredentialStatuses, upsertCredential, type CredentialStatus } from '../api/credentials';

const EXCHANGE_OPTIONS = ['binance', 'okx', 'bybit', 'bitget', 'gateio'] as const;

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

const loading = ref(false);
const globalError = ref('');
const forms = ref<StoredCredentialForm[]>(
  EXCHANGE_OPTIONS.map((exchange) => ({
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
  }))
);

function applyStatuses(statuses: CredentialStatus[]): void {
  const map = new Map(statuses.filter((item) => item.exchange).map((item) => [item.exchange, item]));
  forms.value.forEach((form) => {
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

async function refreshStatuses(): Promise<void> {
  loading.value = true;
  globalError.value = '';
  try {
    const statuses = await fetchCredentialStatuses();
    applyStatuses(statuses);
  } catch (error) {
    globalError.value = error instanceof Error ? error.message : '加载托管凭据失败';
  } finally {
    loading.value = false;
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
    await refreshStatuses();
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
    await refreshStatuses();
  } catch (error) {
    formValue.error = error instanceof Error ? error.message : '删除失败';
  } finally {
    formValue.saving = false;
  }
}

onMounted(async () => {
  await refreshStatuses();
});
</script>

<template>
  <section class="panel">
    <header class="panel-head">
      <div>
        <h2>API 托管配置</h2>
        <p>凭据由后端加密存储，页面不会返回 Secret 明文。</p>
      </div>
      <button type="button" class="ghost" :disabled="loading" @click="refreshStatuses">
        {{ loading ? '刷新中...' : '刷新状态' }}
      </button>
    </header>

    <p v-if="globalError" class="feedback error">{{ globalError }}</p>

    <div class="credential-grid">
      <article v-for="item in forms" :key="item.exchange" class="credential-item">
        <div class="credential-head">
          <h3>{{ item.exchange }}</h3>
          <small class="status" :class="{ ok: item.configured }">
            {{ item.configured ? `已配置 ${item.apiKeyMasked}` : '未配置' }}
          </small>
        </div>

        <label>
          <span>API Key</span>
          <input v-model.trim="item.apiKey" placeholder="输入后点击保存" />
        </label>
        <label>
          <span>API Secret</span>
          <input v-model.trim="item.apiSecret" type="password" placeholder="输入后点击保存" />
        </label>
        <label>
          <span>Passphrase（如有）</span>
          <input v-model.trim="item.passphrase" type="password" placeholder="可留空" />
        </label>
        <label class="checkbox">
          <input v-model="item.testnet" type="checkbox" />
          <span>使用 Testnet</span>
        </label>

        <div class="credential-actions">
          <button type="button" class="mini" :disabled="item.saving" @click="saveStored(item)">
            {{ item.saving ? '保存中...' : '保存' }}
          </button>
          <button type="button" class="mini danger" :disabled="item.saving || !item.configured" @click="removeStored(item)">
            删除
          </button>
        </div>

        <p v-if="item.updatedAt" class="updated">更新时间：{{ item.updatedAt }}</p>
        <p v-if="item.error" class="feedback error">{{ item.error }}</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.panel {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  display: grid;
  gap: 12px;
  padding: 14px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
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

.credential-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.credential-item {
  border: 1px solid var(--line-soft);
  background: #101722;
  padding: 12px;
  display: grid;
  gap: 8px;
}

.credential-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.credential-head h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.status {
  font-size: 11px;
  color: var(--text-dim);
}

.status.ok {
  color: var(--success);
}

label {
  display: grid;
  gap: 6px;
}

label span {
  font-size: 12px;
  color: var(--text-dim);
}

input {
  border: 1px solid var(--line-soft);
  background: #111927;
  color: var(--text-main);
  border-radius: 2px;
  padding: 7px 10px;
  outline: none;
  font-size: 13px;
}

input:focus {
  border-color: var(--accent);
}

.checkbox {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.checkbox input {
  width: 14px;
  height: 14px;
  margin: 0;
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

.updated {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
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

@media (max-width: 960px) {
  .credential-grid {
    grid-template-columns: 1fr;
  }
}
</style>
