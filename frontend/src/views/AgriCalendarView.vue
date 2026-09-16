<script setup lang="ts">
import {
  Bell,
  BellOff,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  RefreshCw
} from 'lucide-vue-next'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import { useAgriCalendarStore } from '@/stores/agriCalendar'
import { useAuthStore } from '@/stores/auth'

const calendarStore = useAgriCalendarStore()
const auth = useAuthStore()
const router = useRouter()

const isSubscribed = computed(() =>
  calendarStore.subscriptions.includes(calendarStore.selectedProductKey)
)

const emptyState = computed(() => {
  if (calendarStore.calendar?.empty_state) {
    return calendarStore.calendar.empty_state
  }

  if (!calendarStore.calendar && calendarStore.products.length === 0) {
    return '暂无该产品农时数据'
  }

  return ''
})

async function loadInitialCalendar() {
  await calendarStore.loadProducts()
  if (calendarStore.error) {
    return
  }
  await calendarStore.loadCalendar(undefined, calendarStore.month)
}

async function changeProduct(event: Event) {
  await calendarStore.selectProduct((event.target as HTMLSelectElement).value)
}

async function toggleSubscription() {
  const productKey = calendarStore.selectedProductKey
  if (!productKey) {
    return
  }

  if (isSubscribed.value) {
    await calendarStore.unsubscribe(productKey)
  } else {
    await calendarStore.subscribe(productKey)
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadInitialCalendar()
})
</script>

<template>
  <div class="calendar-page">
    <AppHeader
      source="live"
      :loading="calendarStore.loading || calendarStore.saving"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <AgriSkillsNav />

    <main class="calendar-main">
      <header class="calendar-heading">
        <span class="calendar-heading__code ark-data">03 / FARMING CALENDAR</span>
        <h1>农时日历</h1>
        <p>按农产品和月份查看农事安排、管理要点与节气提示。</p>
      </header>

      <section class="calendar-controls" aria-label="日历筛选">
        <label class="product-control">
          <span>农产品</span>
          <select
            data-test="product-select"
            :value="calendarStore.selectedProductKey"
            :disabled="calendarStore.loading || calendarStore.products.length === 0"
            @change="changeProduct"
          >
            <option v-if="calendarStore.products.length === 0" value="">
              暂无产品
            </option>
            <option
              v-for="product in calendarStore.products"
              :key="product.key"
              :value="product.key"
            >
              {{ product.name }}
            </option>
          </select>
        </label>

        <div class="month-control" aria-label="月份选择">
          <button
            type="button"
            data-test="month-previous"
            :disabled="calendarStore.loading"
            aria-label="上一个月"
            @click="calendarStore.changeMonth(-1)"
          >
            <ChevronLeft :size="18" aria-hidden="true" />
          </button>
          <span class="month-control__value ark-data">
            {{ calendarStore.month }} 月
          </span>
          <button
            type="button"
            data-test="month-next"
            :disabled="calendarStore.loading"
            aria-label="下一个月"
            @click="calendarStore.changeMonth(1)"
          >
            <ChevronRight :size="18" aria-hidden="true" />
          </button>
        </div>

        <button
          class="subscription-toggle"
          type="button"
          :data-test="`subscribe-${calendarStore.selectedProductKey}`"
          :aria-pressed="isSubscribed"
          :disabled="
            !calendarStore.selectedProductKey ||
            calendarStore.loading ||
            calendarStore.saving
          "
          @click="toggleSubscription"
        >
          <BellOff v-if="isSubscribed" :size="17" aria-hidden="true" />
          <Bell v-else :size="17" aria-hidden="true" />
          {{ isSubscribed ? '取消订阅' : '订阅提醒' }}
        </button>
      </section>

      <section
        class="calendar-content"
        :aria-busy="calendarStore.loading"
        aria-live="polite"
      >
        <div v-if="calendarStore.loading && !calendarStore.calendar" class="calendar-state">
          <RefreshCw class="spinning" :size="19" aria-hidden="true" />
          <span>正在加载农时数据</span>
        </div>

        <div v-else-if="calendarStore.error" class="calendar-state calendar-state--error" role="alert">
          <p>{{ calendarStore.error }}</p>
          <button type="button" @click="loadInitialCalendar">
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </div>

        <div v-else-if="emptyState" class="calendar-state">
          <CalendarDays :size="22" aria-hidden="true" />
          <p>{{ emptyState }}</p>
        </div>

        <template v-else-if="calendarStore.calendar">
          <header class="calendar-content__head">
            <div>
              <span class="ark-data">
                {{ calendarStore.calendar.month }} / 12
              </span>
              <h2>{{ calendarStore.calendar.product.name }}</h2>
            </div>
            <span>农时档案</span>
          </header>

          <div class="calendar-grid">
            <section
              class="calendar-panel calendar-panel--tasks"
              data-test="calendar-tasks"
            >
              <h2>农事任务</h2>
              <ul>
                <li v-for="task in calendarStore.calendar.tasks" :key="task">
                  {{ task }}
                </li>
              </ul>
            </section>

            <section class="calendar-panel" data-test="calendar-management">
              <h2>管理要点</h2>
              <ul>
                <li
                  v-for="item in calendarStore.calendar.management"
                  :key="item"
                >
                  {{ item }}
                </li>
              </ul>
            </section>

            <section
              class="calendar-panel calendar-panel--terms"
              data-test="calendar-solar-terms"
            >
              <h2>节气提示</h2>
              <div class="solar-term-list">
                <span
                  v-for="term in calendarStore.calendar.solar_terms"
                  :key="term"
                >
                  {{ term }}
                </span>
              </div>
            </section>

            <section
              class="calendar-panel calendar-panel--reminder"
              data-test="calendar-reminder"
            >
              <h2>当月农事提示</h2>
              <p>{{ calendarStore.calendar.reminder }}</p>
            </section>
          </div>
        </template>
      </section>
    </main>
  </div>
