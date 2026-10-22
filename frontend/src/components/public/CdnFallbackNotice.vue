<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

const failures = ref<string[]>([]);
let observer: MutationObserver | null = null;

function updateFailures(): void {
  const next: string[] = [];
  if (document.documentElement.dataset.cdnFontAwesome === "failed") {
    next.push("Font Awesome 图标资源加载失败，部分图标可能无法显示。");
  }
  if (document.documentElement.dataset.cdnModelViewer === "failed") {
    next.push("model-viewer 资源加载失败，3D 预览暂不可用。");
  }
  failures.value = next;
}

onMounted(() => {
  updateFailures();
  observer = new MutationObserver(updateFailures);
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["data-cdn-font-awesome", "data-cdn-model-viewer"],
  });
});

onBeforeUnmount(() => {
  observer?.disconnect();
});
</script>

<template>
  <div
    v-if="failures.length"
    class="cdn-fallback"
    role="status"
    aria-live="polite"
  >
    <strong>外部资源降级</strong>
    <span
      v-for="message in failures"
      :key="message"
    >
      {{ message }}
    </span>
  </div>
</template>
