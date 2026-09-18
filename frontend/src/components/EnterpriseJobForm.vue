<script setup lang="ts">
import { Save, X } from 'lucide-vue-next'

import type {
  ApiFieldErrors,
  EnterpriseJobPayload,
  InterestTag
} from '@/api/types'

const props = defineProps<{
  categories: InterestTag[]
  modelValue: EnterpriseJobPayload
  editing: boolean
  saving: boolean
  fieldErrors: ApiFieldErrors
}>()

const emit = defineEmits<{
  'update:modelValue': [value: EnterpriseJobPayload]
  submit: []
  cancel: []
}>()

type TextField = Exclude<keyof EnterpriseJobPayload, 'category_id'>

function updateText(field: TextField, value: string) {
  emit('update:modelValue', {
    ...props.modelValue,
    [field]: value
  })
}

function updateCategory(event: Event) {
  emit('update:modelValue', {
    ...props.modelValue,
    category_id: Number((event.target as HTMLSelectElement).value)
  })
}
</script>

<template>
  <form
    data-test="job-form"
    class="enterprise-job-form"
    novalidate
    @submit.prevent="emit('submit')"
  >
    <header class="enterprise-job-form__heading">
      <div>
        <h2>{{ editing ? '编辑职位' : '发布职位' }}</h2>
        <p>
          提交后进入待审核状态。审核结果由内容审核流程同步，无需企业手动操作。
        </p>
      </div>
      <span class="ark-data">{{ editing ? 'EDIT' : 'NEW' }}</span>
    </header>

    <div class="enterprise-job-form__grid">
      <div
        class="enterprise-job-form__field"
        :class="{ 'has-error': fieldErrors.title }"
      >
        <label for="job-title">职位标题 *</label>
        <input
          id="job-title"
          data-test="job-title"
          type="text"
          name="title"
          :value="modelValue.title"
          maxlength="100"
          required
          :aria-invalid="fieldErrors.title ? 'true' : undefined"
          :aria-describedby="fieldErrors.title ? 'job-title-error' : undefined"
          @input="updateText('title', ($event.target as HTMLInputElement).value)"
        />
        <p
          v-if="fieldErrors.title"
          id="job-title-error"
          data-test="job-title-error"
          role="alert"
        >
          {{ fieldErrors.title }}
        </p>
      </div>

      <div
        class="enterprise-job-form__field"
        :class="{ 'has-error': fieldErrors.salary }"
      >
        <label for="job-salary">薪资 *</label>
        <input
          id="job-salary"
          data-test="job-salary"
          type="text"
          name="salary"
          :value="modelValue.salary"
          maxlength="80"
          required
          :aria-invalid="fieldErrors.salary ? 'true' : undefined"
          :aria-describedby="
            fieldErrors.salary ? 'job-salary-error' : undefined
          "
          @input="updateText('salary', ($event.target as HTMLInputElement).value)"
        />
        <p
          v-if="fieldErrors.salary"
          id="job-salary-error"
          data-test="job-salary-error"
          role="alert"
        >
          {{ fieldErrors.salary }}
        </p>
      </div>

      <div
        class="enterprise-job-form__field"
        :class="{ 'has-error': fieldErrors.location }"
      >
        <label for="job-location">工作地点 *</label>
        <input
          id="job-location"
          data-test="job-location"
          type="text"
          name="location"
          :value="modelValue.location"
          maxlength="120"
          required
          :aria-invalid="fieldErrors.location ? 'true' : undefined"
          :aria-describedby="
            fieldErrors.location ? 'job-location-error' : undefined
          "
          @input="
            updateText('location', ($event.target as HTMLInputElement).value)
          "
        />
        <p
          v-if="fieldErrors.location"
          id="job-location-error"
          data-test="job-location-error"
          role="alert"
        >
          {{ fieldErrors.location }}
        </p>
      </div>

      <div
        class="enterprise-job-form__field"
        :class="{ 'has-error': fieldErrors.category_id }"
      >
        <label for="job-category-select">职位类别 *</label>
        <select
          id="job-category-select"
          data-test="job-category-select"
          name="category_id"
          :value="modelValue.category_id || ''"
          required
          :aria-invalid="fieldErrors.category_id ? 'true' : undefined"
          :aria-describedby="
            fieldErrors.category_id ? 'job-category-error' : undefined
          "
          @change="updateCategory"
        >
          <option value="">请选择职位类别</option>
          <option
            v-for="category in categories"
            :key="category.id"
            :value="category.id"
          >
            {{ category.name }}
          </option>
        </select>
        <p
          v-if="fieldErrors.category_id"
          id="job-category-error"
          data-test="job-category-error"
          role="alert"
        >
          {{ fieldErrors.category_id }}
        </p>
      </div>

      <div
        class="enterprise-job-form__field enterprise-job-form__field--wide"
        :class="{ 'has-error': fieldErrors.description }"
      >
        <label for="job-description">职位描述 *</label>
        <textarea
          id="job-description"
          data-test="job-description"
          name="description"
          :value="modelValue.description"
          rows="7"
          maxlength="4000"
          required
          :aria-invalid="fieldErrors.description ? 'true' : undefined"
          :aria-describedby="
            fieldErrors.description ? 'job-description-error' : undefined
          "
          @input="
            updateText('description', ($event.target as HTMLTextAreaElement).value)
          "
        />
        <p
          v-if="fieldErrors.description"
          id="job-description-error"
          data-test="job-description-error"
          role="alert"
        >
          {{ fieldErrors.description }}
        </p>
      </div>
    </div>

    <footer class="enterprise-job-form__actions">
      <button
        type="button"
        data-test="job-form-cancel"
        :disabled="saving"
        @click="emit('cancel')"
      >
        <X :size="16" aria-hidden="true" />
        取消
      </button>
      <button
        class="enterprise-job-form__submit"
        type="submit"
        data-test="job-form-submit"
        :disabled="saving"
      >
        <Save :size="16" aria-hidden="true" />
        {{ saving ? '保存中...' : editing ? '保存修改' : '提交审核' }}
      </button>
    </footer>
  </form>
