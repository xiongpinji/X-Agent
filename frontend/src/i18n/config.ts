/**
 * Internationalization Configuration
 *
 * Supports 10+ languages with RTL support for Arabic and Hebrew
 */

export type LanguageCode =
  | 'en' | 'zh' | 'ja' | 'ko'
  | 'fr' | 'de' | 'es'
  | 'pt' | 'ru' | 'ar'

export interface LanguageConfig {
  code: LanguageCode
  name: string
  nativeName: string
  direction: 'ltr' | 'rtl'
  dateFormat: string
  timeFormat: string
  currencyCode: string
}

export const SUPPORTED_LANGUAGES: Record<LanguageCode, LanguageConfig> = {
  en: {
    code: 'en',
    name: 'English',
    nativeName: 'English',
    direction: 'ltr',
    dateFormat: 'MM/dd/yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'USD',
  },
  zh: {
    code: 'zh',
    name: 'Chinese (Simplified)',
    nativeName: '简体中文',
    direction: 'ltr',
    dateFormat: 'yyyy/MM/dd',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'CNY',
  },
  ja: {
    code: 'ja',
    name: 'Japanese',
    nativeName: '日本語',
    direction: 'ltr',
    dateFormat: 'yyyy/MM/dd',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'JPY',
  },
  ko: {
    code: 'ko',
    name: 'Korean',
    nativeName: '한국어',
    direction: 'ltr',
    dateFormat: 'yyyy.MM.dd',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'KRW',
  },
  fr: {
    code: 'fr',
    name: 'French',
    nativeName: 'Français',
    direction: 'ltr',
    dateFormat: 'dd/MM/yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'EUR',
  },
  de: {
    code: 'de',
    name: 'German',
    nativeName: 'Deutsch',
    direction: 'ltr',
    dateFormat: 'dd.MM.yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'EUR',
  },
  es: {
    code: 'es',
    name: 'Spanish',
    nativeName: 'Español',
    direction: 'ltr',
    dateFormat: 'dd/MM/yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'EUR',
  },
  pt: {
    code: 'pt',
    name: 'Portuguese',
    nativeName: 'Português',
    direction: 'ltr',
    dateFormat: 'dd/MM/yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'BRL',
  },
  ru: {
    code: 'ru',
    name: 'Russian',
    nativeName: 'Русский',
    direction: 'ltr',
    dateFormat: 'dd.MM.yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'RUB',
  },
  ar: {
    code: 'ar',
    name: 'Arabic',
    nativeName: 'العربية',
    direction: 'rtl',
    dateFormat: 'dd/MM/yyyy',
    timeFormat: 'HH:mm:ss',
    currencyCode: 'AED',
  },
}

export const DEFAULT_LANGUAGE: LanguageCode = 'en'

export const getLanguageConfig = (code: LanguageCode): LanguageConfig => {
  return SUPPORTED_LANGUAGES[code] || SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE]
}

export const isRTL = (code: LanguageCode): boolean => {
  return getLanguageConfig(code).direction === 'rtl'
}
