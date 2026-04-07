/**
 * Pinia 语言状态管理。
 * 管理当前语言设置，切换时同步更新 i18n 实例和 localStorage。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import i18n, { STORAGE_KEY, type SupportedLocale } from '@/i18n'

export const useLangStore = defineStore('lang', () => {
  const locale = ref<SupportedLocale>(i18n.global.locale.value as SupportedLocale)

  /** 切换语言并持久化 */
  function setLocale(newLocale: SupportedLocale) {
    locale.value = newLocale
    i18n.global.locale.value = newLocale
    localStorage.setItem(STORAGE_KEY, newLocale)
    document.documentElement.lang = newLocale === 'zh-CN' ? 'zh-CN' : 'en'
  }

  /** 切换到另一种语言 */
  function toggleLocale() {
    setLocale(locale.value === 'zh-CN' ? 'en-US' : 'zh-CN')
  }

  return { locale, setLocale, toggleLocale }
})
