<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { ApiError } from "@/api/client";
import {
  generateResumeSection,
  getEmploymentStats,
  getLearnerProfile,
  getResume,
  saveResume,
  type EmploymentStats,
  type LearnerCertificate,
  type LearnerProfile,
  type LearnerTrainingRecord,
  type ResumeAiSection,
  type ResumePayload,
  type ResumeRecord,
} from "@/api/employment";
import { useSessionStore } from "@/stores/session";

type FeedbackKind = "success" | "error" | "info";

const AI_SECTION_LABELS: Readonly<Record<ResumeAiSection, string>> = {
  self_eval: "自我评价",
  skills: "专业技能",
  experience: "工作与实践经历",
};

const session = useSessionStore();

const loading = ref(false);
const loadError = ref("");
const statsError = ref("");
const profile = ref<LearnerProfile | null>(null);
const stats = ref<EmploymentStats | null>(null);
const resumeMeta = ref<ResumeRecord | null>(null);
const aiSections = ref<ResumeAiSection[]>([]);
const saveBusy = ref(false);
const aiBusy = ref("");
const feedback = ref<{ kind: FeedbackKind; text: string } | null>(null);

const form = reactive<ResumePayload>({
  title: "",
  region: "",
  education: "",
  work_years: "",
  phone: "",
  email: "",
  self_eval: "",
  skills: "",
  experience: [],
});

const loginTarget = computed(() => ({
  path: "/login",
  query: { redirect: "/employment?tab=resume" },
}));
const hasAiUsed = computed(
  () => Boolean(resumeMeta.value?.ai_used) || aiSections.value.length > 0,
);
const profileName = computed(
  () =>
    profile.value?.basic.name ||
    session.user?.name ||
    "姓名未填写",
);

onMounted(() => {
  void loadPanel();
});

async function loadPanel(): Promise<void> {
  if (!session.isAuthenticated || !session.user) {
    profile.value = null;
    stats.value = null;
    resumeMeta.value = null;
    return;
  }

  loading.value = true;
  loadError.value = "";
  statsError.value = "";
  feedback.value = null;
  const userId = session.user.id;
  const [profileResult, resumeResult, statsResult] = await Promise.allSettled([
    getLearnerProfile(userId),
    getResume(userId),
    getEmploymentStats(userId),
  ]);

  if (profileResult.status === "rejected") {
    loadError.value = describeError(
      profileResult.reason,
      "能力档案加载失败，请稍后重试",
    );
  } else if (resumeResult.status === "rejected") {
    loadError.value = describeError(
      resumeResult.reason,
      "简历加载失败，请稍后重试",
    );
  } else {
    profile.value = profileResult.value.profile;
    resumeMeta.value = resumeResult.value.resume;
    fillForm(resumeResult.value.resume);
    aiSections.value = normalizeAiSections(
      resumeResult.value.resume?.ai_sections,
    );
  }

  if (statsResult.status === "fulfilled") {
    stats.value = statsResult.value.stats;
  } else {
    stats.value = null;
    statsError.value = describeError(
      statsResult.reason,
      "求职统计加载失败",
    );
  }
  loading.value = false;
}

function fillForm(resume: ResumeRecord | null): void {
  form.title = resume?.title ?? "";
  form.region = resume?.region ?? "";
  form.education = resume?.education ?? "";
  form.work_years = resume?.work_years ?? "";
  form.phone =
    resume?.phone || profile.value?.basic.phone || session.user?.phone || "";
  form.email =
    resume?.email || profile.value?.basic.email || session.user?.email || "";
  form.self_eval = resume?.self_eval ?? "";
  form.skills = resume?.skills ?? "";
  form.experience = Array.isArray(resume?.experience)
    ? resume.experience.map((item) => ({ ...item }))
    : [];
}

function normalizeAiSections(value: unknown): ResumeAiSection[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is ResumeAiSection =>
      item === "self_eval" || item === "skills" || item === "experience",
  );
}

function addExperience(): void {
  form.experience.push({
    company: "",
    position: "",
    period: "",
    desc: "",
  });
}

function removeExperience(index: number): void {
  form.experience.splice(index, 1);
}

