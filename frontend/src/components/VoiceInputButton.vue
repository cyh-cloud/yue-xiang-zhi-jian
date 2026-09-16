<script setup lang="ts">
import { Mic, Square } from 'lucide-vue-next'
import { onBeforeUnmount } from 'vue'

const props = withDefaults(
  defineProps<{
    recording: boolean
    disabled?: boolean
    error?: string
  }>(),
  {
    disabled: false,
    error: ''
  }
)

const emit = defineEmits<{
  'update:recording': [recording: boolean]
  recorded: [blob: Blob, filename: string]
  'permission-denied': []
}>()

const mediaRecorderSupported =
  typeof MediaRecorder !== 'undefined' &&
  typeof navigator !== 'undefined' &&
  Boolean(navigator.mediaDevices?.getUserMedia)

let recorder: MediaRecorder | null = null
let mediaStream: MediaStream | null = null
let chunks: Blob[] = []

function extensionFor(mimeType: string): string {
  const normalized = mimeType.split(';')[0].trim().toLowerCase()
  const knownExtensions: Record<string, string> = {
    'audio/webm': 'webm',
    'audio/ogg': 'ogg',
    'audio/mp4': 'm4a',
    'audio/mpeg': 'mp3',
    'audio/wav': 'wav',
    'audio/x-wav': 'wav'
  }
  return knownExtensions[normalized] ?? 'webm'
}

function stopTracks() {
  mediaStream?.getTracks().forEach(track => track.stop())
  mediaStream = null
}

function resetRecorder() {
  stopTracks()
  recorder = null
  chunks = []
  emit('update:recording', false)
}

function preferredMimeType(): string {
  if (typeof MediaRecorder.isTypeSupported !== 'function') {
    return ''
  }
  return (
    [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4'
    ].find(type => MediaRecorder.isTypeSupported(type)) ?? ''
  )
}

async function startRecording() {
  if (props.disabled || !mediaRecorderSupported) {
    return
  }

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = preferredMimeType()
    recorder = mimeType
      ? new MediaRecorder(mediaStream, { mimeType })
      : new MediaRecorder(mediaStream)
    chunks = []

    recorder.addEventListener('dataavailable', event => {
      if (event.data.size > 0) {
        chunks.push(event.data)
      }
    })
    recorder.addEventListener('stop', () => {
      const finalType = recorder?.mimeType || chunks[0]?.type || 'audio/webm'
      const blob = new Blob(chunks, { type: finalType })
      resetRecorder()
      emit('recorded', blob, `question.${extensionFor(finalType)}`)
    })

    recorder.start()
    emit('update:recording', true)
  } catch {
    resetRecorder()
    emit('permission-denied')
  }
}

function stopRecording() {
  if (recorder && recorder.state !== 'inactive') {
    recorder.stop()
    return
  }
  resetRecorder()
}

function toggleRecording() {
  if (props.recording) {
    stopRecording()
  } else {
    void startRecording()
  }
}

onBeforeUnmount(() => {
  if (recorder && recorder.state !== 'inactive') {
    recorder.stop()
  } else {
    stopTracks()
  }
})
</script>

<template>
  <div class="voice-input">
    <button
      class="voice-input__button"
      type="button"
      :class="{ 'is-recording': recording }"
      :disabled="disabled || (!recording && !mediaRecorderSupported)"
      :aria-label="recording ? '停止语音输入' : '开始语音输入'"
      :aria-pressed="recording"
      @click="toggleRecording"
    >
      <Square v-if="recording" :size="17" aria-hidden="true" />
      <Mic v-else :size="18" aria-hidden="true" />
    </button>
    <p v-if="error" class="voice-input__error" role="alert">
      {{ error }}
    </p>
  </div>
</template>

<style scoped>
.voice-input {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.voice-input__button {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  padding: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.voice-input__button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.voice-input__button.is-recording {
  border-color: var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.voice-input__error {
  max-width: 28ch;
  margin: 0;
  color: var(--ark-paper);
  font-size: 0.78rem;
  line-height: 1.45;
  overflow-wrap: anywhere;
}
</style>
