<script setup lang="ts">
import {
  AlertCircle,
  Check,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import type { ResumePayload, StudentResume } from '@/api/types'
import ResumeSectionEditor from '@/components/ResumeSectionEditor.vue'
import { useJobMatchingStore } from '@/stores/jobMatching'

type ActionName = 'save' | 'optimize' | 'adopt' | 'discard'
type ResumeEntries = Array<Record<string, string>>

const AI_UNAVAILABLE_MESSAGE = 'AI 服务暂时不可用'

const educationFields = [
  { key: 'school', testKey: 'school', label: '学校', required: true },
  { key: 'major', testKey: 'major', label: '专业', required: true },
  { key: 'degree', testKey: 'degree', label: '学位' },
  {
    key: 'start_date',
    testKey: 'start',
    label: '开始时间',
    type: 'month' as const,
    required: true
  },
  {
    key: 'end_date',
    testKey: 'end',
    label: '结束时间',
    type: 'month' as const
  }
]

const workFields = [
  { key: 'company', testKey: 'company', label: '公司', required: true },
  { key: 'role', testKey: 'role', label: '职位', required: true },
  {
    key: 'start_date',
    testKey: 'start',
    label: '开始时间',
    type: 'month' as const,
    required: true
  },
  {
    key: 'end_date',
    testKey: 'end',
    label: '结束时间',
    type: 'month' as const
  },
  {
    key: 'description',
    testKey: 'description',
    label: '工作内容',
    type: 'textarea' as const,
    wide: true
  }
]

const store = useJobMatchingStore()
const educationEntries = ref<ResumeEntries>([])
const workEntries = ref<ResumeEntries>([])
const skills = ref<string[]>([])
const activeAction = ref<ActionName | null>(null)
const validationError = ref('')
const actionNotice = ref('')
const aiUnavailable = ref(false)

const busy = computed(() => store.saving || activeAction.value !== null)
const showPreview = computed(
  () => store.optimizationOffer?.status === 'offered'
)
const showAiUnavailable = computed(
  () =>
    aiUnavailable.value ||
    store.errorCode === 'ai_unavailable' ||
    store.error === AI_UNAVAILABLE_MESSAGE
)
const canOptimize = computed(
  () =>
    !busy.value &&
    Boolean(store.resume?.has_saved_resume && store.resume.version > 0)
)

function cloneEntries(entries: ResumeEntries): ResumeEntries {
  return entries.map(entry => ({ ...entry }))
}

function syncDraft(resume: StudentResume | null) {
  if (!resume) {
    return
  }
  educationEntries.value = cloneEntries(resume.education_experiences)
  workEntries.value = cloneEntries(resume.work_experiences)
  skills.value = [...resume.skills]
}

function addEducation() {
  educationEntries.value.push({
    school: '',
    major: '',
    degree: '',
    start_date: '',
    end_date: ''
  })
}

function addWork() {
  workEntries.value.push({
    company: '',
    role: '',
    start_date: '',
    end_date: '',
    description: ''
  })
}

function updateEducationField(
  index: number,
  key: string,
  value: string
) {
  const entry = educationEntries.value[index]
  if (entry) {
    entry[key] = value
  }
}

function updateWorkField(index: number, key: string, value: string) {
  const entry = workEntries.value[index]
  if (entry) {
    entry[key] = value
  }
}

function removeEntry(entries: ResumeEntries, index: number) {
  entries.splice(index, 1)
}

function addSkill() {
  skills.value.push('')
}

function updateSkill(index: number, value: string) {
  skills.value[index] = value
}

function removeSkill(index: number) {
  skills.value.splice(index, 1)
}

function hasStructuredContent(): boolean {
  return (
    educationEntries.value.some(entry =>
      Object.values(entry).some(value => value.trim())
    ) ||
    workEntries.value.some(entry =>
      Object.values(entry).some(value => value.trim())
    ) ||
    skills.value.some(skill => skill.trim())
  )
}

function resumePayload(): ResumePayload {
  return {
    education_experiences: cloneEntries(educationEntries.value),
    work_experiences: cloneEntries(workEntries.value),
    skills: [...skills.value]
  }
}

async function saveResume() {
  if (busy.value) {
    return
  }

  validationError.value = ''
  actionNotice.value = ''
  aiUnavailable.value = false

  if (!hasStructuredContent()) {
    validationError.value = '至少填写一个简历区块'
    return
  }

  activeAction.value = 'save'
  try {
    const saved = await store.saveResume({
      expected_version: store.resume?.version ?? 0,
      ...resumePayload()
    })
    if (saved) {
      syncDraft(saved)
      actionNotice.value = '简历已保存'
    }
  } finally {
    activeAction.value = null
  }
}

async function optimizeResume() {
  if (!canOptimize.value) {
    return
  }

  actionNotice.value = ''
  aiUnavailable.value = false
  activeAction.value = 'optimize'
  try {
    const offer = await store.optimizeResume(store.resume?.version ?? 0)
    if (
      !offer &&
      (store.errorCode === 'ai_unavailable' ||
        store.error === AI_UNAVAILABLE_MESSAGE)
    ) {
      aiUnavailable.value = true
    }
  } finally {
    activeAction.value = null
  }
}

async function adoptOptimization() {
  const offer = store.optimizationOffer
  const currentVersion = store.resume?.version
  if (
    busy.value ||
    !offer ||
    offer.rewritten_resume === null ||
    currentVersion === undefined
  ) {
    return
  }

  actionNotice.value = ''
  activeAction.value = 'adopt'
  try {
    const saved = await store.adoptOptimization(
      offer.offer_id,
      currentVersion
    )
    if (saved) {
      syncDraft(saved)
      actionNotice.value = '改写已采纳并保存'
    }
  } finally {
    activeAction.value = null
  }
}

async function discardOptimization() {
  const offer = store.optimizationOffer
  if (busy.value || !offer) {
    return
  }

  actionNotice.value = ''
  activeAction.value = 'discard'
  try {
    const discarded = await store.discardOptimization(offer.offer_id)
    if (discarded) {
      actionNotice.value = '已放弃本次改写'
    }
  } finally {
    activeAction.value = null
  }
}

watch(() => store.resume, syncDraft, { immediate: true })

onMounted(() => {
  if (!store.resume) {
    void store.loadResume()
  }
})
</script>

<template>
  <div class="resume-editor-page">
    <main class="resume-editor-main">
      <header class="resume-editor-heading">
        <div>
          <h1>我的简历</h1>
          <p>
            填写教育经历、工作经历和技能特长。保存后的版本可用于岗位投递。
          </p>
        </div>
        <div class="resume-editor-meta">
          <span>当前版本</span>
          <strong class="ark-data">{{ store.resume?.version ?? 0 }}</strong>
        </div>
      </header>

      <section
        v-if="store.loading && !store.resume"
        class="resume-editor-loading"
        data-test="resume-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="18" aria-hidden="true" />
        正在加载简历
      </section>

      <div
        v-else
        class="resume-editor-layout"
        :class="{ 'has-preview': showPreview }"
      >
        <form
          class="resume-editor-form"
          data-test="resume-form"
          novalidate
          :aria-busy="busy"
          @submit.prevent="saveResume"
        >
          <ResumeSectionEditor
            kind="education"
            title="教育经历"
            description="填写学校、专业和就读时间。结束时间留空表示仍在就读。"
            :entries="educationEntries"
            :fields="educationFields"
            :errors="store.fieldErrors"
            :disabled="busy"
            @add="addEducation"
            @remove="index => removeEntry(educationEntries, index)"
            @update-field="updateEducationField"
          />

          <ResumeSectionEditor
            kind="work"
            title="工作经历"
            description="填写公司、职位和任职时间。结束时间留空表示仍在职。"
            :entries="workEntries"
            :fields="workFields"
            :errors="store.fieldErrors"
            :disabled="busy"
            @add="addWork"
            @remove="index => removeEntry(workEntries, index)"
            @update-field="updateWorkField"
          />

          <section class="resume-editor-skills" aria-labelledby="skills-title">
            <header class="resume-editor-skills__heading">
              <div>
                <h2 id="skills-title">技能特长</h2>
                <p>逐项填写掌握的操作、工具或业务能力。</p>
              </div>
              <button
                class="resume-editor-skills__add"
                type="button"
                data-test="add-skill"
                :disabled="busy"
                @click="addSkill"
              >
                <Plus :size="16" aria-hidden="true" />
                添加技能
              </button>
            </header>

            <div v-if="skills.length" class="resume-editor-skills__list">
              <label
                v-for="(skill, index) in skills"
                :key="index"
                class="resume-editor-skills__row"
              >
                <span class="ark-sr-only">技能 {{ index + 1 }}</span>
                <input
                  data-test="resume-skill"
                  type="text"
                  :value="skill"
                  :disabled="busy"
                  :aria-invalid="store.fieldErrors.skills ? 'true' : undefined"
                  @input="
                    updateSkill(
                      index,
                      ($event.target as HTMLInputElement).value
                    )
                  "
                >
                <button
                  type="button"
                  :data-test="`remove-skill-${index}`"
                  :disabled="busy"
                  :aria-label="`删除第 ${index + 1} 项技能`"
                  @click="removeSkill(index)"
                >
                  <Trash2 :size="16" aria-hidden="true" />
                </button>
              </label>
            </div>
            <p v-else class="resume-editor-skills__empty">
              暂未添加技能特长。
            </p>
            <p
              v-if="store.fieldErrors.skills"
              class="resume-editor-skills__error"
              role="alert"
            >
              {{ store.fieldErrors.skills }}
            </p>
          </section>

          <footer class="resume-editor-form__footer">
            <div class="resume-editor-form__messages">
              <p
                v-if="validationError"
                class="resume-editor-message is-error"
                data-test="resume-empty-error"
                role="alert"
              >
                <AlertCircle :size="16" aria-hidden="true" />
                {{ validationError }}
              </p>
              <p
                v-if="showAiUnavailable"
                class="resume-editor-message is-error"
                data-test="ai-unavailable"
                role="alert"
              >
                {{ AI_UNAVAILABLE_MESSAGE }}
              </p>
              <p
                v-else-if="
                  store.error &&
                  !validationError &&
                  Object.keys(store.fieldErrors).length === 0
                "
                class="resume-editor-message is-error"
                role="alert"
              >
                <AlertCircle :size="16" aria-hidden="true" />
                {{ store.error }}
              </p>
              <p
                v-if="actionNotice"
                class="resume-editor-message is-success"
                role="status"
              >
                <Check :size="16" aria-hidden="true" />
                {{ actionNotice }}
              </p>
            </div>

            <div class="resume-editor-form__actions">
              <button
                type="button"
                data-test="optimize-resume"
                :disabled="!canOptimize"
                @click="optimizeResume"
              >
                <RefreshCw
                  v-if="activeAction === 'optimize'"
                  class="spinning"
                  :size="17"
                  aria-hidden="true"
                />
                <Sparkles v-else :size="17" aria-hidden="true" />
                AI 优化
              </button>
              <button
                class="resume-editor-form__save"
                type="submit"
                data-test="resume-save"
                :disabled="busy"
              >
                <RefreshCw
                  v-if="activeAction === 'save'"
                  class="spinning"
                  :size="17"
                  aria-hidden="true"
                />
                <Save v-else :size="17" aria-hidden="true" />
                保存简历
              </button>
            </div>
          </footer>
        </form>

        <aside
          v-if="showPreview && store.optimizationOffer"
          class="resume-optimization-preview"
          data-test="optimization-preview"
          aria-labelledby="optimization-preview-title"
        >
          <header class="resume-optimization-preview__heading">
            <div>
              <h2 id="optimization-preview-title">AI 优化预览</h2>
              <p>采纳前不会替换当前已保存的简历。</p>
            </div>
            <Sparkles :size="20" aria-hidden="true" />
          </header>

          <section
            class="resume-optimization-preview__section"
            aria-labelledby="optimization-suggestions-title"
          >
            <h3 id="optimization-suggestions-title">优化建议</h3>
            <ul>
              <li
                v-for="suggestion in store.optimizationOffer.suggestions"
                :key="suggestion"
              >
                {{ suggestion }}
              </li>
            </ul>
          </section>

          <template v-if="store.optimizationOffer.rewritten_resume">
            <section
              class="resume-optimization-preview__section"
              aria-labelledby="optimization-education-title"
            >
              <h3 id="optimization-education-title">改写后的教育经历</h3>
              <ul v-if="store.optimizationOffer.rewritten_resume.education_experiences.length">
                <li
                  v-for="(entry, index) in store.optimizationOffer
                    .rewritten_resume.education_experiences"
                  :key="index"
                >
                  <strong>{{ entry.school }}</strong>
                  <span>
                    {{ entry.major }} · {{ entry.degree }}
                  </span>
                  <small class="ark-data">
                    {{ entry.start_date }} 至 {{ entry.end_date || '在读' }}
                  </small>
                </li>
              </ul>
              <p v-else class="resume-optimization-preview__empty">
                未改写教育经历
              </p>
            </section>

            <section
              class="resume-optimization-preview__section"
              aria-labelledby="optimization-work-title"
            >
              <h3 id="optimization-work-title">改写后的工作经历</h3>
              <ul v-if="store.optimizationOffer.rewritten_resume.work_experiences.length">
                <li
                  v-for="(entry, index) in store.optimizationOffer
                    .rewritten_resume.work_experiences"
                  :key="index"
                >
                  <strong>{{ entry.company }}</strong>
                  <span>{{ entry.role }}</span>
                  <small class="ark-data">
                    {{ entry.start_date }} 至 {{ entry.end_date || '在职' }}
                  </small>
                  <p>{{ entry.description }}</p>
                </li>
              </ul>
              <p v-else class="resume-optimization-preview__empty">
                未改写工作经历
              </p>
            </section>

            <section
              class="resume-optimization-preview__section"
              aria-labelledby="optimization-skills-title"
            >
              <h3 id="optimization-skills-title">改写后的技能特长</h3>
              <ul
                v-if="store.optimizationOffer.rewritten_resume.skills.length"
                class="resume-optimization-preview__skills"
              >
                <li
                  v-for="skill in store.optimizationOffer.rewritten_resume.skills"
                  :key="skill"
                >
                  {{ skill }}
                </li>
              </ul>
              <p v-else class="resume-optimization-preview__empty">
                未改写技能特长
              </p>
            </section>

            <footer class="resume-optimization-preview__actions">
              <button
                class="is-primary"
                type="button"
                data-test="adopt-optimization"
                :disabled="busy"
                @click="adoptOptimization"
              >
                <RefreshCw
                  v-if="activeAction === 'adopt'"
                  class="spinning"
                  :size="16"
                  aria-hidden="true"
                />
                <Check v-else :size="16" aria-hidden="true" />
                采纳改写
              </button>
              <button
                type="button"
                data-test="discard-optimization"
                :disabled="busy"
                @click="discardOptimization"
              >
                <X :size="16" aria-hidden="true" />
                放弃
              </button>
            </footer>
          </template>

          <template v-else>
            <p class="resume-optimization-preview__notice">
              本次结果仅包含建议，不会替换当前简历。
            </p>
            <footer class="resume-optimization-preview__actions">
              <button
                type="button"
                data-test="discard-optimization"
                :disabled="busy"
                @click="discardOptimization"
              >
                <X :size="16" aria-hidden="true" />
                放弃
              </button>
            </footer>
          </template>
        </aside>
      </div>
    </main>
  </div>
</template>

<style scoped>
.resume-editor-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
  color: var(--ark-paper);
}

