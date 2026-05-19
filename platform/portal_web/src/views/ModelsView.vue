<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-7xl mx-auto px-6 py-8">
      <!-- Header -->
      <div class="flex items-center justify-between mb-8">
        <div>
          <h1 class="text-2xl font-bold text-slate-900">Model Marketplace</h1>
          <p class="mt-1 text-sm text-slate-500">Explore all available models on DeepPool platform</p>
        </div>
        <button
          @click="showCreateDialog = true"
          class="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition shadow-sm"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          {{ $t('service.mymodels.create_custom') }}
        </button>
      </div>

      <!-- Search & Filters -->
      <div class="flex flex-wrap items-center gap-3 mb-6">
        <div class="relative flex-1 min-w-[240px] max-w-md">
          <svg
            class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search models by name or tag..."
            class="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400 transition"
          />
        </div>

        <!-- Source Filter (Preset vs Custom) -->
        <div class="flex items-center gap-1.5 border-r border-slate-200 pr-3">
          <button
            v-for="sf in sourceFilters"
            :key="sf.value"
            class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            :class="
              activeSourceFilter === sf.value
                ? 'bg-slate-800 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            "
            @click="activeSourceFilter = sf.value"
          >
            {{ sf.label }}
          </button>
        </div>

        <!-- Vendor Type Filter -->
        <div class="flex items-center gap-1.5">
          <button
            v-for="vt in vendorFilters"
            :key="vt.value"
            class="px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
            :class="
              activeVendorFilter === vt.value
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            "
            @click="activeVendorFilter = vt.value"
          >
            {{ vt.label }}
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-20">
        <div class="w-8 h-8 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredModels.length === 0" class="text-center py-20">
        <div class="text-slate-400 text-4xl mb-3">🔍</div>
        <p class="text-slate-500">No models found matching your criteria</p>
        <button
          v-if="activeSourceFilter === 'custom'"
          @click="showCreateDialog = true"
          class="inline-flex items-center gap-1 mt-4 text-sm text-blue-600 hover:text-blue-700"
        >
          {{ $t('service.mymodels.create_custom') }} →
        </button>
      </div>

      <!-- Model Cards Grid -->
      <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div
          v-for="model in filteredModels"
          :key="model.model_name"
          class="group bg-white rounded-xl border border-slate-100 p-5 cursor-pointer transition-all hover:shadow-md hover:border-blue-200 hover:-translate-y-0.5"
          @click="openDetail(model)"
        >
          <!-- Vendor Badge -->
          <div class="flex items-center justify-between mb-3">
            <span
              class="inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold"
              :class="vendorBadgeClass(model.vendor_type)"
            >
              {{ vendorLabel(model.vendor_type) }}
            </span>
            <div class="flex items-center gap-1.5">
              <button
                v-if="model._isCustom"
                class="p-1 rounded-md text-slate-400 opacity-0 group-hover:opacity-100 hover:bg-blue-50 hover:text-blue-600 transition-all"
                title="Edit"
                @click.stop="openEdit(model)"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125"
                  />
                </svg>
              </button>
              <span v-if="model._isCustom" class="text-[10px] text-violet-500 font-medium">Custom</span>
            </div>
          </div>

          <!-- Model Name -->
          <h3 class="text-sm font-semibold text-slate-800 mb-2 truncate group-hover:text-blue-600 transition-colors">
            {{ model._displayName || model.model_name }}
          </h3>

          <!-- Tags -->
          <div class="flex flex-wrap gap-1 mb-3 min-h-[22px]">
            <span
              v-for="tag in (model.tags || []).slice(0, 4)"
              :key="tag"
              class="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600"
            >
              {{ tag }}
            </span>
            <span v-if="(model.tags || []).length > 4" class="text-[10px] text-slate-400"
              >+{{ (model.tags || []).length - 4 }}</span
            >
          </div>

          <!-- Meta -->
          <div class="flex items-center gap-3 text-[11px] text-slate-400">
            <span v-if="model.max_context_length">{{ formatCtx(model.max_context_length) }} ctx</span>
            <span v-if="model.pricing_tiers?.length"> ¥{{ model.pricing_tiers[0].input_price }}/M in </span>
            <span v-else-if="model.price_range">
              ¥{{ model.price_range.min_input_price }}~{{ model.price_range.max_input_price }}/M
            </span>
            <span v-else class="text-emerald-500 font-medium">Free</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Detail Drawer -->
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="translate-x-full"
    >
      <div
        v-if="detailModel"
        class="fixed inset-y-0 right-0 z-50 w-[480px] max-w-full bg-white shadow-2xl flex flex-col"
      >
        <!-- Drawer Header -->
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 class="text-lg font-semibold text-slate-800 truncate">
            {{ detailModel._displayName || detailModel.model_name }}
          </h2>
          <button class="p-1.5 rounded-lg hover:bg-slate-100 transition" @click="detailModel = null">
            <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Drawer Body -->
        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <!-- Vendor -->
          <div class="flex items-center gap-2">
            <span
              :class="vendorBadgeClass(detailModel.vendor_type)"
              class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold"
            >
              {{ vendorLabel(detailModel.vendor_type) }}
            </span>
            <span v-if="detailModel._isCustom" class="text-xs text-violet-500 font-medium">Custom Model</span>
          </div>

          <!-- Model Name (full) -->
          <div class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Model Name</h4>
            <p class="text-sm text-slate-800 font-mono">{{ detailModel.model_name }}</p>
          </div>

          <!-- Tags -->
          <div v-if="detailModel.tags?.length" class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Tags</h4>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="tag in detailModel.tags"
                :key="tag"
                class="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-700"
              >
                {{ tag }}
              </span>
            </div>
          </div>

          <!-- Context Length -->
          <div v-if="detailModel.max_context_length" class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Max Context Length</h4>
            <p class="text-sm text-slate-800 font-mono">{{ formatCtx(detailModel.max_context_length) }} tokens</p>
          </div>

          <!-- Pricing -->
          <div class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Pricing</h4>
            <div v-if="detailModel.pricing_tiers?.length" class="space-y-1">
              <div
                v-for="(tier, idx) in detailModel.pricing_tiers"
                :key="idx"
                class="flex items-center gap-2 text-sm text-slate-700"
              >
                <span class="text-xs text-slate-400 w-16">{{
                  tier.max_input_tokens ? `≤${formatCtx(tier.max_input_tokens)}` : '∞'
                }}</span>
                <span>¥{{ tier.input_price }}/M input</span>
                <span class="text-slate-300">|</span>
                <span>¥{{ tier.output_price }}/M output</span>
              </div>
            </div>
            <div v-else-if="detailModel.price_range" class="text-sm text-slate-700">
              <p>
                Input: ¥{{ detailModel.price_range.min_input_price }} ~ ¥{{ detailModel.price_range.max_input_price }} /
                M tokens
              </p>
              <p>
                Output: ¥{{ detailModel.price_range.min_output_price }} ~ ¥{{
                  detailModel.price_range.max_output_price
                }}
                / M tokens
              </p>
              <p class="text-xs text-slate-400 mt-1">Dynamic pricing based on child model selected</p>
            </div>
            <p v-else class="text-sm text-emerald-600 font-medium">Free</p>
          </div>

          <!-- Contributor Tiers -->
          <div v-if="detailModel.contributor_tiers?.length" class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Contributor Earnings</h4>
            <div class="space-y-1">
              <div
                v-for="(tier, idx) in detailModel.contributor_tiers"
                :key="idx"
                class="flex items-center gap-2 text-sm text-slate-700"
              >
                <span class="text-xs text-slate-400 w-16">{{
                  tier.max_input_tokens ? `≤${formatCtx(tier.max_input_tokens)}` : '∞'
                }}</span>
                <span>¥{{ tier.input_price }}/M in</span>
                <span class="text-slate-300">|</span>
                <span>¥{{ tier.output_price }}/M out</span>
              </div>
            </div>
          </div>

          <!-- Child Models (Hybrid) -->
          <div v-if="detailModel.price_range?.child_models?.length" class="space-y-1">
            <h4 class="text-xs font-medium text-slate-500 uppercase tracking-wide">Child Models</h4>
            <div class="flex flex-wrap gap-1.5">
              <span
                v-for="child in detailModel.price_range.child_models"
                :key="child"
                class="inline-flex items-center rounded-md bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
              >
                {{ child }}
              </span>
            </div>
          </div>
        </div>

        <!-- Drawer Footer -->
        <div class="px-6 py-4 border-t border-slate-100">
          <router-link
            :to="{ path: '/service', query: { model: detailModel.model_name } }"
            class="block w-full text-center px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition"
          >
            Try this model →
          </router-link>
        </div>
      </div>
    </Transition>

    <!-- Backdrop -->
    <Transition
      enter-active-class="transition duration-200"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div v-if="detailModel" class="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" @click="detailModel = null" />
    </Transition>

    <!-- Custom Model Create Dialog -->
    <CustomModelDialog
      :visible="showCreateDialog"
      :custom-models="rawCustomModels"
      @close="showCreateDialog = false"
      @saved="onCustomModelSaved"
    />

    <!-- Custom Model Edit Dialog -->
    <CustomModelDialog
      :visible="showEditDialog"
      :editing-model="editingCustomModel"
      :custom-models="rawCustomModels"
      @close="showEditDialog = false; editingCustomModel = null"
      @saved="onCustomModelSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getPublicModels, type PublicModel, type PricingTier, type PriceRange } from '@/api/model'
