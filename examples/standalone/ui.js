(function bootstrapWin2kUI(global) {
  'use strict';

  const defaults = Object.freeze({
    help: true,
    locale: 'en-GB',
    readyText: 'Ready',
    helpUrl: '?page=help'
  });

  const instances = new WeakMap();

  const readBoolean = (value, fallback) => {
    if (value === undefined || value === null || value === '') return fallback;
    return value !== false && value !== 'false';
  };

  const getConfig = (root, overrides = {}) => {
    const host = root.matches?.('[data-win2k-app],.win2k-app') ? root : root.querySelector?.('[data-win2k-app],.win2k-app');
    const dataset = host?.dataset || {};
    return {
      ...defaults,
      help: readBoolean(dataset.helpEnabled, defaults.help),
      locale: dataset.locale || defaults.locale,
      helpUrl: dataset.helpUrl || defaults.helpUrl,
      ...(global.WIN2K_UI_CONFIG || {}),
      ...overrides
    };
  };

  const setExpanded = (button, panel, expanded) => {
    button?.setAttribute('aria-expanded', String(expanded));
    if (panel) panel.hidden = !expanded;
  };

  const init = (root = document, overrides = {}) => {
    const app = root.matches?.('[data-win2k-app],.win2k-app') ? root : root.querySelector?.('[data-win2k-app],.win2k-app');
    if (!app) return null;
    if (instances.has(app)) return instances.get(app);

    const config = getConfig(app, overrides);
    const cleanup = [];
    const on = (target, eventName, listener, options) => {
      target?.addEventListener(eventName, listener, options);
      cleanup.push(() => target?.removeEventListener(eventName, listener, options));
    };

    const startButton = app.querySelector('[data-win2k-start-button]');
    const startMenu = app.querySelector('[data-win2k-start-menu]');
    const statusFields = [...app.querySelectorAll('[data-win2k-status]')];

    const closeCascades = (except) => {
      app.querySelectorAll('[data-win2k-cascade]').forEach((trigger) => {
        if (trigger === except) return;
        const panel = document.getElementById(trigger.getAttribute('aria-controls'));
        setExpanded(trigger, panel, false);
      });
    };

    const closeStart = () => {
      setExpanded(startButton, startMenu, false);
      closeCascades();
    };

    const toggleStart = () => {
      const expanded = startButton?.getAttribute('aria-expanded') === 'true';
      setExpanded(startButton, startMenu, !expanded);
      if (!expanded) startMenu?.querySelector('a,button')?.focus();
    };

    on(startButton, 'click', (event) => {
      event.stopPropagation();
      toggleStart();
    });

    app.querySelectorAll('[data-win2k-cascade]').forEach((trigger) => {
      const panel = document.getElementById(trigger.getAttribute('aria-controls'));
      on(trigger, 'click', (event) => {
        event.stopPropagation();
        const expanded = trigger.getAttribute('aria-expanded') === 'true';
        closeCascades(trigger);
        setExpanded(trigger, panel, !expanded);
        if (!expanded) panel?.querySelector('a,button')?.focus();
      });
    });

    const menuDetails = [...app.querySelectorAll('details[data-win2k-menu]')];
    menuDetails.forEach((menu) => on(menu, 'toggle', () => {
      if (!menu.open) return;
      menuDetails.forEach((other) => { if (other !== menu) other.open = false; });
    }));

    on(document, 'click', (event) => {
      if (!app.contains(event.target)) return;
      if (!event.target.closest('[data-win2k-start-menu],[data-win2k-start-button]')) closeStart();
      if (!event.target.closest('details[data-win2k-menu]')) menuDetails.forEach((menu) => { menu.open = false; });
    });

    on(document, 'keydown', (event) => {
      if (event.ctrlKey && event.key === 'Escape') {
        event.preventDefault();
        toggleStart();
        return;
      }
      if (event.key === 'Escape') {
        closeStart();
        menuDetails.forEach((menu) => { menu.open = false; });
      }
      if (event.key === 'F1' && config.help) {
        event.preventDefault();
        const helpLink = app.querySelector('[data-win2k-help-link]');
        global.location.assign(helpLink?.href || config.helpUrl);
      }
    });

    app.querySelectorAll('[data-win2k-help]').forEach((element) => {
      element.hidden = !config.help;
    });

    const updateClock = () => {
      const now = new Date();
      app.querySelectorAll('[data-win2k-clock]').forEach((element) => {
        element.textContent = new Intl.DateTimeFormat(config.locale, { hour: '2-digit', minute: '2-digit' }).format(now);
      });
      app.querySelectorAll('[data-win2k-date]').forEach((element) => {
        element.textContent = new Intl.DateTimeFormat(config.locale, { day: '2-digit', month: '2-digit', year: 'numeric' }).format(now);
      });
    };

    updateClock();
    const clockTimer = global.setInterval(updateClock, 30_000);
    cleanup.push(() => global.clearInterval(clockTimer));

    const notify = (message, timeout = 2400) => {
      statusFields.forEach((field) => { field.textContent = message; });
      global.clearTimeout(app.__win2kStatusTimer);
      app.__win2kStatusTimer = global.setTimeout(() => {
        statusFields.forEach((field) => { field.textContent = config.readyText; });
      }, timeout);
    };

    on(app, 'win2k:status', (event) => notify(event.detail?.message || config.readyText, event.detail?.timeout));

    const api = {
      app,
      config,
      notify,
      closeStart,
      destroy() {
        cleanup.splice(0).forEach((dispose) => dispose());
        instances.delete(app);
      }
    };

    instances.set(app, api);
    app.dataset.win2kReady = 'true';
    app.dispatchEvent(new CustomEvent('win2k:ready', { detail: api }));
    return api;
  };

  global.Win2kUI = Object.freeze({ init, defaults });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => init(), { once: true });
  } else {
    init();
  }
})(window);
