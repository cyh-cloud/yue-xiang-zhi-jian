<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'

import ModuleVisual from '@/components/ModuleVisual.vue'
import type { HomeModule } from '@/api/types'

defineProps<{
  module: HomeModule
  active: boolean
}>()

const emit = defineEmits<{
  activate: [id: HomeModule['id']]
}>()
</script>

<template>
  <section
    :id="`module-${module.id}`"
    class="module"
    :data-module="module.id"
    :data-active="active"
    :data-source="module.source"
    :aria-labelledby="`module-title-${module.id}`"
  >
    <div class="module-frame">
      <header class="module-intro">
        <div class="title-row">
          <h2 :id="`module-title-${module.id}`">{{ module.title }}</h2>
          <span class="module-code ark-data">{{ module.code }}</span>
        </div>
        <p>{{ module.summary }}</p>

        <dl class="module-metrics" :aria-label="`${module.title}概览`">
          <div v-for="metric in module.metrics" :key="metric.label">
            <dt>{{ metric.label }}</dt>
            <dd>
              <span class="ark-data">{{ metric.value }}</span>
              <small v-if="metric.note">{{ metric.note }}</small>
            </dd>
          </div>
        </dl>
      </header>

      <div class="module-stage">
        <ModuleVisual :visual="module.visual" />
        <div class="stage-caption">
          <span>{{ module.latin }}</span>
          <span :data-source="module.source">
            {{ module.source === 'live' ? 'Flask' : '示例' }}
          </span>
        </div>
      </div>

      <ol class="module-items" :aria-label="`${module.title}代表内容`">
        <li v-for="item in module.items" :key="`${item.tag}-${item.title}-${item.meta}`">
          <span class="item-tag">{{ item.tag }}</span>
          <div class="item-copy">
            <strong>{{ item.title }}</strong>
            <small>{{ item.meta }}</small>
            <p>{{ item.detail }}</p>
          </div>
        </li>
      </ol>

      <footer class="module-foot">
        <button type="button" @click="emit('activate', module.id)">
          设为当前方向
          <ArrowUpRight :size="15" aria-hidden="true" />
        </button>
        <span>
          {{ module.source === 'live' ? '数据来源：Flask API' : '数据来源：前端示例数据' }}
        </span>
      </footer>
    </div>
  </section>
</template>

<style scoped>
.module {
  position: relative;
  padding: clamp(52px, 7vw, 92px) 24px;
  scroll-margin-top: clamp(92px, 11vw, 124px);
  border-top: 1px solid var(--ark-line);
  background: var(--ark-ink);
}

.module:nth-of-type(odd) {
  background: linear-gradient(rgb(244 246 246 / 0.018), transparent 38%), var(--ark-ink);
}

.module[data-active="true"]::before {
  content: "";
  position: absolute;
  top: -1px;
  left: 0;
  width: 112px;
  height: 2px;
  background: var(--ark-signal);
}

.module-frame {
  display: grid;
  gap: 24px;
  width: min(100%, var(--ark-shell-max));
  margin-inline: auto;
}

.module-intro {
  min-width: 0;
  grid-area: intro;
}

.module-stage {
  grid-area: stage;
}

.module-items {
  grid-area: items;
}

.module-foot {
  grid-area: foot;
}

.title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--ark-line-strong);
}

h2 {
  margin: 0;
  font-size: clamp(2.1rem, 4vw, 3.5rem);
  font-weight: 700;
  line-height: 1;
}

.module-code {
  flex: 0 0 auto;
  padding: 5px 8px;
  border: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.76rem;
}

.module-intro p {
  max-width: 62ch;
  margin: 18px 0 0;
  color: #c9d2d4;
  font-size: 1rem;
  line-height: 1.75;
}

.module-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 24px 0 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.module-metrics div {
  min-height: 72px;
  padding: 10px;
  background: var(--ark-surface-1);
}

.module-metrics dt {
  color: var(--ark-muted);
  font-size: 0.73rem;
}

.module-metrics dd {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin: 6px 0 0;
  font-size: 1rem;
}

.module-metrics small {
  color: var(--ark-muted);
  font-size: 0.64rem;
}

.module-stage {
  position: relative;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: rgb(5 6 7 / 0.88);
}

.module-stage::after {
  content: "";
  position: absolute;
  top: 0;
  right: 0;
  width: 34px;
  height: 34px;
  border-top: 1px solid var(--ark-signal);
  border-right: 1px solid var(--ark-signal);
}

.module-stage svg {
  width: 100%;
  height: auto;
  aspect-ratio: 13 / 9;
  padding: clamp(10px, 2vw, 22px);
}

.stage-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-top: 1px solid var(--ark-line);
}

.stage-caption span:first-child {
  overflow: hidden;
  color: var(--ark-muted);
  font-size: 0.66rem;
  letter-spacing: 0.14em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}

.stage-caption span:last-child {
  flex: 0 0 auto;
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.stage-caption span[data-source="live"] {
  color: var(--ark-state);
}

.module-items {
  display: grid;
  min-width: 0;
  margin: 0;
  padding: 0;
  list-style: none;
  border-top: 1px solid var(--ark-line);
}

.module-items li {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 8px 16px;
  padding: 15px 0;
  border-bottom: 1px solid rgb(244 246 246 / 0.09);
}

.item-tag {
  padding-top: 3px;
  color: var(--ark-signal);
  font-size: 0.73rem;
}

.item-copy {
  min-width: 0;
}

.item-copy strong {
  display: block;
  font-size: 1.05rem;
  line-height: 1.35;
}

.item-copy small {
  display: block;
  margin-top: 4px;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.item-copy p {
  margin: 7px 0 0;
  color: #bac3c6;
  font-size: 0.88rem;
  line-height: 1.65;
}

.module-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding-top: 8px;
}

.module-foot button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.module-foot button:hover,
.module-foot button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
  background: rgb(24 209 255 / 0.1);
}

