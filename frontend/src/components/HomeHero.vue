<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowRight,
  Briefcase,
  Hammer,
  Library,
  MonitorPlay,
  ShoppingCart,
  Sprout
} from 'lucide-vue-next'

import HomeStageArt from '@/components/HomeStageArt.vue'
import type { HomeModule, ModuleId, SnapshotSource } from '@/api/types'

const props = defineProps<{
  modules: HomeModule[]
  activeModuleId: ModuleId
  source: SnapshotSource
  loading: boolean
}>()

const emit = defineEmits<{
  select: [id: ModuleId]
}>()

const activeModule = computed(
  () => props.modules.find(module => module.id === props.activeModuleId) ?? props.modules[0]
)

const icons = {
  agriculture: Sprout,
  ecommerce: ShoppingCart,
  crafts: Hammer,
  simulation: MonitorPlay,
  resources: Library,
  employment: Briefcase
} as const

const sourceLabel = computed(() => {
  if (props.source === 'live') {
    return 'Flask 数据'
  }
  if (props.source === 'mixed') {
    return '混合数据'
  }
  return '示例数据'
})
</script>

<template>
  <section class="hero" aria-labelledby="home-title">
    <div class="hero-grid">
      <div class="hero-copy">
        <h1 id="home-title">从技能到收入，<br />一条线打通。</h1>
        <p>
          选择农业、电商或手工方向，先在虚拟实训里练习，再连到广东本地岗位、
          求购需求和政策档案。这里是给农村学员的操作台，不是课程目录。
        </p>

        <div class="hero-actions">
          <button
            class="primary-action"
            type="button"
            @click="emit('select', activeModule.id)"
          >
            进入{{ activeModule.title }}
            <ArrowRight :size="17" aria-hidden="true" />
          </button>
          <button class="secondary-action" type="button" @click="emit('select', 'employment')">
            查看就业对接
            <Briefcase :size="16" aria-hidden="true" />
          </button>
        </div>

        <ol class="hero-path" aria-label="当前方向学习路径">
          <li>
            <strong>当前方向</strong>
            <small>{{ activeModule.title }}</small>
          </li>
          <li>
            <strong>虚拟实训</strong>
            <small>先练操作，再学理论</small>
          </li>
          <li>
            <strong>岗位 / 政策</strong>
            <small>连接本地机会</small>
          </li>
        </ol>

        <dl class="hero-metrics" aria-label="平台概览">
          <div>
            <dt>学习方向</dt>
            <dd class="ark-data">6</dd>
          </div>
          <div>
            <dt>学习路径</dt>
            <dd>学、练、连</dd>
          </div>
          <div>
            <dt>当前数据</dt>
            <dd>{{ sourceLabel }}</dd>
          </div>
        </dl>
      </div>

      <section class="dossier" :data-module="activeModule.id" aria-live="polite">
        <header class="dossier-head">
          <div>
            <h2>当前方向档案</h2>
            <strong>{{ activeModule.title }}</strong>
          </div>
          <span class="module-code ark-data">{{ activeModule.code }}</span>
        </header>

        <HomeStageArt :visual="activeModule.visual" />

        <p class="module-summary">{{ activeModule.summary }}</p>

        <dl class="module-metrics">
          <div v-for="metric in activeModule.metrics" :key="metric.label">
            <dt>{{ metric.label }}</dt>
            <dd>
              <span class="ark-data">{{ metric.value }}</span>
              <small v-if="metric.note">{{ metric.note }}</small>
            </dd>
          </div>
        </dl>

        <ul class="module-items">
          <li v-for="item in activeModule.items" :key="`${item.title}-${item.meta}`">
            <span>{{ item.tag }}</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.meta }}</small>
            <p>{{ item.detail }}</p>
          </li>
        </ul>

        <footer class="dossier-foot">
          <span :data-source="activeModule.source">
            {{ activeModule.source === 'live' ? 'Flask 已连接' : '示例数据' }}
          </span>
          <button class="dossier-action" type="button" @click="emit('select', activeModule.id)">
            {{ activeModule.actionLabel }}
            <ArrowRight :size="15" aria-hidden="true" />
          </button>
        </footer>
      </section>
    </div>

    <div class="direction-rail" role="group" aria-label="选择学习方向">
      <button
        v-for="module in modules"
        :key="module.id"
        type="button"
        :aria-pressed="module.id === activeModuleId"
        :class="{ active: module.id === activeModuleId }"
        @click="emit('select', module.id)"
      >
        <component :is="icons[module.id]" :size="18" aria-hidden="true" />
        <span>{{ module.title }}</span>
        <small>{{ module.code }}</small>
      </button>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  min-height: calc(100svh - 72px);
  padding: 48px 24px 26px;
  background:
    linear-gradient(rgb(16 23 25 / 0.055) 1px, transparent 1px),
    linear-gradient(90deg, rgb(16 23 25 / 0.045) 1px, transparent 1px);
  background-size: 72px 72px;
  background-color: var(--ark-ink);
}

.hero::after {
  content: "";
  position: absolute;
  right: 24px;
  bottom: 18px;
  width: 96px;
  height: 1px;
  background: var(--ark-signal);
}

