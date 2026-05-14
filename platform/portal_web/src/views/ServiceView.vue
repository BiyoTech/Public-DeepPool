<template>
  <div class="min-h-screen bg-slate-50">
    <div
      v-if="toast"
      class="fixed top-6 left-1/2 z-[60] -translate-x-1/2 rounded-xl px-4 py-2 text-sm font-medium text-white shadow-lg transition-all duration-300"
      :class="toast.type === 'success' ? 'bg-emerald-500' : 'bg-slate-700'"
    >
      {{ toast.message }}
    </div>

    <div class="max-w-7xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">{{ $t('service.title') }}</h1>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- 左侧：模型对话区域 -->
        <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col" style="min-height: 600px;">
          <!-- 模型选择 -->
          <div class="px-6 py-4 border-b border-slate-100 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="flex items-center gap-3">
              <label class="text-sm font-medium text-dp-muted">{{ $t('service.chat.model') }}</label>
              <!-- Custom dropdown to display vendor_type tag alongside model name -->
              <div class="relative" ref="modelDropdownRef">
                <button
                  type="button"
                  :disabled="!hasAvailableModels"
                  class="min-w-[480px] flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg border text-sm text-left
                         focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                         disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-dp-placeholder"
                  :class="modelDropdownOpen ? 'border-dp-blue ring-2 ring-blue-100 bg-white' : 'border-slate-200 bg-white'"
                  @click="modelDropdownOpen = !modelDropdownOpen"
                >
                  <span v-if="!hasAvailableModels" class="text-dp-placeholder truncate">{{ $t('service.chat.no_models') }}</span>
                  <template v-else-if="selectedModelOption">
                    <span class="truncate text-dp-body">{{ selectedModelOption.id }}</span>
                    <span :class="vendorTypeTagClass(selectedModelOption.vendor_type)" class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none">
                      {{ vendorTypeLabel(selectedModelOption.vendor_type) }}
                    </span>
                  </template>
                  <span v-else class="text-dp-placeholder truncate">{{ $t('service.chat.model') }}</span>
                  <svg class="w-4 h-4 shrink-0 text-slate-400 transition-transform" :class="{ 'rotate-180': modelDropdownOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
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
                    class="absolute z-50 mt-1 max-h-80 w-full min-w-[480px] overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                  >
                    <!-- Search input inside dropdown -->
                    <li class="sticky top-0 bg-white px-2 py-1.5 border-b border-slate-100">
                      <input
                        v-model="modelSearchQuery"
                        type="text"
                        placeholder="Search model name..."
                        class="w-full px-3 py-1.5 rounded-md border border-slate-200 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-400"
                        @click.stop
                      />
                    </li>
                    <li
                      v-for="model in filteredAvailableModels"
                      :key="model.id"
                      class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50"
                      :class="model.id === selectedModel ? 'bg-blue-50 text-dp-blue font-medium' : 'text-dp-body'"
                      @click="selectModel(model.id)"
                    >
                      <div class="flex-1 min-w-0">
                        <div class="truncate">{{ model.id }}</div>
                        <div class="flex flex-wrap items-center gap-1 mt-0.5">
                          <span v-if="model.max_context_length" class="text-[10px] text-slate-400">{{ formatModelCtx(model.max_context_length) }}</span>
                          <span
                            v-for="tag in (model.tags || [])"
                            :key="tag"
                            class="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0 text-[10px] text-slate-500"
                          >{{ tag }}</span>
                        </div>
                      </div>
                      <span :class="vendorTypeTagClass(model.vendor_type)" class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none">
                        {{ vendorTypeLabel(model.vendor_type) }}
                      </span>
                    </li>
                  </ul>
                </Transition>
              </div>
              <!-- Hybrid routing inquiry tooltip -->
              <div class="relative group flex items-center">
                <svg class="w-5 h-5 text-amber-500 cursor-help" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                </svg>
                <div class="invisible group-hover:visible opacity-0 group-hover:opacity-100
                            absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 px-3 py-2
                            bg-slate-800 text-white text-xs leading-relaxed rounded-lg shadow-lg
                            transition-all duration-200 z-50 pointer-events-none">
                  {{ $t('service.chat.hybrid_tip') }}
                  <div class="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-x-[6px] border-x-transparent border-t-[6px] border-t-slate-800" />
                </div>
              </div>
            </div>
            <div class="flex flex-wrap items-center gap-2 text-xs">
              <span class="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-dp-muted">
                {{ $t('service.chat.available_models', { count: availableModels.length }) }}
              </span>
              <span
                v-if="selectedModelOption"
                class="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 font-medium text-dp-blue"
              >
                {{ vendorTypeLabel(selectedModelOption.vendor_type) }}
              </span>
              <span
                v-if="selectedModelOption?.model_family"
                class="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-1 font-medium text-emerald-600"
              >
                {{ selectedModelOption.model_family }}
              </span>
            </div>
          </div>
          <div v-if="modelLoadError" class="px-6 py-3 border-b border-rose-100 bg-rose-50 text-sm text-rose-600">
            {{ modelLoadError }}
          </div>
          <div v-else-if="!hasAvailableModels" class="px-6 py-3 border-b border-slate-100 bg-slate-50 text-sm text-dp-muted">
            {{ $t('service.chat.no_models') }}
          </div>

          <!-- 聊天消息区域 -->
          <div ref="chatContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            <div v-if="messages.length === 0" class="flex items-center justify-center h-full text-dp-muted text-sm">
              {{ $t('service.chat.placeholder') }}
            </div>
            <div
              v-for="(msg, i) in messages"
              :key="i"
              class="flex"
              :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
                :class="msg.role === 'user'
                  ? 'bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white rounded-br-md'
                  : 'bg-slate-100 text-dp-body rounded-bl-md'"
              >
                <!-- 思考过程折叠 -->
                <details v-if="msg.reasoning" class="mb-2">
                  <summary class="cursor-pointer text-xs opacity-70 hover:opacity-100">
                    {{ $t('service.chat.thinking') }}
                  </summary>
                  <div class="mt-1 text-xs opacity-60 border-l-2 border-slate-300 pl-2">{{ msg.reasoning }}</div>
                </details>
                <!-- 用户消息中的图片预览 -->
                <div v-if="msg.images && msg.images.length" class="flex flex-wrap gap-2 mb-2">
                  <img
                    v-for="(img, idx) in msg.images"
                    :key="idx"
                    :src="img"
                    class="max-w-[200px] max-h-[200px] rounded-lg border border-white/20 object-cover cursor-pointer"
                    @click="previewImage(img)"
                  />
                </div>
                {{ msg.content }}
                <!-- 流式打字光标 -->
                <span v-if="msg.streaming" class="inline-block w-1.5 h-4 bg-dp-blue animate-pulse ml-0.5 align-text-bottom" />
              </div>
            </div>
          </div>

          <!-- 输入区域 -->
          <div class="px-6 py-4 border-t border-slate-100">
            <!-- 已粘贴图片预览 -->
            <div v-if="pendingImages.length" class="flex flex-wrap gap-2 mb-3">
              <div
                v-for="(img, idx) in pendingImages"
                :key="idx"
                class="relative group"
              >
                <img
                  :src="img"
                  class="w-16 h-16 rounded-lg border border-slate-200 object-cover"
                />
                <button
                  @click="removePendingImage(idx)"
                  class="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[10px]
                         flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity
                         hover:bg-red-600 shadow-sm"
                >✕</button>
              </div>
              <div class="flex items-end">
                <span class="text-[10px] text-dp-placeholder">{{ $t('service.chat.images_attached', { count: pendingImages.length }) }}</span>
              </div>
            </div>
            <form @submit.prevent="sendMessage" class="flex gap-3">
              <div class="flex-1 relative">
                <input
                  ref="chatInputRef"
                  v-model="userInput"
                  type="text"
                  :placeholder="pendingImages.length ? $t('service.chat.input_placeholder_with_image') : $t('service.chat.input_placeholder')"
                  :disabled="isSending"
                  class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-dp-body
                         placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                         transition-all duration-200 disabled:opacity-60"
                  @paste="handlePaste"
                />
              </div>
              <button
                type="submit"
                :disabled="isSending || (!userInput.trim() && !pendingImages.length)"
                class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white text-sm font-medium
                       shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {{ isSending ? '...' : $t('service.chat.send') }}
              </button>
            </form>
            <div class="mt-1.5 text-[10px] text-dp-placeholder">{{ $t('service.chat.paste_image_tip') }}</div>
          </div>
        </div>

        <!-- 右侧：API Key / 我的模型 管理面板 -->
        <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
          <!-- Tab navigation -->
          <div class="flex border-b border-slate-100 mb-4">
            <button
              @click="rightPanelTab = 'apikeys'"
              class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
              :class="rightPanelTab === 'apikeys' ? 'border-dp-blue text-dp-blue' : 'border-transparent text-dp-muted hover:text-dp-body'"
            >
              API Keys
            </button>
            <button
              @click="rightPanelTab = 'mymodels'"
              class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
              :class="rightPanelTab === 'mymodels' ? 'border-dp-blue text-dp-blue' : 'border-transparent text-dp-muted hover:text-dp-body'"
            >
              {{ $t('service.mymodels.title') || '我的模型' }}
            </button>
          </div>

          <!-- Tab: API Keys -->
          <div v-show="rightPanelTab === 'apikeys'">
          <div class="flex items-center justify-between mb-4">
            <h2 class="text-lg font-bold text-dp-title">{{ $t('service.apikey.title') }}</h2>
            <button
              @click="showCreateDialog = true"
              class="px-3 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors"
            >
              + {{ $t('service.apikey.create') }}
            </button>
          </div>

          <!-- 新创建的密钥提示 -->
          <div v-if="newlyCreatedKey" class="mb-4 p-3 rounded-lg bg-green-50 border border-green-200">
            <p class="text-xs font-medium text-green-800 mb-1">{{ $t('service.apikey.created_tip') }}</p>
            <div class="flex items-center gap-2">
              <code class="flex-1 text-xs bg-green-100 px-2 py-1 rounded font-mono break-all">{{ newlyCreatedKey }}</code>
              <button
                @click="copyKey(newlyCreatedKey!)"
                class="shrink-0 text-xs text-green-700 hover:text-green-900 font-medium"
              >
                {{ $t('service.apikey.copy') }}
              </button>
            </div>
            <button @click="newlyCreatedKey = null" class="mt-2 text-xs text-green-600 hover:underline">
              {{ $t('service.apikey.dismiss') }}
            </button>
          </div>

          <!-- API Key 列表 -->
          <div v-if="apiKeys.length === 0 && !keysLoading" class="text-center text-dp-muted text-sm py-8">
            {{ $t('service.apikey.empty') }}
          </div>
          <div v-else class="space-y-3">
            <div
              v-for="key in apiKeys"
              :key="key.id"
              class="p-3 rounded-lg border transition-all duration-200"
              :class="selectedAPIKeyId === key.id
                ? 'border-dp-blue bg-blue-50 shadow-sm ring-1 ring-blue-100'
                : 'border-slate-100 hover:border-slate-200 cursor-pointer'"
              @click="handleSelect(key.id)"
            >
              <div class="flex items-center justify-between mb-1 gap-2">
                <div class="flex items-center gap-2 min-w-0">
                  <span
                    v-if="selectedAPIKeyId === key.id"
                    class="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-dp-blue text-[11px] font-bold text-white"
                  >
                    ✓
                  </span>
                  <span class="text-sm font-medium text-dp-body truncate">{{ key.name }} <span class="text-dp-muted font-normal">(ID:{{ key.id }})</span></span>
                </div>
                <div class="flex items-center gap-3 shrink-0">
                  <button
                    @click.stop="handleCopyStoredKey(key.id)"
                    class="text-xs text-dp-blue hover:text-dp-blue-dark transition-colors"
                  >
                    {{ $t('service.apikey.copy') }}
                  </button>
                  <button
                    @click.stop="handleDelete(key.id)"
                    class="text-xs text-red-400 hover:text-red-600 transition-colors"
                  >
                    {{ $t('service.apikey.delete') }}
                  </button>
                </div>
              </div>
              <div class="text-xs text-dp-muted font-mono">{{ key.key_prefix }}••••••</div>
              <!-- 配额与限流信息 -->
              <div class="mt-1.5 space-y-1">
                <div v-if="key.quota_total >= 0" class="flex items-center gap-2">
                  <div class="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      class="h-full rounded-full transition-all duration-300"
                      :class="quotaPercent(key) > 90 ? 'bg-red-400' : quotaPercent(key) > 70 ? 'bg-amber-400' : 'bg-emerald-400'"
                      :style="{ width: quotaPercent(key) + '%' }"
                    />
                  </div>
                  <span class="text-[10px] text-dp-placeholder shrink-0">{{ formatTokens(key.quota_used) }}/{{ formatTokens(key.quota_total) }}</span>
                </div>
                <div v-else class="text-[10px] text-dp-placeholder">{{ $t('service.apikey.quota_unlimited') || '配额: 不限' }}</div>
                <div class="text-[10px] text-dp-placeholder flex items-center gap-2">
                  <span>RPM: {{ key.rate_limit_rpm === 0 ? '∞' : key.rate_limit_rpm }} · TPM: {{ key.rate_limit_tpm === 0 ? '∞' : formatTokens(key.rate_limit_tpm) }}</span>
                  <button
                    @click.stop="openEditRateLimit(key)"
                    class="text-dp-blue hover:text-dp-blue-dark text-[10px]"
                  >{{ $t('service.apikey.edit_limit') || '编辑' }}</button>
                </div>
              </div>
              <div class="text-xs text-dp-placeholder mt-1">
                {{ key.last_used_at
                  ? $t('service.apikey.last_used', { time: formatTime(key.last_used_at) })
                  : $t('service.apikey.never_used')
                }}
              </div>
            </div>
          </div>

          <!-- 推理参数设置 -->
          <div class="mt-6">
            <button
              @click="showParams = !showParams"
              class="flex items-center justify-between w-full text-sm font-medium text-dp-body hover:text-dp-blue transition-colors"
            >
              <span>{{ $t('service.params.title') }}</span>
              <svg
                class="w-4 h-4 transition-transform duration-200"
                :class="showParams ? 'rotate-180' : ''"
                fill="none" stroke="currentColor" viewBox="0 0 24 24"
              >
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <div v-show="showParams" class="mt-3 space-y-4">
              <!-- Temperature -->
              <div>
                <div class="flex items-center justify-between mb-1">
                  <label class="text-xs font-medium text-dp-muted">Temperature</label>
                  <span class="text-xs text-dp-placeholder font-mono">{{ inferParams.temperature.toFixed(2) }}</span>
                </div>
                <input
                  v-model.number="inferParams.temperature"
                  type="range" min="0" max="2" step="0.05"
                  class="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                         [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-dp-blue [&::-webkit-slider-thumb]:shadow-sm"
                />
                <div class="flex justify-between text-[10px] text-dp-placeholder mt-0.5">
                  <span>{{ $t('service.params.precise') }}</span>
                  <span>{{ $t('service.params.creative') }}</span>
                </div>
              </div>

              <!-- Max Tokens -->
              <div>
                <label class="text-xs font-medium text-dp-muted mb-1 block">Max Tokens</label>
                <input
                  v-model.number="inferParams.maxTokens"
                  type="number" min="1" max="32768" step="64"
                  class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                         focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <!-- Top P (多样性) -->
              <div>
                <div class="flex items-center justify-between mb-1">
                  <label class="text-xs font-medium text-dp-muted">Top P {{ $t('service.params.diversity') }}</label>
                  <span class="text-xs text-dp-placeholder font-mono">{{ inferParams.topP.toFixed(2) }}</span>
                </div>
                <input
                  v-model.number="inferParams.topP"
                  type="range" min="0" max="1" step="0.05"
                  class="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer
                         [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5
                         [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-dp-blue [&::-webkit-slider-thumb]:shadow-sm"
                />
              </div>

              <!-- System Prompt -->
              <div>
                <label class="text-xs font-medium text-dp-muted mb-1 block">System Prompt</label>
                <textarea
                  v-model="inferParams.systemPrompt"
                  rows="3"
                  :placeholder="$t('service.params.system_placeholder')"
                  class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body
                         placeholder:text-dp-placeholder resize-none
                         focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <!-- Stop 序列 -->
              <div>
                <label class="text-xs font-medium text-dp-muted mb-1 block">{{ $t('service.params.stop') }}</label>
                <div class="flex flex-wrap gap-1.5 mb-2">
                  <span
                    v-for="(s, i) in inferParams.stop"
                    :key="i"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-xs text-dp-body font-mono"
                  >
                    {{ s }}
                    <button @click="inferParams.stop.splice(i, 1)" class="text-dp-placeholder hover:text-red-500 text-[10px]">✕</button>
                  </span>
                </div>
                <div class="flex gap-2">
                  <input
                    v-model="stopInput"
                    type="text"
                    :placeholder="$t('service.params.stop_placeholder')"
                    class="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-dp-body
                           placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
                    @keydown.enter.prevent="addStop"
                  />
                  <button
                    @click="addStop"
                    :disabled="!stopInput.trim()"
                    class="px-2.5 py-1.5 rounded-lg bg-slate-100 text-xs text-dp-muted hover:bg-slate-200
                           transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                  >+</button>
                </div>
              </div>

              <!-- Reasoning Effort -->
              <div>
                <div class="flex items-center justify-between mb-1">
                  <label class="text-xs font-medium text-dp-muted">{{ $t('service.params.reasoning_effort') }}</label>
                </div>
                <select
                  v-model="inferParams.reasoningEffort"
                  class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                         focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 bg-white"
                  @change="persistParams"
                >
                  <option value="">{{ $t('service.params.reasoning_effort_default') }}</option>
                  <option value="none">none</option>
                  <option value="low">low</option>
                  <option value="medium">medium</option>
                  <option value="high">high</option>
                </select>
                <p class="text-[10px] text-dp-placeholder mt-0.5">{{ $t('service.params.reasoning_effort_desc') }}</p>
              </div>

              <!-- 重置按钮 -->
              <button
                @click="resetParams"
                class="w-full py-1.5 rounded-lg border border-slate-200 text-xs text-dp-muted
                       hover:bg-slate-50 transition-colors"
              >
                {{ $t('service.params.reset') }}
              </button>
            </div>
          </div>

          <!-- API 接入说明 -->
          <div class="mt-6 p-4 rounded-lg bg-slate-50">
            <h3 class="text-sm font-medium text-dp-body mb-2">{{ $t('service.apikey.usage_title') }}</h3>
            <pre class="text-xs text-dp-muted bg-slate-100 p-3 rounded-lg overflow-x-auto leading-relaxed"><code>curl {{ apiBaseUrl }}/chat/completions \
  -H "Authorization: Bearer dp-your-key" \
  -H "Content-Type: application/json" \
  -d '{
  "model": "{{ selectedModel }}",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "temperature": {{ inferParams.temperature }},
  "max_tokens": {{ inferParams.maxTokens }},
  "top_p": {{ inferParams.topP }}{{ inferParams.reasoningEffort ? `,\n  "reasoning_effort": "${inferParams.reasoningEffort}"` : '' }}
}'</code></pre>
          </div>
          </div><!-- end Tab: API Keys -->

          <!-- Tab: My Models (Custom Hybrid + Provider) -->
          <div v-show="rightPanelTab === 'mymodels'">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-lg font-bold text-dp-title">{{ $t('service.mymodels.title') || '我的模型' }}</h2>
              <button
                @click="showCustomModelDialog = true; editingCustomModel = null; resetCustomModelForm()"
                class="px-3 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors"
              >
                + 创建
              </button>
            </div>
            <p class="text-xs text-dp-muted mb-3">自定义 Hybrid / Provider 模型。({{ customModels.length }}/{{ maxCustomModels }})</p>

            <!-- Empty state -->
            <div v-if="customModels.length === 0 && !customModelsLoading" class="text-center py-8">
              <p class="text-sm text-dp-muted mb-3">还没有自定义模型</p>
              <button
                @click="showCustomModelDialog = true; editingCustomModel = null; resetCustomModelForm()"
                class="px-4 py-2 rounded-lg border border-dp-blue text-dp-blue text-sm hover:bg-blue-50 transition-colors"
              >
                创建第一个模型
              </button>
            </div>

            <!-- Models list -->
            <div v-else class="space-y-3">
              <div
                v-for="cm in customModels"
                :key="cm.id"
                class="p-3 rounded-lg border border-slate-100 hover:border-slate-200 transition-all"
              >
                <div class="flex items-center justify-between mb-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-dp-body">{{ cm.display_name }}</span>
                    <span
                      class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium"
                      :class="cm.vendor_type === 'provider' ? 'bg-emerald-50 text-emerald-600' : 'bg-purple-50 text-purple-600'"
                    >{{ cm.vendor_type }}</span>
                    <span v-if="cm.model_family" class="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{{ cm.model_family }}</span>
                    <span
                      class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                      :class="cm.enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'"
                    >{{ cm.enabled ? '启用' : '禁用' }}</span>
                  </div>
                  <div class="flex items-center gap-2">
                    <button @click="editCustomModel(cm)" class="text-xs text-dp-blue hover:text-dp-blue-dark">编辑</button>
                    <button @click="deleteCustomModelConfirm(cm)" class="text-xs text-red-400 hover:text-red-600">删除</button>
                  </div>
                </div>
                <div class="text-xs text-dp-muted font-mono mb-1">{{ cm.model_name }}</div>
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="tag in (cm.tags || [])"
                    :key="'tag-'+tag"
                    class="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] text-dp-blue font-medium"
                  >{{ tag }}</span>
                  <!-- hybrid: show child models -->
                  <span
                    v-if="cm.vendor_type === 'hybrid'"
                    v-for="child in cm.child_models"
                    :key="child"
                    class="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500"
                  >{{ child }}</span>
                  <!-- provider: show capabilities -->
                  <template v-if="cm.vendor_type === 'provider'">
                    <span v-if="cm.supports_reasoning" class="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-600">reasoning</span>
                    <span v-if="cm.supports_vision" class="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-600">vision</span>
                    <span v-if="cm.supports_function_call" class="inline-flex items-center rounded-full bg-teal-50 px-2 py-0.5 text-[10px] text-teal-600">tools</span>
                  </template>
                </div>
              </div>
            </div>
          </div><!-- end Tab: My Models -->

        </div>
      </div>
    </div>

    <!-- Custom Model 创建/编辑弹窗 -->
    <div v-if="showCustomModelDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <h3 class="text-lg font-bold text-dp-title mb-4">{{ editingCustomModel ? '编辑模型' : '创建自定义模型' }}</h3>

        <!-- Vendor Type selector (create only) -->
        <div v-if="!editingCustomModel" class="mb-4">
          <label class="text-xs font-medium text-dp-muted mb-1.5 block">模型类型</label>
          <div class="flex gap-3">
            <button
              type="button"
              @click="cmForm.vendorType = 'hybrid'"
              class="flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors"
              :class="cmForm.vendorType === 'hybrid' ? 'border-dp-blue bg-blue-50 text-dp-blue' : 'border-slate-200 text-dp-muted hover:bg-slate-50'"
            >
              Hybrid 混合路由
            </button>
            <button
              type="button"
              @click="cmForm.vendorType = 'provider'"
              class="flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors"
              :class="cmForm.vendorType === 'provider' ? 'border-emerald-500 bg-emerald-50 text-emerald-600' : 'border-slate-200 text-dp-muted hover:bg-slate-50'"
            >
              Provider 注册端点
            </button>
          </div>
          <p class="text-[10px] text-dp-placeholder mt-1">
            {{ cmForm.vendorType === 'hybrid' ? 'Hybrid: 智能路由分发到多个子模型' : 'Provider: 注册已有的 API 端点，免计费调用' }}
          </p>
        </div>

        <!-- Display Name (create only) -->
        <div v-if="!editingCustomModel" class="mb-4">
          <label class="text-xs font-medium text-dp-muted mb-1 block">模型名称</label>
          <input
            v-model="cmForm.displayName"
            type="text"
            placeholder="如 anthropic/claude-opus-4.6 (2-64位)"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm
                   focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
          <p class="text-[10px] text-dp-placeholder mt-1">创建后模型标识为: u{{ currentUserId }}-{{ cmForm.displayName || '...' }}</p>
        </div>

        <!-- ═══ Hybrid Form ═══ -->
        <template v-if="cmForm.vendorType === 'hybrid'">
          <!-- Child Models multi-select -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">子模型（至少选 2 个）</label>
            <div class="max-h-40 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
              <label
                v-for="pm in hybridChildCandidates"
                :key="pm.model_name"
                class="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-50 cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  :value="pm.model_name"
                  v-model="cmForm.childModels"
                  class="rounded border-slate-300 text-dp-blue focus:ring-blue-200"
                />
                <span class="text-dp-body">{{ pm.model_name }}</span>
                <span class="text-[10px] text-slate-400">{{ pm.vendor_type }}</span>
                <span v-if="pm.is_user_provider" class="text-[10px] text-emerald-500">(我的)</span>
              </label>
            </div>
            <p class="text-[10px] text-dp-placeholder mt-1">已选 {{ cmForm.childModels.length }} 个（含平台模型 + 我的 Provider 模型）</p>
          </div>

          <!-- Routing Policy YAML editor -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">路由策略 (YAML)</label>
            <textarea
              v-model="cmForm.routingPolicy"
              rows="8"
              placeholder="留空使用默认 least-inflight 策略。"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-mono text-dp-body
                     placeholder:text-dp-placeholder resize-y
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              style="min-height: 100px;"
            ></textarea>
          </div>
        </template>

        <!-- ═══ Provider Form ═══ -->
        <template v-if="cmForm.vendorType === 'provider'">
          <!-- Model Family -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">Model Family</label>
            <select
              v-model="cmForm.modelFamily"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            >
              <option value="">请选择</option>
              <option v-for="pt in modelFamilyOptions" :key="pt" :value="pt">{{ pt }}</option>
            </select>
          </div>

          <!-- Endpoint -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">Endpoint (API Base URL)</label>
            <input
              v-model="cmForm.endpoint"
              type="text"
              placeholder="https://api.openai.com/v1"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <!-- Upstream Model Name -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">上游模型名称</label>
            <input
              v-model="cmForm.upstreamModel"
              type="text"
              placeholder="gpt-4o / claude-3-5-sonnet-20241022"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <!-- API Key -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-1 block">API Key</label>
            <input
              v-model="cmForm.apiKey"
              type="password"
              :placeholder="editingCustomModel ? '留空不修改' : '输入 API Key（加密存储）'"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <p class="text-[10px] text-dp-placeholder mt-1">密钥将加密存储，仅用于代理转发请求</p>
          </div>

          <!-- Capability Toggles -->
          <div class="mb-4">
            <label class="text-xs font-medium text-dp-muted mb-2 block">模型能力</label>
            <div class="flex flex-wrap gap-4">
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-dp-body">
                <input type="checkbox" v-model="cmForm.supportsReasoning" class="rounded border-slate-300 text-dp-blue focus:ring-blue-200" />
                Reasoning
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-dp-body">
                <input type="checkbox" v-model="cmForm.supportsVision" class="rounded border-slate-300 text-dp-blue focus:ring-blue-200" />
                Vision
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-dp-body">
                <input type="checkbox" v-model="cmForm.supportsFunctionCall" class="rounded border-slate-300 text-dp-blue focus:ring-blue-200" />
                Function Call
              </label>
            </div>
          </div>
        </template>

        <!-- Tags (common) -->
        <div class="mb-4">
          <label class="text-xs font-medium text-dp-muted mb-1 block">标签</label>
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span
              v-for="(tag, idx) in cmForm.tags"
              :key="idx"
              class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs text-dp-blue"
            >
              {{ tag }}
              <button @click="cmForm.tags.splice(idx, 1)" class="text-blue-300 hover:text-red-400 text-[10px] leading-none">&times;</button>
            </span>
          </div>
          <div class="flex gap-2">
            <input
              v-model="cmTagInput"
              type="text"
              placeholder="输入标签后按回车添加"
              class="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 text-xs
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              @keydown.enter.prevent="addCmTag"
            />
          </div>
        </div>

        <!-- Error message -->
        <div v-if="cmError" class="mb-4 px-3 py-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-600">
          {{ cmError }}
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-3">
          <button
            @click="showCustomModelDialog = false"
            class="px-4 py-2 rounded-lg border border-slate-200 text-sm text-dp-muted hover:bg-slate-50 transition-colors"
          >取消</button>
          <button
            @click="saveCustomModel"
            :disabled="cmSaving"
            class="px-4 py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-50"
          >{{ cmSaving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>

    <!-- 创建 API Key 弹窗 -->
    <div v-if="showCreateDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h3 class="text-lg font-bold text-dp-title mb-4">{{ $t('service.apikey.create_title') }}</h3>
        <input
          v-model="newKeyName"
          type="text"
          :placeholder="$t('service.apikey.name_placeholder')"
          class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                 placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          @keydown.enter="handleCreate"
        />
        <!-- RPM/TPM settings -->
        <div class="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">RPM (0=∞)</label>
            <input
              v-model.number="newKeyRPM"
              type="number"
              min="0"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">TPM (0=∞)</label>
            <input
              v-model.number="newKeyTPM"
              type="number"
              min="0"
              step="100000"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
        </div>
        <p class="text-[10px] text-dp-placeholder mt-1.5">设为 0 表示不限制。默认 RPM=60, TPM=1,000K</p>
        <div class="flex gap-3 mt-4">
          <button
            @click="showCreateDialog = false; newKeyName = ''"
            class="flex-1 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-muted hover:bg-slate-50 transition-colors"
          >
            {{ $t('service.apikey.cancel') }}
          </button>
          <button
            @click="handleCreate"
            :disabled="!newKeyName.trim() || creating"
            class="flex-1 py-2.5 rounded-lg bg-dp-blue text-white text-sm font-medium
                   hover:bg-dp-blue-dark transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {{ creating ? '...' : $t('service.apikey.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑限流弹窗 -->
    <div v-if="editRateLimitDialog" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h3 class="text-lg font-bold text-dp-title mb-4">{{ $t('service.apikey.edit_rate_limit_title') || '编辑限流配置' }}</h3>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">RPM (0=∞)</label>
            <input
              v-model.number="editRPM"
              type="number"
              min="0"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">TPM (0=∞)</label>
            <input
              v-model.number="editTPM"
              type="number"
              min="0"
              step="100000"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
        </div>
        <p class="text-[10px] text-dp-placeholder mt-1.5">设为 0 表示不限制</p>
        <div class="flex gap-3 mt-4">
          <button
            @click="editRateLimitDialog = null"
            class="flex-1 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-muted hover:bg-slate-50 transition-colors"
          >{{ $t('service.apikey.cancel') }}</button>
          <button
            @click="handleSaveRateLimit"
            :disabled="rateLimitSaving"
            class="flex-1 py-2.5 rounded-lg bg-dp-blue text-white text-sm font-medium
                   hover:bg-dp-blue-dark transition-colors disabled:opacity-60"
          >{{ rateLimitSaving ? '...' : ($t('service.apikey.confirm') || '保存') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { createAPIKey, updateAPIKey, listAPIKeys, deleteAPIKey, fetchKeySecret, type APIKey, type CreateAPIKeyParams, type UpdateAPIKeyParams } from '@/api/apikey'
import { listCustomModels, createCustomModel, updateCustomModel, deleteCustomModel, type CustomModel } from '@/api/custom-model'
import { getPublicModels, type PublicModel } from '@/api/model'

const { t } = useI18n()
const route = useRoute()

// ── Right panel tab state ──
const rightPanelTab = ref<'apikeys' | 'mymodels'>('apikeys')

const API_KEY_SELECTED_STORAGE_KEY = 'dp_service_selected_api_key_id'

// ── 模型对话 ──

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  streaming?: boolean
  images?: string[]  // Base64 data URLs for vision messages
}

interface GatewayModelOption {
  id: string
  vendor_type?: string
  model_family?: string
  owned_by?: string
  param_scale?: number
  max_context_length?: number
  tags?: string[]
}

const selectedModel = ref('')
const availableModels = ref<GatewayModelOption[]>([])
const modelLoadError = ref('')
const selectedModelOption = computed(() => availableModels.value.find(model => model.id === selectedModel.value) || null)
const hasAvailableModels = computed(() => availableModels.value.length > 0)
const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isSending = ref(false)
const chatContainer = ref<HTMLElement>()
const chatInputRef = ref<HTMLInputElement>()

// ── 图片粘贴支持 ──
const pendingImages = ref<string[]>([])
const imagePreviewUrl = ref<string | null>(null)

const MAX_PENDING_IMAGES = 5
const MAX_IMAGE_SIZE_MB = 10

/** 处理粘贴事件，提取图片并转为 Base64 */
function handlePaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (!item.type.startsWith('image/')) continue

    e.preventDefault() // 阻止图片被粘贴为文本
    const file = item.getAsFile()
    if (!file) continue

    if (file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024) {
      showToast(t('service.chat.image_too_large', { max: MAX_IMAGE_SIZE_MB }), 'info')
      continue
    }

    if (pendingImages.value.length >= MAX_PENDING_IMAGES) {
      showToast(t('service.chat.image_limit', { max: MAX_PENDING_IMAGES }), 'info')
      break
    }

    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        pendingImages.value.push(reader.result)
      }
    }
    reader.readAsDataURL(file)
  }
}

/** 移除待发送的图片 */
function removePendingImage(index: number) {
  pendingImages.value.splice(index, 1)
}

/** 预览图片（点击放大） */
function previewImage(url: string) {
  window.open(url, '_blank')
}

// ── Custom model dropdown state ──
const modelDropdownOpen = ref(false)
const modelDropdownRef = ref<HTMLElement>()
const modelSearchQuery = ref('')

// Filtered models for the dropdown based on search query.
const filteredAvailableModels = computed(() => {
  const q = modelSearchQuery.value.trim().toLowerCase()
  if (!q) return availableModels.value
  return availableModels.value.filter(m => m.id.toLowerCase().includes(q))
})

function selectModel(id: string) {
  selectedModel.value = id
  modelDropdownOpen.value = false
  modelSearchQuery.value = ''
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

/** Format context length for dropdown display (e.g. 131072 → "128K") */
function formatModelCtx(n: number): string {
  if (!n) return ''
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(0) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

function handleClickOutsideDropdown(e: MouseEvent) {
  if (modelDropdownRef.value && !modelDropdownRef.value.contains(e.target as Node)) {
    modelDropdownOpen.value = false
  }
}

onMounted(() => { document.addEventListener('click', handleClickOutsideDropdown) })
onBeforeUnmount(() => { document.removeEventListener('click', handleClickOutsideDropdown) })

// ── 推理参数 ──

const PARAMS_STORAGE_KEY = 'dp_service_infer_params'

interface InferParams {
  temperature: number
  maxTokens: number
  topP: number
  systemPrompt: string
  stop: string[]
  reasoningEffort: string
}

const defaultParams: InferParams = {
  temperature: 0.7,
  maxTokens: 2048,
  topP: 0.9,
  systemPrompt: '',
  stop: [],
  reasoningEffort: '',
}

function loadStoredParams(): InferParams {
  try {
    const raw = localStorage.getItem(PARAMS_STORAGE_KEY)
    if (!raw) return { ...defaultParams, stop: [] }
    const parsed = JSON.parse(raw)
    return {
      temperature: parsed.temperature ?? defaultParams.temperature,
      maxTokens: parsed.maxTokens ?? defaultParams.maxTokens,
      topP: parsed.topP ?? defaultParams.topP,
      systemPrompt: parsed.systemPrompt ?? defaultParams.systemPrompt,
      stop: Array.isArray(parsed.stop) ? parsed.stop : [],
      reasoningEffort: parsed.reasoningEffort ?? defaultParams.reasoningEffort,
    }
  } catch {
    return { ...defaultParams, stop: [] }
  }
}

function persistParams() {
  localStorage.setItem(PARAMS_STORAGE_KEY, JSON.stringify(inferParams.value))
}

const inferParams = ref<InferParams>(loadStoredParams())
const showParams = ref(false)
const stopInput = ref('')

function addStop() {
  const val = stopInput.value.trim()
  if (!val || inferParams.value.stop.includes(val)) return
  if (inferParams.value.stop.length >= 8) return
  inferParams.value.stop.push(val)
  stopInput.value = ''
  persistParams()
}

function resetParams() {
  inferParams.value = { ...defaultParams, stop: [], reasoningEffort: '' }
  persistParams()
}

// ── API Key 管理 ──

const apiKeys = ref<APIKey[]>([])
const keysLoading = ref(false)
const showCreateDialog = ref(false)
const newKeyName = ref('')
const newKeyRPM = ref(60)
const newKeyTPM = ref(1000000)
const creating = ref(false)
const newlyCreatedKey = ref<string | null>(null)
const newlyCreatedKeyId = ref<number | null>(null)
const selectedAPIKeyId = ref<number | null>(loadSelectedAPIKeyId())
const toast = ref<{ message: string; type: 'success' | 'info' } | null>(null)
let toastTimer: number | null = null

// Edit rate-limit dialog state
const editRateLimitDialog = ref<APIKey | null>(null)
const editRPM = ref(0)
const editTPM = ref(0)
const rateLimitSaving = ref(false)

// In-memory cache for full keys fetched from server (not persisted to localStorage)
const keySecretCache = ref<Record<string, string>>({})

/** Read persisted selected API Key ID. */
function loadSelectedAPIKeyId(): number | null {
  const raw = localStorage.getItem(API_KEY_SELECTED_STORAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

/** Persist current selected API Key ID. */
function persistSelectedAPIKeyId(id: number | null) {
  if (id === null) {
    localStorage.removeItem(API_KEY_SELECTED_STORAGE_KEY)
    return
  }
  localStorage.setItem(API_KEY_SELECTED_STORAGE_KEY, String(id))
}

/** Fetch the full API Key from server (with in-memory cache). */
async function getFullKey(id: number): Promise<string | null> {
  // Check in-memory cache first
  const cached = keySecretCache.value[String(id)]
  if (cached) return cached

  try {
    const res = await fetchKeySecret(id)
    const fullKey = res.data?.data?.full_key
    if (fullKey) {
      keySecretCache.value[String(id)] = fullKey
      return fullKey
    }
  } catch (err) {
    console.error('[ServiceView] fetch key secret failed', err)
  }
  return null
}

/** Sync selected API Key: keep current selection if valid, otherwise pick the first available. */
function syncSelectedAPIKey() {
  const hasSelected = selectedAPIKeyId.value !== null && apiKeys.value.some(key => key.id === selectedAPIKeyId.value)
  if (hasSelected) return

  const first = apiKeys.value[0]
  selectedAPIKeyId.value = first?.id ?? null
  persistSelectedAPIKeyId(selectedAPIKeyId.value)
}

/** Get the full key for the currently selected API Key. */
async function getActiveAPIKey(): Promise<string | null> {
  if (selectedAPIKeyId.value === null) return null
  return getFullKey(selectedAPIKeyId.value)
}

/** Select an API Key. All keys are selectable now (server can always decrypt). */
function handleSelect(id: number) {
  selectedAPIKeyId.value = id
  persistSelectedAPIKeyId(id)
}

/** 发送消息并流式接收回复。 */
async function sendMessage() {
  const text = userInput.value.trim()
  if ((!text && !pendingImages.value.length) || isSending.value) return

  if (!selectedModel.value) {
    messages.value.push({
      role: 'assistant',
      content: t('service.chat.need_model'),
    })
    return
  }

  const apiKey = await getActiveAPIKey()
  if (!apiKey) {
    messages.value.push({
      role: 'assistant',
      content: t('service.chat.need_apikey'),
    })
    return
  }

  // 捕获当前待发送的图片，然后清空
  const imagesToSend = [...pendingImages.value]
  pendingImages.value = []

  // 先写入用户消息（含图片预览），再直接复用当前消息列表构造上下文，避免重复追加最后一条 user 消息。
  messages.value.push({ role: 'user', content: text, images: imagesToSend.length ? imagesToSend : undefined })
  userInput.value = ''
  isSending.value = true
  scrollToBottom()

  messages.value.push({ role: 'assistant', content: '', streaming: true })
  // 通过响应式数组索引引用，确保属性变更触发 Vue 视图更新
  const assistantIdx = messages.value.length - 1

  try {
    // 构造消息列表：如有 system prompt 则注入到开头
    // 支持 Vision API：如果消息包含图片，构造 OpenAI 多部分 content 数组格式
    const chatMessages = messages.value
      .filter(message => !message.streaming)
      .map(message => {
        if (message.images && message.images.length > 0) {
          // 构造 OpenAI Vision API 格式的多部分 content
          const contentParts: Array<Record<string, any>> = []
          if (message.content) {
            contentParts.push({ type: 'text', text: message.content })
          }
          for (const imgDataUrl of message.images) {
            contentParts.push({
              type: 'image_url',
              image_url: { url: imgDataUrl, detail: 'auto' },
            })
          }
          return { role: message.role, content: contentParts }
        }
        return { role: message.role, content: message.content }
      })
    if (inferParams.value.systemPrompt.trim()) {
      chatMessages.unshift({ role: 'system', content: inferParams.value.systemPrompt.trim() })
    }

    // 构造请求体，包含推理参数
    const requestBody: Record<string, any> = {
      model: selectedModel.value,
      messages: chatMessages,
      stream: true,
      temperature: inferParams.value.temperature,
      max_tokens: inferParams.value.maxTokens,
      top_p: inferParams.value.topP,
    }
    if (inferParams.value.stop.length > 0) {
      requestBody.stop = inferParams.value.stop
    }
    if (inferParams.value.reasoningEffort) {
      requestBody.reasoning_effort = inferParams.value.reasoningEffort
    }

    // 参数变更时持久化
    persistParams()

    const response = await fetch(`${apiBaseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify(requestBody),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      messages.value[assistantIdx].content = err?.error?.message || `Error: ${response.status}`
      messages.value[assistantIdx].streaming = false
      return
    }

    const reader = response.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          messages.value[assistantIdx].streaming = false
          break
        }
        try {
          const chunk = JSON.parse(data)
          const delta = chunk.choices?.[0]?.delta
          if (delta?.content) {
            messages.value[assistantIdx].content += delta.content
          }
          if (delta?.reasoning_content) {
            messages.value[assistantIdx].reasoning =
              (messages.value[assistantIdx].reasoning || '') + delta.reasoning_content
          }
        } catch {
          // 忽略解析失败的行
        }
      }
      scrollToBottom()
    }

    messages.value[assistantIdx].streaming = false
  } catch (err: any) {
    messages.value[assistantIdx].content = err?.message || 'Network error'
    messages.value[assistantIdx].streaming = false
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

/** Gateway base URL for inference API calls.
 *  Production: VITE_GATEWAY_BASE_URL → https://api.deeppool.tech/v1
 *  Development: falls back to current origin + /v1 (proxied by Vite).
 *  Also used in the curl example snippet in the template.
 */
const apiBaseUrl = import.meta.env.VITE_GATEWAY_BASE_URL || (window.location.origin + '/v1')

/** Fetch API Key list and sync selection. */
async function fetchKeys() {
  keysLoading.value = true
  try {
    const res = await listAPIKeys()
    apiKeys.value = res.data?.data || []
    syncSelectedAPIKey()
  } catch {
    // silent
  } finally {
    keysLoading.value = false
  }
}

/** Create API Key and cache the full key in memory for immediate use. */
async function handleCreate() {
  if (!newKeyName.value.trim() || creating.value) return

  creating.value = true
  try {
    const params: CreateAPIKeyParams = { name: newKeyName.value.trim() }
    if (newKeyRPM.value !== 60) params.rate_limit_rpm = newKeyRPM.value
    if (newKeyTPM.value !== 1000000) params.rate_limit_tpm = newKeyTPM.value
    const res = await createAPIKey(params)
    const data = res.data?.data
    if (data?.full_key) {
      newlyCreatedKey.value = data.full_key
      newlyCreatedKeyId.value = data.id
      // Cache in memory for immediate use
      keySecretCache.value[String(data.id)] = data.full_key
      handleSelect(data.id)
    }

    showCreateDialog.value = false
    newKeyName.value = ''
    newKeyRPM.value = 60
    newKeyTPM.value = 1000000
    await fetchKeys()
  } catch {
    // error handling
  } finally {
    creating.value = false
  }
}

/** Open edit rate-limit dialog for an API Key. */
function openEditRateLimit(key: APIKey) {
  editRateLimitDialog.value = key
  editRPM.value = key.rate_limit_rpm
  editTPM.value = key.rate_limit_tpm
}

/** Save rate-limit changes. */
async function handleSaveRateLimit() {
  if (!editRateLimitDialog.value || rateLimitSaving.value) return
  rateLimitSaving.value = true
  try {
    const params: UpdateAPIKeyParams = {
      rate_limit_rpm: editRPM.value,
      rate_limit_tpm: editTPM.value,
    }
    await updateAPIKey(editRateLimitDialog.value.id, params)
    editRateLimitDialog.value = null
    await fetchKeys()
    showToast(t('service.apikey.limit_updated') || '限流配置已更新', 'success')
  } catch {
    // error handling
  } finally {
    rateLimitSaving.value = false
  }
}

/** Delete API Key and clean up in-memory cache and selection state. */
async function handleDelete(id: number) {
  if (!confirm(t('service.apikey.delete_confirm'))) return

  try {
    await deleteAPIKey(id)
    delete keySecretCache.value[String(id)]

    if (selectedAPIKeyId.value === id) {
      selectedAPIKeyId.value = null
      persistSelectedAPIKeyId(null)
    }

    if (newlyCreatedKeyId.value === id) {
      newlyCreatedKey.value = null
      newlyCreatedKeyId.value = null
    }

    await fetchKeys()
  } catch {
    // silent
  }
}

/** 显示顶部轻提示。 */
function showToast(message: string, type: 'success' | 'info' = 'success') {
  toast.value = { message, type }

  if (toastTimer !== null) {
    window.clearTimeout(toastTimer)
  }

  toastTimer = window.setTimeout(() => {
    toast.value = null
    toastTimer = null
  }, 1800)
}

/** 复制文本，优先使用 Clipboard API，失败时降级到 textarea 方案。 */
async function copyText(text: string) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)
  textarea.select()

  try {
    const copied = document.execCommand('copy')
    if (!copied) {
      throw new Error('execCommand copy failed')
    }
  } finally {
    document.body.removeChild(textarea)
  }
}

/** 复制 API Key，兼容 http / 非安全上下文场景。 */
async function copyKey(key: string) {
  try {
    await copyText(key)
    showToast('复制成功')
  } catch (error) {
    console.error('[ServiceView] copy api key failed', error)
    showToast('复制失败，请重试', 'info')
  }
}

/** Copy the full API Key by fetching from server; fallback to prefix if unavailable. */
async function handleCopyStoredKey(id: number) {
  const secret = await getFullKey(id)
  if (secret) {
    await copyKey(secret)
    return
  }

  // Full key not available from server — copy the visible prefix as fallback
  const keyRecord = apiKeys.value.find(k => k.id === id)
  if (keyRecord?.key_prefix) {
    try {
      await copyText(keyRecord.key_prefix)
      showToast(t('service.apikey.copy_prefix_tip'), 'info')
    } catch {
      showToast(t('service.apikey.copy_failed'), 'info')
    }
  } else {
    showToast(t('service.apikey.copy_no_cache'), 'info')
  }
}

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

/** 计算配额使用百分比。 */
function quotaPercent(key: APIKey): number {
  if (key.quota_total <= 0) return 0
  return Math.min(100, Math.round((key.quota_used / key.quota_total) * 100))
}

/** 格式化 token 数（K/M/B）。 */
function formatTokens(n: number): string {
  if (n < 0) return '∞'
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
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

function normalizeGatewayModels(items: unknown[]): GatewayModelOption[] {
  const seen = new Set<string>()
  return items
    .map((item): GatewayModelOption => {
      const record = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>
      return {
        id: String(record.id || '').trim(),
        vendor_type: String(record.vendor_type || '').trim(),
        model_family: String(record.model_family || '').trim(),
        owned_by: String(record.owned_by || '').trim(),
        param_scale: Number(record.param_scale || 0),
        max_context_length: Number(record.max_context_length || 0),
        tags: Array.isArray(record.tags) ? (record.tags as string[]) : [],
      }
    })
    .filter(model => {
      if (!model.id || seen.has(model.id)) {
        return false
      }
      seen.add(model.id)
      return true
    })
    .sort((left, right) => left.id.localeCompare(right.id))
}

function syncSelectedModel(models: GatewayModelOption[]) {
  if (selectedModel.value && models.some(model => model.id === selectedModel.value)) {
    return
  }
  selectedModel.value = models[0]?.id || ''
}

// Store gateway (global) models separately so we can re-merge with custom models.
const gatewayModels = ref<GatewayModelOption[]>([])

async function fetchModels() {
  modelLoadError.value = ''
  try {
    const res = await fetch(`${apiBaseUrl}/models`)
    if (!res.ok) {
      throw new Error(`gateway returned ${res.status}`)
    }
    const json = await res.json()
    const items = Array.isArray(json?.data) ? json.data : []
    gatewayModels.value = normalizeGatewayModels(items)
    mergeModelsIntoDropdown()
  } catch (error) {
    console.error('[ServiceView] load models failed', error)
    gatewayModels.value = []
    availableModels.value = []
    selectedModel.value = ''
    modelLoadError.value = t('service.chat.load_models_failed')
  }
}

// Merge gateway models + user custom models into the unified dropdown list.
function mergeModelsIntoDropdown() {
  const seen = new Set(gatewayModels.value.map(m => m.id))
  const customEntries: GatewayModelOption[] = customModels.value
    .filter(cm => cm.enabled && !seen.has(cm.model_name))
    .map(cm => ({
      id: cm.model_name,
      vendor_type: cm.vendor_type || 'hybrid',
      model_family: cm.model_family || '',
      owned_by: 'user',
      param_scale: 0,
      max_context_length: 0,
      tags: cm.tags && cm.tags.length ? [...cm.tags, 'custom'] : ['custom'],
    }))
  const merged = [...gatewayModels.value, ...customEntries].sort((a, b) => a.id.localeCompare(b.id))
  availableModels.value = merged
  syncSelectedModel(merged)
}

// ── Custom Model Management ──

const customModels = ref<CustomModel[]>([])
const customModelsLoading = ref(false)
const maxCustomModels = 10
const showCustomModelDialog = ref(false)
const editingCustomModel = ref<CustomModel | null>(null)
const cmSaving = ref(false)
const cmError = ref('')
const publicModelsList = ref<PublicModel[]>([])

// Model family options
const modelFamilyOptions = ['openai', 'anthropic', 'gemini', 'deepseek', 'qwen', 'kimi', 'glm', 'qianfan', 'minimax', 'custom']

// Get user ID from localStorage for display purposes.
const currentUserId = computed(() => {
  const user = JSON.parse(localStorage.getItem('dp_user') || '{}')
  return user.id || 0
})

const cmForm = ref({
  displayName: '',
  vendorType: 'hybrid' as 'hybrid' | 'provider',
  // hybrid fields
  childModels: [] as string[],
  routingPolicy: '',
  // provider fields
  modelFamily: '',
  endpoint: '',
  upstreamModel: '',
  apiKey: '',
  supportsReasoning: false,
  supportsVision: false,
  supportsFunctionCall: false,
  // common
  tags: [] as string[],
})

const cmTagInput = ref('')

// Hybrid child model candidates: platform non-hybrid models + user's own provider models.
interface ChildCandidate {
  model_name: string
  vendor_type: string
  is_user_provider?: boolean
}
const hybridChildCandidates = computed<ChildCandidate[]>(() => {
  // Platform models (non-hybrid)
  const platformModels: ChildCandidate[] = publicModelsList.value
    .filter(m => m.vendor_type !== 'hybrid')
    .map(m => ({ model_name: m.model_name, vendor_type: m.vendor_type }))

  // User's own enabled provider models
  const userProviders: ChildCandidate[] = customModels.value
    .filter(cm => cm.vendor_type === 'provider' && cm.enabled)
    .map(cm => ({ model_name: cm.model_name, vendor_type: 'provider', is_user_provider: true }))

  return [...platformModels, ...userProviders]
})

function addCmTag() {
  const tag = cmTagInput.value.trim()
  if (tag && !cmForm.value.tags.includes(tag) && cmForm.value.tags.length < 10) {
    cmForm.value.tags.push(tag)
  }
  cmTagInput.value = ''
}

function resetCustomModelForm() {
  cmForm.value = {
    displayName: '', vendorType: 'hybrid',
    childModels: [], routingPolicy: '',
    modelFamily: '', endpoint: '', upstreamModel: '', apiKey: '',
    supportsReasoning: false, supportsVision: false, supportsFunctionCall: false,
    tags: [],
  }
  cmError.value = ''
}

function editCustomModel(cm: CustomModel) {
  editingCustomModel.value = cm
  cmForm.value = {
    displayName: cm.display_name,
    vendorType: cm.vendor_type || 'hybrid',
    childModels: [...(cm.child_models || [])],
    routingPolicy: cm.routing_policy || '',
    modelFamily: cm.model_family || '',
    endpoint: cm.endpoint || '',
    upstreamModel: cm.upstream_model || '',
    apiKey: '', // don't pre-fill (masked on server)
    supportsReasoning: cm.supports_reasoning || false,
    supportsVision: cm.supports_vision || false,
    supportsFunctionCall: cm.supports_function_call || false,
    tags: [...(cm.tags || [])],
  }
  showCustomModelDialog.value = true
}

async function fetchCustomModels() {
  customModelsLoading.value = true
  const res = await listCustomModels()
  customModels.value = res.data?.data || []
  customModelsLoading.value = false
  // Refresh the model dropdown to include/exclude custom models.
  mergeModelsIntoDropdown()
}

async function fetchPublicModelsForSelector() {
  const res = await getPublicModels()
  // Filter out hybrid models (can't be children of user hybrid).
  publicModelsList.value = (res.data?.data || []).filter((m: PublicModel) => m.vendor_type !== 'hybrid')
}

async function saveCustomModel() {
  cmError.value = ''
  const form = cmForm.value

  // Frontend validation.
  if (!editingCustomModel.value) {
    const name = form.displayName.trim()
    if (!name) { cmError.value = '请输入模型名称'; return }
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_./-]{1,63}$/.test(name)) {
      cmError.value = '模型名称需 2-64 位，以字母/数字开头，支持字母/数字/下划线/短横线/点/斜杠'; return
    }
  }

  if (form.vendorType === 'hybrid' && form.childModels.length < 2) {
    cmError.value = '至少选择 2 个子模型'; return
  }
  if (form.vendorType === 'provider') {
    if (!form.modelFamily) { cmError.value = '请选择 Provider 类型'; return }
    if (!form.endpoint) { cmError.value = '请输入 Endpoint'; return }
    if (!form.upstreamModel) { cmError.value = '请输入上游模型名称'; return }
    if (!editingCustomModel.value && !form.apiKey) { cmError.value = '请输入 API Key'; return }
  }

  cmSaving.value = true
  try {
    if (editingCustomModel.value) {
      // Build update payload based on vendor_type.
      const payload: Record<string, any> = { tags: form.tags }
      if (form.vendorType === 'hybrid') {
        payload.child_models = form.childModels
        payload.routing_policy = form.routingPolicy
      } else {
        payload.model_family = form.modelFamily
        payload.endpoint = form.endpoint
        payload.upstream_model = form.upstreamModel
        if (form.apiKey) payload.api_key = form.apiKey
        payload.supports_reasoning = form.supportsReasoning
        payload.supports_vision = form.supportsVision
        payload.supports_function_call = form.supportsFunctionCall
      }
      await updateCustomModel(editingCustomModel.value.id, payload)
    } else {
      const payload: any = {
        display_name: form.displayName.trim(),
        vendor_type: form.vendorType,
        tags: form.tags,
      }
      if (form.vendorType === 'hybrid') {
        payload.child_models = form.childModels
        payload.routing_policy = form.routingPolicy
      } else {
        payload.model_family = form.modelFamily
        payload.endpoint = form.endpoint
        payload.upstream_model = form.upstreamModel
        payload.api_key = form.apiKey
        payload.supports_reasoning = form.supportsReasoning
        payload.supports_vision = form.supportsVision
        payload.supports_function_call = form.supportsFunctionCall
      }
      await createCustomModel(payload)
    }
    showCustomModelDialog.value = false
    await fetchCustomModels()
  } catch (err: any) {
    const msg = err?.response?.data?.message || err?.response?.data?.error || err?.message || '保存失败，请稍后重试'
    cmError.value = msg
  } finally {
    cmSaving.value = false
  }
}

async function deleteCustomModelConfirm(cm: CustomModel) {
  if (!confirm(`确认删除模型「${cm.display_name}」？`)) return
  await deleteCustomModel(cm.id)
  await fetchCustomModels()
}

onMounted(async () => {
  await Promise.all([fetchKeys(), fetchModels(), fetchCustomModels(), fetchPublicModelsForSelector()])
  // Pre-select model from route query (e.g. /service?model=gpt-4o-proxy).
  const queryModel = route.query.model as string
  if (queryModel && availableModels.value.some(m => m.id === queryModel)) {
    selectedModel.value = queryModel
  }
})
</script>
