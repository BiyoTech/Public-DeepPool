<template>
  <div class="flex h-[calc(100vh-4rem)] overflow-hidden">
    <!-- ── Left sidebar: chat history ── -->
    <aside
      class="flex-shrink-0 w-64 bg-slate-50 border-r border-slate-200 flex flex-col transition-all duration-300"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'"
    >
      <!-- New chat button -->
      <div class="p-3 border-b border-slate-200">
        <button
          class="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg border border-slate-200 text-sm font-medium text-dp-title hover:bg-white hover:shadow-sm transition-all"
          @click="handleNewChat"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          {{ $t('misszhao.new_chat') }}
        </button>
      </div>

      <!-- Chat history list -->
      <div class="flex-1 overflow-y-auto p-3">
        <h3 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-2 px-1">
          {{ $t('misszhao.history') }}
        </h3>
        <div v-if="!chatSessions.length" class="text-xs text-dp-muted px-1 py-4 text-center">
          {{ $t('misszhao.no_history') }}
        </div>
        <div
          v-for="(session, idx) in chatSessions"
          :key="idx"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm cursor-pointer transition-colors mb-0.5"
          :class="
            idx === activeSessionIdx
              ? 'bg-white shadow-sm text-dp-title font-medium'
              : 'text-dp-muted hover:bg-white/60 hover:text-dp-title'
          "
          @click="switchSession(idx)"
        >
          <svg
            class="w-4 h-4 flex-shrink-0 opacity-50"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"
            />
          </svg>
          <span class="truncate">{{ session.title }}</span>
        </div>
      </div>
    </aside>

    <!-- Mobile sidebar overlay -->
    <div v-if="sidebarOpen" class="fixed inset-0 bg-black/30 z-40 md:hidden" @click="sidebarOpen = false" />

    <!-- ── Center: main chat area ── -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Mobile top bar -->
      <div class="md:hidden flex items-center gap-3 px-4 py-2 border-b border-slate-200 bg-white">
        <button @click="sidebarOpen = !sidebarOpen" class="text-dp-muted hover:text-dp-title">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        <span class="text-sm font-medium text-dp-title">{{ $t('misszhao.title') }}</span>
      </div>

      <!-- Model & API Key config bar -->
      <div class="border-b border-slate-100 bg-white px-4 py-2.5">
        <div class="max-w-3xl mx-auto flex flex-wrap items-center gap-3">
          <!-- Model selector -->
          <div class="flex items-center gap-2">
            <label class="text-xs font-medium text-dp-muted whitespace-nowrap">{{ $t('misszhao.select_model') }}</label>
            <div class="relative" ref="modelDropdownRef">
              <button
                type="button"
                :disabled="!availableModels.length"
                class="min-w-[280px] flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg border text-sm text-left focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-dp-placeholder"
                :class="
                  modelDropdownOpen ? 'border-dp-blue ring-2 ring-blue-100 bg-white' : 'border-slate-200 bg-white'
                "
                @click="modelDropdownOpen = !modelDropdownOpen"
              >
                <span v-if="!availableModels.length" class="text-dp-placeholder truncate">{{
                  $t('misszhao.no_models')
                }}</span>
                <template v-else-if="selectedModelOption">
                  <span class="truncate text-dp-body">{{ selectedModelOption.id }}</span>
                  <span
                    :class="vendorTypeTagClass(selectedModelOption.vendor_type)"
                    class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  >
                    {{ vendorTypeLabel(selectedModelOption.vendor_type) }}
                  </span>
                </template>
                <span v-else class="text-dp-placeholder truncate">{{ $t('misszhao.select_model') }}</span>
                <svg
                  class="w-4 h-4 shrink-0 text-slate-400 transition-transform"
                  :class="{ 'rotate-180': modelDropdownOpen }"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <Transition
                enter-active-class="transition duration-100 ease-out"
                enter-from-class="opacity-0 -translate-y-1"
                enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition duration-75 ease-in"
                leave-from-class="opacity-100 translate-y-0"
                leave-to-class="opacity-0 -translate-y-1"
              >
                <ul
                  v-if="modelDropdownOpen"
                  class="absolute z-50 mt-1 max-h-64 w-full min-w-[280px] overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                >
                  <li
                    v-for="m in availableModels"
                    :key="m.id"
                    class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50"
                    :class="m.id === selectedModel ? 'bg-blue-50 text-dp-blue font-medium' : 'text-dp-body'"
                    @click="selectModel(m.id)"
                  >
                    <span class="truncate">{{ m.id }}</span>
                    <span
                      :class="vendorTypeTagClass(m.vendor_type)"
                      class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                    >
                      {{ vendorTypeLabel(m.vendor_type) }}
                    </span>
                  </li>
                </ul>
              </Transition>
            </div>
          </div>

          <!-- API Key selector -->
          <div class="flex items-center gap-2">
            <label class="text-xs font-medium text-dp-muted whitespace-nowrap">API Key</label>
            <template v-if="apiKeys.length">
              <select
                v-model="selectedKeyId"
                class="min-w-[160px] px-2.5 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body bg-white focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
                @change="onKeyChange"
              >
                <option v-for="k in apiKeys" :key="k.id" :value="k.id">{{ k.name }} ({{ k.key_prefix }}...)</option>
              </select>
            </template>
            <template v-else>
              <router-link
                to="/service"
                class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 text-xs font-medium text-dp-blue hover:bg-blue-100 transition-colors"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
                  />
                </svg>
                {{ $t('misszhao.create_apikey') }}
              </router-link>
            </template>
          </div>

          <!-- File panel toggle -->
          <button
            class="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
            :class="
              filePanelOpen ? 'bg-dp-blue/10 text-dp-blue' : 'text-dp-muted hover:bg-slate-100 hover:text-dp-title'
            "
            @click="filePanelOpen = !filePanelOpen"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"
              />
            </svg>
            {{ $t('misszhao.output_files') }}
          </button>
        </div>
      </div>

      <!-- Messages area -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto">
        <!-- Welcome screen -->
        <div v-if="!messages.length" class="flex flex-col items-center justify-center h-full px-6 py-12">
          <div class="max-w-2xl w-full text-center">
            <img src="/misszhao.png" alt="misszhao" class="w-16 h-16 mx-auto mb-6 rounded-2xl shadow-lg object-cover" />
            <h2 class="text-2xl font-bold text-dp-title mb-3">{{ $t('misszhao.welcome_title') }}</h2>
            <p class="text-dp-muted mb-8 leading-relaxed">{{ $t('misszhao.welcome_desc') }}</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg mx-auto">
              <button
                v-for="(example, idx) in exampleQuestions"
                :key="idx"
                class="text-left p-4 rounded-xl border border-slate-200 hover:border-dp-blue/30 hover:bg-blue-50/30 hover:shadow-sm transition-all text-sm text-dp-body leading-relaxed"
                @click="sendExample(example)"
              >
                {{ example }}
              </button>
            </div>
          </div>
        </div>

        <!-- Message list -->
        <div v-else class="max-w-3xl mx-auto px-4 py-6 space-y-6">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="flex gap-3"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <!-- AI avatar -->
            <img
              v-if="msg.role === 'assistant'"
              src="/misszhao.png"
              alt="misszhao"
              class="flex-shrink-0 w-8 h-8 rounded-lg object-cover mt-0.5"
            />

            <!-- Message bubble -->
            <div
              class="max-w-[80%] rounded-2xl px-4 py-3"
              :class="
                msg.role === 'user'
                  ? 'bg-dp-blue text-white rounded-br-md'
                  : 'bg-white border border-slate-200 shadow-sm rounded-bl-md'
              "
            >
              <!-- User message -->
              <div v-if="msg.role === 'user'" class="text-sm leading-relaxed whitespace-pre-wrap">
                {{ msg.content }}
              </div>

              <!-- AI message with execution steps -->
              <div v-else>
                <!-- Execution progress panel -->
                <ExecutionSteps
                  v-if="msg.steps.length"
                  :steps="msg.steps"
                  :is-active="isStreaming && idx === messages.length - 1"
                />
                <!-- Markdown content -->
                <MarkdownRenderer v-if="msg.content" :content="msg.content" />
                <!-- Copy button -->
                <div v-if="msg.content && !isStreaming" class="flex justify-end mt-2 -mb-1">
                  <button
                    class="text-xs text-dp-muted hover:text-dp-title transition-colors flex items-center gap-1"
                    @click="copyMessage(msg.content)"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
                      />
                    </svg>
                    {{ $t('misszhao.copy_code') }}
                  </button>
                </div>
              </div>
            </div>

            <!-- User avatar -->
            <div
              v-if="msg.role === 'user'"
              class="flex-shrink-0 w-8 h-8 rounded-lg bg-slate-200 flex items-center justify-center mt-0.5"
            >
              <svg
                class="w-4 h-4 text-slate-500"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                />
              </svg>
            </div>
          </div>

          <!-- Loading animation -->
          <div v-if="isStreaming && !streamingContent && !currentSteps.length" class="flex gap-3 justify-start">
            <img src="/misszhao.png" alt="misszhao" class="flex-shrink-0 w-8 h-8 rounded-lg object-cover" />
            <div class="bg-white border border-slate-200 shadow-sm rounded-2xl rounded-bl-md px-4 py-3">
              <div class="flex items-center gap-1.5">
                <span class="text-xs text-dp-muted">{{ $t('misszhao.thinking') }}</span>
                <div class="flex gap-1">
                  <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 0ms" />
                  <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 150ms" />
                  <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 300ms" />
                </div>
              </div>
            </div>
          </div>

          <!-- Error message -->
          <div v-if="errorMessage" class="flex gap-3 justify-start">
            <div class="flex-shrink-0 w-8 h-8 rounded-lg bg-red-100 flex items-center justify-center">
              <svg class="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
            </div>
            <div class="bg-red-50 border border-red-200 rounded-2xl rounded-bl-md px-4 py-3 max-w-[80%]">
              <p class="text-sm text-red-600 mb-2">{{ errorMessage }}</p>
              <button
                class="text-xs font-medium text-red-500 hover:text-red-700 transition-colors flex items-center gap-1"
                @click="retryLastMessage"
              >
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"
                  />
                </svg>
                {{ $t('misszhao.retry') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Bottom input area ── -->
      <div class="border-t border-slate-200 bg-white px-4 py-3">
        <div class="max-w-3xl mx-auto">
          <div class="flex items-end gap-3">
            <div class="flex-1 relative">
              <textarea
                ref="inputRef"
                v-model="inputText"
                :placeholder="$t('misszhao.input_placeholder')"
                class="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm text-dp-body placeholder:text-dp-muted/50 focus:outline-none focus:ring-2 focus:ring-dp-blue/20 focus:border-dp-blue/40 transition-all"
                :style="{ height: inputHeight + 'px' }"
                rows="1"
                @input="autoResize"
                @keydown="handleKeydown"
              />
            </div>

            <!-- Send / Stop button -->
            <button
              v-if="isStreaming"
              class="flex-shrink-0 w-10 h-10 rounded-xl bg-red-500 hover:bg-red-600 text-white flex items-center justify-center transition-colors shadow-sm"
              @click="stopStreaming"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
            </button>
            <button
              v-else
              class="flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors shadow-sm"
              :class="
                inputText.trim()
                  ? 'bg-dp-blue hover:bg-dp-blue-dark text-white'
                  : 'bg-slate-100 text-slate-300 cursor-not-allowed'
              "
              :disabled="!inputText.trim()"
              @click="handleSend"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Right panel: workspace file browser ── -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      enter-from-class="w-0 opacity-0"
      enter-to-class="w-80 opacity-100"
      leave-active-class="transition-all duration-150 ease-in"
      leave-from-class="w-80 opacity-100"
      leave-to-class="w-0 opacity-0"
    >
      <aside
        v-if="filePanelOpen"
        class="flex-shrink-0 w-80 border-l border-slate-200 bg-white flex flex-col overflow-hidden"
      >
        <!-- Header -->
        <div class="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-dp-title">{{ $t('misszhao.output_files') }}</h3>
          <button class="text-dp-muted hover:text-dp-title transition-colors p-1 rounded" @click="refreshFiles">
            <svg
              class="w-4 h-4"
              :class="{ 'animate-spin': filesLoading }"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"
              />
            </svg>
          </button>
        </div>

        <!-- Search -->
        <div class="px-4 py-2">
          <input
            v-model="fileSearchQuery"
            type="text"
            :placeholder="$t('misszhao.search_files')"
            class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-xs bg-slate-50 text-dp-body placeholder:text-dp-muted/50 focus:outline-none focus:border-dp-blue/40 focus:ring-1 focus:ring-dp-blue/20"
          />
        </div>

        <!-- File type tabs -->
        <div class="px-4 pb-2 flex gap-1 flex-wrap">
          <button
            v-for="tab in fileTypeTabs"
            :key="tab.key"
            class="px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors"
            :class="
              activeFileTab === tab.key ? 'bg-dp-blue text-white' : 'bg-slate-100 text-dp-muted hover:bg-slate-200'
            "
            @click="activeFileTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <!-- File list -->
        <div class="flex-1 overflow-y-auto px-2">
          <div v-if="filesLoading" class="flex items-center justify-center py-8">
            <div class="flex gap-1">
              <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 0ms" />
              <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 150ms" />
              <span class="w-1.5 h-1.5 bg-dp-blue/40 rounded-full animate-bounce" style="animation-delay: 300ms" />
            </div>
          </div>
          <div v-else-if="!filteredFiles.length" class="text-xs text-dp-muted text-center py-8">
            {{ $t('misszhao.no_files') }}
          </div>
          <FileTreeNode v-for="entry in filteredFiles" :key="entry.path" :entry="entry" />
        </div>
      </aside>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import ExecutionSteps from '@/components/ExecutionSteps.vue'
import type { ExecutionStep } from '@/components/ExecutionSteps.vue'
import FileTreeNode from '@/components/FileTreeNode.vue'
import {
  sendMessage,
  getChatHistory,
  createNewChat,
  listWorkspaceFiles,
  type ChatMessage,
  type StreamCallbacks,
  type AgentEvent,
  type FileEntry,
} from '@/api/misszhao'
import { listAPIKeys, fetchKeySecret, type APIKey } from '@/api/apikey'

const { t } = useI18n()

// ── Display message with execution steps ──

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  steps: ExecutionStep[]
}

interface ChatSession {
  title: string
  messages: DisplayMessage[]
}

// ── Model & API Key state ──

interface GatewayModel {
  id: string
  vendor_type?: string
}

const availableModels = ref<GatewayModel[]>([])
const selectedModel = ref('')
const selectedModelOption = computed(() => availableModels.value.find((m) => m.id === selectedModel.value) || null)
const apiKeys = ref<APIKey[]>([])
const selectedKeyId = ref<number | null>(null)

const modelDropdownOpen = ref(false)
const modelDropdownRef = ref<HTMLElement>()

function selectModel(id: string) {
  selectedModel.value = id
  modelDropdownOpen.value = false
  persistModelSelection()
}

function vendorTypeTagClass(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider':
      return 'bg-emerald-100 text-emerald-700'
    case 'hybrid':
      return 'bg-amber-100 text-amber-700'
    default:
      return 'bg-blue-100 text-dp-blue'
  }
}

