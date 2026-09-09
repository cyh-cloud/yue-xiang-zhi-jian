<script setup lang="ts">
import { nextTick, reactive, ref, watch } from 'vue'
import { LogIn, UserPlus, X } from 'lucide-vue-next'

import { demoAccounts, useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const panel = ref<HTMLElement | null>(null)
let previousFocusedElement: HTMLElement | null = null

const loginForm = reactive({
  username: '',
  password: ''
})

const registerForm = reactive({
  username: '',
  password: '',
  name: '',
  role: 'student',
  phone: '',
  region: '',
  company_name: ''
})

watch(
  () => auth.dialogOpen,
  async open => {
    if (!open) {
      const elementToRestore = previousFocusedElement
      previousFocusedElement = null

      await nextTick()
      elementToRestore?.focus()
      return
    }

    previousFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null
    loginForm.username = ''
    loginForm.password = ''
    registerForm.username = ''
    registerForm.password = ''
    registerForm.name = ''
    registerForm.role = 'student'
    registerForm.phone = ''
    registerForm.region = ''
    registerForm.company_name = ''

    await nextTick()
    focusFirstFormControl()
  }
)

watch(
  () => auth.mode,
  async () => {
    if (!auth.dialogOpen) {
      return
    }

    await nextTick()
    focusFirstFormControl()
  }
)

function focusFirstFormControl() {
  panel.value?.querySelector<HTMLElement>('form input, form select, form button')?.focus()
}

function fillDemo(account: (typeof demoAccounts)[number]) {
  loginForm.username = account.username
  loginForm.password = account.password
}

function submitLogin() {
  void auth.login(loginForm.username, loginForm.password)
}

function submitRegister() {
  void auth.register({
    username: registerForm.username,
    password: registerForm.password,
    name: registerForm.name,
    role: registerForm.role,
    phone: registerForm.phone || undefined,
    region: registerForm.region || undefined,
    company_name: registerForm.role === 'enterprise' ? registerForm.company_name || undefined : undefined
  })
}

function trapFocus(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    auth.closeDialog()
    return
  }

  if (event.key !== 'Tab') {
    return
  }

  const focusable = panel.value?.querySelectorAll<HTMLElement>(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'
  )
  if (!focusable || focusable.length === 0) {
    return
  }

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="auth.dialogOpen"
      class="auth-backdrop"
      @click.self="auth.closeDialog()"
      @keydown="trapFocus"
    >
      <section
        ref="panel"
        class="auth-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        aria-describedby="auth-description"
      >
        <header>
          <div>
            <h2 id="auth-title">{{ auth.mode === 'login' ? '登录学员操作台' : '注册新学员账号' }}</h2>
            <p id="auth-description">
              {{
                auth.mode === 'login'
                  ? '登录后继续查看课程、实训与就业线索。'
                  : '注册账号用于保存学习进度和技能档案。'
              }}
            </p>
          </div>
          <button class="close-button" type="button" aria-label="关闭登录窗口" @click="auth.closeDialog()">
            <X :size="16" aria-hidden="true" />
          </button>
        </header>

        <form v-if="auth.mode === 'login'" @submit.prevent="submitLogin">
          <div class="fields">
            <label for="login-username">用户名</label>
            <input
              id="login-username"
              v-model.trim="loginForm.username"
              name="username"
              autocomplete="username"
              required
            />

            <label for="login-password">密码</label>
            <input
              id="login-password"
              v-model.trim="loginForm.password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
            />
          </div>

          <div class="demo-box">
            <p>演示账号</p>
            <div>
              <button
                v-for="account in demoAccounts"
                :key="account.username"
                type="button"
                @click="fillDemo(account)"
              >
                {{ account.label }}
              </button>
            </div>
          </div>

          <p v-if="auth.error" class="form-error" role="alert">{{ auth.error }}</p>

          <footer>
            <button type="button" class="ghost-action" @click="auth.openDialog('register')">
              改为注册
            </button>
            <button type="submit" class="primary-action" :disabled="auth.loading">
              <LogIn :size="15" aria-hidden="true" />
              {{ auth.loading ? '正在登录' : '登录' }}
            </button>
          </footer>
        </form>

        <form v-else @submit.prevent="submitRegister">
          <div class="fields two-columns">
            <label for="register-name">姓名</label>
            <input id="register-name" v-model.trim="registerForm.name" name="name" required />

            <label for="register-username">用户名</label>
            <input id="register-username" v-model.trim="registerForm.username" name="username" required />

            <label for="register-password">密码（至少6位）</label>
            <input
              id="register-password"
              v-model.trim="registerForm.password"
              name="password"
              type="password"
              minlength="6"
              required
            />

            <label for="register-role">角色</label>
            <select id="register-role" v-model="registerForm.role" name="role">
              <option value="student">学员</option>
              <option value="teacher">教师</option>
              <option value="enterprise">企业</option>
            </select>

            <label for="register-phone">手机号（选填）</label>
            <input id="register-phone" v-model.trim="registerForm.phone" name="phone" type="tel" />

            <label for="register-region">地区（选填）</label>
            <input id="register-region" v-model.trim="registerForm.region" name="region" />

            <template v-if="registerForm.role === 'enterprise'">
              <label for="register-company">企业名称</label>
              <input id="register-company" v-model.trim="registerForm.company_name" name="company_name" />
            </template>
          </div>

          <p v-if="auth.error" class="form-error" role="alert">{{ auth.error }}</p>

          <footer>
            <button type="button" class="ghost-action" @click="auth.openDialog('login')">
              改为登录
            </button>
            <button type="submit" class="primary-action" :disabled="auth.loading">
              <UserPlus :size="15" aria-hidden="true" />
              {{ auth.loading ? '正在注册' : '注册' }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.auth-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(0 0 0 / 0.76);
}

.auth-panel {
  width: min(100%, 460px);
  max-height: min(86vh, 780px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
  box-shadow: 16px 20px 52px rgb(0 0 0 / 0.48);
}

.auth-panel::before {
  content: "";
  display: block;
  height: 3px;
  background: var(--ark-signal);
}

.auth-panel header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px;
  border-bottom: 1px solid var(--ark-line);
}

h2 {
  margin: 0;
  font-size: 1.35rem;
  line-height: 1.25;
}

.auth-panel header p {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-height: 1.6;
}

.close-button {
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
}

.close-button:hover,
.close-button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

form {
  padding: 18px;
}

.fields {
  display: grid;
  gap: 8px;
}

.fields.two-columns {
  grid-template-columns: minmax(0, 1fr);
}

label {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

input,
select {
  width: 100%;
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

input:hover,
select:hover {
  border-color: rgb(24 209 255 / 0.62);
}

input:focus-visible,
select:focus-visible {
  outline-offset: 0;
}

.demo-box {
  margin-top: 16px;
  padding: 12px;
  border: 1px solid var(--ark-line);
  background: rgb(5 6 7 / 0.66);
}

.demo-box p {
  margin: 0 0 8px;
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.demo-box div {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.demo-box button {
  min-height: 32px;
  padding: 0 9px;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.75rem;
}

.demo-box button:hover,
.demo-box button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.form-error {
  margin: 14px 0 0;
  padding: 9px 10px;
  border: 1px solid rgb(255 138 138 / 0.44);
  background: rgb(255 138 138 / 0.08);
  color: #ff9c9c;
  font-size: 0.8rem;
}

form footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 18px;
}

.ghost-action,
.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.84rem;
}

.primary-action {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.ghost-action:hover,
.primary-action:hover:not(:disabled) {
  background: rgb(24 209 255 / 0.1);
}

@media (max-width: 520px) {
  .auth-backdrop {
    align-items: stretch;
    padding: 12px;
  }

  .auth-panel {
    max-height: calc(100vh - 24px);
  }

  form footer {
    flex-direction: column-reverse;
    align-items: stretch;
  }

  .ghost-action,
  .primary-action {
    width: 100%;
  }
}
</style>
