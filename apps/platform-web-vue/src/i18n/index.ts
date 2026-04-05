import { createI18n } from 'vue-i18n'
import { enUS } from './locales/en-US'
import { zhCN } from './locales/zh-CN'

export type LocaleCode = 'zh-CN' | 'en-US'

type LocaleOption = {
  code: LocaleCode
  name: string
  shortLabel: string
}

const LOCALE_STORAGE_KEY = 'pw:locale'
const DEFAULT_LOCALE: LocaleCode = 'zh-CN'

export const availableLocales: LocaleOption[] = [
  { code: 'zh-CN', name: '简体中文', shortLabel: '中' },
  { code: 'en-US', name: 'English', shortLabel: 'EN' }
]

function resolveInitialLocale(): LocaleCode {
  if (typeof window === 'undefined') {
    return DEFAULT_LOCALE
  }

  const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY)
  if (saved === 'zh-CN' || saved === 'en-US') {
    return saved
  }

  const browserLocale = window.navigator.language.toLowerCase()
  return browserLocale.startsWith('en') ? 'en-US' : DEFAULT_LOCALE
}

const i18n = createI18n({
  legacy: false,
  locale: resolveInitialLocale(),
  fallbackLocale: DEFAULT_LOCALE,
  messages: {
    'zh-CN': zhCN,
    'en-US': enUS
  }
})

export function setLocale(localeCode: LocaleCode) {
  i18n.global.locale.value = localeCode

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, localeCode)
  }
}

export default i18n
