<script setup lang="ts">
import { MessageCircleQuestion, RefreshCw, Send } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import type { QaConversation, QaTurn } from '@/api/types'
import AgriSkillsNav from '@/components/AgriSkillsNav.vue'
import AppHeader from '@/components/AppHeader.vue'
import VoiceInputButton from '@/components/VoiceInputButton.vue'
import { useAgriQaStore } from '@/stores/agriQa'
import { useAuthStore } from '@/stores/auth'

const qaStore = useAgriQaStore()
const auth = useAuthStore()
const router = useRouter()
const questionText = ref('')
const inputMode = ref<'text' | 'voice'>('text')

const orderedConversations = computed(() =>
  [...qaStore.conversations].sort((left, right) => {
    const timeDifference =
      Date.parse(right.updated_at) - Date.parse(left.updated_at)
    return Number.isNaN(timeDifference)
      ? right.id - left.id
      : timeDifference || right.id - left.id
  })
)

const orderedTurns = computed(() =>
  [...qaStore.turns].sort(
    (left, right) =>
      Date.parse(left.created_at) - Date.parse(right.created_at) ||
      left.id - right.id
  )
)

const voiceError = computed(() => {
  if (
    qaStore.error === '未能识别，请重试或改用文字输入' ||
    qaStore.error === 'AI 服务暂时不可用'
  ) {
    return qaStore.error
  }
  return ''
})

function formatConversationTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

function answerBody(turn: QaTurn): string {
  const marker = '离线知识库回答'
  return turn.answer.startsWith(marker)
    ? turn.answer.slice(marker.length).trimStart()
    : turn.answer
}

function handleTextInput() {
  inputMode.value = 'text'
  qaStore.error = ''
}

function handleRecordingChange(recording: boolean) {
  qaStore.recording = recording
}

async function handleRecorded(blob: Blob, filename: string) {
  inputMode.value = 'voice'
  const text = await qaStore.transcribe(blob, filename)
  if (text) {
    questionText.value = text
  }
}

function handlePermissionDenied() {
  qaStore.recording = false
  qaStore.error = '未能识别，请重试或改用文字输入'
}

async function submitQuestion() {
  const question = questionText.value.trim()
  if (!question || qaStore.loading) {
    return
  }
  const succeeded = await qaStore.ask(question, inputMode.value)
  if (succeeded) {
    questionText.value = ''
    inputMode.value = 'text'
  }
}

async function selectConversation(conversation: QaConversation) {
  questionText.value = ''
  inputMode.value = 'text'
  await qaStore.openConversation(conversation.id)
}

async function selectSuggestion(suggestion: string) {
  questionText.value = suggestion
  inputMode.value = 'text'
  const succeeded = await qaStore.useSuggestion(suggestion)
  if (succeeded) {
    questionText.value = ''
  }
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}

onMounted(() => {
  void qaStore.loadConversations()
})
</script>

