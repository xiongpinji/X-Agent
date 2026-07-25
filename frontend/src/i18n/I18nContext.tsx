import React, { createContext, useContext, useState, useCallback } from 'react';
import enTranslations from './translations/en.json';
import zhTranslations from './translations/zh.json';
import jaTranslations from './translations/ja.json';
import koTranslations from './translations/ko.json';
import esTranslations from './translations/es.json';

interface I18nContextType {
  language: string;
  region: string;
  setLanguage: (lang: string) => void;
  setRegion: (region: string) => void;
  t: (key: string, params?: Record<string, any>) => string;
  formatDate: (date: Date, format?: string) => string;
  formatCurrency: (amount: number, currency?: string) => string;
  formatNumber: (num: number, decimals?: number) => string;
  timezone: string;
  currency: string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

interface Translations {
  [key: string]: any;
}

const translations: Record<string, Translations> = {
  en: enTranslations,
  zh: zhTranslations,
  ja: jaTranslations,
  ko: koTranslations,
  es: esTranslations,
};

const localizationConfig = {
  timezone: {
    US: 'America/New_York',
    CN: 'Asia/Shanghai',
    JP: 'Asia/Tokyo',
    KR: 'Asia/Seoul',
    ES: 'Europe/Madrid',
    GB: 'Europe/London',
    DE: 'Europe/Berlin',
    FR: 'Europe/Paris',
  },
  currency: {
    US: 'USD',
    CN: 'CNY',
    JP: 'JPY',
    KR: 'KRW',
    ES: 'EUR',
    GB: 'GBP',
    DE: 'EUR',
    FR: 'EUR',
  },
  dateFormat: {
    US: 'MM/DD/YYYY',
    CN: 'YYYY-MM-DD',
    JP: 'YYYY年MM月DD日',
    KR: 'YYYY.MM.DD',
    ES: 'DD/MM/YYYY',
    GB: 'DD/MM/YYYY',
    DE: 'DD.MM.YYYY',
    FR: 'DD/MM/YYYY',
  },
  currencyFormat: {
    US: { symbol: '$', position: 'prefix', space: false },
    CN: { symbol: '¥', position: 'prefix', space: false },
    JP: { symbol: '¥', position: 'prefix', space: false },
    KR: { symbol: '₩', position: 'suffix', space: true },
    ES: { symbol: '€', position: 'suffix', space: true },
    GB: { symbol: '£', position: 'prefix', space: false },
    DE: { symbol: '€', position: 'suffix', space: true },
    FR: { symbol: '€', position: 'suffix', space: true },
  },
  numberFormat: {
    US: { decimal: '.', thousands: ',' },
    CN: { decimal: '.', thousands: ',' },
    JP: { decimal: '.', thousands: ',' },
    KR: { decimal: '.', thousands: ',' },
    ES: { decimal: ',', thousands: '.' },
    GB: { decimal: '.', thousands: ',' },
    DE: { decimal: ',', thousands: '.' },
    FR: { decimal: ',', thousands: ' ' },
  },
};

export const I18nProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguage] = useState('en');
  const [region, setRegion] = useState('US');

  const getNestedValue = (obj: any, path: string): string => {
    const keys = path.split('.');
    let value = obj;
    for (const key of keys) {
      value = value?.[key];
    }
    return value || path;
  };

  const t = useCallback((key: string, params?: Record<string, any>): string => {
    let translation = getNestedValue(translations[language] || translations.en, key);

    if (params) {
      Object.entries(params).forEach(([paramKey, paramValue]) => {
        translation = translation.replace(`{${paramKey}}`, String(paramValue));
      });
    }

    return translation;
  }, [language]);

  const formatDate = useCallback((date: Date, format?: string): string => {
    const regionKey = region as keyof typeof localizationConfig.dateFormat;
    const dateFormat = format || localizationConfig.dateFormat[regionKey] || 'YYYY-MM-DD';

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');

    return dateFormat
      .replace('YYYY', String(year))
      .replace('MM', month)
      .replace('DD', day)
      .replace('HH', hours)
      .replace('mm', minutes)
      .replace('ss', seconds);
  }, [region]);

  const formatNumber = useCallback((num: number, decimals: number = 2): string => {
    const regionKey = region as keyof typeof localizationConfig.numberFormat;
    const fmt = localizationConfig.numberFormat[regionKey] || { decimal: '.', thousands: ',' };

    const parts = num.toFixed(decimals).split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, fmt.thousands);

    return parts.join(fmt.decimal);
  }, [region]);

  const formatCurrency = useCallback((amount: number, _currency?: string): string => {
    const regionKey = region as keyof typeof localizationConfig.currencyFormat;
    const fmt = localizationConfig.currencyFormat[regionKey] || { symbol: '$', position: 'prefix', space: false };
    const formattedAmount = formatNumber(amount, 2);
    const space = fmt.space ? ' ' : '';

    if (fmt.position === 'prefix') {
      return `${fmt.symbol}${space}${formattedAmount}`;
    } else {
      return `${formattedAmount}${space}${fmt.symbol}`;
    }
  }, [region, formatNumber]);

  const timezone = localizationConfig.timezone[region as keyof typeof localizationConfig.timezone] || 'UTC';
  const currency = localizationConfig.currency[region as keyof typeof localizationConfig.currency] || 'USD';

  const value: I18nContextType = {
    language,
    region,
    setLanguage,
    setRegion,
    t,
    formatDate,
    formatCurrency,
    formatNumber,
    timezone,
    currency,
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export const useI18n = (): I18nContextType => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within I18nProvider');
  }
  return context;
};
