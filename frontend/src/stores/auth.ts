import { defineStore } from 'pinia'

import { apiFetch } from '@/api/client'

export interface AuthUser {
  id: string
  name: string
  role: string
  region?: string
  company_name?: string
}

interface LoginResponse {
  success: true
  session_id: string
  user: AuthUser
}

interface AuthState {
  user: AuthUser | null
  sessionId: string
  dialogOpen: boolean
  mode: 'login' | 'register'
  loading: boolean
  error: string
  notice: string
}

const storageKey = 'yuexiang.auth.session'

export const demoAccounts = [
  { label: '学员', username: 'student_demo', password: '123456', role: 'student' },
  { label: '教师', username: 'teacher_demo', password: '123456', role: 'teacher' },
  { label: '企业', username: 'enterprise_demo', password: '123456', role: 'enterprise' },
  { label: '政府', username: 'gov_demo', password: '123456', role: 'government' },
  { label: '超管', username: 'admin_demo', password: 'admin123', role: 'super_admin' }
]

function readStoredSession(): { sessionId: string; user: AuthUser | null } {
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (!raw) {
      return { sessionId: '', user: null }
    }

    const parsed = JSON.parse(raw) as { sessionId?: string; user?: AuthUser }
    return {
      sessionId: parsed.sessionId ?? '',
      user: parsed.user ?? null
    }
  } catch {
    return { sessionId: '', user: null }
  }
}

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => {
    const stored = readStoredSession()
    return {
      user: stored.user,
      sessionId: stored.sessionId,
      dialogOpen: false,
      mode: 'login',
      loading: false,
      error: '',
      notice: ''
    }
  },
  getters: {
    isAuthenticated(state): boolean {
      return Boolean(state.sessionId && state.user)
    }
  },
  actions: {
    persist() {
      window.localStorage.setItem(
        storageKey,
        JSON.stringify({ sessionId: this.sessionId, user: this.user })
      )
    },
    openDialog(mode: 'login' | 'register' = 'login') {
      this.mode = mode
      this.dialogOpen = true
      this.error = ''
      this.notice = ''
    },
    closeDialog() {
      this.dialogOpen = false
      this.error = ''
      this.notice = ''
    },
    async login(username: string, password: string) {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<LoginResponse>('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password })
        })
        this.sessionId = response.session_id
        this.user = response.user
        this.persist()
        this.notice = `已登录：${response.user.name}`
        this.dialogOpen = false
      } catch (error) {
        this.error = error instanceof Error ? error.message : '登录失败'
      } finally {
        this.loading = false
      }
    },
    async register(payload: {
      username: string
      password: string
      name: string
      role: string
      phone?: string
      region?: string
      company_name?: string
    }) {
      this.loading = true
      this.error = ''

      try {
        const response = await apiFetch<LoginResponse>('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify(payload)
        })
        this.sessionId = response.session_id
        this.user = response.user
        this.persist()
        this.notice = `注册成功：${response.user.name}`
        this.dialogOpen = false
      } catch (error) {
        this.error = error instanceof Error ? error.message : '注册失败'
      } finally {
        this.loading = false
      }
    },
    async logout() {
      if (!this.sessionId) {
        this.user = null
        this.sessionId = ''
        window.localStorage.removeItem(storageKey)
        return
      }

      this.loading = true
      try {
        await apiFetch('/api/auth/logout', {
          method: 'POST',
          body: JSON.stringify({ session_id: this.sessionId }),
          sessionId: this.sessionId
        })
      } catch {
        // 本地会话仍然清除，避免把用户锁在失效状态里。
      } finally {
        this.user = null
        this.sessionId = ''
        this.notice = '已退出登录'
        window.localStorage.removeItem(storageKey)
        this.loading = false
      }
    }
  }
})
