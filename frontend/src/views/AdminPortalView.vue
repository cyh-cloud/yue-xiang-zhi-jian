<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRouter } from 'vue-router'

import type { AdminConsoleRole } from '@/api/types'
import AdminConsoleNav from '@/components/AdminConsoleNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const role = computed<AdminConsoleRole>(() =>
  auth.user?.role === 'super_admin' ? 'super_admin' : 'admin'
)

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<template>
  <div
    class="admin-console"
    data-test="admin-console"
    data-ark-theme="ark"
    data-ark-depth="maximal"
  >
    <AppHeader
      source="live"
      :loading="false"
      :user-name="auth.user?.name"
      @logout="logout"
    />

    <AdminConsoleNav :role="role" />

    <main class="admin-console__content" data-test="admin-console-content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.admin-console {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.admin-console__content {
  width: min(100%, 1320px);
  min-width: 0;
  margin-inline: auto;
  padding: 28px 24px 72px;
}

@media (max-width: 720px) {
  .admin-console__content {
    padding: 18px 14px 48px;
  }
}
</style>
