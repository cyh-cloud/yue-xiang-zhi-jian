import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import HomeView from '@/views/HomeView.vue'

import { authGuard } from './roleRoutes'

const RoutePlaceholder = { render: () => null }

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
      component: RoutePlaceholder
    },
    {
      path: '/register',
      name: 'register',
      component: RoutePlaceholder
    },
    {
      path: '/register/interest-tags',
      name: 'interest-tags',
      component: RoutePlaceholder
    },
    {
      path: '/student',
      name: 'student-portal',
      component: RoutePlaceholder,
      meta: { requiresAuth: true, roles: ['student'] }
    },
    {
      path: '/teacher',
      name: 'teacher-portal',
      component: RoutePlaceholder,
      meta: { requiresAuth: true, roles: ['teacher'] }
    },
    {
      path: '/enterprise',
      name: 'enterprise-portal',
      component: RoutePlaceholder,
      meta: { requiresAuth: true, roles: ['enterprise'] }
    },
    {
      path: '/government',
      name: 'government-portal',
      component: RoutePlaceholder,
      meta: { requiresAuth: true, roles: ['government'] }
    },
    {
      path: '/admin',
      name: 'admin-portal',
      component: RoutePlaceholder,
      meta: { requiresAuth: true, roles: ['super_admin', 'admin'] }
    }
  ]
})

router.beforeEach(to => authGuard(to, useAuthStore()))

export default router