function vendorTypeLabel(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider':
      return 'Provider'
    case 'hybrid':
      return 'Hybrid'
    default:
      return 'DeepNode'
  }
}

function handleClickOutsideDropdown(e: MouseEvent) {
  if (modelDropdownRef.value && !modelDropdownRef.value.contains(e.target as Node)) {
    modelDropdownOpen.value = false
  }
}

const keySecretCache = ref<Record<string, string>>({})
const GATEWAY_BASE = import.meta.env.VITE_GATEWAY_BASE_URL || window.location.origin + '/v1'
const SELECTED_MODEL_KEY = 'dp_misszhao_selected_model'
const SELECTED_KEY_KEY = 'dp_misszhao_selected_key_id'

async function fetchModels() {
  const res = await fetch(`${GATEWAY_BASE}/models`)
  if (!res.ok) return
  const json = await res.json()
  const items = Array.isArray(json?.data) ? json.data : []
  availableModels.value = items
    .map((m: any) => ({ id: String(m.id || '').trim(), vendor_type: String(m.vendor_type || '').trim() }))
    .filter((m: GatewayModel) => m.id)
    .sort((a: GatewayModel, b: GatewayModel) => a.id.localeCompare(b.id))

  const saved = localStorage.getItem(SELECTED_MODEL_KEY)
  if (saved && availableModels.value.some((m) => m.id === saved)) {
    selectedModel.value = saved
  } else if (availableModels.value.length) {
    selectedModel.value = availableModels.value[0].id
  }
}