.resume-editor-main {
  width: min(100%, 1180px);
  min-width: 0;
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.resume-editor-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 24px;
  min-width: 0;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.resume-editor-heading h1 {
  min-width: 0;
  margin: 0;
  font-size: 3rem;
  line-height: 1.02;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: balance;
  word-break: normal;
}

.resume-editor-heading p {
  max-width: 66ch;
  margin: 12px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-meta {
  display: grid;
  min-width: 92px;
  gap: 3px;
  padding: 9px 11px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  text-align: right;
  word-break: normal;
}

.resume-editor-meta strong {
  color: var(--ark-signal);
  font-size: 1rem;
}

.resume-editor-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  min-width: 0;
  margin-top: 18px;
}

.resume-editor-layout.has-preview {
  grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
  align-items: start;
}

.resume-editor-form,
.resume-optimization-preview {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.resume-editor-skills {
  min-width: 0;
  padding: 22px;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.resume-editor-skills__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 16px;
}

.resume-editor-skills__heading h2 {
  min-width: 0;
  margin: 0;
  font-size: 1rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-skills__heading p {
  max-width: 66ch;
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-skills__add,
.resume-editor-form__actions button,
.resume-optimization-preview__actions button {
  display: inline-flex;
  min-width: 0;
  min-height: 42px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 13px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-skills__add {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.resume-editor-skills__add:hover,
.resume-editor-skills__add:focus-visible,
.resume-editor-form__actions button:hover:not(:disabled),
.resume-editor-form__actions button:focus-visible:not(:disabled),
.resume-optimization-preview__actions button:hover:not(:disabled),
.resume-optimization-preview__actions button:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.resume-editor-skills__list {
  display: grid;
  min-width: 0;
  gap: 8px;
  margin-top: 16px;
}

.resume-editor-skills__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  min-width: 0;
}

.resume-editor-skills__row input {
  width: 100%;
  min-width: 0;
  min-height: 42px;
  padding: 9px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.resume-editor-skills__row input[aria-invalid="true"] {
  border-color: var(--ark-signal);
}

.resume-editor-skills__row button {
  display: grid;
  width: 42px;
  min-width: 42px;
  min-height: 42px;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.resume-editor-skills__row button:hover,
.resume-editor-skills__row button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.resume-editor-skills__empty,
.resume-editor-skills__error {
  margin: 16px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-skills__empty {
  min-height: 76px;
  padding: 20px 12px;
  border: 1px dashed var(--ark-line-strong);
  background: var(--ark-surface-1);
  text-align: center;
}

.resume-editor-skills__error {
  color: var(--ark-signal);
}

.resume-editor-form__footer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: end;
  min-width: 0;
  padding: 18px 22px 22px;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.resume-editor-form__messages {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.resume-editor-message {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 7px;
  margin: 0;
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-editor-message svg {
  flex: 0 0 auto;
  margin-top: 3px;
}

.resume-editor-message.is-error {
  color: var(--ark-signal);
}

.resume-editor-message.is-success {
  color: var(--ark-state);
}

.resume-editor-form__actions {
  display: grid;
  grid-template-columns: minmax(138px, auto) minmax(128px, auto);
  gap: 8px;
}

.resume-editor-form__actions button {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.resume-editor-form__actions .resume-editor-form__save {
  border-color: var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.resume-editor-form__actions .resume-editor-form__save:hover:not(:disabled),
.resume-editor-form__actions
  .resume-editor-form__save:focus-visible:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.resume-optimization-preview {
  position: sticky;
  top: 18px;
  display: grid;
  gap: 0;
  max-height: calc(100svh - 36px);
  overflow-y: auto;
}

.resume-optimization-preview__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  padding: 16px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.resume-optimization-preview__heading h2 {
  min-width: 0;
  margin: 0;
  font-size: 1rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__heading p {
  margin: 5px 0 0;
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__heading svg {
  color: var(--ark-signal);
}

.resume-optimization-preview__section {
  min-width: 0;
  padding: 15px 16px;
  border-bottom: 1px solid var(--ark-line);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.resume-optimization-preview__section h3 {
  min-width: 0;
  margin: 0;
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__section ul {
  display: grid;
  min-width: 0;
  gap: 8px;
  margin: 10px 0 0;
  padding-left: 1.2rem;
}

.resume-optimization-preview__section li {
  min-width: 0;
  color: var(--ark-paper);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__section li strong,
.resume-optimization-preview__section li span,
.resume-optimization-preview__section li small {
  display: block;
  min-width: 0;
}

.resume-optimization-preview__section li span {
  margin-top: 2px;
  color: var(--ark-muted);
}

.resume-optimization-preview__section li small {
  margin-top: 3px;
  color: var(--ark-muted);
}

.resume-optimization-preview__section li p {
  margin: 6px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__skills {
  padding-left: 1.1rem;
}

.resume-optimization-preview__empty,
.resume-optimization-preview__notice {
  margin: 8px 0 0;
  color: var(--ark-muted);
  font-size: 0.76rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-optimization-preview__notice {
  margin: 0;
  padding: 15px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.resume-optimization-preview__actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 15px 16px 16px;
}

.resume-optimization-preview__actions button.is-primary {
  border-color: var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.resume-optimization-preview__actions button.is-primary:hover:not(:disabled),
.resume-optimization-preview__actions
  button.is-primary:focus-visible:not(:disabled) {
  background: var(--ark-surface-1);
  color: var(--ark-signal);
}

.resume-editor-loading {
  display: flex;
  min-height: 320px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 960px) {
  .resume-editor-layout.has-preview {
    grid-template-columns: minmax(0, 1fr);
  }

  .resume-optimization-preview {
    position: static;
    max-height: none;
  }
}

@media (max-width: 720px) {
  .resume-editor-main {
    padding: 28px 14px 48px;
  }

  .resume-editor-heading {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
    gap: 14px;
  }

  .resume-editor-heading h1 {
    font-size: 2.25rem;
  }

  .resume-editor-meta {
    min-width: 0;
    text-align: left;
  }

  .resume-editor-skills__heading,
  .resume-editor-form__footer {
    grid-template-columns: minmax(0, 1fr);
  }

  .resume-editor-skills__add,
  .resume-editor-form__actions button {
    width: 100%;
  }

  .resume-editor-form__actions {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 360px) {
  .resume-editor-main {
    padding-inline: 12px;
  }

  .resume-editor-skills {
    padding-inline: 14px;
  }

  .resume-editor-form__footer {
    padding-inline: 14px;
  }

  .resume-optimization-preview__actions {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