.hero-grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.82fr) minmax(480px, 1.18fr);
  gap: 36px;
  align-items: stretch;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding-block: 28px;
}

h1 {
  margin: 0;
  font-size: 4.15rem;
  font-weight: 700;
  line-height: 0.96;
}

.hero-copy p {
  max-width: 52ch;
  margin: 28px 0 0;
  color: var(--ark-muted);
  font-size: 1.06rem;
  line-height: 1.8;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 34px;
}

.primary-action,
.secondary-action,
.dossier-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.94rem;
}

.primary-action,
.dossier-action {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.primary-action:hover,
.secondary-action:hover,
.dossier-action:hover {
  background: rgb(24 209 255 / 0.12);
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 26px 0 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.hero-path {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 30px 0 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.hero-path li {
  min-height: 88px;
  padding: 13px;
  background: rgb(255 255 255 / 0.72);
}

.hero-path strong {
  display: block;
  font-size: 0.97rem;
}

.hero-path small {
  display: block;
  margin-top: 7px;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-height: 1.5;
}

.hero-metrics div {
  min-height: 78px;
  padding: 12px;
  background: rgb(255 255 255 / 0.82);
}

.hero-metrics dt {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.hero-metrics dd {
  margin: 6px 0 0;
  font-size: 1.05rem;
}

.dossier {
  position: relative;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: rgb(255 255 255 / 0.88);
  box-shadow: 12px 14px 40px rgb(0 0 0 / 0.42);
}

.dossier::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 84px;
  height: 3px;
  background: var(--ark-signal);
}

.dossier-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px 12px;
  border-bottom: 1px solid var(--ark-line);
}

.dossier-head h2 {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  font-weight: 400;
}

.dossier-head strong {
  display: block;
  margin-top: 3px;
  font-size: 1.55rem;
  line-height: 1.2;
}

.module-code {
  padding: 5px 8px;
  border: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.76rem;
}

.module-summary {
  margin: 0;
  padding: 15px 18px 0;
  color: var(--ark-muted);
  font-size: 0.94rem;
  line-height: 1.72;
}

.module-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 16px 18px 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.module-metrics div {
  min-height: 66px;
  padding: 9px 10px;
  background: var(--ark-surface-1);
}

.module-metrics dt {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.module-metrics dd {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 5px 0 0;
  font-size: 1.02rem;
}

.module-metrics small {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.module-items {
  display: grid;
  margin: 0;
  padding: 14px 18px 16px;
  list-style: none;
  border-bottom: 1px solid var(--ark-line);
}

.module-items li {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  gap: 4px 12px;
  align-items: baseline;
  padding: 11px 0;
  border-bottom: 1px solid rgb(16 23 25 / 0.12);
}

.module-items li:last-child {
  border-bottom: 0;
}

.module-items span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.module-items strong {
  min-width: 0;
  font-size: 1rem;
}

.module-items small {
  color: var(--ark-muted);
  font-size: 0.76rem;
  white-space: nowrap;
}

.module-items p {
  grid-column: 2 / 4;
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-height: 1.6;
}

.dossier-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 18px;
  background: rgb(16 23 25 / 0.035);
}

.dossier-foot span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.dossier-foot span[data-source="live"] {
  color: var(--ark-state);
}

.dossier-action {
  min-height: 40px;
  font-size: 0.84rem;
}

.direction-rail {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  width: min(100%, var(--ark-shell-max));
  margin: 28px auto 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.direction-rail button {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  gap: 4px 8px;
  align-items: center;
  min-height: 62px;
  padding: 10px;
  border: 0;
  background: var(--ark-ink);
  color: var(--ark-muted);
  text-align: left;
}

.direction-rail button span {
  overflow: hidden;
  color: inherit;
  font-size: 0.9rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.direction-rail button small {
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.direction-rail button:hover,
.direction-rail button.active {
  background: var(--ark-surface-2);
  color: var(--ark-paper);
}

.direction-rail button.active {
  box-shadow: inset 0 -3px 0 var(--ark-signal);
}

.direction-rail button.active svg {
  color: var(--ark-signal);
}

@media (max-width: 1280px) {
  h1 {
    font-size: 3.55rem;
  }
}

@media (max-width: 1080px) {
  .hero {
    min-height: auto;
    padding: 34px 18px 22px;
  }

  .hero-grid {
    grid-template-columns: 1fr;
  }

  h1 {
    font-size: 3.15rem;
  }

  .direction-rail {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 700px) {
  h1 {
    font-size: 2.5rem;
  }

  .hero-copy p {
    font-size: 1rem;
  }

  .hero-metrics,
  .hero-path,
  .module-metrics {
    grid-template-columns: 1fr;
  }

  .dossier-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-items li {
    grid-template-columns: minmax(0, 1fr);
  }

  .module-items p {
    grid-column: auto;
  }

  .dossier-foot {
    align-items: stretch;
    flex-direction: column;
  }

  .dossier-action {
    width: 100%;
  }
}

@media (max-width: 520px) {
  .hero {
    padding: 24px 12px 18px;
  }

  h1 {
    font-size: 2.25rem;
  }

  .hero-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .primary-action,
  .secondary-action {
    width: 100%;
  }

  .direction-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .module-items small {
    white-space: normal;
  }
}
</style>
