<script setup lang="ts">
import {
  ArrowRight,
  BookOpen,
  CircleSlash2,
  RefreshCw,
  Shapes
} from 'lucide-vue-next'
import { onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
import { useAuthStore } from '@/stores/auth'
import { useHandcraftInheritanceStore } from '@/stores/handcraftInheritance'

const auth = useAuthStore()
const craftsStore = useHandcraftInheritanceStore()
const router = useRouter()

function isAvailable(craftKey: string | null, available: boolean, sourceAvailable: boolean) {
  return Boolean(craftKey && available && sourceAvailable)
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void craftsStore.loadCrafts()
})
</script>

<template>
  <div class="handcraft-home">
    <AppHeader
      source="live"
      :loading="craftsStore.loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <HandcraftInheritanceNav />

    <main class="handcraft-home__main">
      <header class="handcraft-home__intro">
        <span class="handcraft-home__code ark-data">
          05 / HANDCRAFT INHERITANCE
        </span>
        <h1>手工传承</h1>
        <p>
          选择一项非遗技艺，按步骤学习针法、刀工、塑形与髹饰，并随时从上次完成的位置继续。
        </p>
      </header>

      <section aria-labelledby="handcraft-list-title">
        <div class="handcraft-home__section-head">
          <div>
            <span class="ark-data">CRAFT SOURCE</span>
            <h2 id="handcraft-list-title">非遗技艺</h2>
          </div>
          <span class="ark-data">{{ craftsStore.crafts.length }} 项</span>
        </div>

        <div
          v-if="craftsStore.loading && craftsStore.crafts.length === 0"
          class="handcraft-home__status"
          role="status"
        >
          <RefreshCw class="spinning" :size="20" aria-hidden="true" />
          正在加载技艺
        </div>

        <div
          v-else-if="craftsStore.error && craftsStore.crafts.length === 0"
          class="handcraft-home__error"
          role="alert"
        >
          <span>{{ craftsStore.error }}</span>
          <button type="button" @click="craftsStore.loadCrafts">
            <RefreshCw :size="16" aria-hidden="true" />
            重新加载
          </button>
        </div>

        <p
          v-else-if="craftsStore.crafts.length === 0"
          class="handcraft-home__empty"
          data-test="craft-empty"
        >
          暂无可用的手工传承内容
        </p>

        <template v-else>
          <div
            v-if="craftsStore.error"
            class="handcraft-home__error"
            role="alert"
          >
            <span>{{ craftsStore.error }}</span>
            <button type="button" @click="craftsStore.loadCrafts">
              <RefreshCw :size="16" aria-hidden="true" />
              重新加载
            </button>
          </div>

          <div class="handcraft-home__grid">
            <article
              v-for="(craft, index) in craftsStore.crafts"
              :key="craft.craft_key ?? `craft-${index}`"
              class="craft-card"
              :class="{ 'is-unavailable': !isAvailable(craft.craft_key, craft.available, craft.source_available) }"
              data-test="craft-card"
              :data-craft-key="craft.craft_key"
            >
              <div class="craft-card__icon" aria-hidden="true">
                <Shapes :size="21" />
              </div>
              <div class="craft-card__body">
                <span class="craft-card__code ark-data">
                  CRAFT {{ String(index + 1).padStart(2, '0') }}
                </span>
                <h2>{{ craft.name || '未命名技艺' }}</h2>
                <p>{{ craft.introduction || '介绍暂未提供' }}</p>

                <div
                  v-if="!isAvailable(craft.craft_key, craft.available, craft.source_available)"
                  class="craft-card__unavailable"
                >
                  <CircleSlash2 :size="16" aria-hidden="true" />
                  <span>
                    {{ craft.unavailable_reason || '来源内容暂不可用' }}
                  </span>
                </div>
              </div>

              <RouterLink
                v-if="isAvailable(craft.craft_key, craft.available, craft.source_available)"
                class="craft-card__action"
                :to="`/student/handcraft-inheritance/crafts/${craft.craft_key}`"
              >
                进入学习
                <ArrowRight :size="18" aria-hidden="true" />
              </RouterLink>
              <span v-else class="craft-card__disabled">暂不可学习</span>
            </article>
          </div>
        </template>
      </section>

      <RouterLink
        class="handcraft-home__courses"
        to="/student/handcraft-inheritance/courses"
      >
        <BookOpen :size="19" aria-hidden="true" />
        <span>
          <strong>查看手工课程</strong>
          <small>进入课程进度、推荐与课后测验</small>
        </span>
        <ArrowRight :size="18" aria-hidden="true" />
      </RouterLink>
    </main>
  </div>
</template>

<style scoped>
.handcraft-home {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.handcraft-home__main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 48px 24px 72px;
}

.handcraft-home__intro {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.handcraft-home__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.handcraft-home__intro h1 {
  margin: 10px 0 0;
  font-size: 3.2rem;
  line-height: 1;
  text-wrap: balance;
}

.handcraft-home__intro p {
  max-width: 62ch;
  margin: 16px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.handcraft-home__section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin: 28px 0 12px;
}

.handcraft-home__section-head > div {
  min-width: 0;
}

.handcraft-home__section-head > div > span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.handcraft-home__section-head h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
}

.handcraft-home__section-head > span {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.handcraft-home__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
}

.craft-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  min-width: 0;
  min-height: 190px;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.craft-card.is-unavailable {
  background: var(--ark-surface-1);
}

.craft-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.craft-card__body {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 4px;
}

.craft-card__code {
  color: var(--ark-signal);
  font-size: 0.68rem;
}

.craft-card h2 {
  margin: 0;
  font-size: 1.08rem;
  line-height: 1.35;
  text-wrap: balance;
  word-break: keep-all;
}

.craft-card__body p {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.craft-card__unavailable {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  margin-top: 8px;
  color: var(--ark-paper);
  font-size: 0.78rem;
}

.craft-card__unavailable svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.craft-card__unavailable span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.craft-card__action,
.craft-card__disabled {
  grid-column: 1 / -1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
  margin-top: 6px;
  border-top: 1px solid var(--ark-line);
  font-size: 0.82rem;
}

.craft-card__action {
  color: var(--ark-signal);
  text-decoration: none;
}

.craft-card__action:hover,
.craft-card__action:focus-visible {
  color: var(--ark-paper);
}

.craft-card__disabled {
  color: var(--ark-muted);
}

.handcraft-home__status,
.handcraft-home__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 180px;
  margin: 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.handcraft-home__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 10px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.handcraft-home__error span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.handcraft-home__error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.handcraft-home__courses {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  margin-top: 24px;
  padding: 18px;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  color: var(--ark-paper);
  text-decoration: none;
}

.handcraft-home__courses > svg {
  color: var(--ark-signal);
}

.handcraft-home__courses span {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.handcraft-home__courses strong,
.handcraft-home__courses small {
  overflow-wrap: anywhere;
}

.handcraft-home__courses small {
  color: var(--ark-muted);
}

.handcraft-home__courses:hover,
.handcraft-home__courses:focus-visible {
  color: var(--ark-signal);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .handcraft-home__main {
    padding: 32px 14px 48px;
  }

  .handcraft-home__intro h1 {
    font-size: 2.4rem;
  }

  .handcraft-home__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .handcraft-home__error {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
