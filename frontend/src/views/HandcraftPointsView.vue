<script setup lang="ts">
import { useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import HandcraftInheritanceNav from '@/components/HandcraftInheritanceNav.vue'
import HandcraftPointsPanel from '@/components/HandcraftPointsPanel.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="handcraft-points-page">
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <HandcraftInheritanceNav />
    <HandcraftPointsPanel />
  </div>
</template>

<style scoped>
.handcraft-points-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}
</style>
