import React from 'react';
import { useLanguageSettings, getSupportedLanguages, getSupportedRegions } from '../i18n';

export const LanguageSwitcher: React.FC = () => {
  const { language, region, setLanguage, setRegion } = useLanguageSettings();

  return (
    <div className="flex gap-4 p-4">
      <div>
        <label htmlFor="language-select" className="block text-sm font-medium mb-2">Language</label>
        <select
          id="language-select"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="px-3 py-2 border rounded-md"
        >
          {getSupportedLanguages().map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="region-select" className="block text-sm font-medium mb-2">Region</label>
        <select
          id="region-select"
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="px-3 py-2 border rounded-md"
        >
          {getSupportedRegions().map((reg) => (
            <option key={reg.code} value={reg.code}>
              {reg.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
