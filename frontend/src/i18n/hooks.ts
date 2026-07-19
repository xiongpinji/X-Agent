import { useI18n } from './I18nContext';

export const useTranslation = () => {
  const { t, language } = useI18n();
  return { t, language };
};

export const useLocalization = () => {
  const { formatDate, formatCurrency, formatNumber, timezone, currency, region } = useI18n();
  return { formatDate, formatCurrency, formatNumber, timezone, currency, region };
};

export const useLanguageSettings = () => {
  const { language, region, setLanguage, setRegion } = useI18n();
  return { language, region, setLanguage, setRegion };
};

export const getSupportedLanguages = () => [
  { code: 'en', name: 'English' },
  { code: 'zh', name: '中文' },
  { code: 'ja', name: '日本語' },
  { code: 'ko', name: '한국어' },
  { code: 'es', name: 'Español' },
];

export const getSupportedRegions = () => [
  { code: 'US', name: 'United States' },
  { code: 'CN', name: 'China' },
  { code: 'JP', name: 'Japan' },
  { code: 'KR', name: 'Korea' },
  { code: 'ES', name: 'Spain' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
];

export const getLanguageName = (code: string): string => {
  const lang = getSupportedLanguages().find(l => l.code === code);
  return lang?.name || code;
};

export const getRegionName = (code: string): string => {
  const region = getSupportedRegions().find(r => r.code === code);
  return region?.name || code;
};
