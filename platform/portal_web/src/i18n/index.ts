/**
 * vue-i18n instance and locale detection.
 * Priority: localStorage cache > navigator.language > default en-US
 */
import { createI18n } from 'vue-i18n'
import zhCN from './locales/zh-CN.json'
import enUS from './locales/en-US.json'

const STORAGE_KEY = 'dp_locale'
type SupportedLocale = 'zh-CN' | 'en-US'

/** Detect user locale preference. */
function detectLocale(): SupportedLocale {
  // 1. localStorage cache
  const cached = localStorage.getItem(STORAGE_KEY)
  if (cached === 'zh-CN' || cached === 'en-US') return cached

  // 2. Browser language
  const browserLang = navigator.language
  if (browserLang.startsWith('zh')) return 'zh-CN'

  // 3. Default English
  return 'en-US'
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en-US',
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS,
  },
})

export default i18n
export { STORAGE_KEY, type SupportedLocale }
