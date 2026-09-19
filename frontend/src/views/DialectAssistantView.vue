<script setup lang="ts">
import { Send, Volume2 } from 'lucide-vue-next'
import { nextTick, ref } from 'vue'

import AppHeader from '@/components/AppHeader.vue'
import LocalResourcesNav from '@/components/LocalResourcesNav.vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useDialectAssistantStore } from '@/stores/dialectAssistant'

const store = useDialectAssistantStore()
const answerAudio = ref<HTMLAudioElement | null>(null)

async function handleRecorded(blob: Blob, filename: string) {
  const text = await store.transcribe(blob, filename)
  if (text) {
    store.recognizedText = text
  }
}

function handlePermissionDenied() {
  store.recording = false
  store.error = '未能识别，请重说或改用文字'
}

async function submitQuestion() {
  const question = store.recognizedText.trim()
  if (!question || store.loading) {
    return
  }

  const submitted = await store.submitTurn(question)
  if (!submitted) {
    return
  }

  await nextTick()
  try {
    await answerAudio.value?.play()
  } catch {
    // Keeping the native controls available is the autoplay fallback.
  }
}
</script>

<template>
  <div class="dialect-assistant">
    <AppHeader
      source="live"
      :loading="store.loading"
      :show-auth-controls="false"
    />
    <LocalResourcesNav />

    <main class="dialect-assistant__main">
      <header class="dialect-assistant__heading">
        <span class="dialect-assistant__code ark-data">
          06 / DIALECT ASSISTANT
        </span>
        <h1>方言助手</h1>
        <p>选择方言，通过语音或文字提问，并查看方言与普通话双语回答。</p>
      </header>

      <section
        class="dialect-assistant__workspace"
        aria-labelledby="dialect-workspace-title"
      >
        <header class="dialect-assistant__section-head">
          <span class="ark-data">VOICE INPUT</span>
          <h2 id="dialect-workspace-title">提问</h2>
        </header>

        <form class="dialect-form" @submit.prevent="submitQuestion">
          <div class="dialect-form__controls">
            <div class="dialect-field">
              <label for="dialect-code">方言</label>
              <select
                id="dialect-code"
                v-model="store.dialectCode"
                :disabled="store.loading"
              >
                <option value="yue">粤语</option>
                <option value="hak">客家话</option>
                <option value="nan">潮汕话</option>
              </select>
            </div>

            <div
              class="dialect-voice"
              data-test="dialect-voice-button"
              role="group"
              aria-labelledby="dialect-voice-label"
            >
              <VoiceInputButton
                :recording="store.recording"
                :disabled="store.loading"
                :error="store.error"
                @update:recording="store.recording = $event"
                @recorded="handleRecorded"
                @permission-denied="handlePermissionDenied"
              />
              <strong id="dialect-voice-label">语音提问</strong>
            </div>
          </div>

          <div class="dialect-field dialect-field--question">
            <label for="recognized-question">识别文本</label>
            <textarea
              id="recognized-question"
              v-model="store.recognizedText"
              rows="4"
              placeholder="识别结果会显示在这里，可在提交前修改"
            />
          </div>

          <div class="dialect-form__actions">
            <button
              class="dialect-form__submit"
              type="submit"
              :disabled="store.loading || !store.recognizedText.trim()"
            >
              <Send :size="17" aria-hidden="true" />
              提交问题
            </button>
          </div>
        </form>
      </section>

      <section
        v-if="store.lastTurn"
        class="dialect-answers"
        aria-labelledby="dialect-answers-title"
        aria-live="polite"
      >
        <header class="dialect-assistant__section-head">
          <span class="ark-data">DIALECT RESPONSE</span>
          <h2 id="dialect-answers-title">回答</h2>
        </header>

        <div class="dialect-answers__grid">
          <article class="dialect-answer" data-test="dialect-answer">
            <header class="dialect-answer__head">
              <span>方言原文</span>
              <Volume2 :size="18" aria-hidden="true" />
            </header>
            <p>{{ store.lastTurn.dialect_answer }}</p>
            <audio
              v-if="store.audioUrl"
              ref="answerAudio"
              :src="store.audioUrl"
              aria-label="播放方言回答音频"
              controls
              preload="metadata"
            />
          </article>

          <article class="dialect-answer" data-test="mandarin-answer">
            <header class="dialect-answer__head">
              <span>普通话对照</span>
            </header>
            <p>{{ store.lastTurn.mandarin_answer }}</p>
          </article>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.dialect-assistant {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.dialect-assistant__main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.dialect-assistant__heading {
  padding-bottom: 26px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.dialect-assistant__code,
.dialect-assistant__section-head > span {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.dialect-assistant__heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.dialect-assistant__heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dialect-assistant__workspace,
.dialect-answers {
  margin-top: 22px;
  border-top: 1px solid var(--ark-line-strong);
}

.dialect-assistant__section-head {
  display: grid;
  gap: 3px;
  padding: 18px 0 12px;
}

.dialect-assistant__section-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.dialect-form {
  display: grid;
  gap: 18px;
  min-width: 0;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dialect-form__controls {
  display: grid;
  grid-template-columns: minmax(180px, 0.32fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.dialect-field {
  display: grid;
  min-width: 0;
  gap: 8px;
}

.dialect-field > label {
  color: var(--ark-muted);
  font-size: 0.78rem;
}

.dialect-field select,
.dialect-field textarea {
  width: 100%;
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
}

.dialect-field select {
  min-height: 46px;
  padding: 0 11px;
}

.dialect-field textarea {
  min-height: 108px;
  padding: 11px 12px;
  line-height: 1.55;
  line-break: strict;
  overflow-wrap: anywhere;
  resize: vertical;
  text-wrap: pretty;
  word-break: keep-all;
}

.dialect-field textarea::placeholder {
  color: var(--ark-muted);
}

.dialect-voice {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 10px 14px;
  align-items: center;
  min-height: 80px;
  padding: 8px 12px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-1);
}

.dialect-voice :deep(.voice-input) {
  display: contents;
}

.dialect-voice :deep(.voice-input__button) {
  grid-row: 1;
  grid-column: 1;
  width: 64px;
  height: 64px;
}

.dialect-voice > strong {
  grid-row: 1;
  grid-column: 2;
  min-width: 0;
  font-size: 1.05rem;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dialect-voice :deep(.voice-input__error) {
  grid-row: 2;
  grid-column: 1 / -1;
  max-width: none;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  word-break: keep-all;
}

.dialect-field--question {
  max-width: 860px;
}

.dialect-form__actions {
  display: flex;
  justify-content: flex-end;
}

.dialect-form__submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-width: 132px;
  min-height: 46px;
  padding: 0 16px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
  transition:
    background var(--ark-transition),
    border-color var(--ark-transition),
    color var(--ark-transition);
}

.dialect-form__submit:hover:not(:disabled) {
  border-color: var(--ark-paper);
  background: var(--ark-paper);
}

.dialect-answers__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.dialect-answer {
  display: grid;
  min-width: 0;
  align-content: start;
  gap: 14px;
  padding: 20px;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.dialect-answer__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--ark-signal);
  font-size: 0.8rem;
  font-weight: 700;
}

.dialect-answer p {
  min-width: 0;
  margin: 0;
  line-break: strict;
  overflow-wrap: anywhere;
  text-wrap: pretty;
  white-space: pre-wrap;
  word-break: keep-all;
}

.dialect-answer audio {
  display: block;
  width: 100%;
  min-width: 0;
  min-height: 44px;
  margin-top: 2px;
}

@media (max-width: 720px) {
  .dialect-assistant__main {
    padding: 28px 14px 48px;
  }

  .dialect-assistant__heading h1 {
    font-size: 2.25rem;
  }

  .dialect-form {
    padding: 16px;
  }

  .dialect-form__controls {
    grid-template-columns: minmax(0, 1fr);
  }

  .dialect-answers__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .dialect-answer {
    padding: 16px;
  }

  .dialect-form__actions {
    justify-content: stretch;
  }

  .dialect-form__submit {
    width: 100%;
  }
}

@media (max-width: 360px) {
  .dialect-voice {
    grid-template-columns: 64px minmax(0, 1fr);
    gap: 10px;
    padding-inline: 10px;
  }
}
</style>
