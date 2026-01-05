/**
 * Simple i18n (internationalization) module
 * Loads translations from JSON files and provides translation function
 */

let currentLanguage = 'en';
let translations = {};

// Available languages
const availableLanguages = {
  en: 'English',
  es: 'Español'
};

/**
 * Load translations for a given language
 * @param {string} lang - Language code (e.g., 'en', 'es')
 * @returns {Promise<void>}
 */
async function loadTranslations(lang) {
  try {
    const response = await fetch(`./locales/${lang}.json`);
    if (!response.ok) {
      throw new Error(`Failed to load translations for ${lang}`);
    }
    translations = await response.json();
    currentLanguage = lang;
    
    // Update HTML lang attribute
    document.documentElement.setAttribute('lang', lang);
    
    // Save to localStorage
    localStorage.setItem('preferredLanguage', lang);
    
    return translations;
  } catch (error) {
    console.error(`Error loading translations for ${lang}:`, error);
    // Fallback to English if available
    if (lang !== 'en') {
      return loadTranslations('en');
    }
    throw error;
  }
}

/**
 * Get translation for a key
 * @param {string} key - Translation key (e.g., 'app.title' or 'status.running')
 * @param {object} params - Optional parameters for string interpolation
 * @returns {string} Translated string
 */
function t(key, params = {}) {
  const keys = key.split('.');
  let value = translations;
  
  for (const k of keys) {
    if (value && typeof value === 'object' && k in value) {
      value = value[k];
    } else {
      console.warn(`Translation key not found: ${key}`);
      return key; // Return key as fallback
    }
  }
  
  if (typeof value !== 'string') {
    console.warn(`Translation value is not a string for key: ${key}`);
    return key;
  }
  
  // Simple parameter interpolation: {param}
  if (params && Object.keys(params).length > 0) {
    return value.replace(/\{(\w+)\}/g, (match, paramKey) => {
      return params[paramKey] !== undefined ? params[paramKey] : match;
    });
  }
  
  return value;
}

/**
 * Get current language
 * @returns {string} Current language code
 */
function getCurrentLanguage() {
  return currentLanguage;
}

/**
 * Get available languages
 * @returns {object} Object mapping language codes to display names
 */
function getAvailableLanguages() {
  return availableLanguages;
}

/**
 * Initialize i18n system
 * Detects preferred language from:
 * 1. localStorage (user preference)
 * 2. Browser language
 * 3. Default to English
 */
async function init() {
  // Try to get saved preference
  const savedLang = localStorage.getItem('preferredLanguage');
  
  // Detect browser language
  const browserLang = navigator.language || navigator.userLanguage;
  const browserLangCode = browserLang.split('-')[0].toLowerCase();
  
  // Determine which language to use
  let lang = 'en'; // Default
  if (savedLang && availableLanguages[savedLang]) {
    lang = savedLang;
  } else if (availableLanguages[browserLangCode]) {
    lang = browserLangCode;
  }
  
  await loadTranslations(lang);
  
  return lang;
}

/**
 * Change language and reload translations
 * @param {string} lang - Language code to switch to
 */
async function setLanguage(lang) {
  if (!availableLanguages[lang]) {
    console.error(`Language not available: ${lang}`);
    return;
  }
  
  await loadTranslations(lang);
  
  // Trigger custom event for language change
  window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
  
  // Re-apply translations to all elements with data-i18n
  applyTranslations();
}

/**
 * Apply translations to all elements with data-i18n attribute
 */
function applyTranslations() {
  const elements = document.querySelectorAll('[data-i18n]');
  elements.forEach(element => {
    const key = element.getAttribute('data-i18n');
    const translation = t(key);
    
    // Handle data-i18n-attr to specify which attribute to update
    const attrName = element.getAttribute('data-i18n-attr');
    if (attrName) {
      element.setAttribute(attrName, translation);
      return;
    }
    
    // Handle data-i18n-placeholder for placeholder attributes
    if (element.hasAttribute('data-i18n-placeholder')) {
      const placeholderKey = element.getAttribute('data-i18n-placeholder');
      element.placeholder = t(placeholderKey);
    }
    
    // Handle different element types
    if (element.tagName === 'INPUT' && element.type === 'submit') {
      element.value = translation;
    } else if (element.tagName === 'INPUT' && (element.type === 'text' || element.type === 'email' || element.type === 'password' || element.type === 'number')) {
      // Don't overwrite placeholder if it's set via data-i18n-placeholder
      if (!element.hasAttribute('data-i18n-placeholder')) {
        // Only set textContent for non-input elements
      }
    } else if (element.tagName === 'SELECT') {
      // For select options, update the option text
      const option = element.querySelector(`option[value="${element.value}"]`);
      if (option && option.hasAttribute('data-i18n')) {
        // Options are handled separately
      }
    } else if (element.tagName === 'OPTION') {
      element.textContent = translation;
    } else {
      element.textContent = translation;
    }
  });
  
  // Handle placeholder translations
  const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
  placeholderElements.forEach(element => {
    const key = element.getAttribute('data-i18n-placeholder');
    element.placeholder = t(key);
  });
  
  // Also handle data-i18n-html for innerHTML
  const htmlElements = document.querySelectorAll('[data-i18n-html]');
  htmlElements.forEach(element => {
    const key = element.getAttribute('data-i18n-html');
    element.innerHTML = t(key);
  });
}

// Make functions globally available
window.t = t;
window.init = init;
window.setLanguage = setLanguage;
window.getCurrentLanguage = getCurrentLanguage;
window.getAvailableLanguages = getAvailableLanguages;
window.applyTranslations = applyTranslations;

// Export for use in other scripts (Node.js/CommonJS)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { t, init, setLanguage, getCurrentLanguage, getAvailableLanguages, applyTranslations };
}

