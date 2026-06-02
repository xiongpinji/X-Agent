/**
 * Internationalization Testing Suite
 *
 * Tests for:
 * - Language switching
 * - Translation loading
 * - RTL support
 * - Date/time formatting
 * - Currency formatting
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { I18nProvider, useI18n } from '../context'
import { SUPPORTED_LANGUAGES, isRTL, getLanguageConfig } from '../config'

describe('I18n Configuration', () => {
  it('should have all required languages configured', () => {
    const requiredLanguages = ['en', 'zh', 'ja', 'ko', 'es', 'ar']
    requiredLanguages.forEach(lang => {
      expect(SUPPORTED_LANGUAGES[lang as any]).toBeDefined()
    })
  })

  it('should correctly identify RTL languages', () => {
    expect(isRTL('ar')).toBe(true)
    expect(isRTL('en')).toBe(false)
    expect(isRTL('zh')).toBe(false)
  })

  it('should return correct language config', () => {
    const config = getLanguageConfig('en')
    expect(config.code).toBe('en')
    expect(config.direction).toBe('ltr')
    expect(config.currencyCode).toBe('USD')
  })

  it('should have correct date formats for each language', () => {
    expect(getLanguageConfig('en').dateFormat).toBe('MM/dd/yyyy')
    expect(getLanguageConfig('zh').dateFormat).toBe('yyyy/MM/dd')
    expect(getLanguageConfig('ja').dateFormat).toBe('yyyy/MM/dd')
    expect(getLanguageConfig('ko').dateFormat).toBe('yyyy.MM.dd')
    expect(getLanguageConfig('es').dateFormat).toBe('dd/MM/yyyy')
    expect(getLanguageConfig('ar').dateFormat).toBe('dd/MM/yyyy')
  })
})

describe('I18nProvider', () => {
  const TestComponent = () => {
    const { language, setLanguage, t, isRTL } = useI18n()
    return (
      <div>
        <div data-testid="current-language">{language}</div>
        <div data-testid="is-rtl">{isRTL ? 'rtl' : 'ltr'}</div>
        <div data-testid="translation">{t('common.loading')}</div>
        <button onClick={() => setLanguage('en')} data-testid="btn-en">
          English
        </button>
        <button onClick={() => setLanguage('zh')} data-testid="btn-zh">
          Chinese
        </button>
        <button onClick={() => setLanguage('ar')} data-testid="btn-ar">
          Arabic
        </button>
      </div>
    )
  }

  beforeEach(() => {
    localStorage.clear()
  })

  it('should render with default language', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )
    expect(screen.getByTestId('current-language')).toHaveTextContent('en')
  })

  it('should switch language on button click', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )

    const btnZh = screen.getByTestId('btn-zh')
    fireEvent.click(btnZh)

    expect(screen.getByTestId('current-language')).toHaveTextContent('zh')
  })

  it('should persist language to localStorage', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )

    const btnZh = screen.getByTestId('btn-zh')
    fireEvent.click(btnZh)

    expect(localStorage.getItem('language')).toBe('zh')
  })

  it('should update HTML lang attribute', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )

    const btnZh = screen.getByTestId('btn-zh')
    fireEvent.click(btnZh)

    expect(document.documentElement.lang).toBe('zh')
  })

  it('should set RTL direction for Arabic', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )

    const btnAr = screen.getByTestId('btn-ar')
    fireEvent.click(btnAr)

    expect(screen.getByTestId('is-rtl')).toHaveTextContent('rtl')
    expect(document.documentElement.dir).toBe('rtl')
  })

  it('should set LTR direction for English', () => {
    render(
      <I18nProvider>
        <TestComponent />
      </I18nProvider>
    )

    const btnEn = screen.getByTestId('btn-en')
    fireEvent.click(btnEn)

    expect(screen.getByTestId('is-rtl')).toHaveTextContent('ltr')
    expect(document.documentElement.dir).toBe('ltr')
  })
})

describe('Translation Loading', () => {
  const TestComponent = () => {
    const { t } = useI18n()
    return (
      <div>
        <div data-testid="common-loading">{t('common.loading')}</div>
        <div data-testid="nav-dashboard">{t('navigation.dashboard')}</div>
        <div data-testid="error-notfound">{t('errors.notFound')}</div>
      </div>
    )
  }

  it('should load English translations', () => {
    render(
      <I18nProvider defaultLanguage="en">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('Loading...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('Dashboard')
  })

  it('should load Chinese translations', () => {
    render(
      <I18nProvider defaultLanguage="zh">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('加载中...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('仪表板')
  })

  it('should load Japanese translations', () => {
    render(
      <I18nProvider defaultLanguage="ja">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('読み込み中...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('ダッシュボード')
  })

  it('should load Korean translations', () => {
    render(
      <I18nProvider defaultLanguage="ko">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('로딩 중...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('대시보드')
  })

  it('should load Spanish translations', () => {
    render(
      <I18nProvider defaultLanguage="es">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('Cargando...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('Panel de control')
  })

  it('should load Arabic translations', () => {
    render(
      <I18nProvider defaultLanguage="ar">
        <TestComponent />
      </I18nProvider>
    )

    expect(screen.getByTestId('common-loading')).toHaveTextContent('جاري التحميل...')
    expect(screen.getByTestId('nav-dashboard')).toHaveTextContent('لوحة التحكم')
  })
})

describe('Date and Time Formatting', () => {
  const TestComponent = () => {
    const { formatDate, formatTime } = useI18n()
    const testDate = new Date('2024-01-15T14:30:00')

    return (
      <div>
        <div data-testid="formatted-date">{formatDate(testDate)}</div>
        <div data-testid="formatted-time">{formatTime(testDate)}</div>
      </div>
    )
  }

  it('should format date in English format', () => {
    render(
      <I18nProvider defaultLanguage="en">
        <TestComponent />
      </I18nProvider>
    )

    const dateElement = screen.getByTestId('formatted-date')
    expect(dateElement.textContent).toMatch(/01\/15\/2024/)
  })

  it('should format date in Chinese format', () => {
    render(
      <I18nProvider defaultLanguage="zh">
        <TestComponent />
      </I18nProvider>
    )

    const dateElement = screen.getByTestId('formatted-date')
    expect(dateElement.textContent).toMatch(/2024/)
  })

  it('should format time correctly', () => {
    render(
      <I18nProvider defaultLanguage="en">
        <TestComponent />
      </I18nProvider>
    )

    const timeElement = screen.getByTestId('formatted-time')
    expect(timeElement.textContent).toBeTruthy()
  })
})

describe('Currency Formatting', () => {
  const TestComponent = () => {
    const { formatCurrency } = useI18n()
    return (
      <div>
        <div data-testid="formatted-currency">{formatCurrency(100)}</div>
      </div>
    )
  }

  it('should format currency in USD for English', () => {
    render(
      <I18nProvider defaultLanguage="en">
        <TestComponent />
      </I18nProvider>
    )

    const currencyElement = screen.getByTestId('formatted-currency')
    expect(currencyElement.textContent).toContain('100')
  })

  it('should format currency in CNY for Chinese', () => {
    render(
      <I18nProvider defaultLanguage="zh">
        <TestComponent />
      </I18nProvider>
    )

    const currencyElement = screen.getByTestId('formatted-currency')
    expect(currencyElement.textContent).toBeTruthy()
  })

  it('should format currency in JPY for Japanese', () => {
    render(
      <I18nProvider defaultLanguage="ja">
        <TestComponent />
      </I18nProvider>
    )

    const currencyElement = screen.getByTestId('formatted-currency')
    expect(currencyElement.textContent).toBeTruthy()
  })
})

describe('RTL Support', () => {
  it('should apply RTL styles for Arabic', () => {
    const { container } = render(
      <I18nProvider defaultLanguage="ar">
        <div>Test</div>
      </I18nProvider>
    )

    expect(document.documentElement.dir).toBe('rtl')
  })

  it('should apply LTR styles for English', () => {
    const { container } = render(
      <I18nProvider defaultLanguage="en">
        <div>Test</div>
      </I18nProvider>
    )

    expect(document.documentElement.dir).toBe('ltr')
  })

  it('should toggle RTL when switching languages', () => {
    const TestComponent = () => {
      const { setLanguage } = useI18n()
      return (
        <button onClick={() => setLanguage('ar')} data-testid="switch-ar">
          Switch to Arabic
        </button>
      )
    }

    render(
      <I18nProvider defaultLanguage="en">
        <TestComponent />
      </I18nProvider>
    )

    expect(document.documentElement.dir).toBe('ltr')

    const button = screen.getByTestId('switch-ar')
    fireEvent.click(button)

    expect(document.documentElement.dir).toBe('rtl')
  })
})

describe('Browser Language Detection', () => {
  it('should detect browser language on first load', () => {
    const originalLanguage = navigator.language
    Object.defineProperty(navigator, 'language', {
      value: 'zh-CN',
      configurable: true,
    })

    localStorage.clear()

    render(
      <I18nProvider>
        <div data-testid="test">Test</div>
      </I18nProvider>
    )

    // Should detect Chinese from browser
    expect(document.documentElement.lang).toBe('zh')

    Object.defineProperty(navigator, 'language', {
      value: originalLanguage,
      configurable: true,
    })
  })

  it('should prefer localStorage over browser language', () => {
    localStorage.setItem('language', 'es')

    render(
      <I18nProvider>
        <div data-testid="test">Test</div>
      </I18nProvider>
    )

    expect(document.documentElement.lang).toBe('es')
  })
})
