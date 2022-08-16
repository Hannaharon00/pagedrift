/**
 * Toast - Modern toast notification system
 * Inspired by Toastify, Notyf, and React Hot Toast
 *
 * Usage:
 *   Toast.success('Operation completed!');
 *   Toast.error('Something went wrong');
 *   Toast.info('Here is some information');
 *   Toast.warning('Warning message');
 *   Toast.show('Custom message', { type: 'success', duration: 3000 });
 *
 * License: MIT
 */

(function(window) {
  'use strict';

  // Toast configuration
  const defaultConfig = {
    duration: 5000,        // Auto-dismiss after 5 seconds (0 = no auto-dismiss)
    position: 'top-center', // top-right, top-center, top-left, bottom-right, bottom-center, bottom-left
    closeButton: true,     // Show close button
    progressBar: true,     // Show progress bar
    pauseOnHover: true,    // Pause auto-dismiss on hover
    maxToasts: 5,          // Maximum toasts to show at once
    offset: '20px',        // Offset from edge
    zIndex: 10000,         // Z-index for toast container
  };

  let config = { ...defaultConfig };
  let toastCount = 0;
  let container = null;

  /**
   * Initialize toast system with custom config
   */
  function init(userConfig = {}) {
    config = { ...defaultConfig, ...userConfig };
    createContainer();
  }

  /**
   * Create toast container if it doesn't exist
   */
  function createContainer() {
    if (container) return;

    container = document.createElement('div');
    container.className = `toast-container toast-${config.position}`;
    container.style.zIndex = config.zIndex;
    document.body.appendChild(container);
  }

  /**
   * Show a toast notification
   */
  function show(message, options = {}) {
    createContainer();

    const toast = createToastElement(message, options);

    // Limit number of toasts
    const existingToasts = container.querySelectorAll('.toast');
    if (existingToasts.length >= config.maxToasts) {
      removeToast(existingToasts[0]);
    }

    // Add to container
    container.appendChild(toast);

    // Trigger animation
    requestAnimationFrame(() => {
      toast.classList.add('toast-show');
    });

