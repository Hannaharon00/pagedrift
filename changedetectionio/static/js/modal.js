/**
 * Modern modal dialog system using HTML5 <dialog> element
 * Provides accessible, animated confirmation dialogs
 */

// Escapes a string for safe insertion via innerHTML
function _modalEscapeHTML(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Translatable strings are injected by base.html into window.ModalDialogI18n so
// Babel can extract them from the Jinja template. Fall back to English when a
// key is missing (e.g. a page that renders modal.js without the bridge).
function _modalT(key, fallback) {
  const i18n = window.ModalDialogI18n || {};
  return (key in i18n) ? i18n[key] : fallback;
}

