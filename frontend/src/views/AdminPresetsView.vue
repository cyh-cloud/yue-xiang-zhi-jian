<script setup lang="ts">
import {
  Check,
  Inbox,
  Library,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  X
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'

import type {
  AdminAgriCalendarPreset,
  AdminAgriProductPreset,
  AdminAssistantKnowledgePreset,
  AdminCraftMaterialGuide,
  AdminCraftPresetStep,
  AdminHandcraftCraftPreset,
  AdminPestKnowledgePreset,
  AdminPresetCategory,
  AdminPresetItem,
  AdminPresetPayload,
  AdminSuccessCasePreset
} from '@/stores/adminConsole'
import { useAdminConsoleStore } from '@/stores/adminConsole'

interface PresetCategoryDefinition {
  id: AdminPresetCategory
  label: string
  title: string
  itemNoun: string
  stableLabel: string
}

type PresetTextListKey =
  | 'tasks'
  | 'management'
  | 'solarTerms'
  | 'productNames'
  | 'symptoms'
  | 'aliases'

interface PresetTextListField {
  key: PresetTextListKey
  field: string
  label: string
}

interface PresetFormState {
  stableId: string
  name: string
  title: string
  sortOrder: string
  enabled: boolean
  productKey: string
  month: string
  tasks: string[]
  management: string[]
  solarTerms: string[]
  reminder: string
  pestName: string
  productNames: string[]
  symptoms: string[]
  aliases: string[]
  answer: string
  introduction: string
  sourceAvailable: boolean
  steps: AdminCraftPresetStep[]
  materialGuide: AdminCraftMaterialGuide[]
  summary: string
  background: string
  journey: string
  lessons: string
  publishedAt: string
  body: string
  featureKey: string
  jumpTarget: string
}

// The ten feature keys the assistant knowledge endpoint accepts. The backend
// is the authority, so an unknown key is answered with its own message
// instead of being silently dropped here.
const assistantFeatureOptions: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'agri_skills', label: '农技学堂' },
  { value: 'ai_companion', label: 'AI 助手' },
  { value: 'course_catalog', label: '课程目录' },
  { value: 'ecommerce_training', label: '电商实训' },
  { value: 'handcraft_inheritance', label: '非遗传承' },
  { value: 'job_matching', label: '岗位匹配' },
  { value: 'local_resources', label: '本土资源' },
  { value: 'message_center', label: '消息中心' },
  { value: 'points_mall', label: '积分商城' },
  { value: 'student_profile', label: '学员档案' }
]

const categories: ReadonlyArray<PresetCategoryDefinition> = [
  {
    id: 'agri_products',
    label: '农产品',
    title: '农产品列表',
    itemNoun: '农产品',
    stableLabel: '农产品稳定 ID'
  },
  {
    id: 'agri_calendar',
    label: '农时月历',
    title: '农时条目',
    itemNoun: '农时条目',
    stableLabel: '条目 ID'
  },
  {
    id: 'pest_knowledge',
    label: '病虫害',
    title: '病虫害知识',
    itemNoun: '病虫害条目',
    stableLabel: '条目稳定 ID'
  },
  {
    id: 'handcraft_crafts',
    label: '非遗技艺',
    title: '技艺内容',
    itemNoun: '技艺内容',
    stableLabel: '技艺键'
  },
  {
    id: 'success_cases',
    label: '成功案例',
    title: '成功案例',
    itemNoun: '成功案例',
    stableLabel: '案例稳定 ID'
  },
  {
    id: 'assistant_knowledge',
    label: '助手知识',
    title: '助手知识',
    itemNoun: '知识条目',
    stableLabel: '条目稳定 ID'
  }
]

const store = useAdminConsoleStore()
const activeCategory = computed<AdminPresetCategory>(() => store.presetCategory)
const activeDefinition = computed(
  () => categories.find(item => item.id === activeCategory.value) ?? categories[0]
)
const editingId = ref<string | null>(null)
const editingVersion = ref<number | null>(null)
const editingDemo = ref(false)
const actionMessage = ref('')
const deleteCandidate = ref<{ id: string; label: string; version: number } | null>(
  null
)

function emptyForm(): PresetFormState {
  return {
    stableId: '',
    name: '',
    title: '',
    sortOrder: '0',
    enabled: true,
    productKey: '',
    month: '1',
    tasks: [''],
    management: [''],
    solarTerms: [''],
    reminder: '',
    pestName: '',
    productNames: [''],
    symptoms: [''],
    aliases: [''],
    answer: '',
    introduction: '',
    sourceAvailable: true,
    steps: [],
    materialGuide: [],
    summary: '',
    background: '',
    journey: '',
    lessons: '',
    publishedAt: '',
    body: '',
    featureKey: assistantFeatureOptions[0]?.value ?? 'agri_skills',
    jumpTarget: ''
  }
}

const form = ref<PresetFormState>(emptyForm())

// One category is loaded at a time, so each list is the rows of the open tab
// and every other shape filters out to nothing.
function isAgriProductPreset(
  item: AdminPresetItem
): item is AdminAgriProductPreset {
  // A calendar row also carries `product_key`, so the shape test has to rule
  // the calendar out or a calendar row would be edited as a product.
  return 'product_key' in item && !('month' in item)
}

function isAgriCalendarPreset(
  item: AdminPresetItem
): item is AdminAgriCalendarPreset {
  return 'month' in item
}

function isPestKnowledgePreset(
  item: AdminPresetItem
): item is AdminPestKnowledgePreset {
  return 'pest_name' in item
}

function isHandcraftCraftPreset(
  item: AdminPresetItem
): item is AdminHandcraftCraftPreset {
  return 'craft_key' in item
}

function isSuccessCasePreset(
  item: AdminPresetItem
): item is AdminSuccessCasePreset {
  return 'id' in item
}

function isAssistantKnowledgePreset(
  item: AdminPresetItem
): item is AdminAssistantKnowledgePreset {
  return 'knowledge_id' in item
}

const productItems = computed(() =>
  store.presetItems.filter(isAgriProductPreset)
)
const calendarItems = computed(() =>
  store.presetItems.filter(isAgriCalendarPreset)
)
const pestItems = computed(() => store.presetItems.filter(isPestKnowledgePreset))
const craftItems = computed(() =>
  store.presetItems.filter(isHandcraftCraftPreset)
)
const caseItems = computed(() => store.presetItems.filter(isSuccessCasePreset))
const knowledgeItems = computed(() =>
  store.presetItems.filter(isAssistantKnowledgePreset)
)

const categoryTextLists = computed<ReadonlyArray<PresetTextListField>>(() => {
  if (activeCategory.value === 'agri_calendar') {
    return [
      { key: 'tasks', field: 'tasks', label: '农事任务' },
      { key: 'management', field: 'management', label: '管理要点' },
      { key: 'solarTerms', field: 'solar-terms', label: '节气' }
    ]
  }
  if (activeCategory.value === 'pest_knowledge') {
    return [
      { key: 'productNames', field: 'product-names', label: '关联农产品' },
      { key: 'symptoms', field: 'symptoms', label: '症状表现' },
      { key: 'aliases', field: 'aliases', label: '别名' }
    ]
  }
  return []
})

