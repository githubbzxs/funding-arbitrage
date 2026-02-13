<script setup lang="ts">
import type { MarginSimulation, OpportunityBoardRow, SettlementEventPreview } from '../types/market';
import { formatLeverage, formatMoney, formatPercent, formatTime } from '../utils/format';
import { resolveNextSettlementTime, resolveSingleSideEventCount } from '../utils/marginSim';

const props = defineProps<{
  rows: OpportunityBoardRow[];
  loading: boolean;
  marginInputs: Record<string, string>;
  settlementEventsByRowId: Record<string, SettlementEventPreview[]>;
  simulations: Record<string, MarginSimulation | null>;
}>();

const emit = defineEmits<{
  openDetail: [OpportunityBoardRow];
  openPair: [OpportunityBoardRow];
  openTrade: [OpportunityBoardRow];
  updateMargin: [{ rowId: string; value: string }];
}>();

function colorClass(value: number | null): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '';
  }
  return value >= 0 ? 'positive' : 'negative';
}

function sideText(side: 'long' | 'short' | null): string {
  if (side === 'long') {
    return '多腿';
  }
  if (side === 'short') {
    return '空腿';
  }
  return '未知';
}

function onMarginInput(rowId: string, event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('updateMargin', { rowId, value: target.value });
}

function rowEvents(row: OpportunityBoardRow): SettlementEventPreview[] {
  return props.settlementEventsByRowId[row.id] ?? [];
}

function singleSideCount(row: OpportunityBoardRow, events: SettlementEventPreview[]): number {
  return resolveSingleSideEventCount(row, events);
}

function nextSettlementText(row: OpportunityBoardRow, events: SettlementEventPreview[]): string {
  return formatTime(resolveNextSettlementTime(row, events));
}

function singleSideBrief(events: SettlementEventPreview[]): string {
  const singleSideEvents = events.filter((event) => event.kind === 'single_side');
  if (singleSideEvents.length === 0) {
    return '同结算窗口内无单边事件';
  }
  const preview = singleSideEvents
    .slice(0, 2)
    .map((event) => `${sideText(event.side)} ${formatPercent(event.amountRate, 4)}`)
    .join(' / ');
  const suffix = singleSideEvents.length > 2 ? `，其余 ${singleSideEvents.length - 2} 次见明细` : '';
  return `${preview}${suffix}`;
}

function eventTitle(event: SettlementEventPreview): string {
  if (event.kind === 'single_side') {
    return `${sideText(event.side)}单边`;
  }
  if (event.kind === 'hedged') {
    return '同结算';
  }
  return '结算事件';
}

function simulationEventTitle(simulation: MarginSimulation, index: number): string {
  const event = simulation.events[index];
  if (!event) {
    return `事件 ${index + 1}`;
  }
  if (event.kind === 'single_side') {
    return `${sideText(event.side)}单边`;
  }
  if (event.kind === 'hedged') {
    return '同结算';
  }
  return event.summary || `事件 ${index + 1}`;
}
</script>

<template>
  <section class="table-shell">
    <div v-if="loading && rows.length === 0" class="state">数据加载中...</div>
    <div v-else-if="rows.length === 0" class="state">暂无满足条件的数据</div>

    <div v-else class="table-scroll" role="region" aria-label="套利扫描结果">
      <table class="board-table">
        <thead>
          <tr>
            <th class="col-symbol">币对</th>
            <th class="col-settlement">资金费率 / 结算信息</th>
            <th class="col-score">统一指标</th>
            <th class="col-sim">保证金模拟（到下一次同结算）</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" class="table-row">
            <td class="symbol-cell col-symbol">
              <button type="button" class="symbol-link" @click="emit('openDetail', row)">{{ row.symbol }}</button>
              <p class="pair-hint">多 {{ row.longExchange }} / 空 {{ row.shortExchange }}</p>
            </td>

            <td class="settlement-cell col-settlement">
              <div class="leg-group">
                <p>
                  <strong>多 {{ row.longLeg.exchange }}</strong>
                  <span :class="colorClass(row.longLeg.fundingRateRaw)">{{ formatPercent(row.longLeg.fundingRateRaw, 4) }}</span>
                  <span>{{ row.longLeg.settlementInterval }}</span>
                  <span>{{ formatTime(row.longLeg.nextFundingTime) }}</span>
                </p>
                <p>
                  <strong>空 {{ row.shortLeg.exchange }}</strong>
                  <span :class="colorClass(row.shortLeg.fundingRateRaw)">{{ formatPercent(row.shortLeg.fundingRateRaw, 4) }}</span>
                  <span>{{ row.shortLeg.settlementInterval }}</span>
                  <span>{{ formatTime(row.shortLeg.nextFundingTime) }}</span>
                </p>
              </div>

              <div class="settlement-summary">
                <p>
                  下一次同结算: {{ nextSettlementText(row, rowEvents(row)) }} |
                  单边结算 {{ singleSideCount(row, rowEvents(row)) }} 次
                </p>
                <p class="hint">{{ singleSideBrief(rowEvents(row)) }}</p>
              </div>

              <details v-if="singleSideCount(row, rowEvents(row)) > 0" class="event-details">
                <summary>展开逐次结算事件</summary>
                <ul>
                  <li v-for="event in rowEvents(row)" :key="event.id">
                    <span>{{ formatTime(event.eventTime) }} {{ eventTitle(event) }}</span>
                    <strong :class="colorClass(event.amountRate)">{{ formatPercent(event.amountRate, 4) }}</strong>
                  </li>
                </ul>
              </details>
            </td>

            <td class="score-cell col-score">
              <p class="score-main" :class="colorClass(row.nextCycleScore)">
                {{ formatPercent(row.nextCycleScore, 2) }}
              </p>
              <p class="hint">未杠杆参考 {{ formatPercent(row.nextCycleScoreUnleveraged, 2) }}</p>
              <p class="hint">可用杠杆 {{ formatLeverage(row.maxUsableLeverage) }}</p>
            </td>

            <td class="sim-cell col-sim">
              <label class="sim-input-wrap">
                <span>保证金(USDT)</span>
                <input
                  type="number"
                  min="0"
                  step="10"
                  placeholder="输入保证金"
                  :value="marginInputs[row.id] ?? ''"
                  @input="onMarginInput(row.id, $event)"
                />
              </label>

              <div v-if="simulations[row.id]" class="sim-result">
                <p class="score-main" :class="colorClass(simulations[row.id]!.expectedPnlUsd)">≈ {{ formatMoney(simulations[row.id]!.expectedPnlUsd) }}</p>
                <p class="hint">名义仓位 {{ formatMoney(simulations[row.id]!.notionalUsd) }} ({{ formatLeverage(simulations[row.id]!.leverage) }})</p>
                <p class="hint">单边结算 {{ simulations[row.id]!.singleSideEventCount }} 次</p>

                <details class="event-details">
                  <summary>展开逐次金额明细</summary>
                  <ul>
                    <li v-for="(event, index) in simulations[row.id]!.events" :key="event.id">
                      <span>{{ formatTime(event.eventTime) }} {{ simulationEventTitle(simulations[row.id]!, index) }}</span>
                      <strong :class="colorClass(event.pnlUsd)">
                        {{ formatMoney(event.pnlUsd) }} ({{ formatPercent(event.amountRate, 4) }})
                      </strong>
                    </li>
                  </ul>
                </details>
              </div>
              <p v-else class="hint">输入保证金后按结算事件窗口模拟</p>
            </td>

            <td class="actions col-actions">
              <button type="button" class="ghost" @click="emit('openPair', row)">打开双交易所</button>
              <button type="button" class="accent" @click="emit('openTrade', row)">去交易</button>
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
}

