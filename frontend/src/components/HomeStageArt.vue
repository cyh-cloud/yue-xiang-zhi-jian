<script setup lang="ts">
defineProps<{
  visual: 'field' | 'broadcast' | 'craft' | 'lab' | 'archive' | 'network'
}>()
</script>

<template>
  <svg
    class="stage-art"
    :data-visual="visual"
    viewBox="0 0 720 420"
    role="img"
    aria-label="学习、实训与就业对接流程图"
  >
    <rect class="ground" x="0" y="0" width="720" height="420" />

    <g class="grid">
      <path d="M90 42V378M180 42V378M270 42V378M360 42V378M450 42V378M540 42V378M630 42V378" />
      <path d="M42 90H678M42 160H678M42 230H678M42 300H678" />
    </g>

    <g class="source">
      <rect x="58" y="82" width="96" height="62" />
      <rect x="58" y="176" width="96" height="62" />
      <rect x="58" y="270" width="96" height="62" />
    </g>

    <g class="learner">
      <rect x="292" y="152" width="136" height="112" />
      <path d="M316 186h88M316 214h88M316 242h52" />
    </g>

    <g class="destination">
      <path d="M568 116h92v52h-92z" />
      <path d="M568 272h92v52h-92z" />
    </g>

    <g class="routes">
      <path class="route route-field" d="M154 113H222V208H292" />
      <path class="route route-broadcast" d="M154 207H292" />
      <path class="route route-craft" d="M154 301H222V224H292" />
      <path class="route route-lab" d="M428 186H500V142H568" />
      <path class="route route-archive" d="M428 208H568" />
      <path class="route route-network" d="M428 230H500V298H568" />
    </g>

    <g class="markers">
      <circle cx="154" cy="113" r="4" />
      <circle cx="154" cy="207" r="4" />
      <circle cx="154" cy="301" r="4" />
      <circle cx="292" cy="208" r="4" />
      <circle cx="428" cy="208" r="4" />
      <circle cx="568" cy="142" r="4" />
      <circle cx="568" cy="298" r="4" />
    </g>
  </svg>
</template>

<style scoped>
.stage-art {
  display: block;
  width: 100%;
  height: auto;
  background: var(--ark-surface-0);
}

.ground {
  fill: var(--ark-surface-0);
}

.grid path {
  stroke: rgb(244 246 246 / 0.08);
  stroke-width: 1;
}

.source rect,
.learner rect,
.destination path {
  fill: rgb(244 246 246 / 0.06);
  stroke: rgb(244 246 246 / 0.42);
  stroke-width: 1;
}

.learner rect {
  stroke: rgb(244 246 246 / 0.62);
}

.learner path {
  stroke: rgb(244 246 246 / 0.4);
  stroke-width: 1;
}

.routes path {
  fill: none;
  stroke: rgb(244 246 246 / 0.24);
  stroke-width: 1;
}

.markers circle {
  fill: rgb(244 246 246 / 0.4);
}

.stage-art[data-visual="field"] .route-field,
.stage-art[data-visual="broadcast"] .route-broadcast,
.stage-art[data-visual="craft"] .route-craft,
.stage-art[data-visual="lab"] .route-lab,
.stage-art[data-visual="archive"] .route-archive,
.stage-art[data-visual="network"] .route-network {
  stroke: var(--ark-signal);
  stroke-width: 2;
}

.stage-art[data-visual="field"] .source rect:nth-child(1),
.stage-art[data-visual="broadcast"] .source rect:nth-child(2),
.stage-art[data-visual="craft"] .source rect:nth-child(3),
.stage-art[data-visual="lab"] .destination path:nth-child(1),
.stage-art[data-visual="archive"] .destination path:nth-child(2),
.stage-art[data-visual="network"] .destination path:nth-child(2) {
  stroke: var(--ark-signal);
  fill: rgb(24 209 255 / 0.08);
}

.routes path {
  transition: stroke 220ms ease, stroke-width 220ms ease;
}

.source rect,
.destination path {
  transition: fill 220ms ease, stroke 220ms ease;
}
</style>
