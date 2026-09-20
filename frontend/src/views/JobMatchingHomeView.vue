<script setup lang="ts">
import {
  ArrowRight,
  Bookmark,
  BriefcaseBusiness,
  FileText,
  Send,
  ShieldCheck
} from 'lucide-vue-next'
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import JobMatchingNav from '@/components/JobMatchingNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const entries = [
  {
    label: '简历维护',
    href: '/student/employment/resume',
    description: '维护教育、实习与工作经历，保存企业投递使用的简历。',
    icon: FileText
  },
  {
    label: '我的技能档案',
    href: '/student/employment/skills',
    description: '汇总学习成果，并按项目控制企业可见范围。',
    icon: ShieldCheck
  },
  {
    label: '岗位浏览',
    href: '/student/employment/jobs',
    description: '查看推荐岗位与全部在招岗位，进入详情完成投递。',
    icon: BriefcaseBusiness
  },
  {
    label: '我的投递',
    href: '/student/employment/applications',
    description: '按待处理、已查看、意向沟通和不合适查看进度。',
    icon: Send
  },
  {
    label: '岗位收藏',
    href: '/student/employment/favorites',
    description: '保留关注岗位，关闭后仍可查看最后展示信息。',
    icon: Bookmark
  }
] as const

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="job-matching-home">
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <JobMatchingNav />

    <main class="job-matching-home__main">
      <header class="job-matching-home__intro">
        <span class="job-matching-home__code ark-data">
          07 / EMPLOYMENT
        </span>
        <h1>就业对接</h1>
        <p>集中维护简历与技能档案，浏览岗位并跟踪投递进展。</p>
      </header>

      <section aria-labelledby="job-matching-entries-title">
        <div class="job-matching-home__section-head">
          <h2 id="job-matching-entries-title">功能入口</h2>
          <span class="ark-data">5 个入口</span>
        </div>

        <div class="job-matching-home__grid">
          <RouterLink
            v-for="entry in entries"
            :key="entry.href"
            class="job-matching-home__card"
            :to="entry.href"
            data-test="job-matching-entry"
          >
            <span class="job-matching-home__icon" aria-hidden="true">
              <component :is="entry.icon" :size="21" />
            </span>
            <span class="job-matching-home__body">
              <strong>{{ entry.label }}</strong>
              <small>{{ entry.description }}</small>
            </span>
            <ArrowRight
              class="job-matching-home__arrow"
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
.job-matching-home {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.job-matching-home__main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 48px 24px 72px;
  overflow-x: clip;
}

.job-matching-home__intro {
  min-width: 0;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.job-matching-home__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.job-matching-home__intro h1 {
  margin: 10px 0 0;
  font-size: 3.2rem;
  line-height: 1;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.job-matching-home__intro p {
  max-width: 58ch;
  margin: 16px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-matching-home__section-head {
  display: flex;
  min-width: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 18px;
  margin: 28px 0 12px;
}

.job-matching-home__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.job-matching-home__section-head span {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.job-matching-home__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 10px;
  min-width: 0;
}

.job-matching-home__card {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  min-width: 0;
  min-height: 136px;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  text-decoration: none;
  transition:
    background var(--ark-transition),
    color var(--ark-transition);
}

.job-matching-home__card:hover,
.job-matching-home__card:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.job-matching-home__icon {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.job-matching-home__body {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.job-matching-home__body strong {
  min-width: 0;
  font-size: 1rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.job-matching-home__body small {
  min-width: 0;
  color: var(--ark-muted);
  font-size: 0.8rem;
  line-height: 1.55;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.job-matching-home__arrow {
  color: var(--ark-muted);
}

@media (max-width: 640px) {
  .job-matching-home__main {
    padding: 32px 14px 48px;
  }

  .job-matching-home__intro h1 {
    font-size: 2.4rem;
  }

  .job-matching-home__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 360px) {
  .job-matching-home__main {
    padding-inline: 12px;
  }

  .job-matching-home__card {
    gap: 11px;
    padding: 17px 16px;
  }
}
</style>