async function fetchKeys() {
  const res = await listAPIKeys()
  apiKeys.value = res.data?.data || []
  const saved = localStorage.getItem(SELECTED_KEY_KEY)
  const savedId = saved ? Number(saved) : null
  if (savedId && apiKeys.value.some((k) => k.id === savedId)) {
    selectedKeyId.value = savedId
  } else if (apiKeys.value.length) {
    selectedKeyId.value = apiKeys.value[0].id
  }
}

function onKeyChange() {
  if (selectedKeyId.value !== null) {
    localStorage.setItem(SELECTED_KEY_KEY, String(selectedKeyId.value))
  }
}

async function getActiveApiKey(): Promise<string | null> {
  if (selectedKeyId.value === null) return null
  const cacheKey = String(selectedKeyId.value)
  if (keySecretCache.value[cacheKey]) return keySecretCache.value[cacheKey]
  const res = await fetchKeySecret(selectedKeyId.value)
  const fullKey = res.data?.data?.full_key
  if (fullKey) {
    keySecretCache.value[cacheKey] = fullKey
    return fullKey
  }
  return null
}

function persistModelSelection() {
  if (selectedModel.value) localStorage.setItem(SELECTED_MODEL_KEY, selectedModel.value)
}

// ── Chat state ──

const messages = ref<DisplayMessage[]>([])
const inputText = ref('')
const inputHeight = ref(44)
const isStreaming = ref(false)
const streamingContent = ref('')
const currentSteps = ref<ExecutionStep[]>([])
const errorMessage = ref('')
const sidebarOpen = ref(false)
const chatSessions = reactive<ChatSession[]>([])
const activeSessionIdx = ref(-1)
// Track active conversation thread_id from backend
const currentThreadId = ref<string>('')

