/**
 * FamDoc Theme Manager
 * Manages theme state, persistence, event listeners, and OS preference sync.
 */
(function() {
  // Expose theme toggling globally
  window.FamDocTheme = {
    getCurrentTheme: function() {
      return document.documentElement.getAttribute('data-theme') || 'light';
    },
    setTheme: function(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('famdoc-theme', theme);
      this.updateToggleIcons(theme);
    },
    toggleTheme: function() {
      const current = this.getCurrentTheme();
      const next = current === 'dark' ? 'light' : 'dark';
      this.setTheme(next);
    },
    updateToggleIcons: function(theme) {
      const iconClass = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
      const btns = document.querySelectorAll('#mobileThemeToggle i, #desktopThemeToggle i, .guest-theme-toggle i');
      btns.forEach(icon => {
        icon.className = iconClass;
      });
    },
    init: function() {
      // Run initial icon update
      const theme = this.getCurrentTheme();
      this.updateToggleIcons(theme);

      // Bind event listeners using delegation
      document.body.addEventListener('click', (e) => {
        const btn = e.target.closest('#mobileThemeToggle, #desktopThemeToggle, .guest-theme-toggle');
        if (btn) {
          e.preventDefault();
          this.toggleTheme();
        }
      });

      // Listen for OS changes (only if user hasn't explicitly set a preference)
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
        if (!localStorage.getItem('famdoc-theme')) {
          const nextTheme = e.matches ? 'dark' : 'light';
          this.setTheme(nextTheme);
        }
      });
    }
  };

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.FamDocTheme.init());
  } else {
    window.FamDocTheme.init();
  }
})();
