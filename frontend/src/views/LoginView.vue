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

interface DemoAccount {
  label: string;
  username: string;
  password: string;
}

// 标记当前 username/password 是否由演示填充带入，用于切到注册时清理，
// 避免登录演示账号随 submitRegistration 一并作为注册凭据提交。
const demoFilled = ref(false);

// 与 backend/db_seed_accounts.py 的播种清单保持一致；演示前先跑
// python backend/seed_demo.py 确保账号已灌入。
const demoAccounts: DemoAccount[] = [
  { label: "学员", username: "student_demo", password: "123456" },
  { label: "教师", username: "teacher_demo", password: "123456" },
  { label: "企业", username: "enterprise_demo", password: "123456" },
  { label: "政府", username: "gov_demo", password: "123456" },
  { label: "运营", username: "operator_demo", password: "123456" },
  { label: "管理员", username: "admin_demo", password: "admin123" },
];

function fillDemoAccount(account: DemoAccount): void {
  mode.value = "login";
  username.value = account.username;
  password.value = account.password;
  errorMessage.value = "";
  demoFilled.value = true;
}

function selectTab(tab: "login" | "register"): void {
  mode.value = tab;
  // 演示填充的账号/密码只服务于登录态；切到注册时清空，
  // 否则会随 submitRegistration 一并作为注册凭据提交。
  if (tab === "register" && demoFilled.value) {
    username.value = "";
    password.value = "";
    demoFilled.value = false;
  }
}

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
          @click="selectTab('login')"
        >
          登录
        </button>
        <button
          type="button"
          :class="{ active: mode === 'register' }"
          @click="selectTab('register')"
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
          <p class="register-hint">
            注册后请在企业中心「企业资质」提交营业执照；认证前最多发布 1 个在招岗位。
          </p>
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
      <div
        v-if="mode === 'login'"
        class="demo-accounts"
      >
        <p class="demo-accounts-title">
          演示账号（点击填入）
        </p>
        <div class="demo-accounts-list">
          <button
            v-for="account in demoAccounts"
            :key="account.username"
            type="button"
            class="demo-account-chip"
            @click="fillDemoAccount(account)"
          >
            {{ account.label }}
          </button>
        </div>
      </div>
    </form>
  </main>
</template>

<style src="./login/login.css"></style>
