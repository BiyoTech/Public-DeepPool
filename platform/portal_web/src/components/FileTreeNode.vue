<template>
  <div>
    <!-- Entry row -->
    <div
      class="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-slate-50 cursor-pointer text-xs group"
      :style="{ paddingLeft: `${depth * 16 + 8}px` }"
      @click="toggle"
    >
      <!-- Expand arrow for dirs -->
      <svg
        v-if="entry.is_dir"
        class="w-3 h-3 text-slate-400 transition-transform flex-shrink-0"
        :class="expanded ? 'rotate-90' : ''"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
      </svg>
      <span v-else class="w-3 flex-shrink-0" />

      <!-- Folder icon -->
      <svg v-if="entry.is_dir" class="w-4 h-4 flex-shrink-0 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
        <path
          d="M19.5 21a3 3 0 003-3v-4.5a3 3 0 00-3-3h-15a3 3 0 00-3 3V18a3 3 0 003 3h15zM1.5 10.146V6a3 3 0 013-3h5.379a2.25 2.25 0 011.59.659l2.122 2.121c.14.141.331.22.53.22H19.5a3 3 0 013 3v1.146A4.483 4.483 0 0019.5 9h-15a4.483 4.483 0 00-3 1.146z"
        />
      </svg>
      <!-- File icon -->
      <svg
        v-else
        class="w-4 h-4 flex-shrink-0"
        :class="iconClass"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="1.5"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
        />
      </svg>

      <!-- Name -->
      <span class="truncate flex-1 text-dp-body">{{ entry.name }}</span>

      <!-- Size (on hover) -->
      <span
        v-if="!entry.is_dir && formattedSize"
        class="text-[10px] text-dp-muted/60 whitespace-nowrap hidden group-hover:inline"
        >{{ formattedSize }}</span
      >

      <!-- Modified time -->
      <span v-if="!entry.is_dir && formattedTime" class="text-[10px] text-dp-muted/60 whitespace-nowrap">{{
        formattedTime
      }}</span>
    </div>

    <!-- Children (recursive) -->
    <template v-if="entry.is_dir && expanded && entry.children">
      <FileTreeNode v-for="child in entry.children" :key="child.path" :entry="child" :depth="depth + 1" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FileEntry } from '@/api/misszhao'

const props = withDefaults(
  defineProps<{
    entry: FileEntry
    depth?: number
  }>(),
  { depth: 0 },
)

const expanded = ref(props.depth < 1)

function toggle() {
  if (props.entry.is_dir) expanded.value = !expanded.value
}

const iconClass = computed(() => {
  switch (props.entry.file_type) {
    case 'document':
      return 'text-blue-500'
    case 'image':
      return 'text-purple-500'
    case 'code':
      return 'text-emerald-500'
    case 'spreadsheet':
      return 'text-green-600'
    default:
      return 'text-slate-400'
  }
})

const formattedSize = computed(() => {
  const s = props.entry.size
  if (!s) return ''
  if (s < 1024) return `${s} B`
  if (s < 1024 * 1024) return `${(s / 1024).toFixed(1)} KB`
  return `${(s / (1024 * 1024)).toFixed(1)} MB`
})

const formattedTime = computed(() => {
  if (!props.entry.modified_at) return ''
  const d = new Date(props.entry.modified_at)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
})
</script>
