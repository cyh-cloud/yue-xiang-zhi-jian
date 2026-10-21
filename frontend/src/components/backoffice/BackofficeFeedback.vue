<script setup lang="ts">
defineProps<{
  kind: "info" | "success" | "error";
  message: string;
  testid?: string;
}>();
</script>

<template>
  <div
    v-if="message"
    class="backoffice-feedback"
    :class="`is-${kind}`"
    :data-testid="testid"
    :role="kind === 'error' ? 'alert' : 'status'"
  >
    <i
      class="fas"
      :class="{
        'fa-circle-info': kind === 'info',
        'fa-circle-check': kind === 'success',
        'fa-triangle-exclamation': kind === 'error',
      }"
      aria-hidden="true"
    />
    {{ message }}
  </div>
</template>