import { listCustomModels, type CustomModel } from '@/api/custom-model'
import CustomModelDialog from '@/components/CustomModelDialog.vue'

// Unified model type for display (both preset and custom).
interface DisplayModel {
  model_name: string
  vendor_type: string
  max_context_length: number
  param_scale: number
  pricing_tiers: PricingTier[]
  contributor_tiers: PricingTier[]
  price_range?: PriceRange
  tags?: string[]
  _isCustom: boolean
  _displayName: string
  _customModelId?: number // custom model ID for edit lookup
}

const loading = ref(true)
const presetModels = ref<DisplayModel[]>([])
const customModels = ref<DisplayModel[]>([])
const rawCustomModels = ref<CustomModel[]>([])
const searchQuery = ref('')
const activeVendorFilter = ref('all')
const activeSourceFilter = ref('all')
const detailModel = ref<DisplayModel | null>(null)
const showCreateDialog = ref(false)
const editingCustomModel = ref<CustomModel | null>(null)
const showEditDialog = ref(false)

const sourceFilters = [
  { label: 'All', value: 'all' },
  { label: 'Preset', value: 'preset' },
  { label: 'Custom', value: 'custom' },
]

const vendorFilters = [
  { label: 'All', value: 'all' },
  { label: 'DeepNode', value: 'deepnode' },
  { label: 'Provider', value: 'provider' },
  { label: 'Hybrid', value: 'hybrid' },
]

