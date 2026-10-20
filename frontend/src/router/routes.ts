import type { RouteRecordRaw } from "vue-router";

import { ROLE_FACTS } from "@/shared/roles";

const BackofficeLayout = () => import("@/layouts/BackofficeLayout.vue");

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: () => import("@/layouts/PublicLayout.vue"),
    children: [
      {
        path: "",
        name: "home",
        component: () => import("@/views/HomeView.vue"),
      },
      {
        path: "agriculture",
        name: "agriculture",
        component: () => import("@/views/AgricultureView.vue"),
      },
      {
        path: "ecommerce",
        name: "ecommerce",
        component: () => import("@/views/EcommerceView.vue"),
      },
      {
        path: "crafts",
        name: "crafts",
        component: () => import("@/views/CraftsView.vue"),
      },
      {
        path: "resources",
        name: "resources",
        component: () => import("@/views/ResourcesView.vue"),
      },
      {
        path: "employment",
        name: "employment",
        component: () => import("@/views/EmploymentView.vue"),
      },
      {
        path: "community",
        name: "community",
        component: () => import("@/views/CommunityView.vue"),
      },
      {
        path: "community/:id(\\d+)",
        name: "community-detail",
        component: () => import("@/views/CommunityDetailView.vue"),
      },
      {
        path: "case-detail/:id",
        name: "case-detail",
        component: () => import("@/views/CaseDetailView.vue"),
      },
    ],
  },
  {
    path: "/login",
    name: "login",
    component: () => import("@/views/LoginView.vue"),
  },
  {
    path: "/teacher",
    component: BackofficeLayout,
    meta: {
      requiresAuth: true,
      backofficeRole: "teacher",
      defaultPath: ROLE_FACTS.teacher.defaultPath,
    },
    children: [
      { path: "", redirect: "/teacher/dashboard" },
      {
        path: "dashboard",
        name: "teacher-dashboard",
        component: () => import("@/views/teacher/TeacherDashboardView.vue"),
        meta: {
          title: "工作台",
          capabilities: ["teaching.manage"],
          defaultPath: "/teacher/dashboard",
        },
      },
      {
        path: "announcements",
        name: "teacher-announcements",
        component: () => import("@/views/teacher/TeacherAnnouncementsView.vue"),
        meta: {
          title: "通知公告",
          capabilities: ["teaching.manage"],
          defaultPath: "/teacher/dashboard",
        },
      },
      {
        path: "analytics",
        name: "teacher-analytics",
        component: () => import("@/views/teacher/TeacherAnalyticsView.vue"),
        meta: {
          title: "学情分析",
          capabilities: ["teaching.manage"],
          defaultPath: "/teacher/dashboard",
        },
      },
      {
        path: "trainings",
        name: "teacher-trainings",
        component: () => import("@/views/teacher/TeacherTrainingsView.vue"),
        meta: {
          title: "实训提交",
          capabilities: ["teaching.manage"],
          defaultPath: "/teacher/dashboard",
        },
      },
      {
        path: "models",
        name: "teacher-models",
        component: () => import("@/views/TeacherModelsView.vue"),
        meta: {
          title: "3D 模型",
          capabilities: ["course.manage"],
          defaultPath: "/teacher/dashboard",
        },
      },
      { path: ":pathMatch(.*)*", redirect: "/teacher/dashboard" },
    ],
  },
  {
    path: "/government",
    component: BackofficeLayout,
    meta: {
      requiresAuth: true,
      backofficeRole: "government",
      defaultPath: ROLE_FACTS.government.defaultPath,
    },
    children: [
      { path: "", redirect: "/government/dashboard" },
      {
        path: "dashboard",
        name: "government-dashboard",
        component: () => import("@/views/government/GovernmentDashboardView.vue"),
        meta: {
          title: "数据大屏",
          capabilities: ["policy.manage"],
          defaultPath: "/government/dashboard",
        },
      },
      {
        path: "policies",
        name: "government-policies",
        component: () =>
          import("@/views/government/GovernmentPoliciesView.vue"),
        meta: {
          title: "政策管理",
          capabilities: ["policy.manage"],
          defaultPath: "/government/dashboard",
        },
      },
      {
        path: "publish",
        name: "government-publish",
        component: () =>
          import("@/views/government/GovernmentPublishView.vue"),
        meta: {
          title: "发布政策",
          capabilities: ["policy.manage"],
          defaultPath: "/government/dashboard",
        },
      },
      { path: ":pathMatch(.*)*", redirect: "/government/dashboard" },
    ],
  },
  {
    path: "/enterprise",
    component: BackofficeLayout,
    meta: {
      requiresAuth: true,
      backofficeRole: "enterprise",
      defaultPath: ROLE_FACTS.enterprise.defaultPath,
    },
    children: [
      { path: "", redirect: "/enterprise/dashboard" },
      {
        path: "dashboard",
        name: "enterprise-dashboard",
        component: () =>
          import("@/views/enterprise/EnterpriseDashboardView.vue"),
        meta: {
          title: "工作台",
          capabilities: ["job.manage"],
          defaultPath: "/enterprise/dashboard",
        },
      },
      {
        path: "jobs",
        name: "enterprise-jobs",
        component: () => import("@/views/enterprise/EnterpriseJobsView.vue"),
        meta: {
          title: "职位管理",
          capabilities: ["job.manage"],
          defaultPath: "/enterprise/dashboard",
        },
      },
      {
        path: "applications",
        name: "enterprise-applications",
        component: () =>
          import("@/views/enterprise/EnterpriseApplicationsView.vue"),
        meta: {
          title: "简历管理",
          capabilities: ["job.manage"],
          defaultPath: "/enterprise/dashboard",
        },
      },
      { path: ":pathMatch(.*)*", redirect: "/enterprise/dashboard" },
    ],
  },
  {
    path: "/operator",
    component: BackofficeLayout,
    meta: {
      requiresAuth: true,
      backofficeRole: "operator",
      defaultPath: ROLE_FACTS.operator.defaultPath,
    },
    children: [
      { path: "", redirect: "/operator/overview" },
      {
        path: "overview",
        name: "operator-overview",
        component: () => import("@/views/operator/OperatorOverviewView.vue"),
        meta: {
          title: "总览",
          capabilities: [],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "farming",
        name: "operator-farming",
        component: () => import("@/views/operator/OperatorFarmingView.vue"),
        meta: {
          title: "农时日历",
          capabilities: ["farming.manage"],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "pest",
        name: "operator-pest",
        component: () => import("@/views/operator/OperatorPestView.vue"),
        meta: {
          title: "病虫害知识",
          capabilities: ["pest.manage"],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "crafts",
        name: "operator-crafts",
        component: () => import("@/views/operator/OperatorCraftsView.vue"),
        meta: {
          title: "手工技艺",
          capabilities: ["craft.content.manage"],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "dialects",
        name: "operator-dialects",
        component: () => import("@/views/operator/OperatorDialectsView.vue"),
        meta: {
          title: "方言知识",
          capabilities: ["dialect.manage"],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "recruitments",
        name: "operator-recruitments",
        component: () =>
          import("@/views/operator/OperatorRecruitmentsView.vue"),
        meta: {
          title: "招募公告",
          capabilities: ["recruit.manage"],
          defaultPath: "/operator/overview",
        },
      },
      {
        path: "cases",
        name: "operator-cases",
        component: () => import("@/views/operator/OperatorCasesView.vue"),
        meta: {
          title: "成功案例",
          capabilities: ["case.manage"],
          defaultPath: "/operator/overview",
        },
      },
      { path: ":pathMatch(.*)*", redirect: "/operator/overview" },
    ],
  },
  {
    path: "/admin",
    component: BackofficeLayout,
    meta: {
      requiresAuth: true,
      backofficeRole: "super_admin",
      defaultPath: ROLE_FACTS.super_admin.defaultPath,
    },
    children: [
      { path: "", redirect: "/admin/dashboard" },
      {
        path: "dashboard",
        name: "admin-dashboard",
        component: () => import("@/views/admin/AdminDashboardView.vue"),
        meta: {
          title: "仪表盘",
          capabilities: [],
          defaultPath: "/admin/dashboard",
        },
      },
      {
        path: "users",
        name: "admin-users",
        component: () => import("@/views/admin/AdminUsersView.vue"),
        meta: {
          title: "用户管理",
          capabilities: ["user.manage"],
          defaultPath: "/admin/dashboard",
        },
      },
      {
        path: "reviews",
        name: "admin-reviews",
        component: () => import("@/views/admin/AdminReviewsView.vue"),
        meta: {
          title: "内容审核",
          capabilities: ["review.moderate"],
          defaultPath: "/admin/dashboard",
        },
      },
      {
        path: "announcements",
        name: "admin-announcements",
        component: () => import("@/views/admin/AdminAnnouncementsView.vue"),
        meta: {
          title: "系统公告",
          capabilities: ["announcement.manage"],
          defaultPath: "/admin/dashboard",
        },
      },
      {
        path: "content",
        name: "admin-content",
        component: () => import("@/views/admin/AdminContentView.vue"),
        meta: {
          title: "内容监管",
          capabilities: ["community.manage"],
          defaultPath: "/admin/dashboard",
        },
      },
      { path: ":pathMatch(.*)*", redirect: "/admin/dashboard" },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    component: () => import("@/views/HomeView.vue"),
    beforeEnter: () => ({ path: "/", replace: true }),
  },
];
