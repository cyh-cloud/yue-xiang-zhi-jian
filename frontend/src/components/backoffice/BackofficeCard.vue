<script setup lang="ts">
defineProps<{
  title?: string;
  description?: string;
  flush?: boolean;
}>();
</script>

<template>
  <section
    class="bo-card"
    :class="{ 'is-flush': flush }"
  >
    <header
      v-if="title || $slots.actions"
      class="bo-card-head"
    >
      <div>
        <h2 v-if="title">
          {{ title }}
        </h2>
        <p v-if="description">
          {{ description }}
        </p>
      </div>
      <div
        v-if="$slots.actions"
        class="bo-card-actions"
      >
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>
