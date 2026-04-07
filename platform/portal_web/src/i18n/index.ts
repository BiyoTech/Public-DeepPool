/**
 * vue-i18n 实例创建与语言检测逻辑。
 * 优先级：localStorage 缓存 > navigator.language > 默认 zh-CN
 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'

const STORAGE_KEY = 'dp_locale'
type SupportedLocale = 'zh-CN' | 'en-US'

/** 检测用户语言偏好 */
function detectLocale(): SupportedLocale {
  // 1. localStorage 缓存
  const cached = localStorage.getItem(STORAGE_KEY)
  if (cached === 'zh-CN' || cached === 'en-US') return cached

  // 2. 浏览器语言
  const browserLang = navigator.language
  if (browserLang.startsWith('en')) return 'en-US'

  // 3. 默认中文
  return 'zh-CN'
}

const i18n = createI18n({
  legacy: false, // 使用 Composition API 模式
  locale: detectLocale(),
  fallbackLocale: 'zh-CN',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export default i18n
export { STORAGE_KEY, type SupportedLocale }
