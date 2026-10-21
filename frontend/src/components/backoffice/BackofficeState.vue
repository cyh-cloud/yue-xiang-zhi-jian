<script setup lang="ts">
withDefaults(
  defineProps<{
    kind?: "loading" | "empty" | "error";
    title: string;
    detail?: string;
  }>(),
  { kind: "empty", detail: "" },
);
</script>

<template>
  <div
    class="backoffice-state"
    :class="`is-${kind}`"
    :role="kind === 'error' ? 'alert' : 'status'"
  >
    <i
      class="fas"
      :class="{
        'fa-spinner fa-spin': kind === 'loading',
        'fa-inbox': kind === 'empty',
        'fa-triangle-exclamation': kind === 'error',
      }"
      aria-hidden="true"
    />
    <strong>{{ title }}</strong>
    <p v-if="detail">
      {{ detail }}
    </p>
    <slot />
  </div>
</template>