</template>

<style scoped>
.calendar-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.calendar-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.calendar-heading {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.calendar-heading__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.calendar-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.calendar-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
}

.calendar-controls {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  gap: 12px;
  align-items: end;
  margin-top: 22px;
  padding: 16px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.product-control {
  display: grid;
  min-width: 0;
  gap: 7px;
}

.product-control > span {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.product-control select {
  width: 100%;
  min-width: 0;
  height: 42px;
  padding: 0 36px 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.month-control {
  display: grid;
  grid-template-columns: 42px minmax(72px, auto) 42px;
  align-items: center;
  min-height: 42px;
  border: 1px solid var(--ark-line-strong);
}

.month-control button {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ark-paper);
}

.month-control button:hover:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.month-control__value {
  padding-inline: 12px;
  color: var(--ark-paper);
  font-size: 0.9rem;
  font-weight: 700;
  text-align: center;
  white-space: nowrap;
}

.subscription-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 16px;
  border: 1px solid var(--ark-signal);
  background: transparent;
  color: var(--ark-signal);
  white-space: nowrap;
}

.subscription-toggle[aria-pressed="true"] {
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.subscription-toggle:hover:not(:disabled) {
  background: var(--ark-surface-1);
}

.subscription-toggle[aria-pressed="true"]:hover:not(:disabled) {
  background: var(--ark-paper);
  border-color: var(--ark-paper);
  color: var(--ark-surface-0);
}

.calendar-content {
  min-height: 390px;
  margin-top: 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.calendar-state {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 12px;
  min-height: 390px;
  padding: 28px;
  color: var(--ark-muted);
  text-align: center;
}

.calendar-state p {
  margin: 0;
  overflow-wrap: anywhere;
}

.calendar-state--error {
  color: var(--ark-paper);
}

.calendar-state button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 13px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.calendar-state button:hover {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.calendar-content__head {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--ark-line);
}

.calendar-content__head span {
  color: var(--ark-muted);
  font-size: 0.74rem;
}

.calendar-content__head h2 {
  margin: 3px 0 0;
  font-size: 1.5rem;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.calendar-panel {
  min-width: 0;
  min-height: 190px;
  padding: 24px;
  border-right: 1px solid var(--ark-line);
  border-bottom: 1px solid var(--ark-line);
}

.calendar-panel:nth-child(2n) {
  border-right: 0;
}

.calendar-panel:nth-last-child(-n + 2) {
  border-bottom: 0;
}

.calendar-panel h2 {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  font-weight: 600;
}

.calendar-panel ul {
  display: grid;
  gap: 11px;
  margin: 18px 0 0;
  padding: 0 0 0 1.15em;
}

.calendar-panel li {
  padding-left: 3px;
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.calendar-panel li::marker {
  color: var(--ark-signal);
}

.solar-term-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.solar-term-list span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  color: var(--ark-signal);
  font-size: 0.82rem;
}

.calendar-panel--reminder p {
  margin: 18px 0 0;
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .calendar-main {
    padding: 28px 14px 48px;
  }

  .calendar-heading h1 {
    font-size: 2.25rem;
  }

  .calendar-controls {
    grid-template-columns: minmax(0, 1fr);
    padding: 13px;
  }

  .month-control {
    grid-template-columns: 44px minmax(0, 1fr) 44px;
    width: 100%;
  }

  .month-control button {
    width: 44px;
    height: 44px;
  }

  .subscription-toggle {
    width: 100%;
  }

  .calendar-content__head {
    align-items: flex-start;
    flex-direction: column;
    padding: 18px 16px;
  }

  .calendar-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .calendar-panel {
    min-height: 0;
    padding: 20px 16px;
    border-right: 0;
    border-bottom: 1px solid var(--ark-line);
  }

  .calendar-panel:nth-last-child(-n + 2) {
    border-bottom: 1px solid var(--ark-line);
  }

  .calendar-panel:last-child {
    border-bottom: 0;
  }
}
</style>
