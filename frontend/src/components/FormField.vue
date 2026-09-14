<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  id: string
  label: string
  modelValue: string
  type?: string
  autocomplete?: string
  error?: string
  required?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const input = ref<HTMLInputElement | null>(null)

const describedBy = computed(() => {
  return props.error ? `${props.id}-error` : undefined
})

function handleInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

defineExpose({
  focus() {
    input.value?.focus()
  }
})
</script>

<template>
  <div class="form-field" :class="{ invalid: error }">
    <label :for="id">
      {{ label }}
      <span v-if="required" aria-hidden="true">*</span>
    </label>
    <input
      :id="id"
      ref="input"
      :name="id"
      :type="type ?? 'text'"
      :value="modelValue"
      :autocomplete="autocomplete"
      :required="required"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="describedBy"
      @input="handleInput"
    />
    <p v-if="error" :id="`${id}-error`" class="field-error" role="alert">
      {{ error }}
    </p>
  </div>
</template>

<style scoped>
.form-field {
  display: grid;
  gap: 7px;
  min-width: 0;
}

label {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

label span {
  margin-left: 3px;
  color: var(--ark-signal);
}

input {
  width: 100%;
  min-height: 44px;
  padding: 9px 11px;
  border: 1px solid var(--ark-line-strong);
  border-radius: var(--ark-radius);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

input:hover {
  border-color: rgb(24 209 255 / 0.62);
}

input:focus-visible {
  outline-offset: 0;
}

.invalid input {
  border-color: rgb(255 138 138 / 0.62);
}

.field-error {
  margin: 0;
  color: #ff9c9c;
  font-size: 0.76rem;
  line-height: 1.5;
}
</style>
