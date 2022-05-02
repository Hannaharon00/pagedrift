// Search modal functionality
(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
    const searchModal = document.getElementById('search-modal');
    // The Search button is rendered in the left rail and the mobile drawer.
    const openSearchButtons = document.querySelectorAll('.js-open-search-modal');
    const closeSearchButton = document.getElementById('close-search-modal');
    const searchForm = document.getElementById('search-form');
    const searchInput = document.getElementById('search-modal-input');

    if (!searchModal || openSearchButtons.length === 0) {
      return;
    }

    // Open modal
    function openSearchModal() {
      searchModal.showModal();
      // Focus the input after a small delay to ensure modal is rendered
      setTimeout(function() {
        if (searchInput) {
          searchInput.focus();
        }
      }, 100);
    }

