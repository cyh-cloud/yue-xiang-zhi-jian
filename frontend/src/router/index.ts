import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import AgriCalendarView from '@/views/AgriCalendarView.vue'
import AgriCoursesView from '@/views/AgriCoursesView.vue'
import AgriDiagnosisView from '@/views/AgriDiagnosisView.vue'
import AgriQaView from '@/views/AgriQaView.vue'
import AgriSkillsHomeView from '@/views/AgriSkillsHomeView.vue'
import AdminPortalView from '@/views/AdminPortalView.vue'
import CourseCatalogView from '@/views/CourseCatalogView.vue'
import EnterprisePortalView from '@/views/EnterprisePortalView.vue'
import GovernmentPortalView from '@/views/GovernmentPortalView.vue'
import HomeView from '@/views/HomeView.vue'
import InterestTagsView from '@/views/InterestTagsView.vue'
import LoginView from '@/views/LoginView.vue'
import MessageCenterView from '@/views/MessageCenterView.vue'
import RegisterView from '@/views/RegisterView.vue'
import StudentPortalView from '@/views/StudentPortalView.vue'
import StudentProfileView from '@/views/StudentProfileView.vue'
import TeacherPortalView from '@/views/TeacherPortalView.vue'

import { authGuard } from './roleRoutes'

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
      path: '/teacher',
      name: 'teacher-portal',
      component: TeacherPortalView,
      meta: { requiresAuth: true, roles: ['teacher'] }
    },
    {
      path: '/enterprise',
      name: 'enterprise-portal',
      component: EnterprisePortalView,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/government',
      name: 'government-portal',
      component: GovernmentPortalView,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/admin',
      name: 'admin-portal',
      component: AdminPortalView,
      meta: { requiresAuth: true, roles: ['super_admin', 'admin'] }
    }
  ]
})

router.beforeEach(to => authGuard(to, useAuthStore()))

export default router
