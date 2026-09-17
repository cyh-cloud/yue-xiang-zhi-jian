<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import HandcraftCraftLearning from '@/components/HandcraftCraftLearning.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const craftKey = computed(() => String(route.params.craftKey ?? ''))

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="handcraft-craft-page">
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <HandcraftInheritanceNav />
    <HandcraftCraftLearning :key="craftKey" :craft-key="craftKey" />
  </div>
</template>

<style scoped>
.handcraft-craft-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}
</style>
