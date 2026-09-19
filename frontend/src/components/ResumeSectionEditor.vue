<script setup lang="ts">
import { Plus, Trash2 } from 'lucide-vue-next'

interface ResumeFieldDefinition {
  key: string
  testKey: string
  label: string
  type?: 'text' | 'month' | 'textarea'
  required?: boolean
  wide?: boolean
}

const props = defineProps<{
  kind: 'education' | 'work'
  title: string
  description: string
  entries: Array<Record<string, string>>
  fields: ResumeFieldDefinition[]
  errors: Record<string, string>
}>()

const emit = defineEmits<{
  add: []
  remove: [index: number]
  'update-field': [index: number, key: string, value: string]
}>()

function payloadPrefix(): string {
  return props.kind === 'education'
    ? 'education_experiences'
    : 'work_experiences'
}

function fieldError(field: ResumeFieldDefinition): string {
  return props.errors[`${payloadPrefix()}.${field.key}`] ?? ''
}

function sectionError(): string {
  return props.errors[payloadPrefix()] ?? ''
}

function fieldId(field: ResumeFieldDefinition, index: number): string {
  return `resume-${props.kind}-${field.testKey}-${index}`
}

function fieldErrorId(
  field: ResumeFieldDefinition,
  index: number
): string {
  return `${props.kind}-${field.testKey}-error-${index}`
}
</script>