function collectPayload(): ResumePayload {
  return {
    title: form.title.trim(),
    region: form.region.trim(),
    education: form.education.trim(),
    work_years: form.work_years.trim(),
    phone: form.phone.trim(),
    email: form.email.trim(),
    self_eval: form.self_eval.trim(),
    skills: form.skills.trim(),
    experience: form.experience
      .map((item) => ({
        company: item.company.trim(),
        position: item.position.trim(),
        period: item.period.trim(),
        desc: item.desc.trim(),
      }))
      .filter(
        (item) =>
          item.company || item.position || item.period || item.desc,
      ),
  };
}

async function save(): Promise<void> {
  if (!session.user || saveBusy.value) return;
  saveBusy.value = true;
  feedback.value = null;
  try {
    const response = await saveResume(session.user.id, collectPayload());
    resumeMeta.value = response.resume;
    aiSections.value = normalizeAiSections(response.resume.ai_sections);
    feedback.value = {
      kind: "success",
      text: response.message || "简历已保存",
    };
  } catch (error) {
    feedback.value = {
      kind: "error",
      text: describeResumeError(error, "保存失败，请稍后重试"),
    };
  } finally {
    saveBusy.value = false;
  }
}

async function draftWithAi(
  section: ResumeAiSection,
  experienceIndex = -1,
): Promise<void> {
  if (!session.user || aiBusy.value) return;

  const row =
    section === "experience" && experienceIndex >= 0
      ? form.experience[experienceIndex]
      : null;
  if (section === "experience" && !row) {
    feedback.value = { kind: "error", text: "未找到要润色的经历条目" };
    return;
  }
  if (
    row &&
    !row.company.trim() &&
    !row.position.trim() &&
    !row.desc.trim()
  ) {
    feedback.value = {
      kind: "error",
      text: "请先填写这条经历的单位或内容，AI 不会凭空编造经历",
    };
    return;
  }

  const draft =
    section === "self_eval"
      ? form.self_eval.trim()
      : section === "skills"
        ? form.skills.trim()
        : [row?.company, row?.position, row?.period, row?.desc]
            .filter(Boolean)
            .join(" / ")
            .trim();
  const busyKey =
    section === "experience" ? `experience-${experienceIndex}` : section;
  aiBusy.value = busyKey;
  feedback.value = null;

  try {
    const response = await generateResumeSection(
      session.user.id,
      section,
      draft,
    );
    if (section === "self_eval") form.self_eval = response.text;
    else if (section === "skills") form.skills = response.text;
    else if (row) row.desc = response.text;

    if (!aiSections.value.includes(section)) {
      aiSections.value = [...aiSections.value, section];
    }
    if (resumeMeta.value) resumeMeta.value.ai_used = 1;
    feedback.value = {
      kind: "info",
      text:
        response.notice ||
        `${AI_SECTION_LABELS[section]}已生成，请核对事实后再使用`,
    };
  } catch (error) {
    feedback.value = {
      kind: "error",
      text: describeAiError(error),
    };
  } finally {
    aiBusy.value = "";
  }
}

function isAiBusy(section: ResumeAiSection, index = -1): boolean {
  return section === "experience"
    ? aiBusy.value === `experience-${index}`
    : aiBusy.value === section;
}

function hasAiSection(section: ResumeAiSection): boolean {
  return aiSections.value.includes(section);
}

function certificateStatus(certificate: LearnerCertificate): string {
  if (certificate.earned) {
    return certificate.date
      ? `已获得 · ${certificate.date}`
      : "已获得";
  }
  if (certificate.status === "in_progress") {
    return `学习中 ${certificate.progress}%`;
  }
  return "未开始";
}

function trainingScore(record: LearnerTrainingRecord): string {
  return record.scored ? `${record.score} 分` : "待老师批改";
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "连接服务器失败，请检查网络后重试";
    if (error.status === 401) return "登录已过期，请重新登录后再查看简历";
    if (error.status === 403) return "只能查看本人的求职资料";
    return error.message || fallback;
  }
  return fallback;
}

function describeResumeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 403) {
    return "只能修改本人的简历";
  }
  return describeError(error, fallback);
}

function describeAiError(error: unknown): string {
  if (!(error instanceof ApiError)) return "AI 服务暂时不可用，请稍后重试";
  if (error.status === 0) return "连接服务器失败，请检查网络后重试";
  if (error.code === "ai_not_configured") {
    return "AI 辅助功能尚未启用，请联系管理员（12316）";
  }
  if (error.code === "rate_limited") {
    return "AI 使用过于频繁，请稍后再试";
  }
  if (error.code === "draft_too_long") {
    return "这一条内容过长，请精简后再试";
  }
  if (error.status === 401) return "登录已过期，请重新登录";
  return error.message || "AI 服务暂时不可用，请稍后重试";
}