.table-scroll {
  overflow: auto;
  max-height: clamp(460px, 72vh, 980px);
}

.board-table {
  border-collapse: collapse;
  min-width: 100%;
  width: max-content;
}

.board-table th,
.board-table td {
  border-bottom: 1px solid var(--line-soft);
  padding: 10px 12px;
  font-size: 12px;
  vertical-align: top;
}

.board-table th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #0e141f;
  color: var(--text-dim);
  text-align: left;
  white-space: nowrap;
}

.table-row:hover {
  background: rgba(0, 199, 166, 0.05);
}

.col-symbol {
  min-width: 150px;
}

.col-settlement {
  min-width: 420px;
}

.col-score {
  min-width: 180px;
}

.col-sim {
  min-width: 360px;
}

.col-actions {
  min-width: 190px;
}

.symbol-link {
  border: none;
  background: transparent;
  color: var(--accent-soft);
  font-weight: 700;
  text-align: left;
  padding: 0;
  font-size: 14px;
}

.symbol-link:hover {
  text-decoration: underline;
}

.pair-hint {
  margin: 6px 0 0;
  color: var(--text-dim);
}

.leg-group {
  display: grid;
  gap: 4px;
}

.leg-group p {
  margin: 0;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.settlement-summary {
  margin-top: 8px;
  display: grid;
  gap: 2px;
}

.settlement-summary p {
  margin: 0;
}

.score-cell {
  display: grid;
  gap: 4px;
}

.score-main {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}

.sim-cell {
  display: grid;
  gap: 6px;
}

.sim-input-wrap {
  display: grid;
  gap: 4px;
}

.sim-input-wrap span {
  font-size: 11px;
  color: var(--text-dim);
}

.sim-input-wrap input {
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  height: 30px;
  background: #101722;
  color: var(--text-main);
  padding: 0 8px;
  outline: none;
}

.sim-input-wrap input:focus {
  border-color: var(--accent);
}

.sim-result {
  display: grid;
  gap: 3px;
}

.event-details {
  margin-top: 2px;
}

.event-details summary {
  cursor: pointer;
  color: var(--accent-soft);
  font-size: 11px;
}

.event-details ul {
  margin: 6px 0 0;
  padding-left: 14px;
  display: grid;
  gap: 4px;
}

.event-details li {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-dim);
}

.hint {
  margin: 0;
  color: var(--text-dim);
  font-size: 11px;
}

.actions {
  display: grid;
  gap: 8px;
}

.ghost,
.accent {
  height: 30px;
  padding: 0 10px;
  border-radius: 4px;
  border: 1px solid var(--line-soft);
  background: #101722;
  color: var(--text-main);
  font-size: 12px;
}

.accent {
  border-color: rgba(0, 199, 166, 0.9);
  background: rgba(0, 199, 166, 0.88);
  color: #052019;
}

.state {
  color: var(--text-dim);
  font-size: 13px;
  padding: 16px;
}

.positive {
  color: var(--success);
}

.negative {
  color: var(--danger);
}
</style>