const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
let currentAbortController: AbortController | null = null

// ── File panel state ──

const filePanelOpen = ref(false)
const workspaceFiles = ref<FileEntry[]>([])
const filesLoading = ref(false)
const fileSearchQuery = ref('')
const activeFileTab = ref('all')

const fileTypeTabs = computed(() => [
  { key: 'all', label: t('misszhao.file_tab_all') },
  { key: 'document', label: t('misszhao.file_tab_doc') },
  { key: 'image', label: t('misszhao.file_tab_image') },
  { key: 'spreadsheet', label: t('misszhao.file_tab_sheet') },
  { key: 'code', label: t('misszhao.file_tab_code') },
  { key: 'other', label: t('misszhao.file_tab_other') },
])

/** Filter workspace files by search query and file type tab */
const filteredFiles = computed(() => {
  let files = workspaceFiles.value
  if (activeFileTab.value !== 'all') {
    files = filterByType(files, activeFileTab.value)
  }
  if (fileSearchQuery.value.trim()) {
    files = filterByName(files, fileSearchQuery.value.trim().toLowerCase())
  }
  return files
})

function filterByType(entries: FileEntry[], type: string): FileEntry[] {
  const result: FileEntry[] = []
  for (const e of entries) {
    if (e.is_dir) {
      const children = e.children ? filterByType(e.children, type) : []
      if (children.length) result.push({ ...e, children })
    } else if (e.file_type === type) {
      result.push(e)
    }
  }
  return result
}

