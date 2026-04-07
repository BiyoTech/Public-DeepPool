<template>
  <div class="flex min-h-[calc(100vh-64px)]">
    <!-- 左侧目录树 -->
    <aside class="w-64 flex-shrink-0 border-r border-slate-200 bg-white overflow-y-auto sticky top-16 h-[calc(100vh-64px)]">
      <div class="p-4">
        <!-- 搜索框 -->
        <input
          v-model="searchQuery"
          :placeholder="$t('docs.search_placeholder')"
          class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body
                 placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-1 focus:ring-blue-100
                 transition-all duration-200 mb-4"
        />

        <!-- 目录组 -->
        <nav class="space-y-4">
          <div v-for="group in filteredSidebar" :key="group.title">
            <h3 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-2 px-2">{{ group.title }}</h3>
            <ul class="space-y-0.5">
              <li v-for="item in group.children" :key="item.path">
                <button
                  @click="selectDoc(item.path)"
                  class="w-full text-left px-3 py-1.5 rounded-lg text-sm transition-all duration-200 flex items-center"
                  :class="currentPath === item.path
                    ? 'text-dp-blue bg-blue-50 font-medium border-l-[3px] border-dp-blue'
                    : 'text-dp-body hover:bg-slate-50 hover:text-dp-title border-l-[3px] border-transparent'"
                >
                  {{ item.title }}
                </button>
              </li>
            </ul>
          </div>
        </nav>
      </div>
    </aside>

    <!-- 中间内容区 -->
    <main class="flex-1 min-w-0 bg-white">
      <div class="max-w-4xl mx-auto px-8 py-8">
        <!-- 加载状态 -->
        <div v-if="loading" class="flex items-center justify-center py-20">
          <div class="w-8 h-8 border-2 border-dp-blue border-t-transparent rounded-full animate-spin" />
        </div>

        <!-- 文档内容 -->
        <MarkdownRenderer v-else :content="docContent" />
      </div>
    </main>

    <!-- 右侧 TOC 锚点导航 -->
    <aside class="w-52 flex-shrink-0 hidden xl:block overflow-y-auto sticky top-16 h-[calc(100vh-64px)]">
      <div class="p-4">
        <h3 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-3">{{ $t('docs.toc_title') }}</h3>
        <ul class="space-y-1">
          <li v-for="heading in tocItems" :key="heading.id">
            <a
              :href="`#${heading.id}`"
              class="block text-sm py-0.5 transition-colors duration-200"
              :class="[
                heading.level === 2 ? 'text-dp-body hover:text-dp-blue' : 'text-dp-muted hover:text-dp-body pl-3',
                activeHeading === heading.id ? '!text-dp-blue font-medium' : ''
              ]"
            >
              {{ heading.text }}
            </a>
          </li>
        </ul>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLangStore } from '@/stores/lang'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'

// 使用 import.meta.glob 导入所有文档资源
const mdModules = import.meta.glob('@/docs/**/*.md', { query: '?raw', import: 'default' })
const sidebarModules = import.meta.glob('@/docs/**/_sidebar.json', { eager: true, import: 'default' })

interface SidebarItem {
  title: string
  path: string
}
interface SidebarGroup {
  title: string
  children: SidebarItem[]
}
interface TocItem {
  id: string
  text: string
  level: number
}

const route = useRoute()
const router = useRouter()
const langStore = useLangStore()

const searchQuery = ref('')
const docContent = ref('')
const loading = ref(false)
const currentPath = ref('getting-started/introduction') // 默认文档
const tocItems = ref<TocItem[]>([])
const activeHeading = ref('')

// 根据当前语言获取 sidebar
const sidebar = computed<SidebarGroup[]>(() => {
  const locale = langStore.locale === 'zh-CN' ? 'zh' : 'en'
  const key = `/src/docs/${locale}/_sidebar.json`
  return (sidebarModules[key] as SidebarGroup[]) || []
})

// 搜索过滤
const filteredSidebar = computed(() => {
  if (!searchQuery.value.trim()) return sidebar.value
  const q = searchQuery.value.toLowerCase()
  return sidebar.value
    .map((group) => ({
      ...group,
      children: group.children.filter((item) =>
        item.title.toLowerCase().includes(q) || item.path.toLowerCase().includes(q)
      ),
    }))
    .filter((group) => group.children.length > 0)
})

/** 加载指定路径的 Markdown 文件 */
async function loadDoc(path: string) {
  loading.value = true
  const locale = langStore.locale === 'zh-CN' ? 'zh' : 'en'
  const key = `/src/docs/${locale}/${path}.md`

  try {
    const loader = mdModules[key]
    if (loader) {
      docContent.value = (await loader()) as string
    } else {
      docContent.value = `# 404\n\nDocument not found: \`${path}\``
    }
  } catch {
    docContent.value = `# Error\n\nFailed to load document: \`${path}\``
  } finally {
    loading.value = false
    // 提取 TOC
    extractToc()
  }
}

/** 从文档内容中提取 h2/h3 生成 TOC */
function extractToc() {
  const headingRegex = /^(#{2,3})\s+(.+)$/gm
  const items: TocItem[] = []
  let match
  while ((match = headingRegex.exec(docContent.value)) !== null) {
    const level = match[1].length
    const text = match[2].trim()
    const id = text.toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-').replace(/^-|-$/g, '')
    items.push({ id, text, level })
  }
  tocItems.value = items
}

function selectDoc(path: string) {
  currentPath.value = path
  router.replace(`/docs/${path}`)
}

// 监听路径参数变化
watch(() => route.params.pathMatch, (val) => {
  if (val) {
    const path = Array.isArray(val) ? val.join('/') : val
    if (path) currentPath.value = path
  }
}, { immediate: true })

// 监听当前路径和语言变化，重新加载文档
watch([currentPath, () => langStore.locale], () => {
  loadDoc(currentPath.value)
}, { immediate: true })

// 滚动监听，高亮当前可见的标题
let scrollTimer: number | undefined
function onScroll() {
  if (scrollTimer) cancelAnimationFrame(scrollTimer)
  scrollTimer = requestAnimationFrame(() => {
    const headings = tocItems.value.map((item) => document.getElementById(item.id)).filter(Boolean)
    for (let i = headings.length - 1; i >= 0; i--) {
      const el = headings[i]
      if (el && el.getBoundingClientRect().top <= 100) {
        activeHeading.value = tocItems.value[i].id
        return
      }
    }
    if (tocItems.value.length) activeHeading.value = tocItems.value[0].id
  })
}

onMounted(() => window.addEventListener('scroll', onScroll))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