const allModels = computed(() => [...presetModels.value, ...customModels.value])

const filteredModels = computed(() => {
  let result = allModels.value

  // Filter by source (preset vs custom).
  if (activeSourceFilter.value === 'preset') {
    result = result.filter((m) => !m._isCustom)
  } else if (activeSourceFilter.value === 'custom') {
    result = result.filter((m) => m._isCustom)
  }

  // Filter by vendor type.
  if (activeVendorFilter.value !== 'all') {
    result = result.filter((m) => m.vendor_type === activeVendorFilter.value)
  }

  // Search by name or tags.
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    result = result.filter(
      (m) =>
        m.model_name.toLowerCase().includes(q) ||
        m._displayName.toLowerCase().includes(q) ||
        (m.tags || []).some((tag) => tag.toLowerCase().includes(q)),
    )
  }

  return result
})

async function fetchModels() {
  loading.value = true
  try {
    const [publicRes, customRes] = await Promise.all([
      getPublicModels(),
      listCustomModels().catch(() => ({ data: { data: [] } })),
    ])

    // Map public models to display format.
    const publicItems: PublicModel[] = publicRes?.data?.data || []
    presetModels.value = publicItems.map((m) => ({
      ...m,
      _isCustom: false,
      _displayName: m.model_name,
    }))

    // Map custom models to display format.
    const customItems: CustomModel[] = customRes?.data?.data || []
    rawCustomModels.value = customItems
    customModels.value = customItems
      .filter((cm) => cm.enabled)
      .map((cm) => ({
        model_name: cm.model_name,
        vendor_type: cm.vendor_type,
        max_context_length: 0,
        param_scale: 0,
        pricing_tiers: [],
        contributor_tiers: [],
        tags: cm.tags || [],
        _isCustom: true,
        _displayName: cm.display_name || cm.model_name,
        _customModelId: cm.id,
      }))
  } catch {
    presetModels.value = []
    customModels.value = []
    rawCustomModels.value = []
  } finally {
    loading.value = false
  }
}

function openDetail(model: DisplayModel) {
  detailModel.value = model
}

// Open edit drawer for a custom model
function openEdit(model: DisplayModel) {
  if (!model._isCustom || !model._customModelId) return
  const raw = rawCustomModels.value.find((cm) => cm.id === model._customModelId)
  if (!raw) return
  editingCustomModel.value = raw
  showEditDialog.value = true
}

function vendorLabel(vt: string): string {
  if (vt === 'deepnode') return 'DeepNode'
  if (vt === 'provider') return 'Provider'
  if (vt === 'hybrid') return 'Hybrid'
  return vt
}

function vendorBadgeClass(vt: string): string {
  if (vt === 'deepnode') return 'bg-emerald-50 text-emerald-700'
  if (vt === 'provider') return 'bg-amber-50 text-amber-700'
  if (vt === 'hybrid') return 'bg-indigo-50 text-indigo-700'
  return 'bg-slate-100 text-slate-600'
}

function formatCtx(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${Math.round(value / 1000)}K`
  return String(value)
}

// Called when CustomModelDialog saves successfully — refresh the list.
function onCustomModelSaved() {
  editingCustomModel.value = null
  fetchModels()
}

onMounted(() => fetchModels())
</script>
