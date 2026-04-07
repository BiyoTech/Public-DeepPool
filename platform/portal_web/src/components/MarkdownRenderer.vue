<template>
  <div class="markdown-body prose prose-slate max-w-none" v-html="renderedHTML" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps<{
  content: string
}>()

// 创建 markdown-it 实例，启用代码高亮
const md = new MarkdownIt({
  html: false, // 禁用 HTML 标签渲染，防止 XSS
  linkify: true,
  typographer: true,
  highlight(str: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs rounded-lg overflow-x-auto"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch { /* ignore */ }
    }
    return `<pre class="hljs rounded-lg overflow-x-auto"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

const renderedHTML = computed(() => md.render(props.content || ''))
</script>

<style scoped>
/* Markdown 渲染样式 */
.markdown-body :deep(h1) {
  @apply text-2xl font-bold text-dp-title mt-8 mb-4 pb-2 border-b border-slate-200;
}
.markdown-body :deep(h2) {
  @apply text-xl font-bold text-dp-title mt-6 mb-3;
}
.markdown-body :deep(h3) {
  @apply text-lg font-semibold text-dp-title mt-5 mb-2;
}
.markdown-body :deep(p) {
  @apply text-dp-body leading-7 mb-4;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  @apply mb-4 pl-6;
}
.markdown-body :deep(li) {
  @apply text-dp-body leading-7 mb-1;
}
.markdown-body :deep(ul) {
  @apply list-disc;
}
.markdown-body :deep(ol) {
  @apply list-decimal;
}
.markdown-body :deep(a) {
  @apply text-dp-blue hover:text-dp-blue-dark underline transition-colors;
}
.markdown-body :deep(table) {
  @apply w-full border-collapse mb-4;
}
.markdown-body :deep(th) {
  @apply bg-slate-50 text-left text-sm font-semibold text-dp-title px-4 py-2 border border-slate-200;
}
.markdown-body :deep(td) {
  @apply text-sm text-dp-body px-4 py-2 border border-slate-200;
}
.markdown-body :deep(code:not(pre code)) {
  @apply bg-slate-100 text-dp-blue text-sm px-1.5 py-0.5 rounded;
}
.markdown-body :deep(blockquote) {
  @apply border-l-4 border-dp-blue bg-blue-50/50 pl-4 py-2 my-4 text-dp-muted;
}
.markdown-body :deep(hr) {
  @apply border-slate-200 my-6;
}
.markdown-body :deep(strong) {
  @apply font-semibold text-dp-title;
}
.markdown-body :deep(pre) {
  @apply mb-4;
}
</style>