const isEditing = computed(() => editingId.value !== null)
const canSubmit = computed(() => form.value.stableId.trim().length > 0)

function presetItemId(item: AdminPresetItem): string {
  if (isAgriProductPreset(item)) return item.product_key
  if (isAgriCalendarPreset(item)) return item.item_id
  if (isPestKnowledgePreset(item)) return item.item_id
  if (isHandcraftCraftPreset(item)) return item.craft_key
  if (isSuccessCasePreset(item)) return item.id
  return item.knowledge_id
}

function presetItemLabel(item: AdminPresetItem): string {
  if (isAgriProductPreset(item)) return item.name
  if (isAgriCalendarPreset(item)) return `${item.product_key} ${item.month} 月`
  if (isPestKnowledgePreset(item)) return item.pest_name
  if (isHandcraftCraftPreset(item)) return item.name
  if (isSuccessCasePreset(item)) return item.title
  return item.title
}

function listValues(key: PresetTextListKey): string[] {
  switch (key) {
    case 'tasks':
      return form.value.tasks
    case 'management':
      return form.value.management
    case 'solarTerms':
      return form.value.solarTerms
    case 'productNames':
      return form.value.productNames
    case 'symptoms':
      return form.value.symptoms
    default:
      return form.value.aliases
  }
}

function setListValues(key: PresetTextListKey, values: string[]): void {
  switch (key) {
    case 'tasks':
      form.value.tasks = values
      return
    case 'management':
      form.value.management = values
      return
    case 'solarTerms':
      form.value.solarTerms = values
      return
    case 'productNames':
      form.value.productNames = values
      return
    case 'symptoms':
      form.value.symptoms = values
      return
    default:
      form.value.aliases = values
  }
}

function addListRow(key: PresetTextListKey): void {
  setListValues(key, [...listValues(key), ''])
}

// A list never collapses to zero rows: one empty row keeps the control
// reachable, and blank rows are dropped when the payload is built.
function removeListRow(key: PresetTextListKey, index: number): void {
  const next = listValues(key).filter((_, position) => position !== index)
  setListValues(key, next.length > 0 ? next : [''])
}

function setListRow(key: PresetTextListKey, index: number, value: string): void {
  const next = [...listValues(key)]
  next[index] = value
  setListValues(key, next)
}

function addStep(): void {
  form.value.steps = [
    ...form.value.steps,
    {
      step_no: form.value.steps.length + 1,
      step_key: '',
      title: '',
      description: '',
      tips: ['']
    }
  ]
}

function removeStep(index: number): void {
  form.value.steps = form.value.steps.filter(
    (_, position) => position !== index
  )
}

function addStepTip(index: number): void {
  form.value.steps = form.value.steps.map((step, position) =>
    position === index ? { ...step, tips: [...step.tips, ''] } : step
  )
}

function removeStepTip(index: number, tipIndex: number): void {
  form.value.steps = form.value.steps.map((step, position) => {
    if (position !== index) return step
    const tips = step.tips.filter((_, spot) => spot !== tipIndex)
    return { ...step, tips: tips.length > 0 ? tips : [''] }
  })
}

function setStepTip(index: number, tipIndex: number, value: string): void {
  form.value.steps = form.value.steps.map((step, position) => {
    if (position !== index) return step
    const tips = [...step.tips]
    tips[tipIndex] = value
    return { ...step, tips }
  })
}

function addMaterial(): void {
  form.value.materialGuide = [
    ...form.value.materialGuide,
    {
      name: '',
      reference_price: '',
      purchase_channel: '',
      precautions: '',
      taobao_keyword: ''
    }
  ]
}

function removeMaterial(index: number): void {
  form.value.materialGuide = form.value.materialGuide.filter(
    (_, position) => position !== index
  )
}

function setStepNumber(index: number, raw: string): void {
  const value = normalizeInteger(raw)
  form.value.steps = form.value.steps.map((step, position) =>
    position === index ? { ...step, step_no: value ?? step.step_no } : step
  )
}

function featureLabel(key: string): string {
  return (
    assistantFeatureOptions.find(option => option.value === key)?.label ?? key
  )
}

function formatTime(value: string | null): string {
  if (!value) return '时间未知'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}

