<script setup lang="ts">
import {
  ArrowRight,
  BookOpen,
  Home,
  MessagesSquare,
  Mic2,
  PenLine,
  Radio,
  Store
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const entries = [
  {
    to: '/student/ecommerce-training',
    code: '总览',
    title: '电商运营实训首页',
    description: '查看直播、文案、装修、客服和课程学习入口。',
    icon: Home
  },
  {
    to: '/student/ecommerce-training/live-script',
    code: '话术',
    title: '直播话术',
    description: '按商品信息与风格生成四段完整直播脚本。',
    icon: Radio
  },
  {
    to: '/student/ecommerce-training/simulation',
    code: '模拟',
    title: '文字直播间模拟',
    description: '按场景完成有序环节，获得四维评分与改进建议。',
    icon: Mic2
  },
  {
    to: '/student/ecommerce-training/copy-training',
    code: '文案',
    title: '文案提示词训练',
    description: '判断教学案例，对照 AI 参考评判并优化文案提示词。',
    icon: PenLine
  },
  {
    to: '/student/ecommerce-training/store-guidance',
    code: '装修',
    title: '店铺装修指导',
    description: '生成首页、色彩、详情页和导航四部分装修方案。',
    icon: Store
  },
  {
    to: '/student/ecommerce-training/customer-service',
    code: '客服',
    title: '客服模拟训练',
    description: '逐轮回复客户，查看分析、目标状态和整场总结。',
    icon: MessagesSquare
  },
  {
    to: '/student/ecommerce-training/courses',
    code: '课程',
    title: '电商课程',
    description: '学习已上架电商课程、记录进度并完成 AI 课后测验。',
    icon: BookOpen
  }
] as const

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="ecommerce-training-home">
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <EcommerceTrainingNav />

    <main class="ecommerce-training-home__main">
      <header class="ecommerce-training-home__intro">
        <span class="ecommerce-training-home__code ark-data">
          04 / E-COMMERCE TRAINING
        </span>
        <h1>电商运营实训</h1>
        <p>把直播、文案、店铺和客服任务放进可回看的训练闭环。</p>
      </header>

      <section aria-labelledby="ecommerce-training-entries-title">
        <div class="ecommerce-training-home__section-head">
          <h2 id="ecommerce-training-entries-title">功能入口</h2>
          <span class="ark-data">7 个模块</span>
        </div>

        <div class="ecommerce-training-home__grid">
          <RouterLink
            v-for="entry in entries"
            :key="entry.to"
            class="ecommerce-training-card"
            :to="entry.to"
          >
            <span class="ecommerce-training-card__icon">
              <component :is="entry.icon" :size="21" aria-hidden="true" />
            </span>
            <span class="ecommerce-training-card__body">
              <span class="ecommerce-training-card__code ark-data">
                {{ entry.code }}
              </span>
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
            </span>
            <ArrowRight
              class="ecommerce-training-card__arrow"
              :size="18"
              aria-hidden="true"
            />
          </RouterLink>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.ecommerce-training-home {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.ecommerce-training-home__main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 48px 24px 72px;
}

.ecommerce-training-home__intro {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.ecommerce-training-home__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.ecommerce-training-home__intro h1 {
  margin: 10px 0 0;
  font-size: 3.2rem;
  line-height: 1;
}

.ecommerce-training-home__intro p {
  max-width: 58ch;
  margin: 16px 0 0;
  color: var(--ark-muted);
}

.ecommerce-training-home__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  margin: 28px 0 12px;
}

.ecommerce-training-home__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.ecommerce-training-home__section-head span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.ecommerce-training-home__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.ecommerce-training-card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  min-height: 144px;
  padding: 20px;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-decoration: none;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.ecommerce-training-card:hover,
.ecommerce-training-card:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.ecommerce-training-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.ecommerce-training-card__body {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.ecommerce-training-card__code {
  color: var(--ark-signal);
  font-size: 0.68rem;
}

.ecommerce-training-card__body strong,
.ecommerce-training-card__body small {
  overflow-wrap: anywhere;
}

.ecommerce-training-card__body strong {
  font-size: 1rem;
}

.ecommerce-training-card__body small {
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-height: 1.55;
}

.ecommerce-training-card__arrow {
  color: var(--ark-muted);
}

@media (max-width: 640px) {
  .ecommerce-training-home__main {
    padding: 32px 14px 48px;
  }

  .ecommerce-training-home__intro h1 {
    font-size: 2.4rem;
  }
}
</style>