.module-foot span {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

/* 每个方向保留同一 shell grammar，但主体构图不同。 */
.module[data-module="agriculture"] .module-frame {
  grid-template-areas:
    "intro stage"
    "items items"
    "foot foot";
  grid-template-columns: minmax(0, 0.82fr) minmax(0, 1.18fr);
}

.module[data-module="agriculture"] .module-intro {
  grid-area: intro;
}

.module[data-module="agriculture"] .module-stage {
  grid-area: stage;
}

.module[data-module="agriculture"] .module-items {
  grid-area: items;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0 26px;
}

.module[data-module="agriculture"] .module-items li {
  grid-template-columns: 1fr;
}

.module[data-module="agriculture"] .module-foot {
  grid-area: foot;
}

.module[data-module="ecommerce"] .module-frame {
  grid-template-areas:
    "stage intro"
    "stage items"
    "foot foot";
  grid-template-columns: minmax(300px, 0.92fr) minmax(0, 1.08fr);
}

.module[data-module="crafts"] .module-frame {
  grid-template-areas:
    "intro intro"
    "stage items"
    "foot foot";
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.1fr);
}

.module[data-module="crafts"] .module-items {
  display: grid;
  gap: 0;
}

.module[data-module="crafts"] .item-tag {
  width: 76px;
  height: 1px;
  margin-top: 14px;
  padding: 0;
  background: var(--ark-signal);
}

.module[data-module="simulation"] .module-frame {
  grid-template-areas:
    "stage intro"
    "items intro"
    "foot foot";
  grid-template-columns: minmax(320px, 1.08fr) minmax(0, 0.92fr);
}

.module[data-module="simulation"] .module-items {
  grid-area: items;
  align-content: start;
  border-top: 0;
}

.module[data-module="simulation"] .module-items li {
  grid-template-columns: minmax(0, 1fr) minmax(180px, 0.72fr);
  gap: 4px 20px;
  align-items: baseline;
  padding-left: 18px;
  padding-block: 14px;
  border-left: 1px solid var(--ark-line-strong);
}

.module[data-module="simulation"] .item-copy {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
}

.module[data-module="simulation"] .item-copy p {
  margin-top: 4px;
}

.module[data-module="resources"] .module-frame {
  grid-template-areas:
    "intro items"
    "stage foot";
  grid-template-columns: minmax(280px, 0.72fr) minmax(0, 1.28fr);
  grid-template-rows: auto 1fr;
}

.module[data-module="resources"] .module-stage {
  max-width: 380px;
}

.module[data-module="resources"] .module-items {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 28px;
}

.module[data-module="employment"] .module-frame {
  grid-template-areas:
    "intro stage"
    "items items"
    "foot foot";
  grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
}

.module[data-module="employment"] .module-items {
  border: 1px solid var(--ark-line);
}

.module[data-module="employment"] .module-items li {
  grid-template-columns: 92px minmax(0, 1fr) 190px;
  gap: 8px 16px;
  padding: 14px 16px;
}

.module[data-module="employment"] .item-copy {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 170px;
  gap: 4px 18px;
  align-items: baseline;
}

.module[data-module="employment"] .item-copy p {
  grid-column: 1 / -1;
}

@media (max-width: 1080px) {
  .module-frame,
  .module[data-module="agriculture"] .module-frame,
  .module[data-module="ecommerce"] .module-frame,
  .module[data-module="crafts"] .module-frame,
  .module[data-module="simulation"] .module-frame,
  .module[data-module="resources"] .module-frame,
  .module[data-module="employment"] .module-frame {
    grid-template-areas:
      "intro"
      "stage"
      "items"
      "foot";
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto;
  }

  .module-intro,
  .module-stage,
  .module-items,
  .module-foot {
    grid-column: auto;
    grid-row: auto;
  }

  .module[data-module="agriculture"] .module-intro,
  .module[data-module="agriculture"] .module-stage,
  .module[data-module="agriculture"] .module-items,
  .module[data-module="agriculture"] .module-foot,
  .module[data-module="ecommerce"] .module-stage,
  .module[data-module="resources"] .module-stage {
    grid-column: auto;
    grid-row: auto;
  }

  .module[data-module="agriculture"] .module-items,
  .module[data-module="resources"] .module-items {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
  }

  .module[data-module="employment"] .module-items li,
  .module[data-module="employment"] .item-copy {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 700px) {
  .module {
    padding-inline: 14px;
  }

  .title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .module-metrics {
    grid-template-columns: 1fr;
  }

  .module-items li,
  .module[data-module="agriculture"] .module-items li,
  .module[data-module="simulation"] .module-items li {
    grid-template-columns: minmax(0, 1fr);
    gap: 4px;
    padding-left: 0;
    border-left: 0;
  }

  .module[data-module="simulation"] .item-copy {
    grid-template-columns: minmax(0, 1fr);
  }

  .module[data-module="crafts"] .item-tag {
    display: block;
    width: 42px;
    margin-top: 0;
  }

  .module-foot {
    align-items: stretch;
    flex-direction: column;
  }

  .module-foot button {
    width: 100%;
  }
}
</style>
