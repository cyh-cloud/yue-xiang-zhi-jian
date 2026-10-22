<script setup lang="ts">
import { RouterLink } from "vue-router";

import DialectAssistant from "@/components/resources/DialectAssistant.vue";
import ResourceCases from "@/components/resources/ResourceCases.vue";
import ResourcePolicies from "@/components/resources/ResourcePolicies.vue";
</script>

<template>
  <section
    id="resources-tab"
    class="tab-content active resources-view"
    aria-labelledby="resources-title"
  >
    <div class="container">
      <div class="section-label">
        Local Resources
      </div>
      <h1
        id="resources-title"
        class="section-title"
      >
        本土化资源库
      </h1>
      <p class="section-desc">
        方言交互支持、本地成功案例、政策信息推送
      </p>
      <RouterLink
        class="resources-community-link"
        to="/community"
      >
        <i
          class="fas fa-comments"
          aria-hidden="true"
        />
        进入社区讨论
      </RouterLink>

      <DialectAssistant />
      <ResourceCases />
      <ResourcePolicies />
    </div>
  </section>
</template>

<style src="./resources/resources.css"></style>

<style scoped>
.resources-community-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: -10px 0 24px;
  color: var(--accent-green);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
}

.resources-community-link:hover {
  text-decoration: underline;
}
</style>
