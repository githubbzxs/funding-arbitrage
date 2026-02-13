<script setup lang="ts">
import type { MarketRow, OpportunityPairRow } from '../types/market';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';

defineProps<{
  rows: OpportunityPairRow[];
  loading: boolean;
}>();

defineEmits<{
  preview: [MarketRow];
  open: [MarketRow];
  visitSymbol: [OpportunityPairRow];
}>();

function rateClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}
</script>

<template>
  <section class="table-shell">
    <div class="table-scroll">
      <table class="market-table">
        <thead>
          <tr>
            <th>币对</th>
            <th>多腿详情</th>
            <th>空腿详情</th>
            <th>差值</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="5" class="empty-cell">数据加载中...</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td colspan="5" class="empty-cell">暂无满足条件的数据</td>
          </tr>
          <tr v-for="row in rows" :key="row.id">
            <td class="symbol-cell">
              <button type="button" class="symbol-link" @click="$emit('visitSymbol', row)">
                {{ row.symbol }}
              </button>
              <div class="pair-route">{{ row.longExchange }} → {{ row.shortExchange }}</div>
            </td>

            <td>
              <div class="leg-card">
                <div class="leg-title">{{ row.longLeg.exchange }}（做多）</div>
                <div class="metric-row">未平仓：{{ formatMoney(row.longLeg.openInterestUsd) }}</div>
                <div class="metric-row">成交额：{{ formatMoney(row.longLeg.volume24hUsd) }}</div>
                <div class="metric-row" :class="rateClass(row.longLeg.fundingRateRaw)">
                  资金费原始值：{{ formatPercent(row.longLeg.fundingRateRaw, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.longLeg.fundingRate1h)">
                  1h：{{ formatPercent(row.longLeg.fundingRate1h, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.longLeg.fundingRate8h)">
                  8h：{{ formatPercent(row.longLeg.fundingRate8h, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.longLeg.fundingRate1y)">
                  年化：{{ formatPercent(row.longLeg.fundingRate1y, 2) }}
                </div>
                <div class="metric-row">下次结算：{{ formatTime(row.longLeg.nextFundingTime) }}</div>
                <div class="metric-row">结算间隔：{{ row.longLeg.settlementInterval || '-' }}</div>
                <div class="metric-row">最大杠杆：{{ formatLeverage(row.longLeg.maxLeverage) }}</div>
                <div class="metric-row">杠杆后名义年化：{{ formatPercent(row.longLeg.leveragedNominalApr, 2) }}</div>
              </div>
            </td>

            <td>
              <div class="leg-card">
                <div class="leg-title">{{ row.shortLeg.exchange }}（做空）</div>
                <div class="metric-row">未平仓：{{ formatMoney(row.shortLeg.openInterestUsd) }}</div>
                <div class="metric-row">成交额：{{ formatMoney(row.shortLeg.volume24hUsd) }}</div>
                <div class="metric-row" :class="rateClass(row.shortLeg.fundingRateRaw)">
                  资金费原始值：{{ formatPercent(row.shortLeg.fundingRateRaw, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.shortLeg.fundingRate1h)">
                  1h：{{ formatPercent(row.shortLeg.fundingRate1h, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.shortLeg.fundingRate8h)">
                  8h：{{ formatPercent(row.shortLeg.fundingRate8h, 4) }}
                </div>
                <div class="metric-row" :class="rateClass(row.shortLeg.fundingRate1y)">
                  年化：{{ formatPercent(row.shortLeg.fundingRate1y, 2) }}
                </div>
                <div class="metric-row">下次结算：{{ formatTime(row.shortLeg.nextFundingTime) }}</div>
                <div class="metric-row">结算间隔：{{ row.shortLeg.settlementInterval || '-' }}</div>
                <div class="metric-row">最大杠杆：{{ formatLeverage(row.shortLeg.maxLeverage) }}</div>
                <div class="metric-row">杠杆后名义年化：{{ formatPercent(row.shortLeg.leveragedNominalApr, 2) }}</div>
              </div>
            </td>

            <td>
              <div class="spread-card">
                <div class="metric-row" :class="rateClass(row.spreadRate1h)">1h差值：{{ formatPercent(row.spreadRate1h, 4) }}</div>
                <div class="metric-row" :class="rateClass(row.spreadRate8h)">8h差值：{{ formatPercent(row.spreadRate8h, 4) }}</div>
                <div class="metric-row strong" :class="rateClass(row.spreadRate1yNominal)">
                  年化差值：{{ formatPercent(row.spreadRate1yNominal, 2) }}
                </div>
                <div class="metric-row strong" :class="rateClass(row.leveragedSpreadRate1yNominal)">
                  杠杆后年化差值：{{ formatPercent(row.leveragedSpreadRate1yNominal, 2) }}
                </div>
              </div>
            </td>

            <td>
              <div class="action-group">
                <button type="button" class="action-button" @click="$emit('preview', row.rawOpportunity)">预览</button>
                <button type="button" class="action-button accent" @click="$emit('open', row.rawOpportunity)">开仓</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.table-shell {
  border: 1px solid var(--line-strong);
  background: var(--panel-bg);
  min-height: 320px;
}

.table-scroll {
  overflow-x: auto;
}

.market-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1560px;
}

th,
td {
  border-bottom: 1px solid var(--line-soft);
  padding: 8px;
  font-size: 12px;
  line-height: 1.35;
  white-space: nowrap;
  text-align: left;
  vertical-align: top;
}

thead th {
  position: sticky;
  top: 0;
  background: #0e141d;
  z-index: 1;
  color: #a9b6c4;
  font-weight: 500;
}

tbody tr:hover {
  background: rgba(0, 199, 166, 0.05);
}

.symbol-cell {
  min-width: 180px;
}

.symbol-link {
  border: none;
  background: transparent;
  color: #77f5de;
  font-weight: 700;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.symbol-link:hover {
  text-decoration: underline;
}

.pair-route {
  margin-top: 6px;
  color: var(--text-dim);
}

.leg-card,
.spread-card {
  display: grid;
  gap: 4px;
  min-width: 280px;
}

.leg-title {
  color: #f3f5f7;
  font-weight: 700;
  margin-bottom: 2px;
}

.metric-row {
  color: var(--text-main);
}

.metric-row.strong {
  font-weight: 700;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}

.action-group {
  display: flex;
  gap: 6px;
}

.action-button {
  height: 26px;
  border: 1px solid var(--line-soft);
  color: var(--text-main);
  background: #101722;
  font-size: 12px;
  border-radius: 2px;
  padding: 0 10px;
}

.action-button:hover {
  border-color: var(--accent);
}

.action-button.accent {
  border-color: rgba(0, 199, 166, 0.8);
  color: #032621;
  background: rgba(0, 199, 166, 0.88);
}

.action-button.accent:hover {
  background: rgba(0, 199, 166, 1);
}

.empty-cell {
  text-align: center;
  color: var(--text-dim);
  padding: 16px 8px;
}

@media (max-width: 900px) {
  .market-table {
    min-width: 1360px;
  }

  .leg-card,
  .spread-card {
    min-width: 240px;
  }
}
</style>