</template>

<style scoped>
.enterprise-job-form {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.enterprise-job-form__heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.enterprise-job-form__heading h2 {
  margin: 0;
  font-size: 1.05rem;
  line-height: 1.35;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: balance;
  word-break: normal;
}

.enterprise-job-form__heading p {
  max-width: 68ch;
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.82rem;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-job-form__heading > span {
  flex: 0 0 auto;
  color: var(--ark-signal);
  font-size: 0.7rem;
}

.enterprise-job-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding: 20px;
}

.enterprise-job-form__field {
  display: grid;
  min-width: 0;
  gap: 7px;
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.enterprise-job-form__field--wide {
  grid-column: 1 / -1;
}

.enterprise-job-form__field label {
  color: var(--ark-paper);
  font-size: 0.82rem;
  font-weight: 700;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-job-form__field input,
.enterprise-job-form__field select,
.enterprise-job-form__field textarea {
  width: 100%;
  min-width: 0;
  min-height: 44px;
  padding: 9px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  word-break: normal;
}

.enterprise-job-form__field textarea {
  min-height: 148px;
  resize: vertical;
}

.enterprise-job-form__field input:focus-visible,
.enterprise-job-form__field select:focus-visible,
.enterprise-job-form__field textarea:focus-visible {
  border-color: var(--ark-focus);
}

.enterprise-job-form__field.has-error input,
.enterprise-job-form__field.has-error select,
.enterprise-job-form__field.has-error textarea {
  border-color: var(--ark-signal);
}

.enterprise-job-form__field > p {
  margin: 0;
  color: var(--ark-signal);
  font-size: 0.78rem;
  line-height: 1.5;
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  word-break: normal;
}

.enterprise-job-form__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 20px 20px;
}

.enterprise-job-form__actions button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 40px;
  padding: 8px 13px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: break-word;
  text-wrap: pretty;
  white-space: normal;
  word-break: normal;
}

.enterprise-job-form__actions .enterprise-job-form__submit {
  border-color: var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.enterprise-job-form__actions button:hover:not(:disabled),
.enterprise-job-form__actions button:focus-visible:not(:disabled) {
  border-color: var(--ark-signal);
}

@media (max-width: 720px) {
  .enterprise-job-form__heading {
    flex-direction: column;
    padding: 16px;
  }

  .enterprise-job-form__grid {
    grid-template-columns: minmax(0, 1fr);
    padding: 16px;
  }

  .enterprise-job-form__field--wide {
    grid-column: auto;
  }

  .enterprise-job-form__actions {
    padding: 0 16px 16px;
  }

  .enterprise-job-form__actions button {
    flex: 1 1 140px;
  }
}
</style>
