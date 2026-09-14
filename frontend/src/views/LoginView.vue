<script setup lang="ts">
import { ArrowRight, KeyRound, LogIn } from 'lucide-vue-next'
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import type { AuthUser } from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import FormField from '@/components/FormField.vue'
import type { AuthRouteMeta } from '@/router/roleRoutes'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({
  username: '',
  password: ''
})
const usernameField = ref<{ focus: () => void } | null>(null)
const recoveryVisible = ref(false)

function validRedirect(user: AuthUser): string | null {
  const redirect = route.query.redirect
  if (
    typeof redirect !== 'string' ||
    !redirect.startsWith('/') ||
    redirect.startsWith('//')
  ) {
    return null
  }

  try {
    const resolved = router.resolve(redirect)
    if (!resolved.matched.length) {
      return null
    }

    const name = typeof resolved.name === 'string' ? resolved.name : ''
    if (name === 'login' || name === 'register' || name === 'interest-tags') {
      return null
    }

    const meta = resolved.meta as AuthRouteMeta
    if (meta.roles?.length && !meta.roles.includes(user.role)) {
      return null
    }

    return resolved.fullPath
  } catch {
    return null
  }
}

async function submitLogin() {
  if (auth.loading) {
    return
  }

  const response = await auth.login(form.username, form.password)
  if (!response) {
    return
  }

  await router.push(validRedirect(response.user) ?? response.default_path)
}

onMounted(() => {
  usernameField.value?.focus()
})
</script>

<template>
  <div class="auth-page">
    <AppHeader
      source="mock"
      :loading="false"
      variant="auth"
      :show-auth-controls="false"
    />

    <main class="auth-layout">
      <section class="auth-intro" aria-labelledby="login-title">
        <h1 id="login-title">登录粤乡智匠</h1>
        <p>
          登录后继续学习、实训与就业对接。账号身份由平台统一校验，登录状态保存在安全的
          HttpOnly Cookie 中。
        </p>

        <dl class="access-notes">
          <div>
            <dt>统一入口</dt>
            <dd>六类角色使用同一登录页</dd>
          </div>
          <div>
            <dt>会话安全</dt>
            <dd>不写入浏览器本地存储</dd>
          </div>
        </dl>
      </section>

      <section class="auth-panel" aria-labelledby="login-panel-title">
        <header>
          <span class="panel-mark" aria-hidden="true"></span>
          <div>
            <h2 id="login-panel-title">账号登录</h2>
            <p>输入用户名和密码进入对应门户。</p>
          </div>
        </header>

        <form novalidate @submit.prevent="submitLogin">
          <FormField
            id="login-username"
            ref="usernameField"
            v-model="form.username"
            label="用户名"
            autocomplete="username"
            required
          />
          <FormField
            id="login-password"
            v-model="form.password"
            label="密码"
            type="password"
            autocomplete="current-password"
            required
          />

          <p v-if="auth.error" class="auth-error" role="alert">
            {{ auth.error }}
          </p>

          <button
            class="forgot-button"
            type="button"
            :aria-expanded="recoveryVisible"
            @click="recoveryVisible = true"
          >
            <KeyRound :size="15" aria-hidden="true" />
            忘记密码
          </button>
          <p v-if="recoveryVisible" class="recovery-message" aria-live="polite">
            请联系管理员重置密码
          </p>

          <button class="primary-action" type="submit" :disabled="auth.loading">
            <LogIn :size="17" aria-hidden="true" />
            {{ auth.loading ? '正在登录' : '登录' }}
          </button>
        </form>

        <footer>
          <span>还没有账号？</span>
          <RouterLink to="/register">
            注册学员或教师账号
            <ArrowRight :size="15" aria-hidden="true" />
          </RouterLink>
        </footer>
      </section>
    </main>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100svh;
  background:
    linear-gradient(rgb(244 246 246 / 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgb(244 246 246 / 0.028) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.auth-layout {
  display: grid;
  grid-template-columns: minmax(0, 0.86fr) minmax(420px, 0.64fr);
  gap: 52px;
  align-items: center;
  width: min(100%, 1180px);
  min-height: calc(100svh - 72px);
  margin-inline: auto;
  padding: 48px 24px 64px;
}

.auth-intro h1 {
  max-width: 12ch;
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
}

.auth-intro > p {
  max-width: 48ch;
  margin: 22px 0 0;
  color: #c4cdcf;
  line-height: 1.8;
}

.access-notes {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  max-width: 560px;
  margin: 34px 0 0;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.access-notes div {
  min-height: 92px;
  padding: 14px;
  background: rgb(5 6 7 / 0.74);
}

.access-notes dt {
  color: var(--ark-signal);
  font-size: 0.77rem;
}

.access-notes dd {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-height: 1.55;
}

.auth-panel {
  position: relative;
  border: 1px solid var(--ark-line-strong);
  background: rgb(5 6 7 / 0.92);
  box-shadow: 14px 18px 44px rgb(0 0 0 / 0.42);
}

.auth-panel::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 92px;
  height: 3px;
  background: var(--ark-signal);
}

.auth-panel header {
  display: grid;
  grid-template-columns: 4px minmax(0, 1fr);
  gap: 13px;
  padding: 22px 20px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.panel-mark {
  background: var(--ark-signal);
}

.auth-panel h2 {
  margin: 0;
  font-size: 1.45rem;
}

.auth-panel header p {
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
}

form {
  display: grid;
  gap: 17px;
  padding: 20px;
}

.auth-error {
  margin: 0;
  padding: 10px 11px;
  border: 1px solid rgb(255 138 138 / 0.44);
  background: rgb(255 138 138 / 0.08);
  color: #ff9c9c;
  font-size: 0.8rem;
}

.forgot-button {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 7px;
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ark-muted);
  font-size: 0.8rem;
}

.forgot-button:hover,
.forgot-button:focus-visible {
  color: var(--ark-signal);
}

.recovery-message {
  margin: -8px 0 0;
  padding: 9px 10px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  font-size: 0.82rem;
}

.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-signal);
  font-size: 0.92rem;
}

.primary-action:hover:not(:disabled) {
  background: rgb(24 209 255 / 0.12);
}

.auth-panel footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 15px 20px 18px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-muted);
  font-size: 0.8rem;
}

.auth-panel footer a {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ark-signal);
  text-decoration: none;
}

@media (max-width: 900px) {
  .auth-layout {
    grid-template-columns: 1fr;
    gap: 30px;
    padding-top: 32px;
  }

  .auth-intro h1 {
    max-width: none;
    font-size: 2.45rem;
  }
}

@media (max-width: 520px) {
  .auth-layout {
    padding: 24px 12px 44px;
  }

  .auth-intro h1 {
    font-size: 2.15rem;
  }

  .access-notes {
    grid-template-columns: 1fr;
  }

  .auth-panel footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