// The backend only accepts timezone-aware ISO 8601 stamps, so a
// `datetime-local` value is widened into the platform offset on the way out.
function toDateTimeLocal(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23'
    })
      .formatToParts(date)
      .filter(part => part.type !== 'literal')
      .map(part => [part.type, part.value])
  )
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`
}

function toPlatformStamp(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''
  if (trimmed.endsWith('Z') || /[+-]\d{2}:\d{2}$/.test(trimmed)) return trimmed
  return `${trimmed}:00+08:00`
}

function normalizeInteger(raw: string): number | undefined {
  const trimmed = raw.trim()
  if (!trimmed) return undefined
  const value = Number(trimmed)
  return Number.isInteger(value) ? value : undefined
}

// Blank rows are the editor's idle state, not content: they are dropped here
// so an untouched row never trips the backend's "cannot contain empty" rule.
function cleanedList(values: string[]): string[] {
  return values.map(value => value.trim()).filter(value => value.length > 0)
}

function resetForm(): void {
  editingId.value = null
  editingVersion.value = null
  editingDemo.value = false
  form.value = emptyForm()
}

function selectTab(id: AdminPresetCategory): void {
  if (id === activeCategory.value) return
  actionMessage.value = ''
  resetForm()
  closeDialogs()
  store.clearPresetsError()
  store.clearPresetFormError()
  void store.loadPresets(id)
}

function startCreate(): void {
  store.clearPresetFormError()
  store.clearPresetsError()
  actionMessage.value = ''
  resetForm()
}

function startEdit(item: AdminPresetItem): void {
  store.clearPresetFormError()
  store.clearPresetsError()
  actionMessage.value = ''
  editingId.value = presetItemId(item)
  editingVersion.value = item.version
  const next = emptyForm()
  next.enabled = item.is_enabled
  next.sortOrder = String(item.sort_order)
  if (isAgriProductPreset(item)) {
    next.stableId = item.product_key
    next.name = item.name
  } else if (isAgriCalendarPreset(item)) {
    next.stableId = item.item_id
    next.productKey = item.product_key
    next.month = String(item.month)
    next.tasks = listOrRow(item.tasks)
    next.management = listOrRow(item.management)
    next.solarTerms = listOrRow(item.solar_terms)
    next.reminder = item.reminder
  } else if (isPestKnowledgePreset(item)) {
    next.stableId = item.item_id
    next.pestName = item.pest_name
    next.productNames = listOrRow(item.product_names)
    next.symptoms = listOrRow(item.symptoms)
    next.aliases = listOrRow(item.aliases)
    next.answer = item.answer
  } else if (isHandcraftCraftPreset(item)) {
    next.stableId = item.craft_key
    next.name = item.name
    next.introduction = item.introduction
    next.sourceAvailable = item.source_available
    next.steps = item.steps.map(step => ({ ...step, tips: [...step.tips] }))
    next.materialGuide = item.material_guide.map(material => ({ ...material }))
    editingDemo.value = false
  } else if (isSuccessCasePreset(item)) {
    next.stableId = item.id
    next.title = item.title
    next.summary = item.summary
    next.background = item.background
    next.journey = item.journey
    next.lessons = item.lessons
    next.publishedAt = toDateTimeLocal(item.published_at)
    editingDemo.value = item.is_demo
  } else {
    next.stableId = item.knowledge_id
    next.title = item.title
    next.body = item.body
    next.featureKey = item.feature_key
    next.jumpTarget = item.jump_target
  }
  form.value = next
}

function listOrRow(values: string[]): string[] {
  return values.length > 0 ? [...values] : ['']
}

function buildPayload(expectedVersion?: number): AdminPresetPayload {
  const version =
    expectedVersion === undefined ? {} : { expected_version: expectedVersion }
  const sortOrder = normalizeInteger(form.value.sortOrder)
  const enabled = form.value.enabled
  switch (activeCategory.value) {
    case 'agri_products':
      return {
        product_key: form.value.stableId.trim(),
        name: form.value.name.trim(),
        sort_order: sortOrder,
        is_enabled: enabled,
        ...version
      }
    case 'agri_calendar':
      return {
        product_key: form.value.productKey.trim(),
        month: normalizeInteger(form.value.month),
        tasks: cleanedList(form.value.tasks),
        management: cleanedList(form.value.management),
        solar_terms: cleanedList(form.value.solarTerms),
        reminder: form.value.reminder.trim(),
        sort_order: sortOrder,
        is_enabled: enabled,
        ...version
      }
    case 'pest_knowledge':
      return {
        item_id: form.value.stableId.trim(),
        sort_order: sortOrder,
        pest_name: form.value.pestName.trim(),
        product_names: cleanedList(form.value.productNames),
        symptoms: cleanedList(form.value.symptoms),
        aliases: cleanedList(form.value.aliases),
        answer: form.value.answer.trim(),
        is_enabled: enabled,
        ...version
      }
    case 'handcraft_crafts':
      return {
        craft_key: form.value.stableId.trim(),
        name: form.value.name.trim(),
        introduction: form.value.introduction.trim(),
        steps: form.value.steps.map(step => ({
          step_no: step.step_no,
          step_key: step.step_key.trim(),
          title: step.title.trim(),
          description: step.description.trim(),
          tips: cleanedList(step.tips)
        })),
        material_guide: form.value.materialGuide.map(material => ({
          name: material.name.trim(),
          reference_price: material.reference_price.trim(),
          purchase_channel: material.purchase_channel.trim(),
          precautions: material.precautions.trim(),
          taobao_keyword: material.taobao_keyword.trim()
        })),
        source_available: form.value.sourceAvailable,
        sort_order: sortOrder,
        is_enabled: enabled,
        ...version
      }
    case 'success_cases':
      return {
        case_id: form.value.stableId.trim(),
        title: form.value.title.trim(),
        summary: form.value.summary.trim(),
        background: form.value.background.trim(),
        journey: form.value.journey.trim(),
        lessons: form.value.lessons.trim(),
        sort_order: sortOrder,
        published_at: toPlatformStamp(form.value.publishedAt),
        is_enabled: enabled,
        ...version
      }
    default:
      return {
        knowledge_id: form.value.stableId.trim(),
        title: form.value.title.trim(),
        body: form.value.body.trim(),
        feature_key: form.value.featureKey,
        jump_target: form.value.jumpTarget.trim(),
        sort_order: sortOrder,
        is_enabled: enabled,
        ...version
      }
  }
}

async function submitForm(): Promise<void> {
  if (!canSubmit.value) return
  const editing = editingId.value
  const saved =
    editing === null
      ? await store.createPreset(activeCategory.value, buildPayload())
      : await store.updatePreset(
          activeCategory.value,
          editing,
          buildPayload(editingVersion.value ?? 1)
        )
  if (saved === null) return
  actionMessage.value =
    editing === null
      ? `已创建${activeDefinition.value.itemNoun}「${presetItemId(saved)}」`
      : `已保存${activeDefinition.value.itemNoun}「${editing}」`
  resetForm()
}

// After a 409 the store has already reloaded the list, so the edit form
// re-seeds its expected version from the refreshed row and keeps the typed
// values. A row that vanished from the list closes the form instead.
async function resyncEditingVersion(): Promise<void> {
  const editing = editingId.value
  if (editing === null) return
  const done = await store.loadPresets(activeCategory.value)
  if (!done) return
  const fresh = store.presetItems.find(item => presetItemId(item) === editing)
  if (fresh) {
    editingVersion.value = fresh.version
    // The operator has now adopted the server's version, so the conflict
    // banner that asked for this reload is no longer the current state.
    store.clearPresetFormError()
    return
  }
  resetForm()
}

function openDelete(item: AdminPresetItem): void {
  actionMessage.value = ''
  store.clearPresetsError()
  deleteCandidate.value = {
    id: presetItemId(item),
    label: presetItemLabel(item),
    version: item.version
  }
}

function closeDialogs(): void {
  deleteCandidate.value = null
}

async function confirmDelete(): Promise<void> {
  const candidate = deleteCandidate.value
  if (candidate === null) return
  const disabled = await store.disablePreset(
    activeCategory.value,
    candidate.id,
    candidate.version
  )
  // The dialog closes either way: a failed stop leaves the row in the list
  // with the server's version, so a version that no longer matches would only
  // invite a second failing submit from a stale confirmation.
  closeDialogs()
  if (disabled === null) return
  actionMessage.value = `已停用${activeDefinition.value.itemNoun}「${candidate.label}」，该条目已停止对用户端可见，稳定 ID 仍保留`
}

onMounted(() => {
  void store.loadPresets(activeCategory.value)
})
</script>

<template>
  <section class="admin-presets" data-test="admin-presets">
    <header class="preset-header">
      <div class="preset-header__identity">
        <Library :size="26" aria-hidden="true" />
        <div>
          <h1>预置内容</h1>
          <p>
            六类预置内容在此管理：农产品、农时月历、病虫害知识、非遗技艺、成功案例与助手知识。
            停用是逻辑停用，稳定 ID 会被保留，管理员始终可见。
          </p>
        </div>
      </div>
      <dl class="preset-header__summary">
        <div>
          <dt>当前类别</dt>
          <dd data-test="preset-active-category">{{ activeDefinition.label }}</dd>
        </div>
        <div>
          <dt>本类条目</dt>
          <dd class="ark-data" data-test="preset-count">{{ store.presetCount }}</dd>
        </div>
      </dl>
    </header>

    <div
      class="preset-tabs"
      role="tablist"
      aria-label="预置内容类别"
      data-test="preset-tabs"
    >
      <button
        v-for="category in categories"
        :key="category.id"
        type="button"
        role="tab"
        :data-test="`preset-tab-${category.id}`"
        :class="{ 'is-active': activeCategory === category.id }"
        :aria-selected="activeCategory === category.id"
        @click="selectTab(category.id)"
      >
        <span>{{ category.label }}</span>
      </button>
    </div>

    <p
      v-if="actionMessage"
      class="preset-message"
      data-test="preset-message"
      role="status"
    >
      <Check :size="17" aria-hidden="true" />
      {{ actionMessage }}
    </p>

    <div
      v-if="store.presetsError"
      class="preset-error"
      data-test="preset-error"
      role="alert"
    >
      <ShieldAlert :size="18" aria-hidden="true" />
      <span>{{ store.presetsError }}</span>
      <button
        type="button"
        data-test="preset-retry"
        :disabled="store.presetsLoading"
        @click="store.loadPresets(activeCategory)"
      >
        <RefreshCw :size="16" aria-hidden="true" />
        重新加载
      </button>
    </div>

    <section class="preset-form" aria-labelledby="preset-form-title">
      <header class="preset-form__heading">
        <Pencil :size="20" aria-hidden="true" />
        <h2 id="preset-form-title">
          {{ isEditing ? `编辑${activeDefinition.itemNoun}` : `新建${activeDefinition.itemNoun}` }}
        </h2>
        <button
          type="button"
          data-test="preset-create"
          :disabled="isEditing || store.presetActionLoading"
          @click="startCreate"
        >
          <Plus :size="16" aria-hidden="true" />
          新建
        </button>
      </header>

      <form class="preset-form__grid" data-test="preset-form" @submit.prevent="submitForm">
        <div v-if="activeCategory === 'agri_calendar'" class="preset-field">
          <label>
            <span>农产品稳定 ID</span>
            <input
              v-model="form.productKey"
              type="text"
              maxlength="64"
              autocomplete="off"
              :disabled="isEditing"
              data-test="preset-product-key"
            />
          </label>
          <small v-if="isEditing">创建后不可修改：农产品与月份共同构成稳定 ID。</small>
          <small v-else>小写字母、数字、- 与 _，以字母或数字开头，最长 64 个字符。</small>
        </div>
        <div v-else class="preset-field">
          <label>
            <span>{{ activeDefinition.stableLabel }}</span>
            <input
              v-model="form.stableId"
              type="text"
              maxlength="64"
              autocomplete="off"
              :disabled="isEditing"
              data-test="preset-stable-id"
            />
          </label>
          <small v-if="isEditing">创建后不可修改：用户端按这个稳定 ID 引用内容。</small>
          <small v-else>小写字母、数字、- 与 _，以字母或数字开头，最长 64 个字符。</small>
        </div>

        <div v-if="activeCategory === 'agri_calendar'" class="preset-field">
          <label>
            <span>月份</span>
            <input
              v-model="form.month"
              type="number"
              min="1"
              max="12"
              step="1"
              inputmode="numeric"
              :disabled="isEditing"
              data-test="preset-month"
            />
          </label>
          <small v-if="isEditing">创建后不可修改：换月等于新建一条农时。</small>
          <small v-else>1 到 12 的整数，同一农产品的同一个月只能有一条。</small>
        </div>

        <p v-if="activeCategory === 'agri_calendar' && isEditing" class="preset-field__note">
          稳定 ID <code data-test="preset-stable-id">{{ editingId }}</code>
        </p>

        <div
          v-if="activeCategory === 'agri_products' || activeCategory === 'handcraft_crafts'"
          class="preset-field"
        >
          <label>
            <span>{{ activeCategory === 'handcraft_crafts' ? '技艺名称' : '农产品名称' }}</span>
            <input
              v-model="form.name"
              type="text"
              maxlength="60"
              autocomplete="off"
              data-test="preset-name"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'handcraft_crafts'" class="preset-field preset-field--wide">
          <label>
            <span>技艺简介</span>
            <textarea
              v-model="form.introduction"
              rows="4"
              maxlength="2000"
              data-test="preset-introduction"
            />
          </label>
        </div>

        <div
          v-else-if="activeCategory === 'success_cases' || activeCategory === 'assistant_knowledge'"
          class="preset-field preset-field--wide"
        >
          <label>
            <span>{{ activeCategory === 'assistant_knowledge' ? '知识标题' : '案例标题' }}</span>
            <input
              v-model="form.title"
              type="text"
              maxlength="80"
              autocomplete="off"
              data-test="preset-title"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'pest_knowledge'" class="preset-field">
          <label>
            <span>病虫害名称</span>
            <input
              v-model="form.pestName"
              type="text"
              maxlength="60"
              autocomplete="off"
              data-test="preset-pest-name"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'agri_calendar'" class="preset-field preset-field--wide">
          <label>
            <span>月度提醒</span>
            <textarea
              v-model="form.reminder"
              rows="3"
              maxlength="200"
              data-test="preset-reminder"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'pest_knowledge'" class="preset-field preset-field--wide">
          <label>
            <span>诊断答案</span>
            <textarea
              v-model="form.answer"
              rows="6"
              maxlength="2000"
              data-test="preset-answer"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'success_cases'" class="preset-field preset-field--wide">
          <label>
            <span>案例摘要</span>
            <textarea
              v-model="form.summary"
              rows="3"
              maxlength="200"
              data-test="preset-summary"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'success_cases'" class="preset-field preset-field--wide">
          <label>
            <span>项目背景</span>
            <textarea
              v-model="form.background"
              rows="4"
              maxlength="1000"
              data-test="preset-background"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'success_cases'" class="preset-field preset-field--wide">
          <label>
            <span>实践历程</span>
            <textarea
              v-model="form.journey"
              rows="4"
              maxlength="1000"
              data-test="preset-journey"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'success_cases'" class="preset-field preset-field--wide">
          <label>
            <span>经验启示</span>
            <textarea
              v-model="form.lessons"
              rows="4"
              maxlength="1000"
              data-test="preset-lessons"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'success_cases'" class="preset-field">
          <label>
            <span>发布时间</span>
            <input
              v-model="form.publishedAt"
              type="datetime-local"
              data-test="preset-published-at"
            />
          </label>
          <small>必填；按平台时区（Asia/Shanghai）保存为带时区的 ISO 8601 时间，留空无法保存。</small>
        </div>

        <div v-if="activeCategory === 'assistant_knowledge'" class="preset-field preset-field--wide">
          <label>
            <span>知识正文</span>
            <textarea
              v-model="form.body"
              rows="6"
              maxlength="2000"
              data-test="preset-body"
            />
          </label>
        </div>

        <div v-if="activeCategory === 'assistant_knowledge'" class="preset-field">
          <label>
            <span>所属功能</span>
            <select v-model="form.featureKey" data-test="preset-feature-key">
              <option
                v-for="option in assistantFeatureOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>
        </div>

        <div v-if="activeCategory === 'assistant_knowledge'" class="preset-field">
          <label>
            <span>跳转路径</span>
            <input
              v-model="form.jumpTarget"
              type="text"
              maxlength="200"
              autocomplete="off"
              placeholder="/agri"
              data-test="preset-jump-target"
            />
          </label>
          <small>留空表示不跳转；填写时必须是站内路径，以 / 开头。</small>
        </div>

        <div class="preset-field">
          <label>
            <span>排序</span>
            <input
              v-model="form.sortOrder"
              type="number"
              step="1"
              inputmode="numeric"
              data-test="preset-sort-order"
            />
          </label>
        </div>

        <div class="preset-field preset-field--switch">
          <label class="preset-switch">
            <input v-model="form.enabled" type="checkbox" data-test="preset-enabled" />
            <span>启用</span>
          </label>
          <small>取消勾选后条目立即停止对用户端可见，稳定 ID 仍保留。</small>
        </div>

        <div v-if="activeCategory === 'handcraft_crafts'" class="preset-field preset-field--switch">
          <label class="preset-switch">
            <input
              v-model="form.sourceAvailable"
              type="checkbox"
              data-test="preset-source-available"
            />
            <span>来源可用</span>
          </label>
          <small>关闭后学员端该技艺显示为不可用。</small>
        </div>

      <div
        v-for="list in categoryTextLists"
        :key="list.key"
        class="preset-list"
        :data-test="`preset-list-${list.field}`"
      >
        <header>
          <span>{{ list.label }}</span>
          <button
            type="button"
            :data-test="`preset-${list.field}-add`"
            @click="addListRow(list.key)"
          >
            <Plus :size="15" aria-hidden="true" />
            添加一行
          </button>
        </header>
        <div
          v-for="(entry, index) in listValues(list.key)"
          :key="index"
          class="preset-list__row"
        >
          <input
            :value="entry"
            type="text"
            maxlength="100"
            :data-test="`preset-${list.field}-${index}`"
            :aria-label="`${list.label} 第 ${index + 1} 项`"
            @input="setListRow(list.key, index, ($event.target as HTMLInputElement).value)"
          />
          <button
            type="button"
            :data-test="`preset-${list.field}-remove-${index}`"
            :aria-label="`删除${list.label} 第 ${index + 1} 项`"
            @click="removeListRow(list.key, index)"
          >
            <X :size="15" aria-hidden="true" />
          </button>
        </div>
      </div>

      <div v-if="activeCategory === 'handcraft_crafts'" class="preset-steps" data-test="preset-steps">
        <header>
          <span>技艺步骤</span>
          <button type="button" data-test="preset-step-add" @click="addStep">
            <Plus :size="15" aria-hidden="true" />
            添加步骤
          </button>
        </header>
        <p class="preset-steps__hint">
          学员端需要 6 个步骤、序号 1 到 6 且步骤键唯一，否则该技艺显示为不可学习。
        </p>
        <article
          v-for="(step, index) in form.steps"
          :key="index"
          class="preset-step"
          :data-test="`preset-step-${index}`"
        >
          <header>
            <span>步骤 {{ index + 1 }}</span>
            <button
              type="button"
              :data-test="`preset-step-remove-${index}`"
              :aria-label="`删除步骤 ${index + 1}`"
              @click="removeStep(index)"
            >
              <Trash2 :size="15" aria-hidden="true" />
              删除步骤
            </button>
          </header>
          <div class="preset-step__grid">
            <label class="preset-field">
              <span>序号</span>
              <input
                :value="step.step_no"
                type="number"
                min="1"
                step="1"
                inputmode="numeric"
                :data-test="`preset-step-no-${index}`"
                @input="setStepNumber(index, ($event.target as HTMLInputElement).value)"
              />
            </label>
            <label class="preset-field">
              <span>步骤键</span>
              <input
                v-model="step.step_key"
                type="text"
                maxlength="64"
                autocomplete="off"
                :data-test="`preset-step-key-${index}`"
              />
            </label>
            <label class="preset-field">
              <span>标题</span>
              <input
                v-model="step.title"
                type="text"
                maxlength="60"
                autocomplete="off"
                :data-test="`preset-step-title-${index}`"
              />
            </label>
            <label class="preset-field preset-field--wide">
              <span>说明</span>
              <textarea
                v-model="step.description"
                rows="3"
                maxlength="1000"
                :data-test="`preset-step-description-${index}`"
              />
            </label>
          </div>
          <div class="preset-list preset-list--tips">
            <header>
              <span>要点</span>
              <button
                type="button"
                :data-test="`preset-step-tip-add-${index}`"
                @click="addStepTip(index)"
              >
                <Plus :size="15" aria-hidden="true" />
                添加要点
              </button>
            </header>
            <div
              v-for="(tip, tipIndex) in step.tips"
              :key="tipIndex"
              class="preset-list__row"
            >
              <input
                :value="tip"
                type="text"
                maxlength="200"
                :data-test="`preset-step-tip-${index}-${tipIndex}`"
                :aria-label="`步骤 ${index + 1} 要点 ${tipIndex + 1}`"
                @input="setStepTip(index, tipIndex, ($event.target as HTMLInputElement).value)"
              />
              <button
                type="button"
                :data-test="`preset-step-tip-remove-${index}-${tipIndex}`"
                :aria-label="`删除步骤 ${index + 1} 要点 ${tipIndex + 1}`"
                @click="removeStepTip(index, tipIndex)"
              >
                <X :size="15" aria-hidden="true" />
              </button>
            </div>
          </div>
        </article>
      </div>

      <div
        v-if="activeCategory === 'handcraft_crafts'"
        class="preset-materials"
        data-test="preset-material-guide"
      >
        <header>
          <span>材料指南</span>
          <button type="button" data-test="preset-material-add" @click="addMaterial">
            <Plus :size="15" aria-hidden="true" />
            添加材料
          </button>
        </header>
        <article
          v-for="(material, index) in form.materialGuide"
          :key="index"
          class="preset-material"
          :data-test="`preset-material-${index}`"
        >
          <header>
            <span>材料 {{ index + 1 }}</span>
            <button
              type="button"
              :data-test="`preset-material-remove-${index}`"
              :aria-label="`删除材料 ${index + 1}`"
              @click="removeMaterial(index)"
            >
              <Trash2 :size="15" aria-hidden="true" />
              删除材料
            </button>
          </header>
          <div class="preset-material__grid">
            <label class="preset-field">
              <span>材料名称</span>
              <input
                v-model="material.name"
                type="text"
                maxlength="200"
                autocomplete="off"
                :data-test="`preset-material-name-${index}`"
              />
            </label>
            <label class="preset-field">
              <span>参考价格</span>
              <input
                v-model="material.reference_price"
                type="text"
                maxlength="200"
                autocomplete="off"
                :data-test="`preset-material-price-${index}`"
              />
            </label>
            <label class="preset-field">
              <span>购买渠道</span>
              <input
                v-model="material.purchase_channel"
                type="text"
                maxlength="200"
                autocomplete="off"
                :data-test="`preset-material-channel-${index}`"
              />
            </label>
            <label class="preset-field">
              <span>注意事项</span>
              <input
                v-model="material.precautions"
                type="text"
                maxlength="200"
                autocomplete="off"
                :data-test="`preset-material-precautions-${index}`"
              />
            </label>
            <label class="preset-field">
              <span>搜索关键词</span>
              <input
                v-model="material.taobao_keyword"
                type="text"
                maxlength="200"
                autocomplete="off"
                :data-test="`preset-material-keyword-${index}`"
              />
            </label>
          </div>
        </article>
      </div>

      <div class="preset-form__actions">
        <button
          type="submit"
          class="preset-submit"
          data-test="preset-save"
          :disabled="!canSubmit || store.presetActionLoading || editingDemo"
        >
          <Check :size="16" aria-hidden="true" />
          {{ store.presetActionLoading ? '正在保存' : isEditing ? '保存修改' : '创建条目' }}
        </button>
        <button
          v-if="isEditing"
          type="button"
          data-test="preset-edit-cancel"
          :disabled="store.presetActionLoading"
          @click="resetForm"
        >
          取消编辑
        </button>
      </div>
      </form>

      <p
        v-if="store.presetFormError"
        class="preset-form__error"
        data-test="preset-form-error"
        role="alert"
      >
        <ShieldAlert :size="17" aria-hidden="true" />
        <span class="preset-form__code" data-test="preset-form-error-code">
          {{ store.presetFormErrorCode }}
        </span>
        <span>{{ store.presetFormError }}</span>
        <button
          v-if="isEditing"
          type="button"
          data-test="preset-form-resync"
          :disabled="store.presetsLoading"
          @click="resyncEditingVersion"
        >
          <RefreshCw :size="16" aria-hidden="true" />
          重新加载
        </button>
      </p>

      <p v-if="editingDemo" class="preset-form__notice" data-test="preset-demo-notice">
        演示内容由平台种子维护，每次启动都会被还原，不能编辑或停用；请新建条目后再修改。
      </p>
    </section>

    <section class="preset-registry" aria-labelledby="preset-registry-title">
      <header class="preset-registry__heading">
        <h2 id="preset-registry-title">{{ activeDefinition.title }}</h2>
        <span class="ark-data" data-test="preset-registry-count">
          共 {{ store.presetCount }} 条
        </span>
      </header>

      <div
        v-if="store.presetsLoading && store.presetItems.length === 0"
        class="preset-state"
        data-test="preset-loading"
        role="status"
      >
        <RefreshCw class="spinning" :size="20" aria-hidden="true" />
        正在加载{{ activeDefinition.title }}
      </div>

      <div
        v-else-if="store.presetItems.length === 0"
        class="preset-state preset-state--empty"
        data-test="preset-empty"
      >
        <Inbox :size="24" aria-hidden="true" />
        <span>当前类别没有{{ activeDefinition.title }}，可用上方表单新建</span>
      </div>

      <div v-else class="preset-table-wrap">
        <table v-if="activeCategory === 'agri_products'" class="preset-table">
          <thead>
            <tr>
              <th scope="col">稳定 ID</th>
              <th scope="col">名称</th>
              <th scope="col">排序</th>
              <th scope="col">状态</th>
              <th scope="col">更新时间</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in productItems"
              :key="item.product_key"
              data-test="preset-row"
              :data-preset-id="item.product_key"
            >
              <td data-label="稳定 ID">
                <span class="preset-mono">{{ item.product_key }}</span>
              </td>
              <td data-label="名称">{{ item.name }}</td>
              <td data-label="排序" class="ark-data">{{ item.sort_order }}</td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="更新时间">
                <time class="ark-data" :datetime="item.updated_at">
                  {{ formatTime(item.updated_at) }}
                </time>
              </td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.product_key}`"
                    :disabled="store.presetActionLoading"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.product_key}`"
                    :disabled="!item.is_enabled || store.presetActionLoading"
                    :title="item.is_enabled ? '停用该农产品' : '该条目已停用'"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="activeCategory === 'agri_calendar'" class="preset-table">
          <thead>
            <tr>
              <th scope="col">条目 ID</th>
              <th scope="col">农产品</th>
              <th scope="col">月份</th>
              <th scope="col">提醒</th>
              <th scope="col">状态</th>
              <th scope="col">版本</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in calendarItems"
              :key="item.item_id"
              data-test="preset-row"
              :data-preset-id="item.item_id"
            >
              <td data-label="条目 ID">
                <span class="preset-mono">{{ item.item_id }}</span>
              </td>
              <td data-label="农产品">
                <span class="preset-mono">{{ item.product_key }}</span>
              </td>
              <td data-label="月份" class="ark-data">{{ item.month }} 月</td>
              <td data-label="提醒">{{ item.reminder }}</td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="版本" class="ark-data">v{{ item.version }}</td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.item_id}`"
                    :disabled="store.presetActionLoading"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.item_id}`"
                    :disabled="!item.is_enabled || store.presetActionLoading"
                    :title="item.is_enabled ? '停用该农时条目' : '该条目已停用'"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="activeCategory === 'pest_knowledge'" class="preset-table">
          <thead>
            <tr>
              <th scope="col">条目 ID</th>
              <th scope="col">病虫害</th>
              <th scope="col">关联农产品</th>
              <th scope="col">状态</th>
              <th scope="col">版本</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in pestItems"
              :key="item.item_id"
              data-test="preset-row"
              :data-preset-id="item.item_id"
            >
              <td data-label="条目 ID">
                <span class="preset-mono">{{ item.item_id }}</span>
              </td>
              <td data-label="病虫害">
                <div class="preset-cell">
                  <strong>{{ item.pest_name }}</strong>
                  <span class="preset-sub">{{ item.answer }}</span>
                </div>
              </td>
              <td data-label="关联农产品">{{ item.product_names.join('、') }}</td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="版本" class="ark-data">v{{ item.version }}</td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.item_id}`"
                    :disabled="store.presetActionLoading"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.item_id}`"
                    :disabled="!item.is_enabled || store.presetActionLoading"
                    :title="item.is_enabled ? '停用该病虫害条目' : '该条目已停用'"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="activeCategory === 'handcraft_crafts'" class="preset-table">
          <thead>
            <tr>
              <th scope="col">技艺键</th>
              <th scope="col">名称</th>
              <th scope="col">步骤</th>
              <th scope="col">可学习</th>
              <th scope="col">状态</th>
              <th scope="col">版本</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in craftItems"
              :key="item.craft_key"
              data-test="preset-row"
              :data-preset-id="item.craft_key"
            >
              <td data-label="技艺键">
                <span class="preset-mono">{{ item.craft_key }}</span>
              </td>
              <td data-label="名称">
                <div class="preset-cell">
                  <strong>{{ item.name }}</strong>
                  <span class="preset-sub">{{ item.introduction }}</span>
                </div>
              </td>
              <td data-label="步骤" class="ark-data">{{ item.steps.length }} 步</td>
              <td data-label="可学习">
                <span
                  class="preset-status"
                  :class="item.available ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-available"
                >
                  {{ item.available ? '可学习' : '不可学习' }}
                </span>
              </td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="版本" class="ark-data">v{{ item.version }}</td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.craft_key}`"
                    :disabled="store.presetActionLoading"
                    :title="'编辑该技艺'"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.craft_key}`"
                    :disabled="!item.is_enabled || store.presetActionLoading"
                    :title="item.is_enabled ? '停用该技艺' : '该条目已停用'"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else-if="activeCategory === 'success_cases'" class="preset-table">
          <thead>
            <tr>
              <th scope="col">案例 ID</th>
              <th scope="col">标题</th>
              <th scope="col">摘要</th>
              <th scope="col">发布时间</th>
              <th scope="col">状态</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in caseItems"
              :key="item.id"
              data-test="preset-row"
              :data-preset-id="item.id"
            >
              <td data-label="案例 ID">
                <span class="preset-mono">{{ item.id }}</span>
                <span v-if="item.is_demo" class="preset-tag" data-test="preset-demo-tag">演示</span>
              </td>
              <td data-label="标题">{{ item.title }}</td>
              <td data-label="摘要">{{ item.summary }}</td>
              <td data-label="发布时间">
                <time class="ark-data" :datetime="item.published_at">
                  {{ formatTime(item.published_at) }}
                </time>
              </td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.id}`"
                    :disabled="store.presetActionLoading || item.is_demo"
                    :title="item.is_demo ? '演示案例由平台种子维护，不可编辑' : '编辑该案例'"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.id}`"
                    :disabled="!item.is_enabled || store.presetActionLoading || item.is_demo"
                    :title="
                      item.is_demo
                        ? '演示案例由平台种子维护，不可停用'
                        : item.is_enabled
                          ? '停用该案例'
                          : '该条目已停用'
                    "
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <table v-else class="preset-table">
          <thead>
            <tr>
              <th scope="col">条目 ID</th>
              <th scope="col">标题</th>
              <th scope="col">所属功能</th>
              <th scope="col">跳转</th>
              <th scope="col">状态</th>
              <th scope="col">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in knowledgeItems"
              :key="item.knowledge_id"
              data-test="preset-row"
              :data-preset-id="item.knowledge_id"
            >
              <td data-label="条目 ID">
                <span class="preset-mono">{{ item.knowledge_id }}</span>
              </td>
              <td data-label="标题">
                <div class="preset-cell">
                  <strong>{{ item.title }}</strong>
                  <span class="preset-sub">{{ item.body }}</span>
                </div>
              </td>
              <td data-label="所属功能">{{ featureLabel(item.feature_key) }}</td>
              <td data-label="跳转">
                <span v-if="item.jump_target" class="preset-mono">{{ item.jump_target }}</span>
                <span v-else class="preset-sub">不跳转</span>
              </td>
              <td data-label="状态">
                <span
                  class="preset-status"
                  :class="item.is_enabled ? 'is-enabled' : 'is-disabled'"
                  data-test="preset-status"
                >
                  {{ item.is_enabled ? '已启用' : '已停用' }}
                </span>
              </td>
              <td data-label="操作">
                <div class="preset-actions">
                  <button
                    type="button"
                    :data-test="`preset-edit-${item.knowledge_id}`"
                    :disabled="store.presetActionLoading"
                    @click="startEdit(item)"
                  >
                    <Pencil :size="16" aria-hidden="true" />
                    编辑
                  </button>
                  <button
                    type="button"
                    :data-test="`preset-delete-${item.knowledge_id}`"
                    :disabled="!item.is_enabled || store.presetActionLoading"
                    :title="item.is_enabled ? '停用该知识条目' : '该条目已停用'"
                    @click="openDelete(item)"
                  >
                    <Trash2 :size="16" aria-hidden="true" />
                    停用
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div
      v-if="deleteCandidate"
      class="preset-dialog-backdrop"
      data-test="preset-delete-dialog"
      @click.self="closeDialogs"
    >
      <section
        class="preset-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="preset-delete-title"
      >
        <header>
          <h2 id="preset-delete-title">停用{{ activeDefinition.itemNoun }}</h2>
          <button
            type="button"
            aria-label="关闭停用确认对话框"
            title="关闭"
            :disabled="store.presetActionLoading"
            @click="closeDialogs"
          >
            <X :size="18" aria-hidden="true" />
          </button>
        </header>
        <p data-test="preset-delete-notice">
          这是<strong>逻辑停用</strong>，不是物理删除：条目会立即停止对学员端、教师端等用户端可见，
          但<strong>稳定 ID 会被保留</strong>，管理员在后台仍然可以看到这条已停用的条目，
          之后可以重新编辑并再次启用。停用同样受版本号保护。
        </p>
        <p class="preset-dialog__quote">
          {{ deleteCandidate.label }}
          <span class="preset-mono">{{ deleteCandidate.id }}</span>
        </p>
        <div class="preset-dialog__actions">
          <button
            type="button"
            data-test="preset-confirm-delete"
            :disabled="store.presetActionLoading"
            @click="confirmDelete"
          >
            <Trash2 :size="16" aria-hidden="true" />
            {{ store.presetActionLoading ? '正在处理' : '确认停用' }}
          </button>
          <button
            type="button"
            :disabled="store.presetActionLoading"
            @click="closeDialogs"
          >
            取消
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.admin-presets {
  min-width: 0;
  color: var(--ark-paper);
}

.preset-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.42fr);
  min-width: 0;
  border-top: 1px solid var(--ark-line-strong);
  border-bottom: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.preset-header__identity {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 16px;
  padding: 28px 26px;
}

.preset-header__identity > svg {
  flex: 0 0 auto;
  margin-top: 4px;
  color: var(--ark-signal);
}

.preset-header__identity > div {
  min-width: 0;
}

.preset-header__identity h1 {
  margin: 0;
  font-size: 2.35rem;
  line-height: 1;
  text-wrap: balance;
}

.preset-header__identity p {
  max-width: 62ch;
  margin: 13px 0 0;
  color: var(--ark-muted);
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.preset-header__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin: 0;
  border-left: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.preset-header__summary div {
  display: grid;
  min-width: 0;
  align-content: center;
  padding: 20px 16px;
  background: var(--ark-surface-1);
}

.preset-header__summary dt {
  color: var(--ark-muted);
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-header__summary dd {
  margin: 5px 0 0;
  color: var(--ark-signal);
  font-size: 1.8rem;
  line-height: 1;
}

.preset-tabs {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-line);
}

.preset-tabs button {
  display: flex;
  min-width: 0;
  min-height: 56px;
  align-items: center;
  justify-content: center;
  padding: 10px 8px;
  border: 0;
  background: var(--ark-surface-0);
  color: var(--ark-muted);
}

.preset-tabs button:hover,
.preset-tabs button:focus-visible {
  background: var(--ark-surface-1);
  color: var(--ark-paper);
}

.preset-tabs button.is-active {
  box-shadow: inset 0 -2px 0 var(--ark-signal);
  color: var(--ark-signal);
}

.preset-tabs button span {
  min-width: 0;
  font-size: 0.86rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-message,
.preset-error {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 14px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.preset-message {
  color: var(--ark-state);
}

.preset-message svg,
.preset-error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
}

.preset-message,
.preset-error span {
  min-width: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.preset-error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  margin-left: auto;
  padding: 0 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-form {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.preset-form__heading {
  display: flex;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.preset-form__heading > svg {
  flex: 0 0 auto;
  color: var(--ark-signal);
}

.preset-form__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.preset-form__heading button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 0 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-form__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.preset-field {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  background: var(--ark-surface-0);
  align-content: start;
}

.preset-field > label {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.preset-field > span,
.preset-field label > span {
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-field small {
  color: var(--ark-muted);
  font-size: 0.68rem;
  line-height: 1.5;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-field--wide {
  grid-column: span 2;
}

.preset-field--switch {
  align-content: center;
}

.preset-field__note {
  grid-column: 1 / -1;
  margin: 0;
  padding: 0 14px 12px;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-field input,
.preset-field select,
.preset-field textarea {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-field textarea {
  resize: vertical;
}

.preset-field input:hover,
.preset-field select:hover,
.preset-field textarea:hover {
  border-color: var(--ark-signal);
}

.preset-field input:disabled {
  background: var(--ark-surface-1);
  color: var(--ark-muted);
}

.preset-switch {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 9px;
  color: var(--ark-paper);
  font-size: 0.8rem;
}

.preset-switch input {
  width: 17px;
  height: 17px;
  min-height: 0;
  flex: 0 0 auto;
  padding: 0;
  accent-color: var(--ark-signal);
}

.preset-list,
.preset-steps,
.preset-materials {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px;
  border-top: 1px solid var(--ark-line);
}

.preset-list header,
.preset-steps header,
.preset-materials header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.preset-list header > span,
.preset-steps header > span,
.preset-materials header > span {
  color: var(--ark-paper);
  font-size: 0.82rem;
  font-weight: 500;
}

.preset-list header button,
.preset-steps header button,
.preset-materials header button {
  display: inline-flex;
  min-height: 34px;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-steps__hint {
  margin: 0;
  color: var(--ark-muted);
  font-size: 0.72rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-list__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 38px;
  gap: 8px;
  min-width: 0;
}

.preset-list__row input {
  width: 100%;
  min-width: 0;
  min-height: 38px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-list__row button,
.preset-step header button,
.preset-material header button {
  display: inline-grid;
  min-height: 38px;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-step header button,
.preset-material header button {
  display: inline-flex;
  min-height: 34px;
  gap: 6px;
  padding: 0 10px;
  margin-left: auto;
}

.preset-step,
.preset-material {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.preset-step header,
.preset-material header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.preset-step header > span,
.preset-material header > span {
  font-size: 0.8rem;
  font-weight: 500;
}

.preset-step__grid,
.preset-material__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 1px;
  min-width: 0;
  background: var(--ark-line);
}

.preset-list--tips {
  padding: 0;
  border-top: 0;
}

.preset-form__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 14px;
  border-top: 1px solid var(--ark-line);
}

.preset-form__actions button {
  display: inline-flex;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 14px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-submit {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.preset-form__error,
.preset-form__notice {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  gap: 10px;
  margin: 0;
  padding: 12px 14px;
  border-top: 1px solid var(--ark-line);
  color: var(--ark-paper);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.preset-form__error {
  background: var(--ark-surface-1);
}

.preset-form__error > svg {
  flex: 0 0 auto;
  margin-top: 2px;
  color: var(--ark-signal);
}

.preset-form__error button {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 7px;
  min-height: 34px;
  margin-left: auto;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-form__code {
  flex: 0 0 auto;
  padding: 2px 7px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.preset-registry {
  margin-top: 18px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.preset-registry__heading {
  display: flex;
  min-height: 62px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.preset-registry__heading h2 {
  margin: 0;
  font-size: 1.1rem;
}

.preset-registry__heading span {
  color: var(--ark-muted);
  font-size: 0.75rem;
}

.preset-state {
  display: flex;
  min-height: 190px;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--ark-muted);
  text-align: center;
}

.preset-state--empty {
  flex-direction: column;
}

/* The table owns its own horizontal scroll so a wide row never widens the
   page shell at 320px. */
.preset-table-wrap {
  min-width: 0;
  overflow-x: auto;
}

.preset-table {
  width: 100%;
  min-width: 720px;
  table-layout: fixed;
  border-collapse: collapse;
}

.preset-table th,
.preset-table td {
  min-width: 0;
  padding: 14px 11px;
  border-bottom: 1px solid var(--ark-line);
  text-align: left;
  vertical-align: top;
}

.preset-table th {
  color: var(--ark-muted);
  font-size: 0.7rem;
  font-weight: 500;
  white-space: nowrap;
}

.preset-table td {
  font-size: 0.8rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.preset-table th:nth-child(1) {
  width: 20%;
}

.preset-table th:nth-child(2) {
  width: 24%;
}

.preset-table th:nth-child(3) {
  width: 16%;
}

.preset-table th:nth-child(4) {
  width: 14%;
}

.preset-table th:nth-child(5) {
  width: 10%;
}

.preset-table th:nth-child(6) {
  width: 8%;
}

.preset-table th:nth-child(7) {
  width: 8%;
}

.preset-table tbody tr:last-child td {
  border-bottom: 0;
}

.preset-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.preset-cell strong {
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.preset-sub {
  display: block;
  color: var(--ark-muted);
  font-size: 0.7rem;
  line-height: 1.5;
}

.preset-mono {
  font-family: ui-monospace, "SFMono-Regular", "Cascadia Mono", Consolas, monospace;
  font-size: 0.74rem;
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: keep-all;
}

.preset-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.preset-status::before {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  background: currentColor;
  content: "";
}

.preset-status.is-enabled {
  color: var(--ark-signal);
}

.preset-status.is-disabled {
  color: var(--ark-muted);
}

.preset-tag {
  display: inline-block;
  margin-top: 4px;
  padding: 1px 6px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  color: var(--ark-muted);
  font-size: 0.66rem;
}

.preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preset-actions button {
  display: inline-flex;
  min-height: 38px;
  flex: 1 1 68px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.preset-dialog-backdrop {
  position: fixed;
  z-index: 40;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: color-mix(in srgb, var(--ark-paper) 72%, transparent);
}

.preset-dialog {
  width: min(100%, 560px);
  max-height: calc(100svh - 40px);
  overflow-y: auto;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
}

.preset-dialog header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--ark-line);
}

.preset-dialog h2 {
  margin: 0;
  font-size: 1.15rem;
}

.preset-dialog header button {
  display: inline-grid;
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: transparent;
  color: var(--ark-paper);
}

.preset-dialog > p {
  margin: 0;
  padding: 18px 18px 0;
  color: var(--ark-muted);
  font-size: 0.84rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.preset-dialog > p strong {
  color: var(--ark-paper);
}

.preset-dialog__quote {
  display: grid;
  gap: 4px;
  color: var(--ark-paper);
  font-size: 0.86rem;
}

.preset-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
}

.preset-dialog__actions button {
  display: inline-flex;
  min-width: 108px;
  min-height: 38px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.preset-dialog__actions button:first-child {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.admin-presets :is(button, input, select, textarea):focus-visible {
  outline: 2px solid var(--ark-focus);
  outline-offset: 3px;
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1080px) {
  .preset-header {
    grid-template-columns: minmax(0, 1fr);
  }

  .preset-header__summary {
    border-top: 1px solid var(--ark-line-strong);
    border-left: 0;
  }

  .preset-tabs {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .preset-field--wide {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .preset-header__identity {
    padding: 21px 16px;
  }

  .preset-header__identity h1 {
    font-size: 2rem;
  }

  .preset-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .preset-form__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .preset-field--wide {
    grid-column: 1 / -1;
  }

  .preset-list__row {
    grid-template-columns: minmax(0, 1fr) 38px;
  }

  .preset-dialog-backdrop {
    padding: 10px;
  }

  .preset-dialog__actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
  }

  .preset-dialog__actions button {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinning {
    animation: none;
  }
}
</style>
