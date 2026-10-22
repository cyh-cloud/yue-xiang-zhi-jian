<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";
import { useRoute, useRouter } from "vue-router";

import {
  addJobIntent,
  applyForJob,
  getJobDetail,
  getJobs,
  getMyJobs,
  getSavedJobs,
  getSimilarJobs,
  removeJobIntent,
  saveJob,
  unsaveJob,
  type Application,
  type CategoryOption,
  type EnterpriseJob,
  type JobIntent,
  type JobListResponse,
  type PublicRecruitment,
} from "@/api/employment";
import { ApiError } from "@/api/client";
import ResumeProfilePanel from "@/components/employment/ResumeProfilePanel.vue";
import { useSessionStore } from "@/stores/session";

type ActiveTab = "jobs" | "resume" | "applications" | "saved";
type ApplicationFilter = "all" | "pending" | "interview" | "approved" | "rejected";
type FeedbackKind = "success" | "error" | "info";

const LOCATIONS = [
  "广州",
  "深圳",
  "茂名",
  "梅州",
  "佛山",
  "湛江",
  "汕头",
  "惠州",
  "潮州",
  "阳江",
  "河源",
  "韶关",
  "清远",
  "江门",
] as const;

const SALARY_OPTIONS = [
  ["3K-5K", "3K-5K"],
  ["5K-8K", "5K-8K"],
  ["8K-12K", "8K-12K"],
  ["12K+", "12K以上"],
] as const;

const APPLICATION_FILTERS: ReadonlyArray<{
  value: ApplicationFilter;
  label: string;
}> = [
  { value: "all", label: "全部" },
  { value: "pending", label: "待审核" },
  { value: "interview", label: "已通知面试" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已拒绝" },
];

const STATUS_META: Readonly<
  Record<
    string,
    { label: string; className: string; timelineLabel: string }
  >
> = {
  pending: { label: "待审核", className: "pending", timelineLabel: "企业查阅中" },
  interview: {
    label: "已通知面试",
    className: "interview",
    timelineLabel: "已通知面试",
  },
  approved: { label: "已通过", className: "approved", timelineLabel: "已通过审核" },
  rejected: { label: "已拒绝", className: "rejected", timelineLabel: "未通过审核" },
};

const FALLBACK_STATUS_META = {
  label: "待审核",
  className: "pending",
  timelineLabel: "企业查阅中",
};

const route = useRoute();
const router = useRouter();
const session = useSessionStore();

const activeTab = ref<ActiveTab>(initialEmploymentTab());
const keyword = ref("");
const location = ref("");
const salary = ref("");
const category = ref("");

const jobData = ref<JobListResponse | null>(null);
const jobsLoading = ref(true);
const jobsError = ref("");
const savedIds = ref<Set<number>>(new Set());

const selectedJob = ref<EnterpriseJob | null>(null);
const selectedRecruitment = ref<PublicRecruitment | null>(null);
const detailOpen = ref(false);
const detailLoading = ref(false);
const detailError = ref("");
const similarJobs = ref<EnterpriseJob[]>([]);

const myJobsLoading = ref(false);
const myJobsError = ref("");
const myJobsLoaded = ref(false);
const applications = ref<Application[]>([]);
const intents = ref<JobIntent[]>([]);
const hasResume = ref<boolean | null>(null);
const intentNotice = ref("");
const applicationFilter = ref<ApplicationFilter>("all");

const savedJobsLoading = ref(false);
const savedJobsError = ref("");
const savedJobs = ref<EnterpriseJob[]>([]);

const feedback = ref<{ kind: FeedbackKind; text: string } | null>(null);
const actionBusy = ref(false);
const busyJobId = ref<number | null>(null);
const busyIntentKey = ref("");

let jobsRequestId = 0;
let detailRequestId = 0;
let feedbackTimer: number | undefined;
let resumeAfterJobsLoad = false;

const enterpriseCategoryOptions = computed(
  () => jobData.value?.category_options.enterprise ?? [],
);
const recruitCategoryOptions = computed(
  () => jobData.value?.category_options.recruit ?? [],
);
const visibleRecruitments = computed(() =>
  salary.value ? [] : (jobData.value?.recruitments ?? []),
);
const activeRecruitments = computed(() =>
  visibleRecruitments.value.filter(
    (item) => item.status === "open" || item.status === "upcoming",
  ),
);
const expiredRecruitments = computed(() =>
  visibleRecruitments.value.filter(
    (item) => item.status !== "open" && item.status !== "upcoming",
  ),
);
const visibleJobs = computed(() => jobData.value?.jobs ?? []);
const visibleCount = computed(
  () => visibleJobs.value.length + visibleRecruitments.value.length,
);
const pendingCount = computed(
  () => jobData.value?.enterprise_review_pending ?? 0,
);
const recruitHiddenBySalary = computed(
  () => jobData.value?.recruit_hidden_by_salary ?? 0,
);
const hasFilters = computed(() =>
  Boolean(keyword.value || location.value || salary.value || category.value),
);
const emptyTitle = computed(() => {
  if (category.value) {
    const optionCount = [
      ...enterpriseCategoryOptions.value,
      ...recruitCategoryOptions.value,
    ].find((option) => option.value === category.value)?.count;
    if (optionCount === 0) return `「${category.value}」下暂时没有岗位`;
    return `「${category.value}」在当前搜索 / 地点条件下没有岗位`;
  }
  if (salary.value) return "没有薪资落在这个范围内的企业岗位";
  if (pendingCount.value > 0 && !keyword.value && !location.value) {
    return "企业岗位正在审核中";
  }
  return "未找到匹配的职位";
});
const emptyHint = computed(() => {
  if (category.value) {
    return salary.value
      ? "分类下拉已标出真实条数，可以更换分类或清空薪资范围。"
      : "分类下拉里已标出每一类的真实条数，可以换一个分类看看。";
  }
  if (salary.value) {
    return "公开招聘公告没有薪资字段、不参与薪资筛选；清空薪资范围后即可查看公告。";
  }
  if (pendingCount.value > 0 && !keyword.value && !location.value) {
    return `有 ${pendingCount.value} 条企业发布的岗位尚未通过平台审核，通过后才会在这里展示。`;
  }
  if (hasFilters.value) {
    return "试试减少搜索关键词，或把工作地点改回不限。";
  }
  return "暂时没有可展示的岗位信息，请稍后再来查看。";
});
const filteredApplications = computed(() => {
  if (applicationFilter.value === "all") return applications.value;
  return applications.value.filter(
    (application) => application.status === applicationFilter.value,
  );
});
const loginTarget = computed(() => ({
  path: "/login",
  query: { redirect: route.fullPath },
}));
const redirectAfterLogin = computed(() => {
  const query: Record<string, string> = {};
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === "string") query[key] = value;
  }
  return query;
});
const returnAction = computed(() => {
  const action = route.query.action;
  const jobId = Number(route.query.job);
  const recruitKey =
    typeof route.query.recruit === "string" ? route.query.recruit : "";
  return {
    action: typeof action === "string" ? action : "",
    jobId: Number.isInteger(jobId) && jobId > 0 ? jobId : 0,
    recruitKey,
  };
});
const intentKeys = computed(
  () => new Set(intents.value.map((intent) => intent.recruit_key)),
);

