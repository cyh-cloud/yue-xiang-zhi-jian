<script setup lang="ts">
import { ArrowLeft, Check, RefreshCw, Save } from 'lucide-vue-next'
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import { apiFetch } from '@/api/client'
import type {
  InterestTag,
  LearningDirection,
  StudentProfile
} from '@/api/types'
import AppHeader from '@/components/AppHeader.vue'
import FormField from '@/components/FormField.vue'
import { useAuthStore } from '@/stores/auth'
import { useStudentStore } from '@/stores/student'

interface TagsResponse {
  success: true
  tags: InterestTag[]
}

const directionOptions: Array<{
  value: LearningDirection
  label: string
}> = [
  { value: 'agriculture', label: '农业' },
  { value: 'ecommerce', label: '电商' },
  { value: 'handcraft', label: '手工' },
  { value: 'comprehensive', label: '综合' }
]

const tagGroups: Array<{
  key: InterestTag['group_key']
  label: string
}> = [
  { key: 'crop', label: '作物类目' },
  { key: 'skill', label: '技能兴趣' },
  { key: 'job', label: '岗位类别' }
]

const auth = useAuthStore()
const student = useStudentStore()
const router = useRouter()
const form = reactive<StudentProfile>({
  name: '',
  contact: '',
  learning_direction: 'comprehensive',
  tag_ids: []
})
const selectedTagIds = ref<number[]>([])
const tags = ref<InterestTag[]>([])
const loadingTags = ref(true)
const tagLoadError = ref('')
const saveNotice = ref('')
const nameField = ref<{ focus: () => void } | null>(null)
const directionFields = ref<HTMLInputElement[] | null>(null)

const groups = computed(() =>
  tagGroups.map(group => ({
    ...group,
    tags: tags.value.filter(tag => tag.group_key === group.key)
  }))
)

const loading = computed(
  () => student.loadingProfile || loadingTags.value
)

watch(
  () => student.profile,
  profile => {
    if (!profile) {
      return
    }

    Object.assign(form, profile)
    selectedTagIds.value = [...profile.tag_ids]
  },
  { immediate: true }
)

function clearFieldError(field: string) {
  if (student.fieldErrors[field]) {
    delete student.fieldErrors[field]
  }
  if (Object.keys(student.fieldErrors).length === 0) {
    student.error = ''
  }
}

async function loadTags() {
  loadingTags.value = true
  tagLoadError.value = ''

  try {
    const response = await apiFetch<TagsResponse>('/api/interest-tags')
    tags.value = response.tags
  } catch (error) {
    tagLoadError.value =
      error instanceof Error ? error.message : '兴趣标签加载失败'
  } finally {
    loadingTags.value = false
  }
}

async function loadPage() {
  saveNotice.value = ''
  await Promise.all([student.loadProfile(), loadTags()])
}

async function focusFirstInvalidField() {
  await nextTick()
  if (student.fieldErrors.name) {
    nameField.value?.focus()
    return
  }
  if (student.fieldErrors.learning_direction) {
    directionFields.value?.[0]?.focus()
  }
}