function filterByName(entries: FileEntry[], query: string): FileEntry[] {
  const result: FileEntry[] = []
  for (const e of entries) {
    if (e.name.toLowerCase().includes(query)) {
      result.push(e)
    } else if (e.is_dir && e.children) {
      const children = filterByName(e.children, query)
      if (children.length) result.push({ ...e, children })
    }
  }
  return result
}

async function refreshFiles() {
  filesLoading.value = true
  try {
    const resp = await listWorkspaceFiles()
    workspaceFiles.value = resp.files
  } catch {
    // Silent on error
  } finally {
    filesLoading.value = false
  }
}

// ── Example questions ──

const exampleQuestions = computed(() => [
  t('misszhao.example1'),
  t('misszhao.example2'),
  t('misszhao.example3'),
  t('misszhao.example4'),
])

// ── Lifecycle ──

onMounted(async () => {
  document.addEventListener('click', handleClickOutsideDropdown)
  await Promise.all([fetchModels(), fetchKeys(), loadHistory(), refreshFiles()])
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutsideDropdown)
})

// ── Chat history ──

async function loadHistory() {
  try {
    // Pass currentThreadId to load only the active conversation's messages
    const threadId = currentThreadId.value || undefined
    const history = await getChatHistory(50, threadId)
    if (history.length) {
      const displayMessages: DisplayMessage[] = history.map((m: ChatMessage) => ({
        role: m.role,
        content: m.content,
        steps: [],
      }))
      messages.value = displayMessages

      const firstUserMsg = displayMessages.find((m) => m.role === 'user')
      chatSessions.push({
        title: firstUserMsg ? firstUserMsg.content.slice(0, 30) : t('misszhao.new_chat'),
        messages: [...displayMessages],
      })
      activeSessionIdx.value = 0

      await nextTick()
      scrollToBottom()
    }
  } catch {
    // Silent
  }
}

