// Hamburger menu toggle functionality
(function() {
  'use strict';

  document.addEventListener('DOMContentLoaded', function() {
    const hamburgerToggle = document.getElementById('hamburger-toggle');
    const mobileMenuDrawer = document.getElementById('mobile-menu-drawer');
    const mobileMenuOverlay = document.getElementById('mobile-menu-overlay');

    if (!hamburgerToggle || !mobileMenuDrawer || !mobileMenuOverlay) {
      return;
    }

    function openMenu() {
      hamburgerToggle.classList.add('active');
      mobileMenuDrawer.classList.add('active');
      mobileMenuOverlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function closeMenu() {
      hamburgerToggle.classList.remove('active');
      mobileMenuDrawer.classList.remove('active');
      mobileMenuOverlay.classList.remove('active');
      document.body.style.overflow = '';
    }

    function toggleMenu() {
      if (mobileMenuDrawer.classList.contains('active')) {
        closeMenu();
      } else {
        openMenu();
      }
    }