onMounted(() => {
  document.addEventListener("keydown", handleDocumentKeydown);
  void loadJobs();
});

watch(
  () => [
    session.isAuthenticated,
    returnAction.value.action,
    jobData.value?.jobs.length,
  ],
  async () => {
    if (!session.isAuthenticated) return;
    const pending = returnAction.value;
    const shouldResume = route.query.resumeAction === "1";
    if (shouldResume && pending.action === "save" && pending.jobId) {
      const job = jobData.value?.jobs.find((item) => item.id === pending.jobId);
      if (!job) {
        resumeAfterJobsLoad = true;
      } else if (!resumeAfterJobsLoad) {
        resumeAfterJobsLoad = true;
        await toggleSaved(job);
      }
    } else if (shouldResume && pending.action === "apply" && pending.jobId) {
      const job = jobData.value?.jobs.find((item) => item.id === pending.jobId);
      if (!job) {
        resumeAfterJobsLoad = true;
      } else if (!resumeAfterJobsLoad) {
        resumeAfterJobsLoad = true;
        await submitApplication(job);
      }
    } else if (
      shouldResume &&
      pending.action === "intent" &&
      pending.recruitKey
    ) {
      const recruitment = jobData.value?.recruitments.find(
        (item) => item.key === pending.recruitKey,
      );
      if (!recruitment) {
        resumeAfterJobsLoad = true;
      } else if (!resumeAfterJobsLoad) {
        resumeAfterJobsLoad = true;
        await toggleIntent(recruitment);
      }
    }
  },
);

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleDocumentKeydown);
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer);
});

async function loadJobs(): Promise<void> {
  const requestId = ++jobsRequestId;
  jobsLoading.value = true;
  jobsError.value = "";
  try {
    const response = await getJobs({
      keyword: keyword.value.trim(),
      location: location.value,
      salary: salary.value,
      category: category.value,
    });
    if (requestId !== jobsRequestId) return;
    jobData.value = response;
    if (session.isAuthenticated) {
      await loadSavedIds();
    } else {
      savedIds.value = new Set();
    }
  } catch (error) {
    if (requestId !== jobsRequestId) return;
    jobsError.value = describeError(error, "岗位列表加载失败，请稍后重试");
  } finally {
    if (requestId === jobsRequestId) jobsLoading.value = false;
  }
}

async function loadSavedIds(): Promise<void> {
  if (!session.user) return;
  try {
    const response = await getSavedJobs(session.user.id);
    savedIds.value = new Set(response.saved_ids);
  } catch {
    // The visible list stays useful when the saved-state request fails.
  }
}

async function selectTab(tab: ActiveTab): Promise<void> {
  activeTab.value = tab;
  const query = { ...route.query };
  if (tab === "resume") {
    query.tab = "resume";
  } else {
    delete query.tab;
  }
  if (JSON.stringify(query) !== JSON.stringify(route.query)) {
    await router.replace({ query });
  }
  if (tab === "applications") await loadMyJobs();
  if (tab === "saved") await loadSavedJobs();
}

function initialEmploymentTab(): ActiveTab {
  return route.query.tab === "resume" ? "resume" : "jobs";
}

async function loadMyJobs(): Promise<void> {
  if (!session.user) return;
  myJobsLoading.value = true;
  myJobsError.value = "";
  try {
    const response = await getMyJobs(session.user.id);
    applications.value = response.applications;
    intents.value = response.intents;
    hasResume.value = response.has_resume;
    intentNotice.value = response.intent_notice;
    myJobsLoaded.value = true;
  } catch (error) {
    myJobsError.value = describeError(error, "求职记录加载失败，请稍后重试");
  } finally {
    myJobsLoading.value = false;
  }
}

async function loadSavedJobs(): Promise<void> {
  if (!session.user) return;
  savedJobsLoading.value = true;
  savedJobsError.value = "";
  try {
    const [saved, jobs] = await Promise.all([
      getSavedJobs(session.user.id),
      getJobs(),
    ]);
    savedIds.value = new Set(saved.saved_ids);
    savedJobs.value = jobs.jobs.filter((job) =>
      saved.saved_ids.includes(job.id),
    );
  } catch (error) {
    savedJobsError.value = describeError(error, "收藏职位加载失败，请稍后重试");
  } finally {
    savedJobsLoading.value = false;
  }
}

async function openJob(jobOrId: EnterpriseJob | number): Promise<void> {
  const jobId = typeof jobOrId === "number" ? jobOrId : jobOrId.id;
  const requestId = ++detailRequestId;
  selectedRecruitment.value = null;
  selectedJob.value = typeof jobOrId === "number" ? null : jobOrId;
  similarJobs.value = [];
  detailError.value = "";
  detailLoading.value = true;
  detailOpen.value = true;

  const [detailResult, similarResult] = await Promise.allSettled([
    getJobDetail(jobId),
    getSimilarJobs(jobId),
  ]);
  if (requestId !== detailRequestId) return;

  if (detailResult.status === "rejected") {
    selectedJob.value = null;
    detailError.value = describeError(
      detailResult.reason,
      "职位详情加载失败，请稍后重试",
    );
  } else if (!detailResult.value.success || !detailResult.value.job) {
    selectedJob.value = null;
    detailError.value =
      detailResult.value.message || "职位不存在或尚未通过审核";
  } else {
    selectedJob.value = detailResult.value.job;
  }

  similarJobs.value =
    similarResult.status === "fulfilled" ? similarResult.value.jobs : [];
  detailLoading.value = false;
}

async function openRecruitment(recruitment: PublicRecruitment): Promise<void> {
  ++detailRequestId;
  selectedJob.value = null;
  selectedRecruitment.value = recruitment;
  similarJobs.value = [];
  detailError.value = "";
  detailLoading.value = false;
  detailOpen.value = true;
  if (session.isAuthenticated && !myJobsLoaded.value) {
    await loadMyJobs();
  }
}

function closeDetail(): void {
  detailOpen.value = false;
  detailLoading.value = false;
  detailError.value = "";
  selectedJob.value = null;
  selectedRecruitment.value = null;
  similarJobs.value = [];
}

async function goToLogin(action: string, jobId: number): Promise<void> {
  const redirect = buildActionRedirect({
    action,
    job: String(jobId),
    resumeAction: "1",
  });
  await router.push({
    path: "/login",
    query: { redirect },
  });
}

async function goToIntentLogin(recruitKey: string): Promise<void> {
  const redirect = buildActionRedirect({
    action: "intent",
    recruit: recruitKey,
    resumeAction: "1",
  });
  await router.push({
    path: "/login",
    query: { redirect },
  });
}

function buildActionRedirect(actionQuery: Record<string, string>): string {
  const query = new URLSearchParams({
    ...redirectAfterLogin.value,
    ...actionQuery,
  });
  return `${route.path}?${query.toString()}`;
}

