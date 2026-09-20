import { createRouter, createWebHistory } from 'vue-router'
import type { RouteComponent } from 'vue-router'
import { defineComponent, h } from 'vue'

import { useAuthStore } from '@/stores/auth'
import AgriCalendarView from '@/views/AgriCalendarView.vue'
import AgriCoursesView from '@/views/AgriCoursesView.vue'
import AgriDiagnosisView from '@/views/AgriDiagnosisView.vue'
import AgriQaView from '@/views/AgriQaView.vue'
import AgriSkillsHomeView from '@/views/AgriSkillsHomeView.vue'
import AdminAccountsView from '@/views/AdminAccountsView.vue'
import AdminAnnouncementsView from '@/views/AdminAnnouncementsView.vue'
import AdminDashboardView from '@/views/AdminDashboardView.vue'
import AdminPortalView from '@/views/AdminPortalView.vue'
import AdminRedemptionsView from '@/views/AdminRedemptionsView.vue'
import AdminReviewView from '@/views/AdminReviewView.vue'
import AdminRewardsView from '@/views/AdminRewardsView.vue'
import CourseCatalogView from '@/views/CourseCatalogView.vue'
import EcommerceCopyTrainingView from '@/views/EcommerceCopyTrainingView.vue'
import EcommerceCoursesView from '@/views/EcommerceCoursesView.vue'
import EcommerceCustomerServiceView from '@/views/EcommerceCustomerServiceView.vue'
import EcommerceLiveScriptView from '@/views/EcommerceLiveScriptView.vue'
import EcommerceSimulationView from '@/views/EcommerceSimulationView.vue'
import EcommerceStoreGuidanceView from '@/views/EcommerceStoreGuidanceView.vue'
import EcommerceTrainingHomeView from '@/views/EcommerceTrainingHomeView.vue'
import EnterpriseApplicationDetailView from '@/views/EnterpriseApplicationDetailView.vue'
import EnterpriseApplicationsView from '@/views/EnterpriseApplicationsView.vue'
import EnterpriseJobsView from '@/views/EnterpriseJobsView.vue'
import EnterprisePortalView from '@/views/EnterprisePortalView.vue'
import GovernmentDashboardView from '@/views/GovernmentDashboardView.vue'
import GovernmentNewsView from '@/views/GovernmentNewsView.vue'
import GovernmentPolicyView from '@/views/GovernmentPolicyView.vue'
import GovernmentPortalView from '@/views/GovernmentPortalView.vue'
import HandcraftCoursesView from '@/views/HandcraftCoursesView.vue'
import HandcraftCraftView from '@/views/HandcraftCraftView.vue'
import HandcraftInheritanceHomeView from '@/views/HandcraftInheritanceHomeView.vue'
import HandcraftPointsView from '@/views/HandcraftPointsView.vue'
import HandcraftRewardsView from '@/views/HandcraftRewardsView.vue'
import HomeView from '@/views/HomeView.vue'
import InterestTagsView from '@/views/InterestTagsView.vue'
import JobDetailView from '@/views/JobDetailView.vue'
import JobFavoritesView from '@/views/JobFavoritesView.vue'
import JobMatchingHomeView from '@/views/JobMatchingHomeView.vue'
import JobsView from '@/views/JobsView.vue'
import LoginView from '@/views/LoginView.vue'
import MessageCenterView from '@/views/MessageCenterView.vue'
import MyApplicationsView from '@/views/MyApplicationsView.vue'
import RegisterView from '@/views/RegisterView.vue'
import ResumeEditorView from '@/views/ResumeEditorView.vue'
import SkillProfileView from '@/views/SkillProfileView.vue'
import StudentPortalView from '@/views/StudentPortalView.vue'
import StudentProfileView from '@/views/StudentProfileView.vue'
import TeacherAnnouncementsView from '@/views/TeacherAnnouncementsView.vue'
import TeacherCoursesView from '@/views/TeacherCoursesView.vue'
import TeacherDashboardView from '@/views/TeacherDashboardView.vue'
import TeacherInteractionsView from '@/views/TeacherInteractionsView.vue'
import TeacherPortalView from '@/views/TeacherPortalView.vue'

import { authGuard } from './roleRoutes'