async function saveProfile() {
  if (student.savingProfile) {
    return
  }

  saveNotice.value = ''
  const saved = await student.saveProfile({
    ...form,
    tag_ids: [...selectedTagIds.value]
  })

  if (!saved) {
    await focusFirstInvalidField()
    return
  }

  Object.assign(form, saved)
  selectedTagIds.value = [...saved.tag_ids]
  if (auth.user) {
    auth.user = { ...auth.user, name: saved.name }
  }
  saveNotice.value = '个人资料已保存'
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <div class="profile-page">
    <AppHeader
      source="live"
      :loading="loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />

    <main class="profile-main">
      <RouterLink class="back-link" to="/student">
        <ArrowLeft :size="16" aria-hidden="true" />
        返回学员门户
      </RouterLink>

      <header class="profile-heading">
        <div>
          <h1>个人资料</h1>
          <p>维护姓名、联系方式、学习方向与兴趣标签。保存后的偏好用于课程聚合推荐。</p>
        </div>
        <span class="selected-count ark-data">
          {{ selectedTagIds.length }} 项兴趣
        </span>
      </header>

      <section v-if="student.loadingProfile && !student.profile" class="profile-loading">
        <span></span>
        <span></span>
        <span></span>
        <p class="ark-sr-only">正在加载个人资料</p>
      </section>

      <section v-else-if="student.error && !student.profile" class="load-error" role="alert">
        <p>{{ student.error }}</p>
        <button type="button" @click="loadPage">
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </section>

      <form v-else novalidate class="profile-form" @submit.prevent="saveProfile">
        <section class="form-section identity-fields" aria-labelledby="identity-title">
          <header>
            <h2 id="identity-title">身份信息</h2>
            <p>姓名用于当前会话与平台内展示。</p>
          </header>
          <div class="field-grid">
            <FormField
              id="profile-name"
              ref="nameField"
              v-model="form.name"
              label="姓名"
              autocomplete="name"
              :error="student.fieldErrors.name"
              required
              @update:model-value="clearFieldError('name')"
            />
            <FormField
              id="profile-contact"
              v-model="form.contact"
              label="联系方式"
              autocomplete="tel"
              :error="student.fieldErrors.contact"
              @update:model-value="clearFieldError('contact')"
            />
          </div>
        </section>

        <fieldset
          class="form-section direction-field"
          :class="{ invalid: student.fieldErrors.learning_direction }"
        >
          <legend>学习方向</legend>
          <p class="field-description">选择当前主要学习方向，或保留综合方向。</p>
          <div class="direction-options" role="radiogroup" aria-label="学习方向">
            <label
              v-for="(option, index) in directionOptions"
              :key="option.value"
              :class="{ selected: form.learning_direction === option.value }"
            >
              <input
                :id="`profile-direction-${option.value}`"
                ref="directionFields"
                v-model="form.learning_direction"
                type="radio"
                name="learning_direction"
                :value="option.value"
                :required="index === 0"
                @change="clearFieldError('learning_direction')"
              />
              <span>{{ option.label }}</span>
            </label>
          </div>
          <p
            v-if="student.fieldErrors.learning_direction"
            class="field-error"
            role="alert"
          >
            {{ student.fieldErrors.learning_direction }}
          </p>
        </fieldset>

        <section class="form-section tag-section" aria-labelledby="tags-title">
          <header>
            <h2 id="tags-title">兴趣标签</h2>
            <p>标签可多选，也可全部清空。</p>
          </header>

          <div v-if="loadingTags" class="tag-loading" role="status">
            正在加载兴趣标签
          </div>
          <div v-else-if="tagLoadError" class="tag-error" role="alert">
            <p>{{ tagLoadError }}</p>
            <button type="button" @click="loadTags">
              <RefreshCw :size="15" aria-hidden="true" />
              重新加载
            </button>
          </div>
          <div v-else class="tag-groups">
            <div v-for="group in groups" :key="group.key" class="tag-group">
              <header>
                <h3>{{ group.label }}</h3>
                <span class="ark-data">{{ group.tags.length }}</span>
              </header>
              <div v-if="group.tags.length" class="tag-options">
                <label v-for="tag in group.tags" :key="tag.id">
                  <input
                    v-model="selectedTagIds"
                    type="checkbox"
                    :value="tag.id"
                    @change="clearFieldError('tag_ids')"
                  />
                  <span>{{ tag.name }}</span>
                </label>
              </div>
              <p v-else class="group-empty">暂无标签</p>
            </div>
          </div>
          <p v-if="student.fieldErrors.tag_ids" class="field-error" role="alert">
            {{ student.fieldErrors.tag_ids }}
          </p>
        </section>

        <p
          v-if="student.error && Object.keys(student.fieldErrors).length === 0"
          class="save-error"
          role="alert"
        >
          {{ student.error }}
        </p>
        <p v-if="saveNotice" class="save-notice" role="status">
          <Check :size="16" aria-hidden="true" />
          {{ saveNotice }}
        </p>

        <footer class="form-actions">
          <p>保存后将立即更新当前会话姓名，并重新读取课程推荐。</p>
          <button type="submit" :disabled="student.savingProfile || loading">
            <Save :size="17" aria-hidden="true" />
            {{ student.savingProfile ? '正在保存' : '保存资料' }}
          </button>
        </footer>
      </form>
    </main>
  </div>
</template>

<style scoped>
.profile-page {
  min-height: 100svh;
  background:
    linear-gradient(rgb(244 246 246 / 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgb(244 246 246 / 0.028) 1px, transparent 1px),
    var(--ark-ink);
  background-size: 72px 72px;
}

.profile-main {
  width: min(100%, 1120px);
  margin-inline: auto;
  padding: 38px 24px 72px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  color: var(--ark-muted);
  font-size: 0.8rem;
  text-decoration: none;
}

.back-link:hover,
.back-link:focus-visible {
  color: var(--ark-signal);
}

.profile-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 24px;
  margin-top: 18px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.profile-heading h1 {
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
}

.profile-heading p {
  max-width: 66ch;
  margin: 14px 0 0;
  color: #c4cdcf;
}

.selected-count {
  flex: 0 0 auto;
  padding: 7px 9px;
  border: 1px solid var(--ark-line);
  color: var(--ark-signal);
  font-size: 0.78rem;
}

.profile-form {
  display: grid;
  margin-top: 22px;
  border: 1px solid var(--ark-line-strong);
  background: rgb(5 6 7 / 0.86);
}

.form-section {
  display: grid;
  grid-template-columns: minmax(180px, 0.24fr) minmax(0, 0.76fr);
  gap: 28px;
  min-width: 0;
  margin: 0;
  padding: 22px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
}

.form-section > header {
  align-self: start;
}

.form-section h2,
.direction-field legend {
  margin: 0;
  padding: 0;
  color: var(--ark-paper);
  font-size: 1rem;
  font-weight: 700;
}

.form-section header p,
.field-description {
  margin: 7px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-height: 1.55;
}

.identity-fields {
  align-items: start;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.direction-field {
  grid-template-columns: minmax(180px, 0.24fr) minmax(0, 0.76fr);
}

.direction-field legend {
  grid-column: 1;
}

.direction-field .field-description {
  grid-column: 1;
}

.direction-options {
  display: grid;
  grid-column: 2;
  grid-row: 1 / span 2;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  align-self: start;
  border: 1px solid var(--ark-line);
  background: var(--ark-line);
}

.direction-options label {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 46px;
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.86rem;
}

.direction-options input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.direction-options label.selected {
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-signal);
  box-shadow: inset 0 -2px 0 var(--ark-signal);
}

.direction-options label:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.direction-field > .field-error {
  grid-column: 2;
}

.tag-section > header {
  align-self: start;
}

.tag-loading,
.tag-error {
  min-height: 166px;
  display: grid;
  place-items: center;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.82rem;
}

.tag-error {
  align-content: center;
  gap: 12px;
  color: #ff9c9c;
}

.tag-error p {
  margin: 0;
}

.tag-error button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

.tag-groups {
  border: 1px solid var(--ark-line);
}

.tag-group {
  display: grid;
  grid-template-columns: minmax(110px, 0.22fr) minmax(0, 0.78fr);
  gap: 18px;
  padding: 16px;
  border-bottom: 1px solid var(--ark-line);
}

.tag-group:last-child {
  border-bottom: 0;
}

.tag-group header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.tag-group h3 {
  margin: 0;
  font-size: 0.86rem;
}

.tag-group header span {
  color: var(--ark-muted);
  font-size: 0.7rem;
}

.tag-options {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.tag-options label {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.tag-options input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
}

.tag-options span {
  padding: 6px 9px;
  font-size: 0.78rem;
}

.tag-options label:has(input:checked) {
  border-color: var(--ark-signal);
  background: rgb(24 209 255 / 0.1);
  color: var(--ark-paper);
}

.tag-options label:focus-within {
  outline: 2px solid var(--ark-focus);
  outline-offset: 2px;
}

.group-empty {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.field-error {
  margin: 8px 0 0;
  color: #ff9c9c;
  font-size: 0.76rem;
}

.tag-section > .field-error {
  grid-column: 2;
}

.invalid .direction-options {
  border-color: rgb(255 138 138 / 0.62);
}

.save-error,
.save-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 22px 18px;
  padding: 10px 11px;
  font-size: 0.8rem;
}

.save-error {
  border: 1px solid rgb(255 138 138 / 0.44);
  background: rgb(255 138 138 / 0.08);
  color: #ff9c9c;
}

.save-notice {
  border: 1px solid rgb(200 235 33 / 0.42);
  color: var(--ark-state);
}

.form-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 22px 20px;
}

.form-actions p {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.form-actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 46px;
  padding: 0 18px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-signal);
  white-space: nowrap;
}

.form-actions button:hover:not(:disabled) {
  background: rgb(24 209 255 / 0.12);
}

.profile-loading,
.load-error {
  min-height: 360px;
  margin-top: 22px;
  border: 1px solid var(--ark-line-strong);
  background: rgb(5 6 7 / 0.84);
}

.profile-loading {
  display: grid;
  align-content: start;
  gap: 18px;
  padding: 26px;
}

.profile-loading span {
  display: block;
  height: 46px;
  border: 1px solid var(--ark-line);
  background: rgb(244 246 246 / 0.06);
}

.profile-loading span:nth-child(2) {
  width: 78%;
}

.profile-loading span:nth-child(3) {
  width: 58%;
}

.load-error {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 14px;
}

.load-error p {
  margin: 0;
  color: #ff9c9c;
}

.load-error button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
}

@media (max-width: 760px) {
  .profile-main {
    padding: 28px 14px 48px;
  }

  .profile-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .profile-heading h1 {
    font-size: 2.25rem;
  }

  .form-section,
  .direction-field {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .direction-field legend,
  .direction-field .field-description,
  .direction-options,
  .direction-field > .field-error,
  .tag-section > .field-error {
    grid-column: 1;
    grid-row: auto;
  }

  .direction-options {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .field-grid {
    grid-template-columns: 1fr;
  }

  .tag-group {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .form-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