<template>
  <div class="agri-qa-page">
    <AppHeader
      source="live"
      :loading="qaStore.loading"
      :user-name="auth.user?.name"
      @logout="logout"
    />
    <AgriSkillsNav />

    <main class="agri-qa-main">
      <header class="agri-qa-heading">
        <span class="agri-qa-heading__code ark-data">03 / AGRICULTURAL Q&amp;A</span>
        <h1>农技问答</h1>
        <p>输入农技问题，获得流式回答、追问建议与完整问答记录。</p>
      </header>

      <div class="agri-qa-workspace">
        <aside class="conversation-history" aria-labelledby="qa-history-title">
          <div class="conversation-history__head">
            <h2 id="qa-history-title">问答记录</h2>
            <button
              type="button"
              :disabled="qaStore.loading"
              aria-label="刷新问答记录"
              @click="qaStore.loadConversations"
            >
              <RefreshCw
                :size="16"
                :class="{ spinning: qaStore.loading }"
                aria-hidden="true"
              />
            </button>
          </div>

          <div v-if="orderedConversations.length" class="conversation-history__list">
            <button
              v-for="conversation in orderedConversations"
              :key="conversation.id"
              type="button"
              :class="{
                'is-active': conversation.id === qaStore.activeConversationId
              }"
              @click="selectConversation(conversation)"
            >
              <strong>{{ conversation.title }}</strong>
              <span class="ark-data">
                {{ formatConversationTime(conversation.updated_at) }}
              </span>
            </button>
          </div>
          <p v-else class="conversation-history__empty">暂无问答记录</p>
        </aside>

        <section class="qa-conversation" aria-labelledby="qa-conversation-title">
          <header class="qa-conversation__head">
            <div>
              <span class="ark-data">LIVE KNOWLEDGE CHANNEL</span>
              <h2 id="qa-conversation-title">
                {{ qaStore.activeConversationId ? '历史对话' : '新问答' }}
              </h2>
            </div>
            <MessageCircleQuestion :size="22" aria-hidden="true" />
          </header>

          <div class="qa-conversation__body">
            <div
              v-if="qaStore.loading && !orderedTurns.length && !qaStore.streamingText"
              class="qa-state"
            >
              <RefreshCw class="spinning" :size="19" aria-hidden="true" />
              <span>正在加载问答内容</span>
            </div>

            <div
              v-else-if="!orderedTurns.length && !qaStore.streamingText"
              class="qa-state"
            >
              <MessageCircleQuestion :size="22" aria-hidden="true" />
              <p>提交问题后，回答将在这里逐段显示。</p>
            </div>

            <ol v-if="orderedTurns.length" class="qa-turns">
              <li v-for="turn in orderedTurns" :key="turn.id">
                <article class="qa-bubble qa-bubble--question">
                  <span class="qa-bubble__label">提问</span>
                  <p>{{ turn.question }}</p>
                </article>
                <article
                  class="qa-bubble qa-bubble--answer"
                  :class="{ 'is-local': turn.answer_mode === 'local_kb' }"
                >
                  <span
                    v-if="turn.answer_mode === 'local_kb'"
                    class="qa-bubble__label"
                    data-test="local-answer"
                  >
                    离线知识库回答
                  </span>
                  <span v-else class="qa-bubble__label">AI 回答</span>
                  <p>{{ answerBody(turn) }}</p>
                </article>
              </li>
            </ol>

            <div
              class="qa-streaming"
              data-test="streaming-answer"
              aria-live="polite"
              :aria-busy="qaStore.loading && Boolean(qaStore.streamingText)"
            >
              <span v-if="qaStore.streamingText">{{ qaStore.streamingText }}</span>
            </div>

            <div
              v-if="qaStore.suggestionError"
              class="qa-inline-error"
              role="alert"
            >
              {{ qaStore.suggestionError }}
            </div>

            <div
              v-if="qaStore.suggestions.length"
              class="qa-suggestions"
              aria-label="追问建议"
            >
              <button
                v-for="(suggestion, index) in qaStore.suggestions.slice(0, 3)"
                :key="suggestion"
                type="button"
                :data-test="`suggestion-${index}`"
                :disabled="qaStore.loading"
                @click="selectSuggestion(suggestion)"
              >
                {{ suggestion }}
              </button>
            </div>

            <div
              v-if="qaStore.error && !voiceError"
              class="qa-inline-error"
              role="alert"
            >
              {{ qaStore.error }}
            </div>
          </div>

          <form class="qa-composer" @submit.prevent="submitQuestion">
            <label for="agri-qa-question">问题</label>
            <div class="qa-composer__row">
              <textarea
                id="agri-qa-question"
                v-model="questionText"
                data-test="question-input"
                rows="4"
                placeholder="例如：荔枝蒂蛀虫应该怎样防治？"
                :disabled="qaStore.loading"
                @input="handleTextInput"
              />
              <div class="qa-composer__actions">
                <VoiceInputButton
                  :recording="qaStore.recording"
                  :disabled="qaStore.loading"
                  :error="voiceError"
                  @update:recording="handleRecordingChange"
                  @recorded="handleRecorded"
                  @permission-denied="handlePermissionDenied"
                />
                <button
                  class="qa-composer__submit"
                  type="submit"
                  :disabled="qaStore.loading || !questionText.trim()"
                >
                  <Send :size="17" aria-hidden="true" />
                  发送
                </button>
              </div>
            </div>
          </form>
        </section>
      </div>
    </main>
  </div>
</template>

<style scoped>
.agri-qa-page {
  min-width: 0;
  min-height: 100svh;
  overflow-x: clip;
  background: var(--ark-ink);
}

.agri-qa-main {
  width: min(100%, 1180px);
  margin-inline: auto;
  padding: 40px 24px 72px;
}

.agri-qa-heading {
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ark-line-strong);
}

.agri-qa-heading__code {
  color: var(--ark-signal);
  font-size: 0.72rem;
}

.agri-qa-heading h1 {
  margin: 9px 0 0;
  font-size: 3rem;
  line-height: 1;
}

.agri-qa-heading p {
  max-width: 62ch;
  margin: 15px 0 0;
  color: var(--ark-muted);
}

.agri-qa-workspace {
  display: grid;
  grid-template-columns: minmax(220px, 270px) minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  margin-top: 22px;
}

.conversation-history,
.qa-conversation {
  min-width: 0;
  border: 1px solid var(--ark-line-strong);
  background: var(--ark-surface-0);
}

.conversation-history__head,
.qa-conversation__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  min-height: 62px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--ark-line);
}

.conversation-history__head h2,
.qa-conversation__head h2 {
  margin: 0;
  font-size: 1rem;
}

.conversation-history__head button {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  padding: 0;
  border: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
}