function buildResumeText(): string {
  const payload = collectPayload();
  const lines: string[] = [];
  lines.push(`${profileName.value}　个人简历`, "");

  const basicRows = [
    ["求职意向", payload.title],
    ["期望地区", payload.region],
    ["最高学历", payload.education],
    ["工作年限", payload.work_years],
    ["联系电话", payload.phone],
    ["电子邮箱", payload.email],
  ].filter(([, value]) => Boolean(value));
  if (basicRows.length) {
    lines.push("【基本信息】");
    for (const [label, value] of basicRows) lines.push(`${label}：${value}`);
    lines.push("");
  }

  if (payload.self_eval) {
    lines.push("【自我评价】", payload.self_eval, "");
  }
  if (payload.skills) {
    lines.push("【专业技能】", payload.skills, "");
  }
  if (payload.experience.length) {
    lines.push("【工作与实践经历】");
    for (const item of payload.experience) {
      lines.push(
        `- ${[item.company, item.position, item.period]
          .filter(Boolean)
          .join(" · ")}`,
      );
      if (item.desc) lines.push(`  ${item.desc}`);
    }
    lines.push("");
  }

  const certificates = (profile.value?.certificates ?? []).filter(
    (item) => item.earned,
  );
  if (certificates.length) {
    lines.push("【平台学习证书（已获得）】");
    for (const item of certificates) {
      lines.push(`- ${item.name}${item.date ? `（${item.date}）` : ""}`);
    }
    lines.push("");
  }

  const scoredTraining = (profile.value?.training ?? []).filter(
    (item) => item.scored,
  );
  if (scoredTraining.length) {
    lines.push("【平台实训成绩】");
    for (const item of scoredTraining) {
      lines.push(`- ${item.title}：${item.score} 分`);
    }
    lines.push("");
  }

  if (hasAiUsed.value) {
    lines.push(
      "【AI 辅助说明】",
      `本简历的${aiSections.value
        .map((section) => AI_SECTION_LABELS[section])
        .join("、") || "部分内容"}使用了 AI 辅助，请逐项核对事实。`,
    );
  }
  return lines.join("\n").trim();
}

function openPrintPreview(): void {
  if (!session.isAuthenticated) {
    feedback.value = { kind: "error", text: "请先登录后再导出简历" };
    return;
  }
  const text = buildResumeText();
  const printWindow = window.open("", "_blank");
  if (!printWindow) {
    feedback.value = {
      kind: "error",
      text: "浏览器拦截了新窗口，请允许弹出窗口后重试",
    };
    return;
  }
  const title = `${profileName.value} - 个人简历`;
  printWindow.document.write(
    `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">` +
      `<title>${escapeHtml(title)}</title><style>` +
      `body{font-family:"Microsoft YaHei",system-ui,sans-serif;line-height:1.9;color:#222;` +
      `max-width:720px;margin:40px auto;padding:0 24px;font-size:14px;}` +
      `pre{white-space:pre-wrap;font:inherit;}` +
      `button{margin-bottom:20px;padding:8px 16px;cursor:pointer;}` +
      `@media print{button{display:none}body{margin:0;max-width:none}}` +
      `</style></head><body><button onclick="window.print()">打印 / 导出 PDF</button>` +
      `<pre data-testid="resume-export-text">${escapeHtml(text)}</pre></body></html>`,
  );
  printWindow.document.close();
  feedback.value = { kind: "success", text: "已打开打印预览" };
}

async function copyResumeText(): Promise<void> {
  try {
    await navigator.clipboard.writeText(buildResumeText());
    feedback.value = { kind: "success", text: "简历纯文本已复制" };
  } catch {
    feedback.value = { kind: "error", text: "复制失败，请使用打印预览导出" };
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => {
    const entities: Readonly<Record<string, string>> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character] ?? character;
  });
}
</script>

