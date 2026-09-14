import { defineStore } from 'pinia'

import { ApiError, apiFetch } from '@/api/client'
import type {
  ApiFieldErrors,
  AuthSessionResponse,
  AuthUser,
  RegisterResponse,
  UserRole
} from '@/api/types'
import { roleDefaultPath } from '@/router/roleRoutes'

export type { AuthUser } from '@/api/types'

interface LoginResponse {
  success: true
  user: AuthUser
  default_path: string
}

interface CompleteInterestTagsResponse {
  success: true
  user: AuthUser
  default_path: string
}

export interface RegisterPayload {
  username: string
  password: string
  confirm_password?: string
  name: string
  role: string
  phone?: string
  region?: string
  company_name?: string
}

type AuthSessionState = 'unknown' | 'anonymous' | 'pending' | 'active'

interface AuthState {
  user: AuthUser | null
  sessionState: AuthSessionState
  nextStep: 'interest-tags' | null
  defaultPath: string
  dialogOpen: boolean
  mode: 'login' | 'register'
  loading: boolean
  error: string
  fieldErrors: ApiFieldErrors
  notice: string
}

export const demoAccounts: Array<{
  label: string
  username: string
  password: string
  role: UserRole
}> = [
  { label: '学员', username: 'student_demo', password: '123456', role: 'student' },
  { label: '教师', username: 'teacher_demo', password: '123456', role: 'teacher' },
  {
    label: '企业',
    username: 'enterprise_demo',
    password: '123456',
    role: 'enterprise'
  },
  { label: '政府', username: 'gov_demo', password: '123456', role: 'government' },
  {
    label: '超管',
    username: 'admin_demo',
    password: 'admin123',
    role: 'super_admin'
  }
]

export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    user: null,
    sessionState: 'unknown',
    nextStep: null,
    defaultPath: '',
    dialogOpen: false,
    mode: 'login',
    loading: false,
    error: '',
    fieldErrors: {},
    notice: ''
  }),
  getters: {
    isAuthenticated(state): boolean {
      return state.sessionState === 'active' && Boolean(state.user)
    },
    isPendingRegistration(state): boolean {
      return state.sessionState === 'pending' && state.nextStep === 'interest-tags'
    },
    isSessionUnknown(state): boolean {
      return state.sessionState === 'unknown'
    }
  },
  actions: {
    clearSession() {
      this.user = null
      this.sessionState = 'anonymous'
      this.nextStep = null
      this.defaultPath = ''
    },
    captureError(error: unknown, fallback: string) {
      if (error instanceof ApiError) {
        this.error = error.message
        this.fieldErrors = error.errors
        return
      }

      this.error = error instanceof Error ? error.message : fallback
      this.fieldErrors = {}
    },
    async restoreSession(force = false) {
      if (!force && this.sessionState !== 'unknown') {
        return
      }

      this.loading = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const response = await apiFetch<AuthSessionResponse>('/api/auth/session')
        this.sessionState = response.state
        this.defaultPath = response.default_path
        this.nextStep = response.next_step ?? null
        this.user = response.state === 'active' ? response.user : null
      } catch (error) {
        this.clearSession()
        this.captureError(error, '会话恢复失败')
      } finally {
        this.loading = false
      }
    },
    openDialog(mode: 'login' | 'register' = 'login') {
      this.mode = mode
      this.dialogOpen = true
      this.error = ''
      this.fieldErrors = {}
      this.notice = ''
    },
    closeDialog() {
      this.dialogOpen = false
      this.error = ''
      this.fieldErrors = {}
      this.notice = ''
    },
    async login(username: string, password: string) {
      this.loading = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const response = await apiFetch<LoginResponse>('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password })
        })
        this.user = response.user
        this.sessionState = 'active'
        this.nextStep = null
        this.defaultPath = response.default_path
        this.notice = `已登录：${response.user.name}`
        this.dialogOpen = false
        return response
      } catch (error) {
        this.captureError(error, '登录失败')
        return null
      } finally {
        this.loading = false
      }
    },
    async register(payload: RegisterPayload) {
      this.loading = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const requestPayload = {
          ...payload,
          confirm_password: payload.confirm_password ?? payload.password
        }
        const response = await apiFetch<RegisterResponse>('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify(requestPayload)
        })
        if (response.next_step === 'interest-tags') {
          this.user = null
          this.sessionState = 'pending'
          this.nextStep = 'interest-tags'
          this.defaultPath = response.default_path || '/register/interest-tags'
        } else {
          this.user = response.user
          this.sessionState = 'active'
          this.nextStep = null
          this.defaultPath =
            response.default_path || roleDefaultPath(response.user.role)
        }
        this.notice = `注册成功：${response.user.name}`
        this.dialogOpen = false
        return response
      } catch (error) {
        this.captureError(error, '注册失败')
        return null
      } finally {
        this.loading = false
      }
    },
    async completeInterestTags(tagIds: number[]) {
      this.loading = true
      this.error = ''
      this.fieldErrors = {}

      try {
        const response = await apiFetch<CompleteInterestTagsResponse>(
          '/api/auth/interest-tags',
          {
            method: 'POST',
            body: JSON.stringify({ tag_ids: tagIds })
          }
        )
        this.user = response.user
        this.sessionState = 'active'
        this.nextStep = null
        this.defaultPath = response.default_path || roleDefaultPath(response.user.role)
        this.notice = '兴趣标签已保存'
        return response
      } catch (error) {
        this.captureError(error, '兴趣标签保存失败')
        return null
      } finally {
        this.loading = false
      }
    },
    async logout() {
      this.loading = true
      this.error = ''
      this.fieldErrors = {}

      try {
        await apiFetch('/api/auth/logout', {
          method: 'POST',
        })
      } catch (error) {
        this.captureError(error, '退出登录失败')
      } finally {
        this.clearSession()
        this.notice = '已退出登录'
        this.loading = false
      }
    }
  }
})
