/**
 * Internationalization Context and Hooks
 *
 * Provides language switching and translation utilities
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { LanguageCode, SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE, getLanguageConfig, isRTL } from './config'

interface I18nContextType {
  language: LanguageCode
  setLanguage: (lang: LanguageCode) => void
  t: (key: string, defaultValue?: string) => string
  formatDate: (date: Date | string) => string
  formatTime: (date: Date | string) => string
  formatCurrency: (amount: number) => string
  isRTL: boolean
}

const I18nContext = createContext<I18nContextType | undefined>(undefined)

interface I18nProviderProps {
  children: ReactNode
  defaultLanguage?: LanguageCode
}

export const I18nProvider: React.FC<I18nProviderProps> = ({
  children,
  defaultLanguage = DEFAULT_LANGUAGE,
}) => {
  const [language, setLanguageState] = useState<LanguageCode>(() => {
    // Try to get from localStorage
    const stored = localStorage.getItem('language') as LanguageCode | null
    if (stored && SUPPORTED_LANGUAGES[stored]) {
      return stored
    }

    // Try to detect from browser
    const browserLang = navigator.language.split('-')[0] as LanguageCode
    if (SUPPORTED_LANGUAGES[browserLang]) {
      return browserLang
    }

    return defaultLanguage
  })

  const setLanguage = (lang: LanguageCode) => {
    if (SUPPORTED_LANGUAGES[lang]) {
      setLanguageState(lang)
      localStorage.setItem('language', lang)
      // Update HTML lang attribute
      document.documentElement.lang = lang
      // Update dir attribute for RTL
      document.documentElement.dir = isRTL(lang) ? 'rtl' : 'ltr'
    }
  }

  // Update HTML attributes on mount and language change
  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dir = isRTL(language) ? 'rtl' : 'ltr'
  }, [language])

  const t = (key: string, defaultValue: string = key): string => {
    // Load translations dynamically based on current language
    try {
      const translations = require(`./translations/${language}.json`)
      const keys = key.split('.')
      let value: any = translations

      for (const k of keys) {
        value = value?.[k]
      }

      return value || defaultValue
    } catch (error) {
      console.warn(`Translation not found for key: ${key}`)
      return defaultValue
    }
  }

  const formatDate = (date: Date | string): string => {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    const config = getLanguageConfig(language)

    return new Intl.DateTimeFormat(language, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(dateObj)
  }

  const formatTime = (date: Date | string): string => {
    const dateObj = typeof date === 'string' ? new Date(date) : date
    return new Intl.DateTimeFormat(language, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(dateObj)
  }

  const formatCurrency = (amount: number): string => {
    const config = getLanguageConfig(language)
    return new Intl.NumberFormat(language, {
      style: 'currency',
      currency: config.currencyCode,
    }).format(amount)
  }

  const value: I18nContextType = {
    language,
    setLanguage,
    t,
    formatDate,
    formatTime,
    formatCurrency,
    isRTL: isRTL(language),
  }

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  )
}

export const useI18n = (): I18nContextType => {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return context
}

export const useLanguage = (): LanguageCode => {
  const { language } = useI18n()
  return language
}

export const useTranslation = () => {
  const { t } = useI18n()
  return { t }
}

export const useFormatters = () => {
  const { formatDate, formatTime, formatCurrency } = useI18n()
  return { formatDate, formatTime, formatCurrency }
}