.conversation-history__head button:hover:not(:disabled) {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.conversation-history__list {
  display: grid;
}

.conversation-history__list button {
  display: grid;
  gap: 5px;
  width: 100%;
  min-width: 0;
  padding: 13px 16px;
  border: 0;
  border-bottom: 1px solid var(--ark-line);
  background: transparent;
  color: var(--ark-paper);
  text-align: left;
}

.conversation-history__list button:last-child {
  border-bottom: 0;
}

.conversation-history__list button:hover,
.conversation-history__list button.is-active {
  background: var(--ark-surface-1);
}

.conversation-history__list button.is-active {
  box-shadow: inset 3px 0 0 var(--ark-signal);
}

.conversation-history__list strong {
  overflow: hidden;
  font-size: 0.88rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conversation-history__list span,
.conversation-history__empty {
  color: var(--ark-muted);
  font-size: 0.72rem;
}

.conversation-history__empty {
  margin: 0;
  padding: 22px 16px;
}

.qa-conversation__head span {
  color: var(--ark-muted);
  font-size: 0.68rem;
}

.qa-conversation__head > svg {
  color: var(--ark-signal);
}

.qa-conversation__body {
  min-height: 320px;
  padding: 22px;
}

.qa-state {
  display: grid;
  place-items: center;
  align-content: center;
  gap: 11px;
  min-height: 270px;
  color: var(--ark-muted);
  text-align: center;
}

.qa-state p {
  max-width: 34ch;
  margin: 0;
  overflow-wrap: anywhere;
}

.qa-turns {
  display: grid;
  gap: 22px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.qa-turns > li {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.qa-bubble {
  min-width: 0;
  max-width: min(86%, 720px);
  padding: 13px 15px;
  border: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.qa-bubble--question {
  justify-self: end;
}

.qa-bubble--answer {
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-0);
}

.qa-bubble--answer.is-local {
  border-left-color: var(--ark-state);
  background: var(--ark-surface-1);
}

.qa-bubble__label {
  display: inline-block;
  margin-bottom: 7px;
  color: var(--ark-signal);
  font-size: 0.72rem;
  font-weight: 700;
}

.qa-bubble--answer.is-local .qa-bubble__label {
  color: var(--ark-state);
}

.qa-bubble p {
  margin: 0;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.qa-streaming {
  min-height: 0;
  margin-top: 14px;
  color: var(--ark-paper);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}

.qa-streaming:empty {
  min-height: 1px;
}

.qa-suggestions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 18px;
}

.qa-suggestions button {
  min-width: 0;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid var(--ark-line-strong);
  background: transparent;
  color: var(--ark-paper);
  font-size: 0.82rem;
  overflow-wrap: anywhere;
  text-align: left;
}

.qa-suggestions button:hover:not(:disabled),
.qa-suggestions button:focus-visible {
  border-color: var(--ark-signal);
  color: var(--ark-signal);
}

.qa-inline-error {
  margin-top: 14px;
  padding: 10px 12px;
  border-left: 3px solid var(--ark-signal);
  background: var(--ark-surface-1);
  color: var(--ark-paper);
  overflow-wrap: anywhere;
}

.qa-composer {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-top: 1px solid var(--ark-line);
  background: var(--ark-surface-1);
}

.qa-composer > label {
  color: var(--ark-muted);
  font-size: 0.76rem;
}

.qa-composer__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: stretch;
}

.qa-composer textarea {
  width: 100%;
  min-width: 0;
  min-height: 96px;
  padding: 11px 12px;
  border: 1px solid var(--ark-line-strong);
  border-radius: 0;
  background: var(--ark-surface-0);
  color: var(--ark-paper);
  line-height: 1.55;
  overflow-wrap: anywhere;
  resize: vertical;
}

.qa-composer textarea::placeholder {
  color: var(--ark-muted);
}

.qa-composer__actions {
  display: grid;
  grid-template-columns: 46px;
  align-content: start;
  gap: 8px;
}

.qa-composer__submit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 96px;
  min-height: 42px;
  padding: 0 13px;
  border: 1px solid var(--ark-signal);
  background: var(--ark-signal);
  color: var(--ark-surface-0);
}

.qa-composer__submit:hover:not(:disabled) {
  background: var(--ark-paper);
  border-color: var(--ark-paper);
}

.spinning {
  animation: spin 900ms linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 760px) {
  .agri-qa-main {
    padding: 28px 14px 48px;
  }

  .agri-qa-heading h1 {
    font-size: 2.25rem;
  }

  .agri-qa-workspace {
    grid-template-columns: minmax(0, 1fr);
  }

  .conversation-history__list {
    grid-auto-columns: minmax(190px, 72%);
    grid-auto-flow: column;
    overflow-x: auto;
    scrollbar-width: thin;
  }

  .conversation-history__list button {
    border-right: 1px solid var(--ark-line);
    border-bottom: 0;
  }

  .qa-conversation__body {
    padding: 18px 14px;
  }

  .qa-bubble {
    max-width: 100%;
  }

  .qa-suggestions {
    grid-template-columns: minmax(0, 1fr);
  }

  .qa-composer {
    padding: 14px;
  }

  .qa-composer__row {
    grid-template-columns: minmax(0, 1fr);
  }

  .qa-composer__actions {
    grid-template-columns: 46px minmax(0, 1fr);
    align-items: start;
  }

  .qa-composer__submit {
    width: 100%;
  }
}
</style>