<template>
  <div
    v-if="!session.isAuthenticated"
    class="emp-empty emp-empty-inline"
  >
    <i
      class="fas fa-user-lock"
      aria-hidden="true"
    />
    <p>登录后可查看能力档案并编辑在线简历</p>
    <span class="emp-empty-sub">简历只保存到当前账号，不会展示给其他学员。</span>
    <RouterLink
      class="btn btn-primary btn-sm"
      :to="loginTarget"
    >
      去登录
    </RouterLink>
  </div>

  <div
    v-else-if="loading"
    class="emp-empty emp-empty-inline"
    role="status"
  >
    <i
      class="fas fa-spinner fa-spin"
      aria-hidden="true"
    />
    <p>能力档案与简历加载中...</p>
  </div>

  <div
    v-else-if="loadError"
    class="emp-empty emp-empty-inline"
    role="alert"
  >
    <i
      class="fas fa-triangle-exclamation"
      aria-hidden="true"
    />
    <p>{{ loadError }}</p>
    <button
      type="button"
      class="btn btn-outline btn-sm"
      @click="loadPanel"
    >
      重试
    </button>
  </div>

  <template v-else>
    <div
      v-if="feedback"
      class="resume-feedback"
      :class="`is-${feedback.kind}`"
      :role="feedback.kind === 'error' ? 'alert' : 'status'"
      data-testid="resume-feedback"
    >
      {{ feedback.text }}
    </div>

    <div class="resume-layout">
      <aside
        class="resume-profile"
        data-testid="resume-profile"
      >
        <div class="resume-profile-head">
          <i
            class="fas fa-id-card"
            aria-hidden="true"
          />
          <div>
            <h2>能力档案</h2>
            <p>平台记录的真实学习数据</p>
          </div>
        </div>

        <ul class="resume-profile-list">
          <li>
            <span>姓名</span>
            <b>{{ profile?.basic.name || "未填写" }}</b>
          </li>
          <li>
            <span>学习方向</span>
            <b>{{ profile?.learning?.direction || "未填写" }}</b>
          </li>
          <li>
            <span>课程完成度</span>
            <b>{{ profile?.learning ? `${profile.learning.progress}%` : "未记录" }}</b>
          </li>
          <li>
            <span>学习积分</span>
            <b>{{ profile?.points ?? 0 }}</b>
          </li>
        </ul>

        <div class="resume-profile-sub">
          <i
            class="fas fa-chart-simple"
            aria-hidden="true"
          />
          求职统计
        </div>
        <div
          v-if="statsError"
          class="resume-profile-error"
          role="alert"
        >
          {{ statsError }}
        </div>
        <div
          v-else
          class="resume-stat-grid"
        >
          <div>
            <b>{{ stats?.applied ?? 0 }}</b>
            <span>投递</span>
          </div>
          <div>
            <b>{{ stats?.saved ?? 0 }}</b>
            <span>收藏</span>
          </div>
          <div>
            <b>{{ stats?.intents ?? 0 }}</b>
            <span>意向</span>
          </div>
        </div>

        <div class="resume-profile-sub">
          <i
            class="fas fa-certificate"
            aria-hidden="true"
          />
          学习证书
        </div>
        <ul
          v-if="profile?.certificates.length"
          class="resume-cert-list"
        >
          <li
            v-for="certificate in profile.certificates"
            :key="`${certificate.name}-${certificate.date}`"
            class="resume-cert"
            :class="{
              'is-earned': certificate.earned,
              'is-progress': certificate.status === 'in_progress',
            }"
          >
            <span class="resume-cert-name">{{ certificate.name }}</span>
            <span class="resume-cert-status">{{ certificateStatus(certificate) }}</span>
          </li>
        </ul>
        <div
          v-else
          class="resume-profile-empty"
        >
          暂无证书记录
        </div>

        <div class="resume-profile-sub">
          <i
            class="fas fa-flask"
            aria-hidden="true"
          />
          实训成绩
        </div>
        <ul
          v-if="profile?.training.length"
          class="resume-training-list"
        >
          <li
            v-for="record in profile.training"
            :key="`${record.title}-${record.submitted_at}`"
            class="resume-training"
          >
            <span>{{ record.title }}</span>
            <span class="resume-training-score">{{ trainingScore(record) }}</span>
          </li>
        </ul>
        <div
          v-else
          class="resume-profile-empty"
        >
          暂无实训记录
        </div>

        <div class="resume-profile-foot">
          以上为 AI 起草时可使用的全部素材；档案里没有的内容，AI 不会替你编造。
        </div>
      </aside>

      <div class="resume-main">
        <div
          class="resume-note"
          :class="{ 'is-ai': hasAiUsed }"
          data-testid="resume-ai-summary"
        >
          <i
            class="fas"
            :class="hasAiUsed ? 'fa-wand-magic-sparkles' : 'fa-shield-halved'"
            aria-hidden="true"
          />
          <span v-if="hasAiUsed">
            这份简历使用过 <strong>AI 辅助</strong>。AI 只根据能力档案与本人填写内容组织文字，请逐项核对事实。
          </span>
          <span v-else>
            AI 起草只会使用左侧能力档案与本人填写内容，未提供的信息会以【待补充】占位。
          </span>
        </div>

        <section class="resume-block">
          <h2><i class="fas fa-user" />基本信息</h2>
          <div class="resume-grid">
            <label>
              求职意向岗位
              <input
                v-model="form.title"
                type="text"
                aria-label="求职意向岗位"
                autocomplete="off"
                placeholder="如：农产品电商运营专员"
              >
            </label>
            <label>
              期望工作地区
              <input
                v-model="form.region"
                type="text"
                aria-label="期望工作地区"
                autocomplete="address-level1"
                placeholder="如：茂名"
              >
            </label>
            <label>
              最高学历
              <input
                v-model="form.education"
                type="text"
                aria-label="最高学历"
                autocomplete="off"
                placeholder="如：大专"
              >
            </label>
            <label>
              工作/实践年限
              <input
                v-model="form.work_years"
                type="text"
                aria-label="工作/实践年限"
                autocomplete="off"
                placeholder="如：1年"
              >
            </label>
            <label>
              联系电话
              <input
                v-model="form.phone"
                type="tel"
                aria-label="联系电话"
                autocomplete="tel"
                placeholder="选填"
              >
            </label>
            <label>
              电子邮箱
              <input
                v-model="form.email"
                type="email"
                aria-label="电子邮箱"
                autocomplete="email"
                placeholder="选填"
              >
            </label>
          </div>
        </section>

        <section class="resume-block">
          <div class="resume-block-head">
            <h2><i class="fas fa-star" />自我评价</h2>
            <div class="resume-block-actions">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="Boolean(aiBusy)"
                @click="draftWithAi('self_eval')"
              >
                <i
                  class="fas"
                  :class="isAiBusy('self_eval') ? 'fa-spinner fa-spin' : 'fa-wand-magic-sparkles'"
                />
                {{ isAiBusy("self_eval") ? "生成中" : "AI 起草" }}
              </button>
              <span
                v-if="hasAiSection('self_eval')"
                class="resume-ai-flag"
                data-testid="resume-ai-flag-self_eval"
              >
                <i class="fas fa-wand-magic-sparkles" />已用 AI 辅助 · 请核对事实
              </span>
            </div>
          </div>
          <textarea
            v-model="form.self_eval"
            rows="4"
            aria-label="自我评价"
            placeholder="可以点「AI 起草」，让 AI 先根据平台学习数据写一版，再自行修改"
          />
        </section>

        <section class="resume-block">
          <div class="resume-block-head">
            <h2><i class="fas fa-tools" />专业技能</h2>
            <div class="resume-block-actions">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="Boolean(aiBusy)"
                @click="draftWithAi('skills')"
              >
                <i
                  class="fas"
                  :class="isAiBusy('skills') ? 'fa-spinner fa-spin' : 'fa-wand-magic-sparkles'"
                />
                {{ isAiBusy("skills") ? "生成中" : "AI 起草" }}
              </button>
              <span
                v-if="hasAiSection('skills')"
                class="resume-ai-flag"
                data-testid="resume-ai-flag-skills"
              >
                <i class="fas fa-wand-magic-sparkles" />已用 AI 辅助 · 请核对事实
              </span>
            </div>
          </div>
          <textarea
            v-model="form.skills"
            rows="3"
            aria-label="专业技能"
            placeholder="如：荔枝栽培管理、电商店铺运营、客户沟通"
          />
        </section>

        <section class="resume-block">
          <div class="resume-block-head">
            <h2><i class="fas fa-briefcase" />工作与实践经历</h2>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="addExperience"
            >
              <i class="fas fa-plus" />添加经历
            </button>
          </div>
          <p class="resume-hint">
            这部分需要你自己填写。可以点单条右侧的「AI 润色」改善表达，
            <strong>但 AI 不会替你添加任何未填写的事实</strong>。
          </p>
          <div
            v-if="!form.experience.length"
            class="resume-profile-empty"
          >
            还没有添加经历。没有也可以留空，平台不会替你补。
          </div>
          <div
            v-for="(item, index) in form.experience"
            :key="index"
            class="resume-exp-row"
          >
            <div class="resume-exp-grid">
              <input
                v-model="item.company"
                type="text"
                :aria-label="`经历 ${index + 1} 单位`"
                autocomplete="off"
                placeholder="单位 / 合作社名称"
              >
              <input
                v-model="item.position"
                type="text"
                :aria-label="`经历 ${index + 1} 角色`"
                autocomplete="off"
                placeholder="担任角色"
              >
              <input
                v-model="item.period"
                type="text"
                :aria-label="`经历 ${index + 1} 时间`"
                autocomplete="off"
                placeholder="时间，如 2024-2025"
              >
            </div>
            <textarea
              v-model="item.desc"
              rows="2"
              :aria-label="`经历 ${index + 1} 描述`"
              placeholder="做了什么、学到什么（可点右侧「AI 润色」改善表达）"
            />
            <div class="resume-exp-actions">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="Boolean(aiBusy)"
                @click="draftWithAi('experience', index)"
              >
                <i
                  class="fas"
                  :class="isAiBusy('experience', index) ? 'fa-spinner fa-spin' : 'fa-wand-magic-sparkles'"
                />
                {{ isAiBusy("experience", index) ? "润色中" : "AI 润色" }}
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                @click="removeExperience(index)"
              >
                删除
              </button>
            </div>
          </div>
          <div
            v-if="hasAiSection('experience')"
            class="resume-ai-flag resume-ai-flag-block"
            data-testid="resume-ai-flag-experience"
          >
            <i class="fas fa-wand-magic-sparkles" />经历描述已用 AI 辅助 · 请核对事实
          </div>
        </section>

        <div class="resume-actions">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="saveBusy"
            @click="save"
          >
            <i
              class="fas"
              :class="saveBusy ? 'fa-spinner fa-spin' : 'fa-floppy-disk'"
            />
            {{ saveBusy ? "保存中" : "保存简历" }}
          </button>
          <button
            type="button"
            class="btn btn-outline"
            @click="openPrintPreview"
          >
            <i class="fas fa-print" />打印 / 导出 PDF
          </button>
          <button
            type="button"
            class="btn btn-outline"
            @click="copyResumeText"
          >
            <i class="fas fa-copy" />复制纯文本
          </button>
        </div>
      </div>
    </div>
  </template>
