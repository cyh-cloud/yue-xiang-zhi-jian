<script setup lang="ts">
import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

export interface OperatorFormOption {
  value: string | number;
  label: string;
}

export interface OperatorFormField {
  key: string;
  label: string;
  type?:
    | "text"
    | "number"
    | "textarea"
    | "select"
    | "checkbox"
    | "list"
    | "chem"
    | "checkboxes";
  required?: boolean;
  options?: OperatorFormOption[];
  hint?: string;
  placeholder?: string;
  maxlength?: number;
  min?: number;
  max?: number;
  rows?: number;
}

type FormValue = string | boolean | string[];
type FormValues = Record<string, FormValue>;

const props = withDefaults(
  defineProps<{
    title: string;
    eyebrow?: string;
    fields: OperatorFormField[];
    initial?: Record<string, unknown>;
    busy?: boolean;
    error?: string;
    submitLabel?: string;
  }>(),
  {
    eyebrow: "内容维护",
    initial: () => ({}),
    busy: false,
    error: "",
    submitLabel: "保存",
  },
);

const emit = defineEmits<{
  close: [];
  submit: [values: Record<string, unknown>];
}>();

const dialog = ref<HTMLElement | null>(null);
const firstField = ref<HTMLInputElement | HTMLSelectElement | null>(null);
const values = ref<FormValues>({});

const CHEM_FIELDS = ["agent", "dose", "interval_days", "max_times"] as const;

watch(
  () => props.initial,
  () => resetValues(),
  { immediate: true, deep: true },
);

onMounted(() => {
  document.addEventListener("keydown", handleKeydown);
  void nextTick(() => firstField.value?.focus());
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeydown);
});

function resetValues(): void {
  const next: FormValues = {};
  for (const field of props.fields) {
    const value = props.initial[field.key];
    if (field.type === "checkbox") {
      next[field.key] = Boolean(value);
    } else if (field.type === "checkboxes") {
      next[field.key] = Array.isArray(value)
        ? value.map((item) => String(item))
        : [];
    } else if (field.type === "list") {
      next[field.key] = Array.isArray(value) ? value.join("\n") : String(value ?? "");
    } else if (field.type === "chem") {
      next[field.key] = Array.isArray(value)
        ? value
            .map((row) =>
              CHEM_FIELDS.map((key) =>
                isRecord(row) ? String(row[key] ?? "") : "",
              ).join(" | "),
            )
            .join("\n")
        : String(value ?? "");
    } else {
      next[field.key] = String(value ?? "");
    }
  }
  values.value = next;
}

function setTextInput(
  field: OperatorFormField,
  element: HTMLInputElement | HTMLSelectElement,
): void {
  if (field.key === props.fields[0]?.key) {
    firstField.value = element;
  }
}

function isChecked(field: OperatorFormField, optionValue: string | number): boolean {
  return Array.isArray(values.value[field.key])
    ? (values.value[field.key] as string[]).includes(String(optionValue))
    : false;
}

function toggleChecked(
  field: OperatorFormField,
  optionValue: string | number,
  checked: boolean,
): void {
  const current = Array.isArray(values.value[field.key])
    ? [...(values.value[field.key] as string[])]
    : [];
  const value = String(optionValue);
  values.value[field.key] = checked
    ? [...new Set([...current, value])]
    : current.filter((item) => item !== value);
}

function submit(): void {
  const payload: Record<string, unknown> = {};
  for (const field of props.fields) {
    const value = values.value[field.key];
    if (field.type === "checkbox") {
      payload[field.key] = Boolean(value);
    } else if (field.type === "list") {
      payload[field.key] = splitLines(String(value ?? ""));
    } else if (field.type === "chem") {
      payload[field.key] = splitChemLines(String(value ?? ""));
    } else if (field.type === "checkboxes") {
      payload[field.key] = Array.isArray(value) ? value : [];
    } else {
      payload[field.key] = String(value ?? "").trim();
    }
  }
  emit("submit", payload);
}

function splitLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function splitChemLines(value: string): Array<Record<string, string>> {
  return splitLines(value).map((line) => {
    const parts = line.split("|").map((part) => part.trim());
    return Object.fromEntries(
      CHEM_FIELDS.map((key, index) => [key, parts[index] ?? ""]),
    );
  });
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && !props.busy) emit("close");
  if (event.key !== "Tab" || !dialog.value) return;
  const focusable = Array.from(
    dialog.value.querySelectorAll<HTMLElement>(
      "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])",
    ),
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!first || !last) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function stringValue(key: string): string {
  const value = values.value[key];
  return typeof value === "string" ? value : String(value ?? "");
}

function updateString(
  key: string,
  event: Event,
): void {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement;
  values.value[key] = target.value;
}
</script>