<template>
  <section class="resume-section-editor" :aria-labelledby="`${kind}-section-title`">
    <header class="resume-section-editor__heading">
      <div>
        <h2 :id="`${kind}-section-title`">{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <button
        class="resume-section-editor__add"
        type="button"
        :data-test="`add-${kind}`"
        @click="emit('add')"
      >
        <Plus :size="16" aria-hidden="true" />
        {{ kind === 'education' ? '添加教育经历' : '添加工作经历' }}
      </button>
    </header>

    <div v-if="entries.length" class="resume-section-editor__entries">
      <article
        v-for="(entry, index) in entries"
        :key="index"
        class="resume-section-editor__entry"
        :data-test="`${kind}-entry-${index}`"
      >
        <header class="resume-section-editor__entry-heading">
          <h3>
            {{ kind === 'education' ? '教育经历' : '工作经历' }}
            <span class="ark-data">{{ index + 1 }}</span>
          </h3>
          <button
            class="resume-section-editor__remove"
            type="button"
            :data-test="`remove-${kind}-${index}`"
            :aria-label="`删除第 ${index + 1} 条${
              kind === 'education' ? '教育经历' : '工作经历'
            }`"
            @click="emit('remove', index)"
          >
            <Trash2 :size="16" aria-hidden="true" />
            <span>删除</span>
          </button>
        </header>

        <div class="resume-section-editor__fields">
          <label
            v-for="field in fields"
            :key="field.key"
            class="resume-section-editor__field"
            :class="{ 'is-wide': field.wide }"
          >
            <span>
              {{ field.label }}
              <b v-if="field.required" aria-hidden="true">*</b>
            </span>
            <textarea
              v-if="field.type === 'textarea'"
              :id="fieldId(field, index)"
              :data-test="`${kind}-${field.testKey}-${index}`"
              :value="entry[field.key] ?? ''"
              rows="3"
              :aria-invalid="fieldError(field) ? 'true' : undefined"
              :aria-describedby="
                fieldError(field) ? fieldErrorId(field, index) : undefined
              "
              @input="
                emit(
                  'update-field',
                  index,
                  field.key,
                  ($event.target as HTMLTextAreaElement).value
                )
              "
            />
            <input
              v-else
              :id="fieldId(field, index)"
              :data-test="`${kind}-${field.testKey}-${index}`"
              :type="field.type ?? 'text'"
              :value="entry[field.key] ?? ''"
              :aria-invalid="fieldError(field) ? 'true' : undefined"
              :aria-describedby="
                fieldError(field) ? fieldErrorId(field, index) : undefined
              "
              @input="
                emit(
                  'update-field',
                  index,
                  field.key,
                  ($event.target as HTMLInputElement).value
                )
              "
            >
            <p
              v-if="fieldError(field)"
              :id="fieldErrorId(field, index)"
              :data-test="`${kind}-${field.testKey}-error-${index}`"
              role="alert"
            >
              {{ fieldError(field) }}
            </p>
          </label>
        </div>
      </article>
    </div>

    <p v-else class="resume-section-editor__empty">
      暂未添加{{ kind === 'education' ? '教育经历' : '工作经历' }}。
    </p>
    <p
      v-if="sectionError()"
      class="resume-section-editor__section-error"
      role="alert"
    >
      {{ sectionError() }}
    </p>
  </section>
</template>

<style scoped>
.resume-section-editor {
  min-width: 0;
  padding: 22px;
  border-bottom: 1px solid var(--ark-line);
  line-break: strict;
  overflow-wrap: anywhere;
  word-break: normal;
}

.resume-section-editor__heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 16px;
}

.resume-section-editor__heading h2,
.resume-section-editor__entry-heading h3 {
  min-width: 0;
  margin: 0;
  color: var(--ark-paper);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__heading h2 {
  font-size: 1rem;
  line-height: 1.35;
}

.resume-section-editor__heading p {
  max-width: 66ch;
  margin: 6px 0 0;
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__add,
.resume-section-editor__remove {
  display: inline-flex;
  min-width: 0;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border: 1px solid var(--ark-signal);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-signal);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__add {
  padding: 8px 12px;
}

.resume-section-editor__add:hover,
.resume-section-editor__add:focus-visible {
  background: var(--ark-surface-1);
}

.resume-section-editor__entries {
  display: grid;
  min-width: 0;
  gap: 1px;
  margin-top: 16px;
  background: var(--ark-line);
}

.resume-section-editor__entry {
  display: grid;
  min-width: 0;
  gap: 14px;
  padding: 16px;
  background: var(--ark-surface-0);
}

.resume-section-editor__entry-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.resume-section-editor__entry-heading h3 {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 0.86rem;
}

.resume-section-editor__entry-heading h3 span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.resume-section-editor__remove {
  padding: 7px 10px;
  border-color: var(--ark-line-strong);
  color: var(--ark-paper);
}

.resume-section-editor__remove:hover,
.resume-section-editor__remove:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.resume-section-editor__fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 13px;
}

.resume-section-editor__field {
  display: grid;
  min-width: 0;
  gap: 6px;
  color: var(--ark-paper);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__field.is-wide {
  grid-column: 1 / -1;
}

.resume-section-editor__field > span {
  min-width: 0;
}

.resume-section-editor__field b {
  color: var(--ark-signal);
  font-weight: 700;
}

.resume-section-editor__field input,
.resume-section-editor__field textarea {
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

.resume-section-editor__field textarea {
  min-height: 94px;
  resize: vertical;
}

.resume-section-editor__field input[aria-invalid="true"],
.resume-section-editor__field textarea[aria-invalid="true"] {
  border-color: var(--ark-signal);
}

.resume-section-editor__field > p,
.resume-section-editor__section-error {
  margin: 0;
  color: var(--ark-signal);
  font-size: 0.75rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__empty {
  min-height: 76px;
  margin: 16px 0 0;
  padding: 20px 12px;
  border: 1px dashed var(--ark-line-strong);
  background: var(--ark-surface-1);
  color: var(--ark-muted);
  font-size: 0.78rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-align: center;
  text-wrap: pretty;
  word-break: normal;
}

.resume-section-editor__section-error {
  margin-top: 10px;
}

@media (max-width: 720px) {
  .resume-section-editor {
    padding: 18px 16px;
  }

  .resume-section-editor__heading,
  .resume-section-editor__entry-heading {
    grid-template-columns: minmax(0, 1fr);
  }

  .resume-section-editor__add,
  .resume-section-editor__remove {
    width: 100%;
  }

  .resume-section-editor__fields {
    grid-template-columns: minmax(0, 1fr);
  }

  .resume-section-editor__field.is-wide {
    grid-column: auto;
  }
}
</style>
