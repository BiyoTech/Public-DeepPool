<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Global toast notification -->
    <div
      v-if="toast"
      class="fixed top-6 left-1/2 z-[60] -translate-x-1/2 rounded-xl px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300"
      :class="toast.type === 'success' ? 'bg-emerald-500' : 'bg-slate-700'"
    >
      {{ toast.message }}
    </div>

    <div class="max-w-7xl mx-auto px-6 py-8">
      <!-- Page header with Create Custom Model shortcut -->
      <div class="flex items-center justify-between mb-2">
        <h1 class="text-2xl font-bold text-dp-title">{{ $t('service.title') }}</h1>
        <button
          @click="showCustomModelCreate = true"
          class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition shadow-sm"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {{ $t('service.mymodels.create_custom') }}
        </button>
      </div>

      <!-- ===== Top-level Tabs ===== -->
      <div class="flex items-center gap-1 border-b border-slate-200 mb-6">
        <button
          @click="activePageTab = 'apikeys'"
          class="px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="
            activePageTab === 'apikeys'
              ? 'border-dp-blue text-dp-blue'
              : 'border-transparent text-dp-muted hover:text-dp-body'
          "
        >
          API Key
        </button>
        <button
          @click="activePageTab = 'playground'"
          class="px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="
            activePageTab === 'playground'
              ? 'border-dp-blue text-dp-blue'
              : 'border-transparent text-dp-muted hover:text-dp-body'
          "
        >
          Playground
        </button>
      </div>

      <!-- ===== TAB: API Key Management ===== -->
      <div v-show="activePageTab === 'apikeys'">
        <ApiKeyManager
          ref="apiKeyManagerRef"
          :available-models="playgroundAvailableModels"
          @toast="showToast"
          @keys-changed="onKeysChanged"
        />
      </div>

      <!-- ===== TAB: Playground ===== -->
      <div v-show="activePageTab === 'playground'">
        <PlaygroundPanel ref="playgroundRef" :api-keys="apiKeys" :get-full-key="getFullKey" @toast="showToast" />
      </div>
    </div>

    <!-- Custom Model Create/Edit Drawer -->
    <CustomModelDialog
      :visible="showCustomModelCreate"
      :custom-models="customModels"
      @close="showCustomModelCreate = false"
      @saved="onCustomModelSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { listCustomModels, type CustomModel } from '@/api/custom-model'
import type { APIKey } from '@/api/apikey'
import ApiKeyManager from '@/components/ApiKeyManager.vue'
import PlaygroundPanel from '@/components/PlaygroundPanel.vue'
import CustomModelDialog from '@/components/CustomModelDialog.vue'

// ── Top-level page tab state ──
const activePageTab = ref<'apikeys' | 'playground'>('apikeys')

// ── Component refs ──
const apiKeyManagerRef = ref<InstanceType<typeof ApiKeyManager>>()
const playgroundRef = ref<InstanceType<typeof PlaygroundPanel>>()

// ── Shared state: API Keys (owned by ApiKeyManager, synced via events) ──
const apiKeys = ref<APIKey[]>([])

function onKeysChanged(keys: APIKey[]) {
  apiKeys.value = keys
  // Sync playground's API Key selector
  playgroundRef.value?.syncSelectedAPIKey()
}

/** Delegate full key resolution to ApiKeyManager. */
async function getFullKey(id: number): Promise<string | null> {
  return apiKeyManagerRef.value?.getFullKey(id) ?? null
}

// ── Available models for guardrail evaluator selector (from PlaygroundPanel) ──
const playgroundAvailableModels = computed(() => {
  return playgroundRef.value?.availableModels ?? []
})

// ── Custom Model Management ──
const customModels = ref<CustomModel[]>([])
const showCustomModelCreate = ref(false)

async function fetchCustomModels() {
  const res = await listCustomModels()
  customModels.value = res.data?.data || []
}

function onCustomModelSaved() {
  showCustomModelCreate.value = false
  fetchCustomModels()
  // Refresh playground model dropdown
  playgroundRef.value?.fetchCustomModels()
}

// ── Global toast ──
const toast = ref<{ message: string; type: 'success' | 'info' } | null>(null)
let toastTimer: number | null = null

function showToast(message: string, type: 'success' | 'info' = 'success') {
  toast.value = { message, type }
  if (toastTimer !== null) window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 1800)
}

// ── Lifecycle ──
onMounted(() => {
  fetchCustomModels()
})
</script>
