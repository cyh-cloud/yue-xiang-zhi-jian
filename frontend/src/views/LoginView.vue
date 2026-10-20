<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/client";
import type { RegisterPayload } from "@/api/types";
import { useSessionStore } from "@/stores/session";
import { resolveInSiteRedirect } from "@/shared/url";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const username = ref("");
const password = ref("");
const errorMessage = ref("");
const submitting = ref(false);
const mode = ref<"login" | "register">("login");
const registerRole = ref<RegisterPayload["role"]>("student");
const registerName = ref("");
const registerPhone = ref("");
const registerRegion = ref("");
const registerCompany = ref("");

async function submit(): Promise<void> {
  if (!username.value.trim() || !password.value) {
    errorMessage.value = "请输入用户名和密码";
    return;
  }

  submitting.value = true;
  errorMessage.value = "";
  try {
    await session.login(username.value.trim(), password.value);
    const redirect = resolveInSiteRedirect(route.query.redirect, session.defaultPath);
    await router.replace(redirect);
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? error.message : "连接服务器失败";
  } finally {
    submitting.value = false;
  }
}

async function submitRegistration(): Promise<void> {
  if (!username.value.trim() || !password.value || !registerName.value.trim()) {
    errorMessage.value = "请填写用户名、密码和姓名";
    return;
  }
  if (password.value.length < 6) {
    errorMessage.value = "密码至少6位";
    return;
  }

  submitting.value = true;
  errorMessage.value = "";
  try {
    await session.registerAccount({
      username: username.value.trim(),
      password: password.value,
      name: registerName.value.trim(),
      role: registerRole.value,
      phone: registerPhone.value.trim(),
      company_name: registerCompany.value.trim(),
      region: registerRegion.value.trim(),
    });
    await router.replace(session.defaultPath);
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError ? error.message : "连接服务器失败";
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <form
      class="login-card"
      @submit.prevent="mode === 'login' ? submit() : submitRegistration()"
    >
      <h1>登录粤乡智匠</h1>
      <div class="auth-tabs">
        <button
          type="button"
          :class="{ active: mode === 'login' }"
          @click="mode = 'login'"
        >
          登录
        </button>
        <button
          type="button"
          :class="{ active: mode === 'register' }"
          @click="mode = 'register'"
        >
          注册
        </button>
      </div>
      <p
        v-if="route.query.unavailable"
        class="login-error"
        role="alert"
      >
        连接服务器失败，请稍后重试
      </p>
      <label for="username">用户名</label>
      <input
        id="username"
        v-model="username"
        name="username"
        autocomplete="username"
      >
      <label for="password">密码</label>
      <input
        id="password"
        v-model="password"
        name="password"
        type="password"
        autocomplete="current-password"
      >
      <template v-if="mode === 'register'">
        <label for="register-name">姓名</label>
        <input
          id="register-name"
          v-model="registerName"
          name="name"
          autocomplete="name"
        >
        <label for="register-role">注册身份</label>
        <select
          id="register-role"
          v-model="registerRole"
          name="role"
        >
          <option value="student">
            学员（学习技能）
          </option>
          <option value="teacher">
            教师（传授技能）
          </option>
          <option value="enterprise">
            企业用户（发布岗位）
          </option>
        </select>
        <template v-if="registerRole === 'enterprise'">
          <label for="register-company">公司名称</label>
          <input
            id="register-company"
            v-model="registerCompany"
            name="company_name"
            autocomplete="organization"
          >
        </template>
        <label for="register-phone">手机号</label>
        <input
          id="register-phone"
          v-model="registerPhone"
          name="phone"
          autocomplete="tel"
        >
        <label for="register-region">所在地区</label>
        <input
          id="register-region"
          v-model="registerRegion"
          name="region"
          autocomplete="address-level1"
        >
      </template>
      <p
        v-if="errorMessage"
        class="login-error"
        role="alert"
      >
        {{ errorMessage }}
      </p>
      <button
        type="submit"
        :disabled="submitting"
      >
        {{
          submitting
            ? (mode === "login" ? "正在登录..." : "正在注册...")
            : (mode === "login" ? "登录" : "注册")
        }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  background: #f2f4f1;
}

.login-card {
  display: grid;
  width: min(420px, 90vw);
  gap: 12px;
  padding: 36px;
  border: 1px solid #e2e6e0;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
}

h1 {
  margin: 0 0 12px;
  color: #1f5e43;
  font-size: 1.5rem;
}

label {
  font-size: 0.875rem;
  color: #5c6660;
}

input {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font: inherit;
}

select {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
  font: inherit;
}

.auth-tabs {
  display: flex;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e6e0;
}

.auth-tabs button {
  margin: 0;
  padding: 6px 12px;
  background: transparent;
  color: #5c6660;
}

.auth-tabs button.active {
  background: #e8f1ec;
  color: #1f5e43;
}

button {
  margin-top: 8px;
  padding: 11px 16px;
  border: 0;
  border-radius: 8px;
  background: #1f5e43;
  color: #fff;
  font: inherit;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.login-error {
  margin: 0;
  color: #b3382f;
  font-size: 0.875rem;
}
</style>
