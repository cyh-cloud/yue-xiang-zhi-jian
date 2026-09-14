<script setup lang="ts">
import { ArrowRight, Check, GraduationCap, UserPlus } from 'lucide-vue-next'
import { nextTick, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AppHeader from '@/components/AppHeader.vue'
import FormField from '@/components/FormField.vue'
import { useAuthStore } from '@/stores/auth'

type RegistrationRole = 'student' | 'teacher'
type FieldHandle = { focus: () => void }

const auth = useAuthStore()
const router = useRouter()

const roleOptions: Array<{
  value: RegistrationRole
  label: string
  description: string
}> = [
  { value: 'student', label: '学员', description: '学习课程并连接就业机会' },
  { value: 'teacher', label: '教师', description: '发布课程并管理教学内容' }
]

const form = reactive({
  username: '',
  password: '',
  confirm_password: '',
  name: '',
  role: 'student' as RegistrationRole
})

const usernameField = ref<FieldHandle | null>(null)
const passwordField = ref<FieldHandle | null>(null)
const confirmPasswordField = ref<FieldHandle | null>(null)
const nameField = ref<FieldHandle | null>(null)
const roleFields = ref<HTMLInputElement[] | null>(null)

const fieldRefs: Record<string, typeof usernameField> = {
  username: usernameField,
  password: passwordField,
  confirm_password: confirmPasswordField,
  name: nameField
}

function clearFieldError(field: string) {
  if (auth.fieldErrors[field]) {
    delete auth.fieldErrors[field]
  }
}

async function focusFirstInvalidField() {
  const fieldOrder = ['username', 'password', 'confirm_password', 'name', 'role']
  const field = fieldOrder.find(name => auth.fieldErrors[name])
  if (!field) {
    return
  }

  await nextTick()
  if (field === 'role') {
    roleFields.value?.[0]?.focus()
    return
  }

  fieldRefs[field]?.value?.focus()
}

async function submitRegister() {
  if (auth.loading) {
    return
  }

  const response = await auth.register({
    username: form.username,
    password: form.password,
    confirm_password: form.confirm_password,
    name: form.name,
    role: form.role
  })

  if (!response) {
    await focusFirstInvalidField()
    return
  }

  await router.push(
    response.user.role === 'teacher' ? '/teacher' : '/register/interest-tags'
  )
}
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
      <section class="auth-intro" aria-labelledby="register-title">
        <h1 id="register-title">建立学员或教师身份</h1>
        <p>
          学员注册后选择兴趣方向再进入学习门户；教师注册完成后直接进入教学工作台。
          企业、政府和管理员账号不开放自助注册。
        </p>

        <div class="path-preview" aria-label="注册后路径">
          <div>
            <GraduationCap :size="19" aria-hidden="true" />
            <span>
              <strong>学员</strong>
              <small>兴趣标签 → 学员门户</small>
            </span>
          </div>
          <ArrowRight :size="18" aria-hidden="true" />
          <div>
            <Check :size="19" aria-hidden="true" />
            <span>
              <strong>教师</strong>
              <small>直接进入教师工作台</small>
            </span>
          </div>
        </div>
      </section>

      <section class="auth-panel" aria-labelledby="register-panel-title">
        <header>
          <span class="panel-mark" aria-hidden="true"></span>
          <div>
            <h2 id="register-panel-title">注册账号</h2>
            <p>角色、账号与姓名将在提交时统一校验。</p>
          </div>
        </header>

        <form novalidate @submit.prevent="submitRegister">
          <fieldset class="role-field" :class="{ invalid: auth.fieldErrors.role }">
            <legend>注册角色</legend>
            <div class="role-options" role="radiogroup" aria-label="注册角色">
              <label
                v-for="(option, index) in roleOptions"
                :key="option.value"
                :class="{ selected: form.role === option.value }"
              >
                <input
                  :id="`register-role-${option.value}`"
                  ref="roleFields"
                  v-model="form.role"
                  type="radio"
                  name="role"
                  :value="option.value"
                  :required="index === 0"
                  @change="clearFieldError('role')"
                />
                <span>
                  <strong>{{ option.label }}</strong>
                  <small>{{ option.description }}</small>
                </span>
              </label>
            </div>
            <p v-if="auth.fieldErrors.role" id="register-role-error" role="alert">
              {{ auth.fieldErrors.role }}
            </p>
          </fieldset>

          <div class="field-grid">
            <FormField
              id="register-name"
              ref="nameField"
              v-model="form.name"
              label="姓名"
              autocomplete="name"
              :error="auth.fieldErrors.name"
              required
            />
            <FormField
              id="register-username"
              ref="usernameField"
              v-model="form.username"
              label="用户名"
              autocomplete="username"
              :error="auth.fieldErrors.username"
              required
            />
            <FormField
              id="register-password"
              ref="passwordField"
              v-model="form.password"
              label="密码（至少8位）"
              type="password"
              autocomplete="new-password"
              :error="auth.fieldErrors.password"
              required
            />
            <FormField
              id="register-confirm-password"
              ref="confirmPasswordField"
              v-model="form.confirm_password"
              label="确认密码"
              type="password"
              autocomplete="new-password"
              :error="auth.fieldErrors.confirm_password"
              required
            />
          </div>

          <p
            v-if="auth.error && Object.keys(auth.fieldErrors).length === 0"
            class="auth-error"
            role="alert"
          >
            {{ auth.error }}
          </p>

          <button class="primary-action" type="submit" :disabled="auth.loading">
            <UserPlus :size="17" aria-hidden="true" />
            {{ auth.loading ? '正在注册' : '注册并继续' }}
          </button>
        </form>

        <footer>
          <span>已有账号？</span>
          <RouterLink to="/login">
            返回登录
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
    linear-gradient(rgb(16 23 25 / 0.045) 1px, transparent 1px),
    linear-gradient(90deg, rgb(16 23 25 / 0.038) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.auth-layout {
  display: grid;
  grid-template-columns: minmax(0, 0.72fr) minmax(520px, 0.78fr);
  gap: 46px;
  align-items: center;
  width: min(100%, 1240px);
  min-height: calc(100svh - 72px);
  margin-inline: auto;
  padding: 44px 24px 64px;
}

.auth-intro h1 {
  max-width: 11ch;
  margin: 0;
  font-size: 3rem;
  line-height: 1.04;
}

.auth-intro > p {
  max-width: 48ch;
  margin: 22px 0 0;
  color: var(--ark-muted);
  line-height: 1.8;
}

.path-preview {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  max-width: 560px;
  margin-top: 34px;
  padding: 16px;
  border: 1px solid var(--ark-line);
  background: rgb(255 255 255 / 0.72);
}

.path-preview > div {
  display: flex;
  align-items: flex-start;
  gap: 9px;
}

.path-preview svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.path-preview span {
  display: grid;
  gap: 4px;
}

.path-preview strong {
  font-size: 0.9rem;
}

.path-preview small {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-height: 1.45;
}

.auth-panel {
  position: relative;
  border: 1px solid var(--ark-line-strong);
  background: rgb(255 255 255 / 0.92);
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
  gap: 18px;
  padding: 20px;
}

.role-field {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.role-field legend {
  margin-bottom: 8px;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.role-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.role-options label {
  position: relative;
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 74px;
  padding: 11px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.role-options input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.role-options label::before {
  content: "";
  display: block;
  width: 36px;
  height: 36px;
  border: 1px solid var(--ark-line-strong);
  background:
    linear-gradient(45deg, transparent 46%, var(--ark-muted) 47% 53%, transparent 54%),
    linear-gradient(-45deg, transparent 46%, var(--ark-muted) 47% 53%, transparent 54%);
}

.role-options label.selected {
  border-color: var(--ark-signal);
  background: rgb(24 209 255 / 0.08);
}

.role-options label.selected::before {
  border-color: var(--ark-signal);
  background: var(--ark-signal);
}

.role-options label:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.role-options span {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.role-options strong {
  font-size: 0.9rem;
}

.role-options small {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-height: 1.45;
}

.role-field > p {
  margin: 7px 0 0;
  color: #b42318;
  font-size: 0.76rem;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.auth-error {
  margin: 0;
  padding: 10px 11px;
  border: 1px solid rgb(180 35 24 / 0.44);
  background: rgb(180 35 24 / 0.08);
  color: #b42318;
  font-size: 0.8rem;
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

@media (max-width: 980px) {
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

@media (max-width: 620px) {
  .auth-layout {
    padding: 24px 12px 44px;
  }

  .auth-intro h1 {
    font-size: 2.15rem;
  }

  .path-preview,
  .field-grid {
    grid-template-columns: 1fr;
  }

  .path-preview > svg {
    display: none;
  }

  .auth-panel footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
