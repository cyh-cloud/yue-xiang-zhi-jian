<script setup lang="ts">
defineProps<{
  visual: 'field' | 'broadcast' | 'craft' | 'lab' | 'archive' | 'network'
}>()
</script>

<template>
  <svg
    class="module-visual"
    :data-visual="visual"
    viewBox="0 0 260 180"
    aria-hidden="true"
  >
    <g v-if="visual === 'field'">
      <rect x="18" y="24" width="224" height="132" />
      <path d="M18 62h224M18 100h224M18 138h224" />
      <path d="M52 34v118M96 34v118M140 34v118M184 34v118" />
      <path d="M18 80h70l24 22h58l28-24h44" />
      <circle cx="216" cy="38" r="10" />
    </g>

    <g v-else-if="visual === 'broadcast'">
      <rect x="20" y="42" width="96" height="96" />
      <path d="M128 68c16 10 16 34 0 44M148 52c28 18 28 58 0 76" />
      <path d="M20 74h96M20 96h72M20 118h84" />
      <rect x="178" y="62" width="62" height="12" />
      <rect x="196" y="90" width="44" height="12" />
      <rect x="184" y="118" width="56" height="12" />
    </g>

    <g v-else-if="visual === 'craft'">
      <rect x="28" y="24" width="204" height="132" />
      <path d="M28 58h204M28 92h204M28 126h204" />
      <path d="M48 36c34 30 76-22 112 12s54 4 54 4" />
      <path d="M48 108c42-32 82 28 126-8" />
      <circle cx="72" cy="72" r="7" />
      <circle cx="188" cy="112" r="7" />
    </g>

    <g v-else-if="visual === 'lab'">
      <circle cx="130" cy="90" r="54" />
      <path d="M130 20v30M130 130v30M60 90h30M170 90h30" />
      <path d="M100 90h60M130 60v60" />
      <rect x="24" y="38" width="38" height="24" />
      <rect x="198" y="118" width="38" height="24" />
    </g>

    <g v-else-if="visual === 'archive'">
      <rect x="24" y="24" width="212" height="132" />
      <path d="M24 68h212M24 112h212" />
      <path d="M48 36h78M48 50h52M48 80h96M48 94h64M48 124h84M48 138h42" />
      <path d="M174 36l38 24v64l-38 24z" />
    </g>

    <g v-else>
      <circle cx="46" cy="42" r="15" />
      <circle cx="46" cy="138" r="15" />
      <circle cx="130" cy="90" r="25" />
      <circle cx="214" cy="54" r="16" />
      <circle cx="214" cy="126" r="16" />
      <path d="M61 48l49 31M61 132l49-31M155 78l45-17M155 102l45 17" />
      <path d="M40 90h18M202 90h12" />
    </g>
  </svg>
</template>

<style scoped>
.module-visual {
  display: block;
  width: 100%;
  height: auto;
  color: rgb(16 23 25 / 0.62);
}

.module-visual g * {
  fill: none;
  stroke: currentColor;
  stroke-width: 1;
}

.module-visual circle,
.module-visual rect {
  fill: rgb(16 23 25 / 0.04);
}

.module-visual g > :last-child,
.module-visual [data-visual="field"] path:nth-child(5),
.module-visual [data-visual="broadcast"] path:nth-child(2),
.module-visual [data-visual="craft"] path:nth-child(4),
.module-visual [data-visual="lab"] path:nth-child(4),
.module-visual [data-visual="archive"] path:nth-child(7),
.module-visual [data-visual="network"] path:nth-child(6) {
  stroke: var(--ark-signal);
}
</style>