async function toggleSaved(job: EnterpriseJob): Promise<void> {
  if (!session.isAuthenticated) {
    await goToLogin("save", job.id);
    return;
  }
  if (!session.user || actionBusy.value) return;
  actionBusy.value = true;
  busyJobId.value = job.id;
  const wasSaved = savedIds.value.has(job.id);
  try {
    const response = wasSaved
      ? await unsaveJob(session.user.id, job.id)
      : await saveJob(session.user.id, job.id);
    const next = new Set(savedIds.value);
    if (wasSaved) next.delete(job.id);
    else if (response.success) next.add(job.id);
    savedIds.value = next;
    showFeedback(response.message || (wasSaved ? "已取消收藏" : "收藏成功"),
      response.success ? "success" : "error");
    if (activeTab.value === "saved") await loadSavedJobs();
  } catch (error) {
    showFeedback(describeError(error, "操作失败，请稍后重试"), "error");
  } finally {
    busyJobId.value = null;
    actionBusy.value = false;
  }
}

async function submitApplication(job: EnterpriseJob): Promise<void> {
  if (!session.isAuthenticated) {
    await goToLogin("apply", job.id);
    return;
  }
  if (!session.user || actionBusy.value) return;
  actionBusy.value = true;
  busyJobId.value = job.id;
  try {
    const response = await applyForJob(session.user.id, job.id);
    if (!response.success) {
      showFeedback(response.message || "申请失败", "error");
      return;
    }
    const resumeNote =
      response.has_resume === false
        ? " · 你还没有填写简历，企业暂时看不到简历内容"
        : "";
    showFeedback(`${response.message}${resumeNote}`, "success");
    if (myJobsLoaded.value) await loadMyJobs();
  } catch (error) {
    showFeedback(describeError(error, "申请失败，请稍后重试"), "error");
  } finally {
    busyJobId.value = null;
    actionBusy.value = false;
  }
}

async function toggleIntent(recruitment: PublicRecruitment): Promise<void> {
  if (!session.isAuthenticated) {
    await goToIntentLogin(recruitment.key);
    return;
  }
  if (!session.user || actionBusy.value) return;
  actionBusy.value = true;
  busyIntentKey.value = recruitment.key;
  const registered = intentKeys.value.has(recruitment.key);
  try {
    const response = registered
      ? await removeJobIntent(session.user.id, recruitment.key)
      : await addJobIntent(session.user.id, recruitment.key);
    if (!response.success) {
      showFeedback(response.message || "操作失败", "error");
      return;
    }
    if (registered) {
      intents.value = intents.value.filter(
        (intent) => intent.recruit_key !== recruitment.key,
      );
      showFeedback("已取消意向登记", "success");
    } else {
      const detail = response.notice
        ? `${response.message}（${response.notice}）`
        : response.message;
      showFeedback(detail, "success");
      if (!myJobsLoaded.value) await loadMyJobs();
      else {
        const refreshed = await getMyJobs(session.user.id);
        intents.value = refreshed.intents;
        applications.value = refreshed.applications;
        hasResume.value = refreshed.has_resume;
        intentNotice.value = refreshed.intent_notice;
      }
    }
  } catch (error) {
    showFeedback(describeError(error, "操作失败，请稍后重试"), "error");
  } finally {
    busyIntentKey.value = "";
    actionBusy.value = false;
  }
}

async function openRecruitmentFromIntent(intent: JobIntent): Promise<void> {
  const recruitment = jobData.value?.recruitments.find(
    (item) => item.key === intent.recruit_key,
  );
  if (recruitment) {
    await openRecruitment(recruitment);
    return;
  }
  await openRecruitment({
    key: intent.recruit_key,
    title: intent.title,
    org: intent.org,
    region: intent.region,
    category: intent.category,
    deadline: intent.deadline,
    status: intent.status as PublicRecruitment["status"],
    status_label: intent.status_label,
    source_type: "public_recruit",
  });
}

async function removeIntentFromHistory(intent: JobIntent): Promise<void> {
  if (!session.user || actionBusy.value) return;
  actionBusy.value = true;
  busyIntentKey.value = intent.recruit_key;
  try {
    const response = await removeJobIntent(session.user.id, intent.recruit_key);
    if (!response.success) {
      showFeedback(response.message || "取消意向失败", "error");
      return;
    }
    intents.value = intents.value.filter(
      (item) => item.recruit_key !== intent.recruit_key,
    );
    showFeedback("已取消意向登记", "success");
  } catch (error) {
    showFeedback(describeError(error, "取消意向失败，请稍后重试"), "error");
  } finally {
    busyIntentKey.value = "";
    actionBusy.value = false;
  }
}

function showFeedback(text: string, kind: FeedbackKind): void {
  feedback.value = { text, kind };
  if (feedbackTimer !== undefined) window.clearTimeout(feedbackTimer);
  feedbackTimer = window.setTimeout(() => {
    feedback.value = null;
    feedbackTimer = undefined;
  }, 5_000);
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return "连接服务器失败，请检查网络后重试";
    return error.message || fallback;
  }
  return fallback;
}

function handleDocumentKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && detailOpen.value) closeDetail();
}

function categoryLabel(option: CategoryOption): string {
  return `${option.value}（${option.count > 0 ? option.count : "暂无"}）`;
}

function companyInitial(company: string): string {
  return company?.trim().charAt(0) || "企";
}

function relativeDate(value: string): string {
  if (!value) return "";
  const date = new Date(value.replace(" ", "T"));
  if (!Number.isFinite(date.getTime())) return value;
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return "今天发布";
  if (days === 1) return "1天前发布";
  if (days < 7) return `${days}天前发布`;
  if (days < 30) return `${Math.floor(days / 7)}周前发布`;
  return value.slice(0, 10);
}

function jobTags(job: EnterpriseJob): string[] {
  const tags = job.requirements.slice(0, 3);
  return job.category ? [job.category, ...tags] : tags;
}

function statusMeta(status: string) {
  return STATUS_META[status] ?? FALLBACK_STATUS_META;
}

function applicationTimeline(application: Application) {
  const meta = statusMeta(application.status);
  return [
    {
      label: `提交申请 ${application.applied_at || ""}`.trim(),
      done: true,
      active: false,
    },
    {
      label: "企业查阅中",
      done: application.status !== "pending",
      active: application.status === "pending",
    },
    {
      label: meta.timelineLabel,
      done: application.status !== "pending",
      active: application.status === "interview",
    },
  ];
}

function recruitmentDeadline(recruitment: PublicRecruitment): string {
  return recruitment.deadline ? `报名截止 ${recruitment.deadline}` : "";
}

function recruitmentTimeHint(recruitment: PublicRecruitment): string {
  if (recruitment.status === "open" && recruitment.days_left != null) {
    return `还剩 ${recruitment.days_left} 天`;
  }
  if (recruitment.status === "upcoming" && recruitment.starts_in != null) {
    return `距开始报名 ${recruitment.starts_in} 天`;
  }
  return "";
}