<template>
  <Teleport to="body">
    <div
      class="operator-dialog-overlay"
      @click.self="!busy && emit('close')"
    >
      <section
        ref="dialog"
        class="bo-modal operator-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="operator-dialog-title"
        data-testid="operator-record-dialog"
      >
        <header class="bo-modal-head">
          <div>
            <p>{{ eyebrow }}</p>
            <h2 id="operator-dialog-title">
              {{ title }}
            </h2>
          </div>
          <button
            type="button"
            class="bo-icon-button"
            aria-label="关闭"
            :disabled="busy"
            @click="emit('close')"
          >
            <i
              class="fas fa-times"
              aria-hidden="true"
            />
          </button>
        </header>

        <form
          class="bo-modal-body operator-dialog-form"
          @submit.prevent="submit"
        >
          <div
            v-if="error"
            class="bo-feedback is-error"
            role="alert"
            data-testid="operator-dialog-error"
          >
            {{ error }}
          </div>

          <template
            v-for="(field, index) in fields"
            :key="field.key"
          >
            <label
              v-if="field.type === 'select'"
              class="bo-field"
            >
              <span>{{ field.label }}{{ field.required ? " *" : "" }}</span>
              <select
                :ref="(element) => {
                  if (index === 0 && element) {
                    setTextInput(field, element as HTMLSelectElement);
                  }
                }"
                :value="stringValue(field.key)"
                :required="field.required"
                :aria-label="field.label"
                @change="updateString(field.key, $event)"
              >
                <option value="">
                  不指定
                </option>
                <option
                  v-for="option in field.options ?? []"
                  :key="String(option.value)"
                  :value="String(option.value)"
                >
                  {{ option.label }}
                </option>
              </select>
            </label>

            <label
              v-else-if="field.type === 'textarea' || field.type === 'list' || field.type === 'chem'"
              class="bo-field"
            >
              <span>{{ field.label }}{{ field.required ? " *" : "" }}</span>
              <textarea
                :ref="(element) => {
                  if (index === 0 && element) {
                    setTextInput(field, element as unknown as HTMLInputElement);
                  }
                }"
                :value="stringValue(field.key)"
                :rows="field.rows ?? (field.type === 'textarea' ? 3 : 5)"
                :required="field.required"
                :maxlength="field.maxlength"
                :placeholder="field.placeholder"
                :aria-label="field.label"
                @input="updateString(field.key, $event)"
              />
              <small
                v-if="field.hint"
                class="operator-field-hint"
              >
                {{ field.hint }}
              </small>
            </label>

            <fieldset
              v-else-if="field.type === 'checkboxes'"
              class="operator-checkboxes"
            >
              <legend>{{ field.label }}</legend>
              <label
                v-for="option in field.options ?? []"
                :key="String(option.value)"
              >
                <input
                  type="checkbox"
                  :aria-label="String(option.value)"
                  :checked="isChecked(field, option.value)"
                  @change="toggleChecked(
                    field,
                    option.value,
                    ($event.target as HTMLInputElement).checked,
                  )"
                >
                <span>{{ option.label }}</span>
              </label>
              <small
                v-if="field.hint"
                class="operator-field-hint"
              >
                {{ field.hint }}
              </small>
            </fieldset>

            <label
              v-else-if="field.type === 'checkbox'"
              class="operator-checkbox"
            >
              <input
                v-model="values[field.key]"
                type="checkbox"
              >
              <span>{{ field.label }}</span>
            </label>

            <label
              v-else
              class="bo-field"
            >
              <span>{{ field.label }}{{ field.required ? " *" : "" }}</span>
              <input
                :ref="(element) => {
                  if (index === 0 && element) {
                    setTextInput(field, element as HTMLInputElement);
                  }
                }"
                :value="stringValue(field.key)"
                :type="field.type === 'number' ? 'number' : 'text'"
                :required="field.required"
                :maxlength="field.maxlength"
                :min="field.min"
                :max="field.max"
                :placeholder="field.placeholder"
                :aria-label="field.label"
                @input="updateString(field.key, $event)"
              >
            </label>
          </template>

          <footer class="bo-modal-actions operator-dialog-actions">
            <button
              type="button"
              class="bo-button is-secondary"
              :disabled="busy"
              @click="emit('close')"
            >
              取消
            </button>
            <button
              type="submit"
              class="bo-button"
              :disabled="busy"
            >
              <i
                v-if="busy"
                class="fas fa-spinner fa-spin"
                aria-hidden="true"
              />
              {{ busy ? "保存中" : submitLabel }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.operator-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(6, 18, 12, 0.52);
  backdrop-filter: blur(3px);
}

.operator-dialog {
  width: min(720px, calc(100vw - 48px));
}

.operator-dialog-form {
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}

.operator-dialog-form textarea {
  width: 100%;
  min-height: 90px;
  padding: 9px 10px;
  border: 1px solid var(--bo-input-border);
  border-radius: 8px;
  background: var(--bo-input-bg);
  color: var(--bo-text);
  font: inherit;
  font-size: 0.82rem;
  line-height: 1.55;
  resize: vertical;
}

.operator-dialog-form textarea:focus {
  border-color: var(--bo-accent);
  box-shadow: 0 0 0 3px var(--bo-accent-soft);
  outline: none;
}

.operator-field-hint {
  color: var(--bo-muted);
  font-size: 0.68rem;
  line-height: 1.45;
}

.operator-checkboxes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 12px;
  border: 1px solid var(--bo-input-border);
  border-radius: 9px;
}

.operator-checkboxes legend {
  padding: 0 5px;
  color: var(--bo-muted);
  font-size: 0.72rem;
  font-weight: 700;
}

.operator-checkboxes label,
.operator-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
}

.operator-checkboxes input,
.operator-checkbox input {
  width: auto;
}

.operator-dialog-actions {
  padding: 4px 0 0;
}
</style>