</template>

<style scoped>
.resume-profile-head h2 {
  margin: 0;
  font-size: 0.95rem;
  color: var(--text-primary);
}

.resume-block > h2,
.resume-block-head h2 {
  margin: 0 0 12px;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
}

.resume-block-head h2 {
  margin-bottom: 0;
}

.resume-block > h2 i,
.resume-block-head h2 i {
  margin-right: 5px;
  color: var(--brand);
  font-size: 0.85rem;
}

.resume-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.resume-stat-grid div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 9px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  text-align: center;
}

.resume-stat-grid b {
  color: var(--text-primary);
  font-size: 1rem;
}

.resume-stat-grid span,
.resume-profile-empty {
  color: var(--text-muted);
  font-size: 0.76rem;
}

.resume-profile-empty {
  padding: 8px 0;
  line-height: 1.7;
}

.resume-feedback {
  margin: 0 0 16px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  line-height: 1.6;
}

.resume-feedback.is-success {
  background: rgba(31, 94, 67, 0.1);
  color: var(--accent-blue);
}

.resume-feedback.is-error {
  background: rgba(239, 68, 68, 0.1);
  color: #b3382f;
}

.resume-feedback.is-info {
  background: rgba(217, 162, 39, 0.12);
  color: #7a5600;
}

.resume-ai-flag-block {
  display: inline-flex;
  margin-top: 10px;
}

[data-theme="dark"] .resume-feedback.is-error {
  color: #f28b82;
}

[data-theme="dark"] .resume-feedback.is-info {
  color: #efc75e;
}
</style>