function safeHttpUrl(value: string | undefined): string {
  if (!value || !/^https?:\/\//i.test(value)) return "";
  return value;
}

function primarySourceUrl(recruitment: PublicRecruitment): string {
  return safeHttpUrl(recruitment.sources?.[0]?.url);
}

function recruitmentInfoRows(recruitment: PublicRecruitment) {
  return [
    ["发布单位", recruitment.org],
    ["地区", recruitment.region],
    ["岗位类别", recruitment.category],
    ["用工性质", recruitment.job_type],
    ["招聘人数", recruitment.headcount],
    ["学历要求", recruitment.education],
    ["其他条件", recruitment.experience],
    ["薪酬待遇", recruitment.salary],
    [
      "报名时间",
      [recruitment.signup_start, recruitment.deadline].filter(Boolean).join(" 至 "),
    ],
    ["报名方式", recruitment.signup_way],
    ["咨询方式", recruitment.contact],
    ["发布日期", recruitment.publish_date],
  ].filter((row): row is [string, string] => Boolean(row[1]));
}

function isIntentRegistered(key: string): boolean {
  return intentKeys.value.has(key);
}
</script>

<template>
  <section
    id="employment-tab"
    class="tab-content active employment-view"
    aria-labelledby="employment-title"
  >
    <div class="container">
      <div class="employment-container">
        <div class="section-label">
          Employment
        </div>
        <h1
          id="employment-title"
          class="section-title"
        >
          就业对接
        </h1>
        <p class="section-desc">
          能力档案 → AI 简历辅助 → 相似职位推荐 → 投递与报名，一条链路跑通求职全程
        </p>

        <form
          class="employment-search-bar"
          role="search"
          @submit.prevent="loadJobs"
        >
          <div class="employment-search-input-wrap">
            <i
              class="fas fa-search"
              aria-hidden="true"
            />
            <input
              v-model="keyword"
              type="text"
              name="employment_keyword"
              autocomplete="off"
              aria-label="搜索职位、公司、技能"
              placeholder="搜索职位、公司、技能..."
            >
          </div>
          <select
            v-model="location"
            aria-label="工作地点"
          >
            <option value="">
              工作地点
            </option>
            <option
              v-for="item in LOCATIONS"
              :key="item"
              :value="item"
            >
              {{ item }}
            </option>
          </select>
          <select
            v-model="salary"
            aria-label="薪资范围"
          >
            <option value="">
              薪资范围
            </option>
            <option
              v-for="[value, label] in SALARY_OPTIONS"
              :key="value"
              :value="value"
            >
              {{ label }}
            </option>
          </select>
          <select
            v-model="category"
            aria-label="职位类型"
          >
            <option value="">
              职位类型
            </option>
            <optgroup label="企业招聘岗位">
              <option
                v-for="option in enterpriseCategoryOptions"
                :key="`enterprise-${option.value}`"
                :value="option.value"
              >
                {{ categoryLabel(option) }}
              </option>
            </optgroup>
            <optgroup label="公开招聘公告">
              <option
                v-for="option in recruitCategoryOptions"
                :key="`recruit-${option.value}`"
                :value="option.value"
              >
                {{ categoryLabel(option) }}
              </option>
            </optgroup>
          </select>
          <button
            type="submit"
            class="btn btn-primary"
          >
            <i
              class="fas fa-search"
              aria-hidden="true"
            />
            搜索
          </button>
        </form>

        <div
          class="employment-tabs"
          role="tablist"
          aria-label="就业信息分类"
        >
          <button
            type="button"
            class="employment-tab"
            :class="{ active: activeTab === 'jobs' }"
            role="tab"
            :aria-selected="activeTab === 'jobs'"
            @click="selectTab('jobs')"
          >
            全部职位
          </button>
          <button
            type="button"
            class="employment-tab"
            :class="{ active: activeTab === 'resume' }"
            role="tab"
            :aria-selected="activeTab === 'resume'"
            @click="selectTab('resume')"
          >
            我的简历
          </button>
          <button
            type="button"
            class="employment-tab"
            :class="{ active: activeTab === 'applications' }"
            role="tab"
            :aria-selected="activeTab === 'applications'"
            @click="selectTab('applications')"
          >
            我的求职
          </button>
          <button
            type="button"
            class="employment-tab"
            :class="{ active: activeTab === 'saved' }"
            role="tab"
            :aria-selected="activeTab === 'saved'"
            @click="selectTab('saved')"
          >
            收藏职位
          </button>
        </div>

        <div
          v-if="feedback"
          class="employment-feedback"
          :class="`is-${feedback.kind}`"
          :role="feedback.kind === 'error' ? 'alert' : 'status'"
          data-testid="employment-feedback"
        >
          {{ feedback.text }}
        </div>

        <div
          v-if="activeTab === 'jobs'"
          class="employment-panel active"
          role="tabpanel"
        >
          <div
            v-if="jobsLoading"
            class="employment-empty"
            role="status"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>岗位信息加载中...</p>
          </div>
          <div
            v-else-if="jobsError"
            class="employment-empty"
            role="alert"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            <p>{{ jobsError }}</p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="loadJobs"
            >
              重新加载
            </button>
          </div>
          <template v-else>
            <div class="employment-job-count">
              共 {{ visibleCount }} 条信息
              <span
                v-if="visibleCount"
                class="employment-job-count-detail"
              >
                （企业岗位 {{ visibleJobs.length }} · 公开招聘 {{ visibleRecruitments.length }}）
              </span>
            </div>

            <div
              v-if="salary && recruitHiddenBySalary > 0"
              class="employment-filter-note"
              role="status"
              data-testid="employment-filter-note"
            >
              <i
                class="fas fa-circle-info"
                aria-hidden="true"
              />
              <span>
                薪资筛选只作用于<b>企业招聘岗位</b>：{{ recruitHiddenBySalary }}
                条公开招聘公告没有薪资字段、不参与薪资筛选，已暂时隐藏。想同时看公告，把「薪资范围」清空即可。
              </span>
            </div>

            <section
              v-if="activeRecruitments.length"
              aria-labelledby="active-recruit-title"
            >
              <h2
                id="active-recruit-title"
                class="employment-list-section-title"
              >
                <i
                  class="fas fa-bullhorn"
                  aria-hidden="true"
                />
                公开招聘信息
                <span class="employment-list-section-note">官方公告汇编 · 点卡片查看公告原文</span>
              </h2>
              <article
                v-for="recruitment in activeRecruitments"
                :key="recruitment.key"
                class="employment-job-card employment-recruit-card"
                data-testid="employment-recruitment-card"
                :data-recruitment-key="recruitment.key"
                :class="{ 'is-closed': recruitment.status === 'closed' }"
              >
                <div class="employment-job-card-left">
                  <div class="employment-company-logo employment-recruit-logo">
                    <i
                      class="fas fa-bullhorn"
                      aria-hidden="true"
                    />
                  </div>
                </div>
                <div class="employment-job-card-body">
                  <div class="employment-job-header">
                    <button
                      type="button"
                      class="employment-job-title employment-job-title-button"
                      data-testid="employment-job-title"
                      @click="openRecruitment(recruitment)"
                    >
                      {{ recruitment.title }}
                    </button>
                    <span
                      class="employment-recruit-status"
                      :class="`rec-${recruitment.status}`"
                    >
                      {{ recruitment.status_label }}
                    </span>
                  </div>
                  <div class="employment-job-company">
                    {{ recruitment.org }}
                    <template v-if="recruitment.region">
                      <span class="employment-dot">·</span>{{ recruitment.region }}
                    </template>
                    <template v-if="recruitment.job_type">
                      <span class="employment-dot">·</span>{{ recruitment.job_type }}
                    </template>
                  </div>
                  <div class="employment-job-tags">
                    <span class="employment-tag employment-tag-src employment-tag-rec">
                      <i
                        class="fas fa-bullhorn"
                        aria-hidden="true"
                      />
                      公开招聘
                    </span>
                    <span
                      v-if="recruitment.category"
                      class="employment-tag"
                    >{{ recruitment.category }}</span>
                    <span
                      v-if="recruitment.headcount"
                      class="employment-tag"
                    >{{ recruitment.headcount }}</span>
                    <span
                      v-if="recruitment.education"
                      class="employment-tag"
                    >{{ recruitment.education }}</span>
                  </div>
                </div>
                <div class="employment-job-card-right">
                  <span
                    v-if="recruitmentDeadline(recruitment)"
                    class="employment-job-date"
                  >{{ recruitmentDeadline(recruitment) }}</span>
                  <span
                    v-if="recruitmentTimeHint(recruitment)"
                    class="employment-recruit-left"
                  >{{ recruitmentTimeHint(recruitment) }}</span>
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    @click="openRecruitment(recruitment)"
                  >
                    <i
                      class="fas fa-external-link-alt"
                      aria-hidden="true"
                    />
                    查看公告
                  </button>
                </div>
              </article>
            </section>

            <details
              v-if="expiredRecruitments.length"
              class="employment-recruit-expired"
            >
              <summary>
                <i
                  class="fas fa-clock-rotate-left"
                  aria-hidden="true"
                />
                已过报名期 {{ expiredRecruitments.length }} 条
                <span class="employment-recruit-expired-note">报名已结束，仅作岗位与条件参考</span>
              </summary>
              <article
                v-for="recruitment in expiredRecruitments"
                :key="recruitment.key"
                class="employment-job-card employment-recruit-card is-closed"
                data-testid="employment-recruitment-card"
                :data-recruitment-key="recruitment.key"
              >
                <div class="employment-job-card-left">
                  <div class="employment-company-logo employment-recruit-logo">
                    <i
                      class="fas fa-bullhorn"
                      aria-hidden="true"
                    />
                  </div>
                </div>
                <div class="employment-job-card-body">
                  <div class="employment-job-header">
                    <button
                      type="button"
                      class="employment-job-title employment-job-title-button"
                      data-testid="employment-job-title"
                      @click="openRecruitment(recruitment)"
                    >
                      {{ recruitment.title }}
                    </button>
                    <span
                      class="employment-recruit-status"
                      :class="`rec-${recruitment.status}`"
                    >
                      {{ recruitment.status_label }}
                    </span>
                  </div>
                  <div class="employment-job-company">
                    {{ recruitment.org }}
                    <span
                      v-if="recruitment.region"
                      class="employment-dot"
                    >·</span>{{ recruitment.region }}
                  </div>
                </div>
                <div class="employment-job-card-right">
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    @click="openRecruitment(recruitment)"
                  >
                    查看公告
                  </button>
                </div>
              </article>
            </details>

            <section
              v-if="visibleJobs.length"
              aria-labelledby="enterprise-jobs-title"
            >
              <h2
                id="enterprise-jobs-title"
                class="employment-list-section-title"
              >
                <i
                  class="fas fa-building"
                  aria-hidden="true"
                />
                企业招聘岗位
                <span class="employment-list-section-note">由入驻企业发布，平台审核通过后展示</span>
              </h2>
              <article
                v-for="job in visibleJobs"
                :key="job.id"
                class="employment-job-card"
                data-testid="employment-job-card"
                :data-job-id="job.id"
                :class="{ 'is-demo': job.is_demo }"
                @click="openJob(job)"
              >
                <div class="employment-job-card-left">
                  <div class="employment-company-logo">
                    {{ companyInitial(job.company) }}
                  </div>
                </div>
                <div class="employment-job-card-body">
                  <div class="employment-job-header">
                    <button
                      type="button"
                      class="employment-job-title employment-job-title-button"
                      data-testid="employment-job-title"
                      @click.stop="openJob(job)"
                    >
                      {{ job.title }}
                    </button>
                    <span class="employment-job-salary">{{ job.salary }}</span>
                  </div>
                  <div class="employment-job-company">
                    {{ job.company }}<span class="employment-dot">·</span>{{ job.location || "广东" }}<span class="employment-dot">·</span>{{ job.experience || "不限" }}<span class="employment-dot">·</span>{{ job.education || "不限" }}
                  </div>
                  <div class="employment-job-tags">
                    <span
                      v-if="job.is_demo"
                      class="employment-tag employment-tag-demo"
                    >
                      <i
                        class="fas fa-flask"
                        aria-hidden="true"
                      />
                      演示数据
                    </span>
                    <span class="employment-tag employment-tag-src">
                      <i
                        class="fas fa-building"
                        aria-hidden="true"
                      />
                      企业发布
                    </span>
                    <span
                      v-for="tag in jobTags(job)"
                      :key="`${job.id}-${tag}`"
                      class="employment-tag"
                    >{{ tag }}</span>
                  </div>
                </div>
                <div class="employment-job-card-right">
                  <span class="employment-job-date">{{ relativeDate(job.posted_at) }}</span>
                  <button
                    type="button"
                    class="btn btn-primary btn-sm"
                    :disabled="actionBusy && busyJobId === job.id"
                    @click.stop="submitApplication(job)"
                  >
                    申请职位
                  </button>
                  <button
                    type="button"
                    class="employment-save-btn"
                    :class="{ saved: savedIds.has(job.id) }"
                    :aria-label="savedIds.has(job.id) ? `取消收藏 ${job.title}` : `收藏 ${job.title}`"
                    :title="savedIds.has(job.id) ? '取消收藏' : '收藏'"
                    :disabled="actionBusy && busyJobId === job.id"
                    @click.stop="toggleSaved(job)"
                  >
                    <i
                      class="fa-heart"
                      :class="savedIds.has(job.id) ? 'fas' : 'far'"
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </article>
            </section>

            <div
              v-if="pendingCount > 0 && visibleJobs.length === 0"
              class="employment-review-pending"
              role="status"
            >
              <i
                class="fas fa-hourglass-half"
                aria-hidden="true"
              />
              <span>
                另有 <b>{{ pendingCount }}</b> 条企业发布的岗位<b>正在审核中</b>，通过平台审核后才会在这里展示。
              </span>
            </div>

            <div
              v-if="visibleCount === 0"
              class="employment-empty"
              data-testid="employment-empty"
            >
              <i
                class="fas fa-search"
                aria-hidden="true"
              />
              <p>{{ emptyTitle }}</p>
              <span class="employment-empty-sub">{{ emptyHint }}</span>
            </div>

            <div
              v-if="visibleRecruitments.length"
              class="employment-recruit-footnote"
            >
              <i
                class="fas fa-info-circle"
                aria-hidden="true"
              />
              {{ jobData?.recruit_source_note }}
              <br>
              {{ jobData?.recruit_disclaimer }}
            </div>
          </template>
        </div>

        <div
          v-else-if="activeTab === 'resume'"
          class="employment-panel active"
          role="tabpanel"
        >
          <ResumeProfilePanel />
        </div>

        <div
          v-else-if="activeTab === 'applications'"
          class="employment-panel active"
          role="tabpanel"
        >
          <div
            v-if="!session.isAuthenticated"
            class="employment-empty employment-empty-inline"
          >
            <i
              class="fas fa-user-lock"
              aria-hidden="true"
            />
            <p>登录后可查看投递记录与求职意向</p>
            <RouterLink
              class="btn btn-primary btn-sm"
              :to="loginTarget"
            >
              去登录
            </RouterLink>
          </div>
          <div
            v-else-if="myJobsLoading"
            class="employment-empty employment-empty-inline"
            role="status"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>求职记录加载中...</p>
          </div>
          <div
            v-else-if="myJobsError"
            class="employment-empty employment-empty-inline"
            role="alert"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            <p>{{ myJobsError }}</p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="loadMyJobs"
            >
              重试
            </button>
          </div>
          <template v-else>
            <h2 class="employment-list-section-title">
              <i
                class="fas fa-bookmark"
                aria-hidden="true"
              />
              公开招聘意向
              <span class="employment-list-section-note">仅记录你的意向 · 报名请按公告原文自行完成</span>
            </h2>
            <div
              v-if="!intents.length"
              class="employment-empty employment-empty-inline"
            >
              <i
                class="far fa-bookmark"
                aria-hidden="true"
              />
              <p>还没有登记求职意向</p>
              <span class="employment-empty-sub">在「全部职位」里打开任意一条公开招聘公告，点「登记求职意向」即可</span>
            </div>
            <div
              v-else
              class="employment-intent-list"
            >
              <article
                v-for="intent in intents"
                :key="intent.recruit_key"
                class="employment-intent-card"
                data-testid="employment-intent-card"
                :data-recruitment-key="intent.recruit_key"
              >
                <div class="employment-intent-main">
                  <div class="employment-intent-head">
                    <span class="employment-intent-title">{{ intent.title }}</span>
                    <span
                      class="employment-recruit-status"
                      :class="`rec-${intent.status}`"
                    >
                      {{ intent.status_label }}
                    </span>
                  </div>
                  <div class="employment-intent-meta">
                    {{ intent.org }}
                    <template v-if="intent.region">
                      <span class="employment-dot">·</span>{{ intent.region }}
                    </template>
                    <span class="employment-dot">·</span>{{ intent.deadline ? `报名截止 ${intent.deadline}` : "报名时间以公告原文为准" }}
                  </div>
                  <div
                    v-if="intent.note"
                    class="employment-intent-note"
                  >
                    备注：{{ intent.note }}
                  </div>
                  <div class="employment-intent-disclaimer">
                    <i
                      class="fas fa-circle-info"
                      aria-hidden="true"
                    />
                    本站仅记录意向，<strong>不代办报名</strong>，请按公告原文自行报名。
                  </div>
                </div>
                <div class="employment-intent-actions">
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    @click="openRecruitmentFromIntent(intent)"
                  >
                    查看公告
                  </button>
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    @click="removeIntentFromHistory(intent)"
                  >
                    取消意向
                  </button>
                </div>
              </article>
            </div>
            <div
              v-if="intentNotice"
              class="employment-recruit-footnote"
            >
              {{ intentNotice }}
            </div>

            <h2 class="employment-list-section-title">
              <i
                class="fas fa-paper-plane"
                aria-hidden="true"
              />
              企业岗位投递
              <span class="employment-list-section-note">站内投递 · 企业端可查看简历并给反馈</span>
            </h2>
            <div
              class="employment-app-tabs"
              role="tablist"
              aria-label="投递状态"
            >
              <button
                v-for="item in APPLICATION_FILTERS"
                :key="item.value"
                type="button"
                class="employment-app-tab"
                :class="{ active: applicationFilter === item.value }"
                role="tab"
                :aria-selected="applicationFilter === item.value"
                @click="applicationFilter = item.value"
              >
                {{ item.label }}
              </button>
            </div>
            <div
              v-if="hasResume === false"
              class="employment-app-note"
              role="status"
            >
              <i
                class="fas fa-triangle-exclamation"
                aria-hidden="true"
              />
              <span>
                你还没有填写简历，企业端暂时看不到你的简历内容。
                <button
                  type="button"
                  class="employment-inline-link"
                  @click="selectTab('resume')"
                >
                  去完善简历
                </button>
              </span>
            </div>
            <div
              v-if="!filteredApplications.length"
              class="employment-empty employment-empty-inline"
            >
              <i
                class="fas fa-paper-plane"
                aria-hidden="true"
              />
              <p>暂无企业岗位投递记录</p>
              <span class="employment-empty-sub">在「全部职位」里找到合适的岗位，点「申请职位」即可。</span>
            </div>
            <div
              v-else
              class="employment-app-list"
            >
              <article
                v-for="application in filteredApplications"
                :key="application.id"
                class="employment-app-card"
                data-testid="employment-application-card"
                :data-application-id="application.id"
                :data-job-id="application.job_id"
              >
                <div class="employment-app-header">
                  <h3>{{ application.title }}</h3>
                  <span
                    class="employment-app-status"
                    :class="statusMeta(application.status).className"
                  >
                    {{ statusMeta(application.status).label }}
                  </span>
                </div>
                <p class="employment-app-company">
                  {{ application.company }} · {{ application.location || "广东" }}
                </p>
                <p class="employment-app-salary">
                  {{ application.salary }}
                </p>
                <div class="employment-app-timeline">
                  <div
                    v-for="step in applicationTimeline(application)"
                    :key="step.label"
                    class="employment-timeline-item"
                    :class="{ done: step.done, active: step.active }"
                  >
                    <span class="employment-timeline-dot" />
                    <span>{{ step.label }}</span>
                  </div>
                </div>
              </article>
            </div>
          </template>
        </div>

        <div
          v-else
          class="employment-panel active"
          role="tabpanel"
        >
          <div
            v-if="!session.isAuthenticated"
            class="employment-empty employment-empty-inline"
          >
            <i
              class="fas fa-user-lock"
              aria-hidden="true"
            />
            <p>登录后可收藏职位</p>
            <span class="employment-empty-sub">登录后，在「全部职位」里点卡片右侧的爱心即可收藏</span>
            <RouterLink
              class="btn btn-primary btn-sm"
              :to="loginTarget"
            >
              去登录
            </RouterLink>
          </div>
          <div
            v-else-if="savedJobsLoading"
            class="employment-empty employment-empty-inline"
            role="status"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>收藏职位加载中...</p>
          </div>
          <div
            v-else-if="savedJobsError"
            class="employment-empty employment-empty-inline"
            role="alert"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            <p>{{ savedJobsError }}</p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              @click="loadSavedJobs"
            >
              重试
            </button>
          </div>
          <div
            v-else-if="!savedJobs.length"
            class="employment-empty employment-empty-inline"
          >
            <i
              class="far fa-heart"
              aria-hidden="true"
            />
            <p>暂无收藏的职位</p>
          </div>
          <div
            v-else
            class="employment-job-list"
          >
            <article
              v-for="job in savedJobs"
              :key="job.id"
              class="employment-job-card"
              data-testid="employment-job-card"
              :data-job-id="job.id"
              :class="{ 'is-demo': job.is_demo }"
              @click="openJob(job)"
            >
              <div class="employment-job-card-left">
                <div class="employment-company-logo">
                  {{ companyInitial(job.company) }}
                </div>
              </div>
              <div class="employment-job-card-body">
                <div class="employment-job-header">
                  <button
                    type="button"
                    class="employment-job-title employment-job-title-button"
                    data-testid="employment-job-title"
                    @click.stop="openJob(job)"
                  >
                    {{ job.title }}
                  </button>
                  <span class="employment-job-salary">{{ job.salary }}</span>
                </div>
                <div class="employment-job-company">
                  {{ job.company }}<span class="employment-dot">·</span>{{ job.location || "广东" }}
                </div>
                <div class="employment-job-tags">
                  <span class="employment-tag employment-tag-src">企业发布</span>
                  <span
                    v-for="tag in jobTags(job)"
                    :key="`${job.id}-saved-${tag}`"
                    class="employment-tag"
                  >{{ tag }}</span>
                </div>
              </div>
              <div class="employment-job-card-right">
                <button
                  type="button"
                  class="employment-save-btn saved"
                  :aria-label="`取消收藏 ${job.title}`"
                  @click.stop="toggleSaved(job)"
                >
                  <i
                    class="fas fa-heart"
                    aria-hidden="true"
                  />
                </button>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>
  </section>

  <Teleport to="body">
    <div
      v-if="detailOpen"
      class="modal-overlay detail-modal"
      data-testid="employment-detail"
      @click.self="closeDetail"
    >
      <div
        class="modal-content employment-detail-modal"
        role="dialog"
        aria-modal="true"
        :aria-label="selectedRecruitment ? '公开招聘公告' : '职位详情'"
      >
        <div class="modal-header">
          <h2>{{ selectedRecruitment ? "公开招聘公告" : "职位详情" }}</h2>
          <button
            type="button"
            class="modal-close"
            aria-label="关闭"
            @click="closeDetail"
          >
            <i
              class="fas fa-times"
              aria-hidden="true"
            />
          </button>
        </div>
        <div class="modal-body">
          <div
            v-if="detailLoading"
            class="employment-empty"
            role="status"
          >
            <i
              class="fas fa-spinner fa-spin"
              aria-hidden="true"
            />
            <p>职位详情加载中...</p>
          </div>
          <div
            v-else-if="detailError"
            class="employment-empty"
            role="alert"
          >
            <i
              class="fas fa-triangle-exclamation"
              aria-hidden="true"
            />
            <p>{{ detailError }}</p>
          </div>
          <template v-else-if="selectedJob">
            <div
              v-if="selectedJob.is_demo"
              class="employment-demo-notice"
            >
              <i
                class="fas fa-flask"
                aria-hidden="true"
              />
              <div>
                <strong>这是演示岗位</strong><br>
                由平台演示企业账号发布、经管理员审核通过后展示，用于演示「企业发布 → 平台审核 → 学员投递 → 企业查看简历」的完整流程，<strong>不是真实招聘信息</strong>，请勿据此做求职决策。
              </div>
            </div>
            <div class="employment-detail-header">
              <h2>{{ selectedJob.title }}</h2>
              <span class="employment-detail-salary">{{ selectedJob.salary }}</span>
              <div class="employment-detail-tags">
                <span
                  v-for="tag in jobTags(selectedJob)"
                  :key="`detail-${tag}`"
                  class="employment-tag"
                >{{ tag }}</span>
              </div>
              <div class="employment-detail-posted">
                <i
                  class="fas fa-clock"
                  aria-hidden="true"
                />
                {{ relativeDate(selectedJob.posted_at) }}
              </div>
            </div>
            <div class="employment-detail-company">
              <div class="employment-company-logo-lg">
                {{ companyInitial(selectedJob.company) }}
              </div>
              <div class="employment-detail-company-info">
                <h3>{{ selectedJob.company }}</h3>
                <p>
                  {{ selectedJob.company_size || "" }}
                  {{ selectedJob.industry ? `· ${selectedJob.industry}` : "" }}
                  {{ selectedJob.location ? `· ${selectedJob.location}` : "" }}
                </p>
              </div>
            </div>
            <div class="employment-detail-section">
              <h3>职位信息</h3>
              <div class="employment-detail-info-grid">
                <div class="employment-detail-info-item">
                  <i class="fas fa-map-marker-alt" />
                  <div>
                    <div class="employment-detail-info-label">
                      工作地点
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.location || "广东" }}
                    </div>
                  </div>
                </div>
                <div class="employment-detail-info-item">
                  <i class="fas fa-graduation-cap" />
                  <div>
                    <div class="employment-detail-info-label">
                      学历要求
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.education || "不限" }}
                    </div>
                  </div>
                </div>
                <div class="employment-detail-info-item">
                  <i class="fas fa-briefcase" />
                  <div>
                    <div class="employment-detail-info-label">
                      经验要求
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.experience || "不限" }}
                    </div>
                  </div>
                </div>
                <div class="employment-detail-info-item">
                  <i class="fas fa-clock" />
                  <div>
                    <div class="employment-detail-info-label">
                      工作类型
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.job_type || "全职" }}
                    </div>
                  </div>
                </div>
                <div class="employment-detail-info-item">
                  <i class="fas fa-building" />
                  <div>
                    <div class="employment-detail-info-label">
                      公司规模
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.company_size || "未知" }}
                    </div>
                  </div>
                </div>
                <div class="employment-detail-info-item">
                  <i class="fas fa-industry" />
                  <div>
                    <div class="employment-detail-info-label">
                      所属行业
                    </div>
                    <div class="employment-detail-info-value">
                      {{ selectedJob.industry || "未知" }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="employment-detail-section">
              <h3>职位描述</h3>
              <div class="employment-detail-desc">
                {{ selectedJob.description || "暂无详细描述" }}
              </div>
            </div>
            <div
              v-if="selectedJob.requirements.length"
              class="employment-detail-section"
            >
              <h3>任职要求</h3>
              <ul class="employment-detail-reqs">
                <li
                  v-for="requirement in selectedJob.requirements"
                  :key="requirement"
                >
                  {{ requirement }}
                </li>
              </ul>
            </div>
            <div class="employment-detail-section">
              <h3>申请建议</h3>
              <div class="employment-detail-tips">
                <p>1. 确保简历中突出了与该岗位相关的技能和经验</p>
                <p>2. 如持有相关证书，请在简历中标注</p>
                <p>3. 申请后可在「我的求职」中查看审核进度</p>
              </div>
            </div>
            <div
              v-if="similarJobs.length"
              class="employment-detail-section"
            >
              <h3>相似职位推荐</h3>
              <div class="employment-similar-jobs">
                <button
                  v-for="similar in similarJobs"
                  :key="similar.id"
                  type="button"
                  class="employment-similar-job-item"
                  data-testid="employment-similar-job"
                  :data-job-id="similar.id"
                  @click="openJob(similar)"
                >
                  <div>
                    <span class="employment-similar-job-title">{{ similar.title }}</span>
                    <span class="employment-similar-job-company">{{ similar.company }} · {{ similar.location || "广东" }}</span>
                  </div>
                  <span class="employment-similar-job-salary">{{ similar.salary }}</span>
                </button>
              </div>
            </div>
            <div class="employment-detail-actions">
              <button
                type="button"
                class="btn btn-primary"
                :disabled="actionBusy && busyJobId === selectedJob.id"
                @click="submitApplication(selectedJob)"
              >
                <i
                  class="fas fa-paper-plane"
                  aria-hidden="true"
                />
                申请职位
              </button>
              <button
                type="button"
                class="btn btn-outline"
                :disabled="actionBusy && busyJobId === selectedJob.id"
                @click="toggleSaved(selectedJob)"
              >
                <i
                  class="fa-heart"
                  :class="savedIds.has(selectedJob.id) ? 'fas' : 'far'"
                  aria-hidden="true"
                />
                {{ savedIds.has(selectedJob.id) ? "取消收藏" : "收藏职位" }}
              </button>
            </div>
          </template>
          <template v-else-if="selectedRecruitment">
            <div class="employment-recruit-detail">
              <div class="employment-recruit-detail-head">
                <h2>{{ selectedRecruitment.title }}</h2>
                <span
                  class="employment-recruit-status"
                  :class="`rec-${selectedRecruitment.status}`"
                >
                  {{ selectedRecruitment.status_label }}
                </span>
              </div>
              <div class="employment-recruit-info">
                <div
                  v-for="[label, value] in recruitmentInfoRows(selectedRecruitment)"
                  :key="label"
                  class="employment-recruit-row"
                >
                  <span class="employment-recruit-k">{{ label }}</span>
                  <span class="employment-recruit-v">{{ value }}</span>
                </div>
              </div>
              <div class="employment-detail-section">
                <h3>公告内容摘要</h3>
                <div class="employment-detail-desc">
                  {{ selectedRecruitment.description || "详见公告原文" }}
                </div>
              </div>
              <div class="employment-detail-section">
                <h3>资料来源</h3>
                <ul class="employment-recruit-src">
                  <li
                    v-for="source in selectedRecruitment.sources ?? []"
                    :key="`${source.title}-${source.url}`"
                  >
                    <a
                      v-if="safeHttpUrl(source.url)"
                      :href="safeHttpUrl(source.url)"
                      target="_blank"
                      rel="noopener noreferrer"
                    >{{ source.title || source.url }}</a>
                    <span v-else>{{ source.title || source.url }}</span>
                    <span class="employment-recruit-src-meta">{{ [source.media, source.date].filter(Boolean).join(" · ") }}</span>
                  </li>
                </ul>
              </div>
              <div class="employment-recruit-note">
                {{
                  selectedRecruitment.status === "closed"
                    ? "该公告报名已结束，信息仅供了解岗位与条件；如需跟进，请留意发布单位的下一轮公告。"
                    : (jobData?.recruit_disclaimer || "岗位条件、报名时间以发布单位公告原文为准；本平台不代办报名。")
                }}
              </div>
              <div
                v-if="selectedRecruitment.status === 'open' || selectedRecruitment.status === 'upcoming'"
                class="employment-recruit-intent-box"
              >
                <div class="employment-recruit-intent-tip">
                  <i
                    class="fas fa-circle-info"
                    aria-hidden="true"
                  />
                  想让平台记住你的意向、方便后续查看？可以登记求职意向。
                  <strong>报名仍需你按「前往公告原文」自行完成，本平台不代办报名。</strong>
                </div>
                <button
                  type="button"
                  class="btn btn-outline employment-recruit-intent"
                  :class="{ active: isIntentRegistered(selectedRecruitment.key) }"
                  :disabled="actionBusy && busyIntentKey === selectedRecruitment.key"
                  @click="toggleIntent(selectedRecruitment)"
                >
                  <i
                    class="far fa-bookmark"
                    aria-hidden="true"
                  />
                  {{ isIntentRegistered(selectedRecruitment.key) ? "已登记意向（点击取消）" : "登记求职意向" }}
                </button>
              </div>
              <div class="employment-detail-actions">
                <a
                  v-if="primarySourceUrl(selectedRecruitment)"
                  class="btn btn-primary"
                  :href="primarySourceUrl(selectedRecruitment)"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <i
                    class="fas fa-external-link-alt"
                    aria-hidden="true"
                  />
                  前往公告原文
                </a>
                <span
                  v-else
                  class="btn btn-outline disabled"
                >公告原文链接暂不可用</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style src="./employment/employment.css"></style>

<style scoped>
.employment-view {
  min-height: 70vh;
}

.employment-job-title-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.employment-similar-job-item {
  width: 100%;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: left;
}

.employment-feedback {
  margin: 0 0 16px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 0.82rem;
  line-height: 1.6;
}

.employment-feedback.is-success {
  background: rgba(31, 94, 67, 0.1);
  color: var(--accent-blue);
}

.employment-feedback.is-error {
  background: rgba(239, 68, 68, 0.1);
  color: #b3382f;
}

.employment-feedback.is-info {
  background: rgba(217, 162, 39, 0.12);
  color: #7a5600;
}

.employment-detail-modal {
  width: min(760px, calc(100vw - 48px));
  max-height: 86vh;
}

.employment-detail-modal .modal-body {
  max-height: calc(86vh - 72px);
  overflow-y: auto;
}

.employment-detail-section h3,
.employment-detail-company h3 {
  color: var(--text-primary);
}

.employment-detail-company h3 {
  margin: 0 0 2px;
  font-size: 1rem;
}

.employment-detail-section h3 {
  margin: 0 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
  font-size: 0.95rem;
}

.employment-app-header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
}

.employment-inline-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--brand);
  font: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.btn.disabled {
  pointer-events: none;
  opacity: 0.55;
}

[data-theme="dark"] .employment-feedback.is-error {
  color: #f28b82;
}

[data-theme="dark"] .employment-feedback.is-info {
  color: #efc75e;
}
</style>