const teacherMeta = { requiresAuth: true, roles: ['teacher'] as const }
const adminMeta = {
  requiresAuth: true,
  roles: ['super_admin', 'admin'] as const
}
const superAdminMeta = {
  requiresAuth: true,
  roles: ['super_admin'] as const
}
const AdminRoutePlaceholder: RouteComponent = defineComponent({
  name: 'AdminRoutePlaceholder',
  setup() {
    return () => h('div', { 'data-test': 'admin-route-placeholder' })
  }
})

const localResourceViewLoaders = import.meta.glob<{
  default: RouteComponent
}>([
  '../views/LocalResourcesHomeView.vue',
  '../views/DialectAssistantView.vue',
  '../views/LocalResourceCasesView.vue',
  '../views/LocalResourceCaseDetailView.vue',
  '../views/LocalResourcePoliciesView.vue',
  '../views/LocalResourcePolicyDetailView.vue',
  '../views/LocalResourceNewsView.vue',
  '../views/LocalResourceNewsDetailView.vue'
])

function lazyLocalResourceView(path: string) {
  return async (): Promise<RouteComponent> => {
    const loader = localResourceViewLoaders[path]
    if (!loader) {
      throw new Error(`Local resource view not available: ${path}`)
    }
    return (await loader()).default
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView
    },
    {
      path: '/register/interest-tags',
      name: 'interest-tags',
      component: InterestTagsView
    },
    {
      path: '/messages',
      name: 'messages',
      component: MessageCenterView,
      meta: { requiresAuth: true }
    },
    {
      path: '/student',
      name: 'student-portal',
      component: StudentPortalView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/profile',
      name: 'student-profile',
      component: StudentProfileView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/courses',
      name: 'student-courses',
      component: CourseCatalogView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/agri-skills',
      name: 'student-agri-skills',
      component: AgriSkillsHomeView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/agri-skills/calendar',
      name: 'student-agri-calendar',
      component: AgriCalendarView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/agri-skills/qa',
      name: 'student-agri-qa',
      component: AgriQaView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/agri-skills/diagnosis',
      name: 'student-agri-diagnosis',
      component: AgriDiagnosisView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/agri-skills/courses',
      name: 'student-agri-courses',
      component: AgriCoursesView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training',
      name: 'student-ecommerce-training',
      component: EcommerceTrainingHomeView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/live-script',
      name: 'student-ecommerce-live-script',
      component: EcommerceLiveScriptView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/simulation',
      name: 'student-ecommerce-simulation',
      component: EcommerceSimulationView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/copy-training',
      name: 'student-ecommerce-copy-training',
      component: EcommerceCopyTrainingView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/store-guidance',
      name: 'student-ecommerce-store-guidance',
      component: EcommerceStoreGuidanceView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/customer-service',
      name: 'student-ecommerce-customer-service',
      component: EcommerceCustomerServiceView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/ecommerce-training/courses',
      name: 'student-ecommerce-courses',
      component: EcommerceCoursesView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/handcraft-inheritance',
      name: 'student-handcraft-inheritance',
      component: HandcraftInheritanceHomeView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/handcraft-inheritance/crafts/:craftKey',
      name: 'student-handcraft-craft',
      component: HandcraftCraftView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/handcraft-inheritance/points',
      name: 'student-handcraft-points',
      component: HandcraftPointsView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/handcraft-inheritance/rewards',
      name: 'student-handcraft-rewards',
      component: HandcraftRewardsView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/handcraft-inheritance/courses',
      name: 'student-handcraft-courses',
      component: HandcraftCoursesView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment',
      name: 'student-employment',
      component: JobMatchingHomeView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/resume',
      name: 'student-employment-resume',
      component: ResumeEditorView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/skills',
      name: 'student-employment-skills',
      component: SkillProfileView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/jobs',
      name: 'student-employment-jobs',
      component: JobsView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/jobs/:jobId',
      name: 'student-employment-job-detail',
      component: JobDetailView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/applications',
      name: 'student-employment-applications',
      component: MyApplicationsView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/employment/favorites',
      name: 'student-employment-favorites',
      component: JobFavoritesView,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources',
      name: 'local-resources-home',
      component: lazyLocalResourceView('../views/LocalResourcesHomeView.vue'),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/dialect',
      name: 'local-resources-dialect',
      component: lazyLocalResourceView('../views/DialectAssistantView.vue'),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/cases',
      name: 'local-resources-cases',
      component: lazyLocalResourceView('../views/LocalResourceCasesView.vue'),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/cases/:caseId',
      name: 'local-resources-case-detail',
      component: lazyLocalResourceView(
        '../views/LocalResourceCaseDetailView.vue'
      ),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/policies',
      name: 'local-resources-policies',
      component: lazyLocalResourceView('../views/LocalResourcePoliciesView.vue'),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/policies/:policyId',
      name: 'local-resources-policy-detail',
      component: lazyLocalResourceView(
        '../views/LocalResourcePolicyDetailView.vue'
      ),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/news',
      name: 'local-resources-news',
      component: lazyLocalResourceView('../views/LocalResourceNewsView.vue'),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/student/local-resources/news/:newsId',
      name: 'local-resources-news-detail',
      component: lazyLocalResourceView(
        '../views/LocalResourceNewsDetailView.vue'
      ),
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/teacher',
      component: TeacherPortalView,
      meta: teacherMeta,
      children: [
        {
          path: '',
          name: 'teacher-portal',
          redirect: '/teacher/dashboard'
        },
        {
          path: 'courses',
          component: TeacherCoursesView,
          meta: teacherMeta
        },
        {
          path: 'announcements',
          component: TeacherAnnouncementsView,
          meta: teacherMeta
        },
        {
          path: 'interactions',
          component: TeacherInteractionsView,
          meta: teacherMeta
        },
        {
          path: 'dashboard',
          component: TeacherDashboardView,
          meta: teacherMeta
        }
      ]
    },
    {
      path: '/enterprise',
      name: 'enterprise-portal',
      component: EnterprisePortalView,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/enterprise/jobs',
      name: 'enterprise-jobs',
      component: EnterpriseJobsView,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/enterprise/applications',
      name: 'enterprise-applications',
      component: EnterpriseApplicationsView,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/enterprise/applications/:applicationId',
      name: 'enterprise-application-detail',
      component: EnterpriseApplicationDetailView,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/government',
      name: 'government-portal',
      component: GovernmentPortalView,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/government/policies',
      name: 'government-policies',
      component: GovernmentPolicyView,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/government/news',
      name: 'government-news',
      component: GovernmentNewsView,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/government/dashboard',
      name: 'government-dashboard',
      component: GovernmentDashboardView,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/admin',
      component: AdminPortalView,
      meta: adminMeta,
      children: [
        {
          path: '',
          name: 'admin-portal',
          redirect: '/admin/dashboard'
        },
        {
          path: 'dashboard',
          name: 'admin-dashboard',
          component: AdminDashboardView,
          meta: adminMeta
        },
        {
          path: 'review',
          name: 'admin-review',
          component: AdminReviewView,
          meta: adminMeta
        },
        {
          path: 'moderation',
          name: 'admin-moderation',
          component: AdminRoutePlaceholder,
          meta: adminMeta
        },
        {
          path: 'presets',
          name: 'admin-presets',
          component: AdminRoutePlaceholder,
          meta: adminMeta
        },
        {
          path: 'rewards',
          name: 'admin-rewards',
          component: AdminRewardsView,
          meta: adminMeta
        },
        {
          path: 'redemptions',
          name: 'admin-redemptions',
          component: AdminRedemptionsView,
          meta: adminMeta
        },
        {
          path: 'accounts',
          name: 'admin-accounts',
          component: AdminAccountsView,
          meta: superAdminMeta
        },
        {
          path: 'points-policy',
          name: 'admin-points-policy',
          component: AdminRoutePlaceholder,
          meta: adminMeta
        },
        {
          path: 'content',
          name: 'admin-content',
          component: AdminRoutePlaceholder,
          meta: adminMeta
        },
        {
          path: 'announcements',
          name: 'admin-announcements',
          component: AdminAnnouncementsView,
          meta: superAdminMeta
        }
      ]
    }
  ]
})

router.beforeEach(to => authGuard(to, useAuthStore()))

export default router
