<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next'
import { onMounted } from 'vue'

import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import EnterpriseDashboardCards from '@/components/EnterpriseDashboardCards.vue'
import PortalShell from '@/components/PortalShell.vue'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

const store = useEnterpriseConsoleStore()

onMounted(() => {
  void store.loadDashboard()
})
</script>

<template>
  <PortalShell portal="enterprise">
    <EnterpriseConsoleNav />
    <section
      id="enterprise-dashboard"
      class="enterprise-portal-dashboard"
      aria-labelledby="enterprise-dashboard-title"
    >
      <header class="enterprise-portal-dashboard__heading">
        <span class="ark-data">ENTERPRISE CONSOLE</span>
        <h2 id="enterprise-dashboard-title">企业数据</h2>
        <p>当前企业的在招职位与累计收到简历。</p>
      </header>
      <EnterpriseDashboardCards
        :dashboard="store.dashboard"
        :loading="store.loading"
      />
      <div
        v-if="store.error"
        class="enterprise-portal-dashboard__error"
        role="alert"
      >
        <span>{{ store.error }}</span>
        <button
          type="button"
          data-test="dashboard-retry"
          @click="store.loadDashboard"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </div>
    </section>
  </PortalShell>
</template>

<style scoped>
.enterprise-portal-dashboard {
  width: min(100%, 1180px);
  min-width: 0;
  margin: 28px auto 0;
  overflow-x: clip;
}

.enterprise-portal-dashboard__heading {
  margin-bottom: 12px;
}

.enterprise-portal-dashboard__heading > span {
  color: var(--ark-signal);
  font-size: 0.68rem;
}

.enterprise-portal-dashboard__heading h2 {
  margin: 3px 0 0;
  font-size: 1.1rem;
  line-height: 1.35;
  text-wrap: balance;
}

.enterprise-portal-dashboard__heading p {
  max-width: 62ch;
  margin: 8px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-portal-dashboard__error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.enterprise-portal-dashboard__error span {
  min-width: 0;
  overflow-wrap: break-word;
  word-break: normal;
}

.enterprise-portal-dashboard__error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 40px;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.enterprise-portal-dashboard__error button:hover,
.enterprise-portal-dashboard__error button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

@media (max-width: 720px) {
  .enterprise-portal-dashboard {
    margin-top: 18px;
  }

  .enterprise-portal-dashboard__error {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