// ── Execution step helpers ──

function formatDuration(ms: number): string {
  const sec = Math.floor(ms / 1000)
  const min = Math.floor(sec / 60)
  const s = sec % 60
  return min > 0
    ? `${min.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `00:${s.toString().padStart(2, '0')}`
}

function makeStepLabel(event: AgentEvent): string {
  switch (event.type) {
    case 'tool_called':
      return event.tool_name
    case 'tool_output':
      return t('misszhao.step_tool_output')
    case 'reasoning':
      return t('misszhao.step_reasoning')
    case 'handoff':
      return `${event.source_agent} → ${event.target_agent}`
    case 'agent_updated':
      return event.agent_name
    default:
      return ''
  }
}

function makeStepDetail(event: AgentEvent): string {
  switch (event.type) {
    case 'tool_called': {
      try {
        const args = JSON.parse(event.arguments)
        return Object.entries(args)
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ')
      } catch {
        return event.arguments
      }
    }
    case 'tool_output':
      return event.output.slice(0, 200)
    case 'reasoning':
      return event.content.slice(0, 200)
    case 'handoff':
      return ''
    case 'agent_updated':
      return ''
    default:
      return ''
  }
}

function handleAgentEvent(event: AgentEvent) {
  const now = Date.now()

  // Mark previous running step as done
  if (event.type === 'tool_output') {
    const toolStep = currentSteps.value.find((s) => s.type === 'tool_called' && s.status === 'running')
    if (toolStep) {
      toolStep.status = 'done'
      toolStep.duration = formatDuration(now - toolStep.startTime)
    }
    // Don't add tool_output as a separate step — just update the tool_called step
    updateAiMessageSteps()
    return
  }

  // Mark all running steps as done when new step starts
  for (const s of currentSteps.value) {
    if (s.status === 'running') {
      s.status = 'done'
      if (!s.duration) s.duration = formatDuration(now - s.startTime)
    }
  }

  const step: ExecutionStep = {
    type: event.type,
    label: makeStepLabel(event),
    detail: makeStepDetail(event),
    status: 'running',
    startTime: now,
    duration: '',
  }

  currentSteps.value.push(step)
  updateAiMessageSteps()
  scrollToBottom()
}

function updateAiMessageSteps() {
  const aiMsg = messages.value[messages.value.length - 1]
  if (aiMsg && aiMsg.role === 'assistant') {
    aiMsg.steps = [...currentSteps.value]
  }
}

// ── Send message ──

function handleSend() {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return
  doSend(text)
}

function sendExample(text: string) {
  doSend(text)
}

async function doSend(text: string) {
  errorMessage.value = ''
  inputText.value = ''
  inputHeight.value = 44

  if (!selectedModel.value) {
    errorMessage.value = t('misszhao.error_no_model')
    return
  }
  persistModelSelection()

  const apiKey = await getActiveApiKey()
  if (!apiKey) {
    errorMessage.value = t('misszhao.error_no_apikey')
    return
  }

  messages.value.push({ role: 'user', content: text, steps: [] })

  if (activeSessionIdx.value === -1 || !chatSessions.length) {
    chatSessions.unshift({ title: text.slice(0, 30), messages: [] })
    activeSessionIdx.value = 0
  }
  if (chatSessions[activeSessionIdx.value]) {
    chatSessions[activeSessionIdx.value].messages = [...messages.value]
  }

  scrollToBottom()

  isStreaming.value = true
  streamingContent.value = ''
  currentSteps.value = []
  messages.value.push({ role: 'assistant', content: '', steps: [] })
  const aiMsgIdx = messages.value.length - 1

  const callbacks: StreamCallbacks = {
    onContent(chunk: string) {
      streamingContent.value += chunk
      messages.value[aiMsgIdx].content = streamingContent.value
      scrollToBottom()
    },
    onEvent(event: AgentEvent) {
      handleAgentEvent(event)
    },
    onDone() {
      // Mark all remaining running steps as done
      const now = Date.now()
      for (const s of currentSteps.value) {
        if (s.status === 'running') {
          s.status = 'done'
          if (!s.duration) s.duration = formatDuration(now - s.startTime)
        }
      }
      updateAiMessageSteps()

      isStreaming.value = false
      if (chatSessions[activeSessionIdx.value]) {
        chatSessions[activeSessionIdx.value].messages = [...messages.value]
      }
      scrollToBottom()

      // Refresh files after agent completes
      refreshFiles()
    },
    onError(error: string) {
      isStreaming.value = false
      if (messages.value[aiMsgIdx] && !messages.value[aiMsgIdx].content && !messages.value[aiMsgIdx].steps.length) {
        messages.value.splice(aiMsgIdx, 1)
      }
      errorMessage.value = error
      scrollToBottom()
    },
  }

  currentAbortController = sendMessage(text, callbacks, {
    model: selectedModel.value,
    apiKey: apiKey,
  })
}

// ── Stop streaming ──

function stopStreaming() {
  if (currentAbortController) {
    currentAbortController.abort()
    currentAbortController = null
  }
  isStreaming.value = false
}

// ── Retry ──

function retryLastMessage() {
  errorMessage.value = ''
  const lastUserMsg = [...messages.value].reverse().find((m) => m.role === 'user')
  if (lastUserMsg) {
    const lastUserIdx = messages.value.lastIndexOf(lastUserMsg)
    messages.value.splice(lastUserIdx, 1)
    doSend(lastUserMsg.content)
  }
}

// ── New chat ──

async function handleNewChat() {
  stopStreaming()
  errorMessage.value = ''

  // Request backend to create new conversation with a fresh thread_id
  try {
    const result = await createNewChat()
    currentThreadId.value = result.thread_id
  } catch {
    // Clear frontend state even if backend fails
  }

  if (messages.value.length && activeSessionIdx.value >= 0) {
    chatSessions[activeSessionIdx.value].messages = [...messages.value]
  }

  messages.value = []
  streamingContent.value = ''
  currentSteps.value = []
  activeSessionIdx.value = -1
  sidebarOpen.value = false
}

// ── Switch session ──

function switchSession(idx: number) {
  if (idx === activeSessionIdx.value) return

  if (activeSessionIdx.value >= 0 && chatSessions[activeSessionIdx.value]) {
    chatSessions[activeSessionIdx.value].messages = [...messages.value]
  }

  activeSessionIdx.value = idx
  messages.value = [...chatSessions[idx].messages]
  errorMessage.value = ''
  sidebarOpen.value = false

  nextTick(() => scrollToBottom())
}

// ── Input auto-resize ──

function autoResize() {
  const el = inputRef.value
  if (!el) return
  el.style.height = '44px'
  const newHeight = Math.min(el.scrollHeight, 200)
  inputHeight.value = newHeight
}

// ── Keyboard events ──

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// ── Scroll to bottom ──

function scrollToBottom() {
  nextTick(() => {
    const container = messagesContainer.value
    if (container) container.scrollTop = container.scrollHeight
  })
}

// ── Copy message ──

async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content)
  } catch {
    /* Silent */
  }
}
</script>
