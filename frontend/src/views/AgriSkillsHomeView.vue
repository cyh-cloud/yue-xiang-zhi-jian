<script setup lang="ts">
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  Home,
  MessageCircleQuestion,
  Stethoscope
} from 'lucide-vue-next'
import { RouterLink } from 'vue-router'

import AgriSkillsNav from '@/components/AgriSkillsNav.vue'

const entries = [
  {
    to: '/student/agri-skills',
    code: '总览',
    title: '农业技能首页',
    description: '查看农时、问答、诊断与课程入口。',
    icon: Home
  },
  {
    to: '/student/agri-skills/calendar',
    code: '农时',
    title: '智能日历',
    description: '按产品和月份查看农事安排，并管理提醒订阅。',
    icon: CalendarDays
  },
  {
    to: '/student/agri-skills/qa',
    code: '问答',
    title: '农技问答',
    description: '使用文字或语音提问，获取流式回答与追问建议。',
    icon: MessageCircleQuestion
  },
  {
    to: '/student/agri-skills/diagnosis',
    code: '诊断',
    title: '病虫害诊断',
    description: '按症状完成多轮诊断，记录复诊并参加自测。',
    icon: Stethoscope
  },
  {
    to: '/student/agri-skills/courses',
    code: '课程',
    title: '农业课程',
    description: '继续学习、查看进度并完成课后测验。',
    icon: BookOpen
  }
] as const
</script>

<template>
  <div class="agri-skills-home">
    <AgriSkillsNav />

    <main class="agri-skills-home__main">
      <header class="agri-skills-home__intro">
        <span class="agri-skills-home__code ark-data">03 / AGRICULTURAL SKILLS</span>
        <h1>农业技能</h1>
        <p>从农时安排到病虫害判断，把每个种植问题落到下一步操作。</p>
      </header>

      <section aria-labelledby="agri-skills-entries-title">
        <div class="agri-skills-home__section-head">
          <h2 id="agri-skills-entries-title">功能入口</h2>
          <span class="ark-data">5 个模块</span>
        </div>

        <div class="agri-skills-home__grid">
          <RouterLink
            v-for="entry in entries"
            :key="entry.to"
            class="agri-skills-card"
            :to="entry.to"
          >
            <span class="agri-skills-card__icon">
              <component :is="entry.icon" :size="21" aria-hidden="true" />
            </span>
            <span class="agri-skills-card__body">
              <span class="agri-skills-card__code ark-data">{{ entry.code }}</span>
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
            </span>
            <ArrowRight
              class="agri-skills-card__arrow"
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
.agri-skills-home {
  min-height: 100svh;
  background: var(--ark-ink);
}

.agri-skills-home__main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 48px 24px 72px;
}

.agri-skills-home__intro {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.agri-skills-home__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.agri-skills-home__intro h1 {
  margin: 10px 0 0;
  font-size: 3.2rem;
  line-height: 1;
}

.agri-skills-home__intro p {
  max-width: 58ch;
  margin: 16px 0 0;
  color: var(--ark-muted);
}

.agri-skills-home__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  margin: 28px 0 12px;
}

.agri-skills-home__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.agri-skills-home__section-head span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.agri-skills-home__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.agri-skills-card {
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

.agri-skills-card:hover,
.agri-skills-card:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.agri-skills-card__icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.agri-skills-card__body {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.agri-skills-card__code {
  color: var(--ark-signal);
  font-size: 0.68rem;
}

.agri-skills-card__body strong {
  font-size: 1rem;
}

.agri-skills-card__body small {
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-height: 1.55;
}

.agri-skills-card__arrow {
  color: var(--ark-muted);
}

@media (max-width: 640px) {
  .agri-skills-home__main {
    padding: 32px 14px 48px;
  }

  .agri-skills-home__intro h1 {
    font-size: 2.4rem;
  }
}
</style>
