(() => {
  const fallbackStyles = [
    ['glassmorphism', 'Glassmorphism'],
    ['neumorphism', 'Neumorphism'],
    ['claymorphism', 'Claymorphism'],
    ['neo-brutalism', 'Neo-Brutalism'],
    ['minimalist', 'Minimalist UI'],
    ['frost-ui', 'Frost UI'],
    ['bento-ui', 'Bento UI'],
    ['mesh-gradients', 'Mesh Gradients'],
    ['cyber-futuristic', 'Cyber / Futuristic'],
    ['retro-synthwave', 'Retro-Futurism / Synthwave'],
    ['isometric-3d', '3D UI / Isometric'],
    ['organic', 'Organic']
  ];
  const styles = window.STYLE_MANIFEST
    ? window.STYLE_MANIFEST.map((style) => [style.slug, style.name])
    : fallbackStyles;

  const pages = [
    ['home', 'Overview', 'OV'],
    ['analysis', 'Analytics', 'AN'],
    ['data', 'Database', 'DB'],
    ['login', 'Login', 'IN'],
    ['profile', 'My profile', 'ME']
  ];

  const records = [
    ['Northwind Expansion', 'Strategy', 'Active', '89%', 'Today'],
    ['Project Aurora', 'Product', 'Active', '76%', 'Today'],
    ['Customer Pulse Q3', 'Analytics', 'Review', '94%', 'Yesterday'],
    ['Retail Signals', 'Data', 'Paused', '48%', 'Aug 2'],
    ['Nordic Launch', 'Marketing', 'Active', '67%', 'Aug 1'],
    ['Atlas Migration', 'Technology', 'Review', '82%', 'Jul 31'],
    ['Partner Network', 'Sales', 'Active', '71%', 'Jul 29'],
    ['Service Blueprint', 'Design', 'Paused', '55%', 'Jul 26']
  ];

  const currentStyle = document.body.dataset.style || styles[0][0];
  const currentName = document.body.dataset.styleName || styles.find(([slug]) => slug === currentStyle)?.[1] || 'Design style';
  const isWindowsMirc = currentStyle === 'windows-2000-mirc';
  const productName = document.body.dataset.productName || 'Workspace';
  const productSlug = productName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workspace';
  const win2kUiConfig = Object.freeze({
    help: document.body.dataset.helpEnabled !== 'false',
    siteTitle: document.body.dataset.siteTitle || 'www.bodbil.com - A site for everyone',
    ...(window.WIN_UI_CONFIG || {}),
    ...(window.WIN2K_UI_CONFIG || {})
  });
  const helpEnabled = isWindowsMirc && win2kUiConfig.help !== false;
  const win2kAuthKey = `${productSlug}-authenticated`;
  let isWin2kAuthenticated = !isWindowsMirc;
  if (isWindowsMirc) {
    try { isWin2kAuthenticated = window.sessionStorage.getItem(win2kAuthKey) === 'true'; } catch { isWin2kAuthenticated = false; }
  }
  if (isWindowsMirc) document.documentElement.lang = 'en';
  const windowsSiteTitle = win2kUiConfig.siteTitle;
  const windowsPrograms = [
    ['home', 'Operations Center', 'OV'],
    ['analysis', 'Insight Center', 'AN'],
    ['data', 'Project Manager', 'DB'],
    ['content', 'Newsroom', 'TX'],
    ['forum', 'Community Forum', 'CF'],
    ['messages', 'Mail', 'MS'],
    ['calendar', 'Team Calendar', 'CA'],
    ['files', 'File Explorer', 'FI']
  ];
  const windowsUtilities = [
    ['controls', 'Component Catalog', 'UI'],
    ['profile', 'My Account', 'ME'],
    ['states', 'System Monitor', 'ST']
  ];
  if (isWindowsMirc) {
    pages.splice(0, pages.length,
      ...windowsPrograms,
      ...windowsUtilities,
      ['forms', 'Project Editor', 'FM'],
      ['details', 'Project Details', 'DT'],
      ['login', 'Log On', 'IN']
    );
    if (helpEnabled) pages.push(['help', 'Help and Support', 'HP']);
  }
  const referenceMenus = (title, primaryAction) => ({
    File: [[primaryAction, 'Ctrl+N'], ['Open…', 'Ctrl+O'], ['Save', 'Ctrl+S'], ['Print', 'Ctrl+P'], '-', ['Close', 'Alt+F4']],
    View: [[`✓ ${title}`], ['Toolbar'], ['Status bar'], '-', ['Refresh', 'F5']],
    Favorites: [[`Add ${title}`], ['Overview'], ['Controls']],
    Tools: [['Options…'], ['Customize view…'], ['Accessibility…']],
    Commands: [[primaryAction], ['Select all', 'Ctrl+A'], ['Clear selection']],
    Window: [['Minimize'], ['Maximize'], ['Restore layout']],
    Help: [[`Help for ${title}`, 'F1'], ['Keyboard shortcuts'], '-', ['About this site']]
  });
  const windowsPageMenus = {
    home: { title: 'Operations Center', menus: {
      File: [['New workspace', 'Ctrl+N'], ['Open recent', 'Ctrl+O'], ['Print overview', 'Ctrl+P'], '-', ['Exit', 'Alt+F4']],
      View: [['✓ Key metrics'], ['✓ Team focus'], ['✓ Recent activity'], '-', ['Refresh', 'F5']],
      Favorites: [['Add Overview'], ['Analytics center'], ['Project registry']],
      Tools: [['Create report'], ['Synchronize data'], ['Settings…']],
      Commands: [['Open analytics'], ['New project'], ['Export snapshot']],
      Window: [['Minimize'], ['Maximize'], ['Restore default layout']],
      Help: [['Overview help', 'F1'], ['Keyboard shortcuts'], '-', [`About ${productName}`]]
    }},
    analysis: { title: 'Insight Center', menus: {
      File: [['New analysis', 'Ctrl+N'], ['Open report', 'Ctrl+O'], ['Save analysis', 'Ctrl+S'], ['Export as PDF']],
      View: [['7 days'], ['✓ 30 days'], ['12 months'], '-', ['Show forecast']],
      Favorites: [['Save current analysis'], ['Management report Q3'], ['Nordic growth signals']],
      Tools: [['Recalculate data'], ['Compare periods'], ['Data sources…']],
      Commands: [['Create insight'], ['Add filter'], ['Share analysis']],
      Window: [['Minimize'], ['Maximize'], ['Customize chart']],
      Help: [['Analytics help', 'F1'], ['Explain metrics'], '-', ['About Analytics center']]
    }},
    data: { title: 'Project Manager', menus: {
      File: [['New project', 'Ctrl+N'], ['Open record', 'Ctrl+O'], ['Save changes', 'Ctrl+S'], ['Export CSV']],
      View: [['✓ All projects'], ['Active'], ['Review'], ['Paused']],
      Favorites: [['Save current search'], ['High-potential projects'], ['Recently updated']],
      Tools: [['Import data'], ['Validate records'], ['Choose columns…']],
      Commands: [['Search', 'Ctrl+F'], ['Filter'], ['Select records']],
      Window: [['Minimize'], ['Maximize'], ['Restore table width']],
      Help: [['Database help', 'F1'], ['Field descriptions'], '-', ['About Project registry']]
    }},
    login: { title: 'Secure sign-in', menus: {
      File: [['Open workspace'], ['New session'], '-', ['Exit', 'Alt+F4']],
      View: [['✓ Sign-in panel'], ['Security information'], ['Demo credentials']],
      Favorites: [['Add sign-in'], ['Overview']],
      Tools: [['Change password'], ['Connection settings…'], ['Clear saved sign-in']],
      Commands: [['Sign in', 'Enter'], ['Reset password'], ['Cancel', 'Esc']],
      Window: [['Minimize'], ['Maximize'], ['Center dialog']],
      Help: [['Sign-in help', 'F1'], ['Contact support'], '-', ['About secure connection']]
    }},
    profile: { title: 'My profile', menus: {
      File: [['Save profile', 'Ctrl+S'], ['Print profile', 'Ctrl+P'], '-', ['Log out']],
      View: [['✓ Profile'], ['Preferences'], ['Saved views']],
      Favorites: [['Add My profile'], ['Management report Q3'], ['High-potential projects']],
      Tools: [['Edit profile'], ['Notifications…'], ['Personalization…']],
      Commands: [['New saved view'], ['Reset preferences'], ['Log out']],
      Window: [['Minimize'], ['Maximize'], ['Restore panels']],
      Help: [['Profile help', 'F1'], ['Privacy'], '-', ['About user profiles']]
    }},
    controls: { title: 'Component Catalog', menus: {
      File: [['New dialog', 'Ctrl+N'], ['Open example', 'Ctrl+O'], ['Save settings', 'Ctrl+S'], '-', ['Close', 'Alt+F4']],
      View: [['✓ All controls'], ['Text fields'], ['Buttons'], ['Choices and lists'], ['Status and sliders']],
      Favorites: [['Add Controls'], ['Form example'], ['Dialog example']],
      Tools: [['Test keyboard'], ['Reset form'], ['Accessibility…']],
      Commands: [['Focus first field', 'Ctrl+F'], ['Show confirmation'], ['Clear fields']],
      Window: [['Minimize'], ['Maximize'], ['Arrange groups']],
      Help: [['Controls help', 'F1'], ['About Windows 2000 UI'], '-', [`About ${productName}`]]
    }},
    forms: { title: 'Project Editor', menus: referenceMenus('Project Editor', 'New project') },
    details: { title: 'Project Details', menus: referenceMenus('Project Details', 'New project') },
    content: { title: 'Newsroom', menus: referenceMenus('Newsroom', 'New article') },
    forum: { title: 'Community Forum', menus: referenceMenus('Community Forum', 'New topic') },
    files: { title: 'File Explorer', menus: referenceMenus('File Explorer', 'New folder') },
    calendar: { title: 'Team Calendar', menus: referenceMenus('Team Calendar', 'New event') },
    messages: { title: 'Mail', menus: referenceMenus('Mail', 'New message') },
    states: { title: 'System Monitor', menus: referenceMenus('System Monitor', 'Refresh status') },
    help: { title: 'Help and Support', menus: referenceMenus('Help and Support', 'Open help topic') }
  };
  const windowsMenuNames = ['File', 'View', 'Favorites', 'Tools', 'Commands', 'Window', ...(helpEnabled ? ['Help'] : [])];
  const windowsMenuLabels = {
    File: '<u>F</u>ile',
    View: '<u>V</u>iew',
    Favorites: 'F<u>a</u>vorites',
    Tools: '<u>T</u>ools',
    Commands: '<u>C</u>ommands',
    Window: '<u>W</u>indow',
    Help: '<u>H</u>elp'
  };
  const win2kIcon = (name) => `<span class="win2k-pixel-icon win2k-icon-${name}" aria-hidden="true"><i></i></span>`;
  const windowsDesktop = isWindowsMirc ? `
    <nav class="win2k-desktop" aria-label="Windows desktop">
      <a class="win2k-desktop-shortcut" href="?page=files" data-page-link="files">${win2kIcon('computer')}<strong>My Computer</strong></a>
      <a class="win2k-desktop-shortcut" href="?page=files" data-page-link="files">${win2kIcon('folder')}<strong>My Documents</strong></a>
      <a class="win2k-desktop-shortcut" href="?page=forum" data-page-link="forum">${win2kIcon('network')}<strong>My Network Places</strong></a>
      <a class="win2k-desktop-shortcut" href="?page=states" data-page-link="states">${win2kIcon('recycle')}<strong>Recycle Bin</strong></a>
    </nav>` : '';
  const windowsProgramChrome = isWindowsMirc ? `
    <section class="win2k-program-chrome" aria-label="Bodbil application window">
      <div class="win2k-titlebar">
        <strong id="win2k-program-title">${windowsSiteTitle}</strong>
        <div class="win2k-window-controls" aria-hidden="true">
          <span>_</span>
          <span>□</span>
          <span>×</span>
        </div>
      </div>
      <nav class="win2k-menubar" aria-label="Application menu bar">
        ${windowsMenuNames.map((name) => `<details data-win-menu="${name}"><summary>${windowsMenuLabels[name]}</summary><div class="win2k-dropdown ${['Favorites', 'Commands'].includes(name) ? 'wide' : ''} ${name === 'Help' ? 'align-right' : ''}" data-win-menu-content></div></details>`).join('')}
      </nav>
    </section>` : '';
  const windowsStartMenu = isWindowsMirc ? `
    <aside class="win2k-start-menu" id="win2k-start-menu" aria-label="Start menu" hidden>
      <div class="win2k-start-side"><strong>Windows</strong><span>2000</span></div>
      <nav class="win2k-start-primary" aria-label="Start-kommandon">
        <div class="win2k-start-cascade-item" data-start-cascade="programs">
          <button class="win2k-start-cascade-trigger" type="button" aria-expanded="false" aria-controls="win2k-programs-menu">${win2kIcon('programs')}<strong><u>P</u>rograms</strong><b aria-hidden="true">▶</b></button>
          <section class="win2k-start-submenu" id="win2k-programs-menu" aria-label="Programs">
            ${windowsPrograms.map(([id, label]) => `<a href="?page=${id}" data-page-link="${id}">${win2kIcon(id)}<strong>${label}</strong></a>`).join('')}
          </section>
        </div>
        <div class="win2k-start-cascade-item" data-start-cascade="settings">
          <button class="win2k-start-cascade-trigger" type="button" aria-expanded="false" aria-controls="win2k-settings-menu">${win2kIcon('settings')}<strong><u>S</u>ettings</strong><b aria-hidden="true">▶</b></button>
          <section class="win2k-start-submenu" id="win2k-settings-menu" aria-label="Settings">
            <a href="?page=controls" data-page-link="controls">${win2kIcon('controls')}<strong>Component Catalog</strong></a>
            <a href="?page=profile" data-page-link="profile">${win2kIcon('profile')}<strong>My Account</strong></a>
            <a href="?page=login" data-page-link="login">${win2kIcon('lock')}<strong>Lock workstation</strong></a>
            <a href="?page=states" data-page-link="states">${win2kIcon('states')}<strong>System Monitor</strong></a>
          </section>
        </div>
        <a class="win2k-start-command" href="?page=data" data-page-link="data" data-focus-target="record-search">${win2kIcon('search')}<strong><u>S</u>earch…</strong></a>
        ${helpEnabled ? `<a class="win2k-start-command" href="?page=help" data-page-link="help">${win2kIcon('help')}<strong><u>H</u>elp</strong></a>` : ''}
        <button class="win2k-start-command" type="button" data-start-run>${win2kIcon('run')}<strong><u>R</u>un…</strong></button>
        <hr>
        <a class="win2k-start-command" href="?page=login" data-page-link="login" data-log-out="true">${win2kIcon('logout')}<strong><u>L</u>og off…</strong></a>
      </nav>
    </aside>` : '';
  const topActions = isWindowsMirc ? `
    <div class="top-actions win2k-task-actions">
      <time class="win2k-task-clock" id="win2k-task-clock" aria-label="Time and date">
        <span data-task-time>--:--</span>
        <small data-task-date>---- -- --</small>
      </time>
    </div>` : `
    <div class="top-actions">
      <label class="style-picker-label" for="style-picker">Style</label>
      <select id="style-picker" class="style-picker" aria-label="Change design style">
        ${styles.map(([slug, label]) => `<option value="${slug}" ${slug === currentStyle ? 'selected' : ''}>${label}</option>`).join('')}
      </select>
      <a class="avatar-button" href="?page=profile" data-page-link="profile" aria-label="Open your profile">AH</a>
    </div>`;
  const taskNavigation = isWindowsMirc ? '<div class="main-nav win2k-task-spacer" aria-hidden="true"></div>' : `
    <nav class="main-nav" aria-label="Main menu">
      ${pages.map(([id, label, icon]) => `<a href="?page=${id}" data-page-link="${id}"><span class="nav-icon">${icon}</span><span>${label}</span></a>`).join('')}
    </nav>`;
  const appTitle = isWindowsMirc ? `${productName} — Windows 2000-inspired interface` : `${currentName} — ${productName}`;
  const windowsFooter = isWindowsMirc ? `
    <footer class="site-footer win2k-statusbar" aria-label="Application status">
      <span data-win2k-ready>Ready</span>
      <span data-win2k-page>Page: Overview</span>
      <span>Local intranet</span>
    </footer>` : `
    <footer class="site-footer">
      <span>${productName} demo workspace</span>
      <span class="footer-style"><i></i>${currentName}</span>
      <a href="../../">All styles</a>
    </footer>`;
  document.title = appTitle;

  document.body.innerHTML = `
    <a class="skip-link" href="#main-content">Skip to content</a>
    <div class="ambient ambient-one" aria-hidden="true"></div>
    <div class="ambient ambient-two" aria-hidden="true"></div>
    <div class="ambient ambient-three" aria-hidden="true"></div>
    ${windowsDesktop}
    <header class="topbar shell-surface">
      ${isWindowsMirc ? '<button class="brand win2k-start-button" id="win2k-start-button" type="button" aria-expanded="false" aria-controls="win2k-start-menu">' : '<a class="brand" href="../../" aria-label="Till stilbiblioteket">'}
        <span class="brand-mark">N</span>
        <span class="brand-copy"><strong>${productName}</strong><small>style lab</small></span>
      ${isWindowsMirc ? '</button>' : '</a>'}
      ${taskNavigation}
      ${topActions}
      ${windowsStartMenu}
    </header>
    ${windowsProgramChrome}
    <main id="main-content" tabindex="-1"></main>
    ${windowsFooter}
    <div id="toast" class="toast" role="status" aria-live="polite"></div>
    <div class="win2k-dialog-layer" id="win2k-system-dialog" hidden>
      <section class="win2k-system-dialog" role="dialog" aria-modal="true" aria-labelledby="win2k-dialog-title" aria-describedby="win2k-dialog-message">
        <div class="win2k-system-dialog-title"><strong id="win2k-dialog-title">Windows</strong><button type="button" aria-label="Close dialog" data-dialog-result="cancel">×</button></div>
        <div class="win2k-system-dialog-body"><span class="win2k-system-dialog-icon" data-dialog-icon aria-hidden="true">i</span><div><p id="win2k-dialog-message"></p><div data-dialog-extra></div></div></div>
        <div class="win2k-system-dialog-actions" data-dialog-actions></div>
      </section>
    </div>
  `;

  const main = document.querySelector('#main-content');
  const toast = document.querySelector('#toast');
  const taskClock = document.querySelector('#win2k-task-clock');
  const updateTaskClock = () => {
    if (!taskClock) return;
    const now = new Date();
    const time = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Stockholm', hour: '2-digit', minute: '2-digit' }).format(now);
    const date = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Stockholm', year: 'numeric', month: 'short', day: '2-digit' }).format(now);
    taskClock.querySelector('[data-task-time]').textContent = time;
    taskClock.querySelector('[data-task-date]').textContent = date;
    taskClock.dateTime = now.toISOString();
    taskClock.setAttribute('aria-label', `${time}, ${date}`);
  };
  if (taskClock) {
    updateTaskClock();
    window.setInterval(updateTaskClock, 30000);
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let toastTimer;

  const getPage = () => {
    const requested = new URLSearchParams(window.location.search).get('page') || 'home';
    return pages.some(([id]) => id === requested) ? requested : 'home';
  };
  const setWin2kAuthenticated = (authenticated) => {
    isWin2kAuthenticated = authenticated;
    if (!isWindowsMirc) return;
    try {
      if (authenticated) window.sessionStorage.setItem(win2kAuthKey, 'true');
      else window.sessionStorage.removeItem(win2kAuthKey);
    } catch { /* The demo still works when session storage is blocked. */ }
  };

  const notify = (message) => {
    clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add('is-visible');
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2800);
  };

  const systemDialog = document.querySelector('#win2k-system-dialog');
  let systemDialogConfirm = null;
  let systemDialogReturnFocus = null;
  let busyTimer;
  const playSystemSound = (kind = 'info') => {
    if (!isWindowsMirc) return;
    try {
      const AudioEngine = window.AudioContext || window.webkitAudioContext;
      if (!AudioEngine) return;
      const audio = new AudioEngine();
      const oscillator = audio.createOscillator();
      const gain = audio.createGain();
      oscillator.type = 'square';
      oscillator.frequency.value = kind === 'warning' ? 220 : 440;
      gain.gain.setValueAtTime(.018, audio.currentTime);
      gain.gain.exponentialRampToValueAtTime(.001, audio.currentTime + .08);
      oscillator.connect(gain).connect(audio.destination);
      oscillator.start();
      oscillator.stop(audio.currentTime + .08);
      oscillator.addEventListener('ended', () => audio.close());
    } catch { /* System sound is optional and must never block the interface. */ }
  };
  const setWin2kBusy = (duration = 240) => {
    if (!isWindowsMirc) return;
    clearTimeout(busyTimer);
    document.body.classList.add('is-win2k-busy');
    document.querySelector('[data-win2k-ready]')?.replaceChildren('Working…');
    busyTimer = setTimeout(() => {
      document.body.classList.remove('is-win2k-busy');
      document.querySelector('[data-win2k-ready]')?.replaceChildren('Ready');
    }, reducedMotion ? 30 : duration);
  };
  const closeSystemDialog = (result = 'cancel') => {
    if (!systemDialog || systemDialog.hidden) return;
    const callback = systemDialogConfirm;
    systemDialogConfirm = null;
    systemDialog.hidden = true;
    document.body.classList.remove('has-win2k-dialog');
    if (result === 'confirm') callback?.();
    systemDialogReturnFocus?.focus?.();
    systemDialogReturnFocus = null;
  };
  const openSystemDialog = ({ title = 'Windows', message, kind = 'info', confirmLabel = 'OK', cancelLabel = '', extra = '', onConfirm = null }) => {
    if (!systemDialog) {
      if (onConfirm && window.confirm(message)) onConfirm();
      return;
    }
    systemDialogReturnFocus = document.activeElement;
    systemDialogConfirm = onConfirm;
    systemDialog.querySelector('#win2k-dialog-title').textContent = title;
    systemDialog.querySelector('#win2k-dialog-message').textContent = message;
    const icon = systemDialog.querySelector('[data-dialog-icon]');
    icon.textContent = kind === 'warning' ? '!' : kind === 'error' ? '×' : kind === 'question' ? '?' : 'i';
    icon.dataset.kind = kind;
    systemDialog.querySelector('[data-dialog-extra]').innerHTML = extra;
    systemDialog.querySelector('[data-dialog-actions]').innerHTML = `${confirmLabel ? `<button class="button win2k-default-button" type="button" data-dialog-result="confirm">${confirmLabel}</button>` : ''}${cancelLabel ? `<button class="button" type="button" data-dialog-result="cancel">${cancelLabel}</button>` : ''}`;
    systemDialog.hidden = false;
    document.body.classList.add('has-win2k-dialog');
    playSystemSound(kind);
    requestAnimationFrame(() => systemDialog.querySelector('[data-dialog-result="confirm"], [data-dialog-result="cancel"]')?.focus());
  };
  systemDialog?.addEventListener('click', (event) => {
    const resultButton = event.target.closest('[data-dialog-result]');
    if (resultButton) closeSystemDialog(resultButton.dataset.dialogResult);
  });

  const programChrome = document.querySelector('.win2k-program-chrome');
  const startButton = document.querySelector('#win2k-start-button');
  const startMenu = document.querySelector('#win2k-start-menu');
  const startCascadeItems = startMenu ? [...startMenu.querySelectorAll('[data-start-cascade]')] : [];
  const closeStartCascades = (except = null) => {
    startCascadeItems.forEach((item) => {
      if (item === except) return;
      item.classList.remove('is-open');
      item.querySelector('.win2k-start-cascade-trigger')?.setAttribute('aria-expanded', 'false');
    });
  };
  const positionStartSubmenu = (item) => {
    const trigger = item.querySelector('.win2k-start-cascade-trigger');
    const submenu = item.querySelector('.win2k-start-submenu');
    if (!trigger || !submenu) return;
    const triggerRect = trigger.getBoundingClientRect();
    const submenuWidth = submenu.offsetWidth;
    const submenuHeight = Math.min(submenu.scrollHeight, window.innerHeight - 8);
    let left = triggerRect.right - 2;
    if (left + submenuWidth > window.innerWidth - 4) left = window.innerWidth <= 760 ? Math.max(38, window.innerWidth - submenuWidth - 4) : triggerRect.left - submenuWidth + 2;
    let top = Math.max(4, triggerRect.top - 3);
    if (top + submenuHeight > window.innerHeight - 4) top = Math.max(4, window.innerHeight - submenuHeight - 4);
    submenu.style.left = `${Math.round(left)}px`;
    submenu.style.top = `${Math.round(top)}px`;
  };
  const openStartCascade = (item) => {
    closeStartCascades(item);
    item.classList.add('is-open');
    item.querySelector('.win2k-start-cascade-trigger')?.setAttribute('aria-expanded', 'true');
    positionStartSubmenu(item);
  };
  const closeStartMenu = () => {
    if (!startMenu) return;
    closeStartCascades();
    startMenu.hidden = true;
    startButton?.setAttribute('aria-expanded', 'false');
    startButton?.classList.remove('is-open');
  };
  startButton?.addEventListener('click', () => {
    const open = startMenu.hidden;
    startMenu.hidden = !open;
    startButton.setAttribute('aria-expanded', String(open));
    startButton.classList.toggle('is-open', open);
  });
  let startCascadeTimer;
  startCascadeItems.forEach((item) => {
    const trigger = item.querySelector('.win2k-start-cascade-trigger');
    trigger?.addEventListener('click', () => item.classList.contains('is-open') ? closeStartCascades() : openStartCascade(item));
    item.addEventListener('pointerenter', () => {
      clearTimeout(startCascadeTimer);
      if (window.matchMedia('(hover: hover)').matches) startCascadeTimer = setTimeout(() => openStartCascade(item), 150);
    });
    item.addEventListener('pointerleave', () => clearTimeout(startCascadeTimer));
  });
  startMenu?.querySelector('[data-start-run]')?.addEventListener('click', () => {
    closeStartMenu();
    openSystemDialog({
      title: 'Run',
      message: 'Type the name of a page you want to open.',
      kind: 'info',
      confirmLabel: 'OK',
      cancelLabel: 'Cancel',
      extra: '<label class="win2k-run-field">Open:<input id="win2k-run-command" value="database"></label>',
      onConfirm: () => {
        const command = document.querySelector('#win2k-run-command')?.value.toLowerCase() || '';
        const match = pages.find(([id, label]) => id === command || label.toLowerCase() === command);
        const url = new URL(window.location.href);
        url.searchParams.set('page', match?.[0] || 'home');
        history.pushState({}, '', url);
        setWin2kBusy();
        renderAppRoute();
      }
    });
    requestAnimationFrame(() => document.querySelector('#win2k-run-command')?.select());
  });
  window.addEventListener('resize', () => {
    const openItem = startCascadeItems.find((item) => item.classList.contains('is-open'));
    if (openItem) positionStartSubmenu(openItem);
  });
  let programMenuTimer;
  programChrome?.querySelectorAll('details').forEach((menu) => {
    menu.addEventListener('toggle', () => {
      if (!menu.open) return;
      programChrome.querySelectorAll('details').forEach((other) => {
        if (other !== menu) other.removeAttribute('open');
      });
    });
    menu.addEventListener('pointerenter', () => {
      if (!programChrome.querySelector('details[open]') || menu.open) return;
      clearTimeout(programMenuTimer);
      programMenuTimer = setTimeout(() => menu.setAttribute('open', ''), 120);
    });
    menu.addEventListener('pointerleave', () => clearTimeout(programMenuTimer));
  });
  programChrome?.addEventListener('click', (event) => {
    const command = event.target.closest('[data-menu-command]');
    if (command) {
      const label = command.childNodes[0]?.textContent?.trim() || command.textContent.trim();
      if (label.startsWith('About ')) {
        openSystemDialog({ title: `About ${productName}`, message: `${productName} is a Windows 2000-inspired interface for www.bodbil.com.`, kind: 'info' });
      } else if (helpEnabled && (label.toLowerCase().includes('help') || label === 'Keyboard shortcuts' || label === 'Explain metrics' || label === 'Field descriptions')) {
        const topic = label === 'Keyboard shortcuts' ? 'shortcuts' : label === 'Explain metrics' ? 'data-visualization' : label === 'Field descriptions' ? 'components' : getPage();
        const url = new URL(window.location.href);
        url.searchParams.set('page', 'help');
        url.searchParams.set('topic', topic);
        history.pushState({}, '', url);
        renderAppRoute();
      } else if (label === 'Exit' || label === 'Close') {
        openSystemDialog({ title: windowsSiteTitle, message: 'Do you want to close this application window?', kind: 'question', confirmLabel: 'Close', cancelLabel: 'Cancel', onConfirm: () => notify('The application window remains open in demo mode.') });
      } else {
        setWin2kBusy(160);
        notify(`${label} — demo action completed.`);
      }
      command.closest('details')?.removeAttribute('open');
    }
  });
  programChrome?.addEventListener('keydown', (event) => {
    const menus = [...programChrome.querySelectorAll('details')];
    const currentMenu = event.target.closest('details');
    if (!currentMenu) return;
    const commands = [...currentMenu.querySelectorAll('[data-menu-command]:not(:disabled)')];
    const commandIndex = commands.indexOf(document.activeElement);
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      currentMenu.setAttribute('open', '');
      commands[Math.min(commandIndex + 1, commands.length - 1)]?.focus();
    } else if (event.key === 'ArrowUp' && commandIndex >= 0) {
      event.preventDefault();
      commands[Math.max(commandIndex - 1, 0)]?.focus();
    } else if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      const nextMenu = menus[(menus.indexOf(currentMenu) + direction + menus.length) % menus.length];
      currentMenu.removeAttribute('open');
      nextMenu.setAttribute('open', '');
      nextMenu.querySelector('summary')?.focus();
    } else if (event.key === 'Escape') {
      currentMenu.removeAttribute('open');
      currentMenu.querySelector('summary')?.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (programChrome && !programChrome.contains(event.target)) programChrome.querySelectorAll('details[open]').forEach((menu) => menu.removeAttribute('open'));
    if (startMenu && !startMenu.contains(event.target) && !startButton?.contains(event.target)) closeStartMenu();
  });
  document.addEventListener('keydown', (event) => {
    if (helpEnabled && event.key === 'F1') {
      event.preventDefault();
      const currentPage = getPage();
      const topicAliases = { home: 'welcome', analysis: 'data-visualization', data: 'components', controls: 'components', content: 'news-feed', forum: 'forum', messages: 'news-feed' };
      const url = new URL(window.location.href);
      url.searchParams.set('page', 'help');
      url.searchParams.set('topic', topicAliases[currentPage] || 'navigation');
      history.pushState({}, '', url);
      closeStartMenu();
      renderAppRoute();
      return;
    }
    if (event.key === 'Escape' && systemDialog && !systemDialog.hidden) {
      closeSystemDialog('cancel');
      return;
    }
    if (isWindowsMirc && event.altKey && !event.ctrlKey && !event.metaKey) {
      const accelerator = { f: 'File', v: 'View', a: 'Favorites', t: 'Tools', c: 'Commands', w: 'Window', h: 'Help' }[event.key.toLowerCase()];
      const targetMenu = accelerator && programChrome?.querySelector(`[data-win-menu="${accelerator}"]`);
      if (targetMenu) {
        event.preventDefault();
        targetMenu.setAttribute('open', '');
        targetMenu.querySelector('summary')?.focus();
        return;
      }
    }
    if (isWindowsMirc && event.ctrlKey && event.key === 'Escape' && startMenu) {
      event.preventDefault();
      const open = startMenu.hidden;
      startMenu.hidden = !open;
      startButton?.setAttribute('aria-expanded', String(open));
      startButton?.classList.toggle('is-open', open);
      if (open) startMenu.querySelector('.win2k-start-cascade-trigger,.win2k-start-command')?.focus();
      return;
    }
    if (event.key !== 'Escape' || !startMenu || startMenu.hidden) return;
    const openItem = startCascadeItems.find((item) => item.classList.contains('is-open'));
    if (openItem) {
      const trigger = openItem.querySelector('.win2k-start-cascade-trigger');
      closeStartCascades();
      trigger?.focus();
      return;
    }
    closeStartMenu();
    startButton?.focus();
  });

  const updateWindowsChrome = (page) => {
    if (!programChrome) return;
    const config = windowsPageMenus[page];
    document.querySelector('#win2k-program-title').textContent = windowsSiteTitle;
    const statusPage = document.querySelector('[data-win2k-page]');
    if (statusPage) statusPage.textContent = `Page: ${config.title}`;
    programChrome.querySelectorAll('[data-win-menu]').forEach((menu) => {
      const items = config.menus[menu.dataset.winMenu];
      menu.querySelector('[data-win-menu-content]').innerHTML = items.map((item) => {
        if (item === '-') return '<hr>';
        const [label, shortcut = ''] = item;
        return `<button type="button" data-menu-command>${label}${shortcut ? `<kbd>${shortcut}</kbd>` : ''}</button>`;
      }).join('');
    });
  };

  const metricCard = (label, value, change, tone = '') => isWindowsMirc ? `
    <fieldset class="metric-card win2k-dashboard-group win2k-group ${tone}">
      <legend>${label}</legend>
      <strong>${value}</strong>
      <small><b>${change}</b> compared with the previous period</small>
    </fieldset>` : `
    <article class="metric-card surface ${tone}">
      <div class="metric-top"><span>${label}</span><span class="metric-dot"></span></div>
      <strong>${value}</strong>
      <small><b>${change}</b> compared with the previous period</small>
    </article>`;

  const pageHeader = (eyebrow, title, description, action = '') => `
    <header class="page-heading">
      <div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p>${description}</p></div>
      ${action}
    </header>`;

  const windowsAppDescriptions = {
    analysis: 'Charts, statistics and forecasts',
    data: 'Search, tables, details and forms',
    content: 'News feeds and long-form content',
    forum: 'Categories, topics and discussions',
    messages: 'Inbox, reading pane and replies',
    calendar: 'Month view and appointments',
    files: 'Folders, files and document lists'
  };

  const windowsAppLauncher = () => isWindowsMirc ? `
    <fieldset class="win2k-app-launcher win2k-dashboard-group win2k-group">
      <legend>Applications</legend>
      <div class="win2k-app-launcher-grid">
        ${windowsPrograms.filter(([id]) => id !== 'home').map(([id, label]) => `<a href="?page=${id}" data-page-link="${id}">${win2kIcon(id)}<span><strong>${label}</strong><small>${windowsAppDescriptions[id]}</small></span></a>`).join('')}
      </div>
    </fieldset>` : '';

  const homePage = () => `
    <section class="page page-home">
      <section class="hero surface ${isWindowsMirc ? 'win2k-page-intro' : ''}">
        <div class="hero-copy">
          ${isWindowsMirc ? '<p class="eyebrow">Operations</p><h1>Operations <span>Center</span></h1><p class="hero-lead">Open the sample applications or review active projects, team focus, new signals and the current forecast.</p>' : `<p class="eyebrow">Good morning, Alex</p><h1>From signal to <span>better decisions.</span></h1><p class="hero-lead">${productName} brings the team’s most important work, business signals and next steps into one focused workspace.</p>`}
          <div class="button-row">
            <a class="button primary" href="?page=analysis" data-page-link="analysis">Open analytics <span>→</span></a>
            <button class="button secondary" type="button" data-action="report">Create report</button>
          </div>
          <div class="hero-meta"><span><i></i> 14 data sources active</span><span>Last synced 09:42</span></div>
        </div>
        <div class="hero-visual" aria-label="This week’s results">
          <div class="signal-card signal-main">
            <span>Weekly momentum</span>
            <strong>+24,8%</strong>
            <div class="spark-bars" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div>
          </div>
          <div class="signal-card signal-float"><span>Target</span><strong>82%</strong><small>on track</small></div>
          <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
        </div>
      </section>

      <section class="metrics-grid" aria-label="Key metrics">
        ${metricCard('Active projects', '18', '+12%')}
        ${metricCard('Team focus', '87%', '+8%')}
        ${metricCard('New signals', '1,284', '+19%')}
        ${metricCard('Forecast', '$4.2M', '+6%')}
      </section>

      ${windowsAppLauncher()}

      <section class="dashboard-grid">
        <${isWindowsMirc ? 'fieldset' : 'article'} class="focus-card ${isWindowsMirc ? 'win2k-dashboard-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? '<legend>Team focus</legend>' : '<div class="section-title"><div><p class="eyebrow">Priority</p><h2>Team focus</h2></div><button class="icon-button" data-action="more" aria-label="More options">•••</button></div>'}
          <div class="focus-list">
            <div class="focus-item"><span class="focus-index">01</span><div><strong>Nordic Launch</strong><small>Marketing · 8 tasks remaining</small></div><div class="progress"><i style="width:76%"></i></div><b>76%</b></div>
            <div class="focus-item"><span class="focus-index">02</span><div><strong>Project Aurora</strong><small>Product · 12 tasks remaining</small></div><div class="progress"><i style="width:64%"></i></div><b>64%</b></div>
            <div class="focus-item"><span class="focus-index">03</span><div><strong>Atlas Migration</strong><small>Technology · 4 tasks remaining</small></div><div class="progress"><i style="width:88%"></i></div><b>88%</b></div>
          </div>
        </${isWindowsMirc ? 'fieldset' : 'article'}>
        <${isWindowsMirc ? 'fieldset' : 'article'} class="activity-card ${isWindowsMirc ? 'win2k-dashboard-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? '<legend>Recent activity</legend>' : '<div class="section-title"><div><p class="eyebrow">Live</p><h2>Recent activity</h2></div><span class="live-badge">Now</span></div>'}
          <div class="activity-list">
            <div><span class="activity-avatar purple">EL</span><p><strong>Elin</strong> published the Q3 analysis<small>8 minutes ago</small></p></div>
            <div><span class="activity-avatar green">MK</span><p><strong>Malik</strong> updated the forecast<small>21 minutes ago</small></p></div>
            <div><span class="activity-avatar orange">SO</span><p><strong>Sofia</strong> added 14 data points<small>46 minutes ago</small></p></div>
          </div>
        </${isWindowsMirc ? 'fieldset' : 'article'}>
      </section>
    </section>`;

  const analysisPage = () => `
    <section class="page page-analysis">
      ${pageHeader('Analysis application', 'Insight Center', 'Explore performance, growth, forecasts and the areas where the team should act next.', `
        <div class="segmented" role="group" aria-label="Select period"><button>7 days</button><button class="is-active">30 days</button><button>12 months</button></div>`)}
      <section class="metrics-grid analysis-metrics">
        ${metricCard('Net revenue', '$1.84M', '+18.4%', 'accent-card')}
        ${metricCard('Conversion', '6.72%', '+1.2%')}
        ${metricCard('Average value', '$12,480', '+4.6%')}
        ${metricCard('Retention', '91.3%', '+2.8%')}
      </section>
      <section class="analysis-grid">
        <${isWindowsMirc ? 'fieldset' : 'article'} class="chart-card chart-wide ${isWindowsMirc ? 'win2k-analysis-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? '<legend>Revenue & forecast</legend><div class="chart-legend win2k-chart-legend"><span><i class="actual"></i>Actual</span><span><i class="forecast"></i>Forecast</span></div>' : '<div class="section-title"><div><p class="eyebrow">Trend</p><h2>Revenue & forecast</h2></div><div class="chart-legend"><span><i class="actual"></i>Actual</span><span><i class="forecast"></i>Forecast</span></div></div>'}
          <div class="chart-area" aria-label="Bar chart of revenue growth">
            <div class="y-labels"><span>500k</span><span>375k</span><span>250k</span><span>125k</span><span>0</span></div>
            <div class="bar-chart">
              ${[['May',42,52],['Jun',55,61],['Jul',49,66],['Aug',68,72],['Sep',77,79],['Oct',82,88],['Nov',91,96]].map(([m,a,f]) => `<div class="bar-group"><div class="bars"><i class="bar-actual" style="height:${a}%"></i><i class="bar-forecast" style="height:${f}%"></i></div><span>${m}</span></div>`).join('')}
            </div>
          </div>
        </${isWindowsMirc ? 'fieldset' : 'article'}>
        <${isWindowsMirc ? 'fieldset' : 'article'} class="chart-card ${isWindowsMirc ? 'win2k-analysis-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? '<legend>Signal distribution</legend>' : '<div class="section-title"><div><p class="eyebrow">Quality</p><h2>Signal distribution</h2></div></div>'}
          <div class="donut-wrap"><div class="donut"><div><strong>1,284</strong><span>signals</span></div></div></div>
          <div class="donut-legend"><span><i class="tone-a"></i>Positive <b>54%</b></span><span><i class="tone-b"></i>Neutral <b>31%</b></span><span><i class="tone-c"></i>Needs action <b>15%</b></span></div>
        </${isWindowsMirc ? 'fieldset' : 'article'}>
        <${isWindowsMirc ? 'fieldset' : 'article'} class="insight-card ${isWindowsMirc ? 'win2k-analysis-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? `<legend>${productName} Insight</legend>` : `<p class="eyebrow">${productName} Insight</p>`}<h2>Returning customers offer the greatest potential.</h2><p>This segment is growing 2.4× faster than average. A targeted campaign could generate an estimated <strong>+$186,000</strong> next month.</p><button class="${isWindowsMirc ? 'button compact' : 'text-button'}" data-action="insight">View recommendation ${isWindowsMirc ? '' : '<span>→</span>'}</button>
        </${isWindowsMirc ? 'fieldset' : 'article'}>
      </section>
    </section>`;

  const dataPage = (query = '', status = 'All', requestedPage = 1) => {
    const filtered = records.filter((row) => {
      const matchesText = row.join(' ').toLowerCase().includes(query.toLowerCase());
      return matchesText && (status === 'All' || row[2] === status);
    });
    const pageSize = isWindowsMirc ? 4 : Math.max(filtered.length, 1);
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const currentPage = Math.min(Math.max(Number(requestedPage) || 1, 1), totalPages);
    const pageStartIndex = (currentPage - 1) * pageSize;
    const visibleRecords = isWindowsMirc ? filtered.slice(pageStartIndex, pageStartIndex + pageSize) : filtered;
    const firstVisible = filtered.length ? pageStartIndex + 1 : 0;
    const lastVisible = Math.min(pageStartIndex + visibleRecords.length, filtered.length);
    return `
      <section class="page page-data">
        ${pageHeader('Database application', 'Project Manager', 'Search, filter and monitor active initiatives, then open a record for more information.', `<a class="button primary" href="?page=forms" data-page-link="forms">+ New project</a>`)}
        <${isWindowsMirc ? 'fieldset' : 'section'} class="data-panel ${isWindowsMirc ? 'win2k-data-group win2k-group' : 'surface'}">
          ${isWindowsMirc ? '<legend>Project list</legend>' : ''}
          <div class="table-toolbar">
            <label class="search-field"><span>Search</span><input id="record-search" type="search" value="${query.replaceAll('"', '&quot;')}" placeholder="Search projects, teams or status…"></label>
            ${isWindowsMirc ? '<button class="button secondary compact win2k-search-button" type="button" data-search-submit>Search</button>' : ''}
            <label class="filter-field"><span>Status</span><select id="status-filter"><option ${status === 'All' ? 'selected' : ''}>All</option><option ${status === 'Active' ? 'selected' : ''}>Active</option><option ${status === 'Review' ? 'selected' : ''}>Review</option><option ${status === 'Paused' ? 'selected' : ''}>Paused</option></select></label>
            <button class="button secondary compact" data-action="export">Export</button>
          </div>
          <div class="table-wrap" tabindex="0" aria-label="Project list, scroll horizontally">
            <table>
              <thead><tr><th scope="col"><input type="checkbox" aria-label="Select all"></th><th scope="col">Project</th><th scope="col">Area</th><th scope="col">Status</th><th scope="col">Data quality</th><th scope="col">Updated</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
              <tbody>${visibleRecords.length ? visibleRecords.map((row, index) => `<tr><td><input type="checkbox" aria-label="Select ${row[0]}"></td><td><span class="record-mark">${String(pageStartIndex + index + 1).padStart(2, '0')}</span><strong>${row[0]}</strong></td><td>${row[1]}</td><td><span class="status status-${row[2].toLowerCase()}"><i></i>${row[2]}</span></td><td><span class="quality"><i style="width:${row[3]}"></i></span><b>${row[3]}</b></td><td>${row[4]}</td><td><a class="row-action" href="?page=details" data-page-link="details" aria-label="Open ${row[0]}">→</a></td></tr>`).join('') : `<tr><td colspan="7" class="empty-state">No projects match your search.</td></tr>`}</tbody>
            </table>
          </div>
          <div class="table-footer"><span>${isWindowsMirc ? `Showing ${firstVisible}–${lastVisible} of ${filtered.length} projects` : `Showing ${filtered.length} of ${records.length} projects`}</span>${isWindowsMirc ? `<div class="pagination win2k-pagination" data-record-pagination data-current-page="${currentPage}" data-total-pages="${totalPages}"><button type="button" data-record-page="first" aria-label="First page" ${currentPage === 1 ? 'disabled' : ''}>&lt;&lt;</button><button type="button" data-record-page="prev" aria-label="Previous page" ${currentPage === 1 ? 'disabled' : ''}>&lt;</button>${Array.from({ length: totalPages }, (_, index) => `<button type="button" data-record-page="${index + 1}" aria-label="Page ${index + 1}" class="${currentPage === index + 1 ? 'is-active' : ''}" ${currentPage === index + 1 ? 'aria-current="page"' : ''}>${index + 1}</button>`).join('')}<button type="button" data-record-page="next" aria-label="Next page" ${currentPage === totalPages ? 'disabled' : ''}>&gt;</button><button type="button" data-record-page="last" aria-label="Last page" ${currentPage === totalPages ? 'disabled' : ''}>&gt;&gt;</button></div>` : `<div class="pagination"><button disabled>←</button><button class="is-active">1</button><button>2</button><button>→</button></div>`}</div>
        </${isWindowsMirc ? 'fieldset' : 'section'}>
      </section>`;
  };

  const loginPage = () => isWindowsMirc ? `
    <section class="page page-login win2k-login-page">
      ${pageHeader('Secure area', 'Sign in', 'Use your work account to open your personal workspace and continue where you left off.', `<a class="button compact" href="?page=home" data-page-link="home">Go to Overview</a>`)}
      <section class="win2k-login-grid">
        <fieldset class="win2k-login-group win2k-group"><legend>Account details</legend>
          <form id="login-form">
            <label>Email address<input name="email" type="email" autocomplete="email" value="demo@${productSlug}.local" required></label>
            <label>Password<span class="password-wrap"><input name="password" type="password" autocomplete="current-password" value="demo1234" required><button class="button compact" type="button" id="show-password">Show</button></span></label>
            <label class="check-label"><input type="checkbox" checked> Remember me on this computer</label>
            <div class="win2k-login-actions"><button class="button win2k-default-button auth-submit" type="submit">Sign in</button><button class="button" type="button" data-action="forgot">Forgot password</button></div>
          </form>
        </fieldset>
        <fieldset class="win2k-login-group win2k-group"><legend>Secure connection</legend>
          <div class="win2k-login-information"><div class="win2k-dialog-message"><span aria-hidden="true">i</span><p><strong>Protected area</strong>Your connection to the workspace is encrypted.</p></div><h2>Welcome back</h2><p>Your signals, projects and decisions are collected in one place.</p><ul><li>Pre-filled demo account</li><li>No information is sent</li><li>12 colleagues are active now</li></ul></div>
        </fieldset>
      </section>
    </section>` : `
    <section class="page auth-page">
      <div class="auth-story">
        <a class="back-link" href="?page=home" data-page-link="home">← Back to workspace</a>
        <div class="auth-story-copy"><p class="eyebrow">${productName} workspace</p><h1>Welcome back to your <span>flow.</span></h1><p>One clear place for signals, collaboration and decisions that move the business forward.</p></div>
        <div class="auth-proof surface"><div class="proof-avatars"><span>EL</span><span>MK</span><span>SO</span><span>+8</span></div><p><strong>12 colleagues</strong> are active in the workspace now.</p></div>
      </div>
      <div class="auth-card surface">
        <div class="auth-heading"><span class="brand-mark large">N</span><p class="eyebrow">Secure area</p><h2>Sign in</h2><p>Use your work account to continue.</p></div>
        <form id="login-form">
          <label>Email address<input name="email" type="email" autocomplete="email" value="demo@${productSlug}.local" required></label>
          <label>Password<span class="password-wrap"><input name="password" type="password" autocomplete="current-password" value="demo1234" required><button type="button" id="show-password">Show</button></span></label>
          <div class="form-meta"><label class="check-label"><input type="checkbox" checked> Remember me</label><button type="button" class="link-button" data-action="forgot">Forgot password?</button></div>
          <button class="button primary auth-submit" type="submit">Sign in <span>→</span></button>
          <p class="demo-note"><i></i>Pre-filled demo account — no information is sent.</p>
        </form>
      </div>
    </section>`;

  const profilePage = () => isWindowsMirc ? `
    <section class="page page-profile win2k-profile-page">
      ${pageHeader('Personal workspace', 'My profile', 'Manage your profile, shortcuts and how the website presents important information.', `<a class="button compact" href="?page=login" data-page-link="login">View sign-in demo</a>`)}
      <section class="win2k-profile-layout">
        <fieldset class="profile-hero win2k-profile-summary win2k-group"><legend>Profile</legend>
          <div class="profile-avatar"><span>AH</span><i title="Online"></i></div><div><h2>Alex Holm</h2><p><strong>Workspace lead</strong></p><p>Strategy & business development · Stockholm</p><div class="profile-tags"><span>Analytics</span><span>Product</span><span>Nordics</span></div></div><button class="button compact" data-action="edit-profile">Edit</button>
        </fieldset>
        <section class="win2k-profile-stats" aria-label="Personal metrics">
          <fieldset class="win2k-profile-stat win2k-group"><legend>Decisions this month</legend><strong>24</strong><small>+8 compared with July</small></fieldset>
          <fieldset class="win2k-profile-stat win2k-group"><legend>Time saved</legend><strong>18.4 h</strong><small>with automations</small></fieldset>
          <fieldset class="win2k-profile-stat win2k-group"><legend>Team impact</legend><strong>92</strong><small>top 8% of the team</small></fieldset>
        </section>
        <fieldset class="settings-card win2k-profile-group win2k-group"><legend>Your experience</legend>
          <div class="settings-list">
            <label><span><strong>Daily summary</strong><small>Receive today’s most important signals at 08:00</small></span><input class="toggle" type="checkbox" checked></label>
            <label><span><strong>Focus mode</strong><small>Hide secondary information during work sessions</small></span><input class="toggle" type="checkbox"></label>
            <label><span><strong>Smart recommendations</strong><small>Let the website suggest the next best action</small></span><input class="toggle" type="checkbox" checked></label>
          </div>
        </fieldset>
        <fieldset class="saved-card win2k-profile-group win2k-group"><legend>Saved views</legend>
          <a href="?page=analysis" data-page-link="analysis"><span class="saved-icon">01</span><div><strong>Executive report Q3</strong><small>Analytics · updated today</small></div><b>→</b></a>
          <a href="?page=data" data-page-link="data"><span class="saved-icon">02</span><div><strong>High-potential projects</strong><small>Database · 18 records</small></div><b>→</b></a>
          <a href="?page=analysis" data-page-link="analysis"><span class="saved-icon">03</span><div><strong>Nordic growth signals</strong><small>Analytics · updated yesterday</small></div><b>→</b></a>
        </fieldset>
      </section>
    </section>` : `
    <section class="page page-profile">
      ${pageHeader('Personal workspace', 'My profile', `Manage your profile, shortcuts and how ${productName} presents important information.`, `<a class="button secondary" href="?page=login" data-page-link="login">View sign-in demo</a>`)}
      <section class="profile-grid">
        <article class="profile-hero surface">
          <div class="profile-avatar"><span>AH</span><i></i></div><div><p class="eyebrow">Workspace lead</p><h2>Alex Holm</h2><p>Strategy & business development · Stockholm</p><div class="profile-tags"><span>Analytics</span><span>Product</span><span>Nordics</span></div></div><button class="button secondary compact" data-action="edit-profile">Edit</button>
        </article>
        <article class="personal-stats surface"><div><span>Decisions this month</span><strong>24</strong><small>+8 compared with July</small></div><div><span>Time saved</span><strong>18.4 h</strong><small>with automations</small></div><div><span>Team impact</span><strong>92</strong><small>top 8% of the team</small></div></article>
        <article class="settings-card surface">
          <div class="section-title"><div><p class="eyebrow">Preferences</p><h2>Your experience</h2></div></div>
          <div class="settings-list">
            <label><span><strong>Daily summary</strong><small>Receive today’s most important signals at 08:00</small></span><input class="toggle" type="checkbox" checked></label>
            <label><span><strong>Focus mode</strong><small>Hide secondary information during work sessions</small></span><input class="toggle" type="checkbox"></label>
            <label><span><strong>Smart recommendations</strong><small>Let ${productName} suggest the next best action</small></span><input class="toggle" type="checkbox" checked></label>
          </div>
        </article>
        <article class="saved-card surface">
          <div class="section-title"><div><p class="eyebrow">Quick access</p><h2>Saved views</h2></div><button class="icon-button" data-action="more" aria-label="More options">•••</button></div>
          <a href="?page=analysis" data-page-link="analysis"><span class="saved-icon">01</span><div><strong>Executive report Q3</strong><small>Analytics · updated today</small></div><b>→</b></a>
          <a href="?page=data" data-page-link="data"><span class="saved-icon">02</span><div><strong>High-potential projects</strong><small>Database · 18 records</small></div><b>→</b></a>
          <a href="?page=analysis" data-page-link="analysis"><span class="saved-icon">03</span><div><strong>Nordic growth signals</strong><small>Analytics · updated yesterday</small></div><b>→</b></a>
        </article>
      </section>
    </section>`;

  const controlsPage = () => `
    <section class="page page-controls">
      ${pageHeader('Settings', 'Component Catalog', 'Inspect the complete set of fields, buttons, choices, sliders and status components available to every Win2k UI application.')}
      <div class="win2k-control-toolbar surface" role="toolbar" aria-label="Example tools">
        <button class="button compact" type="button" data-action="control-new">New</button>
        <button class="button compact" type="button" data-action="control-open">Open</button>
        <button class="button compact" type="button" data-action="control-save">Save</button>
        <span aria-hidden="true"></span>
        <button class="button compact" type="button" data-action="control-print">Print</button>
        <button class="button compact" type="button" disabled>Disabled</button>
      </div>
      <section class="win2k-control-grid">
        <fieldset class="win2k-control-group win2k-group"><legend>Input fields</legend>
          <div class="win2k-form-grid">
            <label>Standard text field<input type="text" value="${productName} Workspace"></label>
            <label>Email address<input type="email" value="alex@${productSlug}.local"></label>
            <label>Password<span class="win2k-inline-field"><input id="control-password" type="password" value="demo1234"><button class="button compact" type="button" data-control-password>Show</button></span></label>
            <label>Search field<span class="win2k-inline-field"><input type="search" placeholder="Search the library"><button class="button compact" type="button" data-action="control-search">Search</button></span></label>
            <label>Number<input type="number" value="42" min="0" max="100"></label>
            <label>Date<input type="date" value="2026-08-05"></label>
            <label>Read-only<input type="text" value="Cannot be changed" readonly></label>
            <label>Disabled<input type="text" value="Not available" disabled></label>
            <label class="wide">Multiline text field<textarea rows="4">Notes and longer messages are entered here.</textarea></label>
          </div>
        </fieldset>

        <fieldset class="win2k-control-group win2k-group"><legend>Buttons and commands</legend>
          <div class="win2k-button-showcase">
            <button class="button win2k-default-button" type="button" data-action="control-confirm">OK</button>
            <button class="button" type="button" data-action="control-cancel">Cancel</button>
            <button class="button" type="button" data-action="control-apply">Apply</button>
            <button class="button is-pressed" type="button" aria-pressed="true">Pressed</button>
            <button class="button" type="button" disabled>Disabled</button>
          </div>
          <div class="win2k-mini-toolbar" role="toolbar" aria-label="Small command buttons">
            <button type="button" aria-label="New document">N</button><button type="button" aria-label="Open">O</button><button type="button" aria-label="Save">S</button><i aria-hidden="true"></i><button type="button" aria-label="Copy">C</button><button type="button" aria-label="Paste">P</button>
          </div>
          <div class="win2k-dialog-message"><span aria-hidden="true">i</span><p><strong>Information</strong>All standard buttons use the same Windows 2000 bevel and keyboard focus.</p></div>
        </fieldset>

        <fieldset class="win2k-control-group win2k-group"><legend>Choices and options</legend>
          <div class="win2k-choice-grid">
            <div><strong>Check boxes</strong><label><input type="checkbox" checked> Show toolbar</label><label><input type="checkbox"> Start automatically</label><label class="disabled"><input type="checkbox" disabled> Locked option</label></div>
            <div><strong>Radio buttons</strong><label><input type="radio" name="density" checked> Normal</label><label><input type="radio" name="density"> Compact</label><label><input type="radio" name="density"> Large</label></div>
            <div><strong>ON/OFF</strong><label class="win2k-toggle-row"><span>Automatic sync</span><input class="toggle" type="checkbox" checked></label><label class="win2k-toggle-row"><span>Sound</span><input class="toggle" type="checkbox"></label></div>
          </div>
        </fieldset>

        <fieldset class="win2k-control-group win2k-group"><legend>Lists and selectors</legend>
          <div class="win2k-form-grid">
            <label>Drop-down list<select><option>Windows 2000</option><option>Windows 98</option><option>Windows XP</option></select></label>
            <label>Sort by<select><option>Name</option><option>Date</option><option>Status</option></select></label>
            <label class="wide">List box<select class="win2k-listbox" size="5" multiple><option selected>Overview</option><option>Analytics</option><option>Database</option><option>My profile</option><option>Controls</option></select></label>
            <label class="wide">File picker<input class="win2k-file-input" type="file"></label>
          </div>
        </fieldset>

        <fieldset class="win2k-control-group win2k-group"><legend>Sliders and status</legend>
          <div class="win2k-range-list">
            <label><span>Volume</span><span class="win2k-range-row"><input id="volume-range" data-win-range type="range" min="0" max="100" value="65"><output for="volume-range">65</output></span></label>
            <label><span>Brightness</span><span class="win2k-range-row"><input id="brightness-range" data-win-range type="range" min="0" max="100" value="40"><output for="brightness-range">40</output></span></label>
          </div>
          <div class="win2k-progress-list">
            <label><span>Loading data</span><span class="win2k-progress" role="progressbar" aria-label="Loading data" aria-valuemin="0" aria-valuemax="100" aria-valuenow="68"><i style="width:68%"></i></span><b>68%</b></label>
            <label><span>Installation</span><span class="win2k-progress" role="progressbar" aria-label="Installation" aria-valuemin="0" aria-valuemax="100" aria-valuenow="32"><i style="width:32%"></i></span><b>32%</b></label>
          </div>
        </fieldset>

        <fieldset class="win2k-control-group win2k-group"><legend>Tabs and messages</legend>
          <div class="win2k-demo-tabs" role="tablist" aria-label="Example tabs"><button class="is-active" type="button" role="tab" aria-selected="true">General</button><button type="button" role="tab" aria-selected="false">Advanced</button><button type="button" role="tab" aria-selected="false">About</button></div>
          <div class="win2k-tab-panel" role="tabpanel"><p><strong>General settings</strong></p><p>The tab content appears in a recessed white panel, just like classic system dialogs.</p></div>
          <div class="win2k-message-list"><p class="info"><b>i</b> Information about the current setting.</p><p class="warning"><b>!</b> Check the value before continuing.</p><p class="error"><b>×</b> A required field is missing.</p></div>
        </fieldset>
      </section>
    </section>`;

  const formsPage = () => `
    <section class="page page-reference">
      ${pageHeader('Project Manager', 'Create project', 'Enter project information, assign responsibility and choose how the new record should be published.', `<button class="button compact win2k-default-button" data-action="reference-save">Save draft</button>`)}
      <section class="win2k-reference-grid">
        <fieldset class="win2k-reference-group win2k-group"><legend>Project information</legend><div class="win2k-form-grid"><label>Project name<input type="text" value="New customer portal"></label><label>Reference<input type="text" value="PROJ-0025"></label><label>Area<select><option>Product</option><option>Technology</option><option>Marketing</option><option>Analytics</option></select></label><label>Owner<select><option>Alex Holm</option><option>Elin Larsson</option><option>Malik Khan</option></select></label><label class="wide">Summary<textarea rows="3">Create a clearer self-service experience for customers.</textarea></label><label class="wide">Objectives and notes<textarea rows="8">Describe the expected result, important milestones and any dependencies here.</textarea></label></div></fieldset>
        <div class="win2k-reference-stack">
          <fieldset class="win2k-reference-group win2k-group"><legend>Planning and status</legend><div class="win2k-choice-grid single"><div><strong>Status</strong><label><input type="radio" name="publish" checked> Draft</label><label><input type="radio" name="publish"> Active</label><label><input type="radio" name="publish"> On hold</label></div><div><strong>Options</strong><label><input type="checkbox" checked> Add to team focus</label><label><input type="checkbox"> Confidential project</label><label><input type="checkbox" checked> Notify the project team</label></div></div><div class="win2k-form-grid compact"><label>Start date<input type="date" value="2026-08-06"></label><label>Target date<input type="date" value="2026-10-30"></label></div></fieldset>
          <fieldset class="win2k-reference-group win2k-group"><legend>Media and actions</legend><div class="win2k-form-grid"><label class="wide">Image or document<input class="win2k-file-input" type="file"></label><label class="wide">Alternative text<input type="text" placeholder="Describe the file content"></label></div><div class="win2k-form-actions"><button class="button win2k-default-button" data-action="reference-publish">Publish</button><button class="button" data-action="reference-preview">Preview</button><button class="button" data-action="reference-cancel">Cancel</button></div></fieldset>
        </div>
      </section>
    </section>`;

  const detailsPage = () => `
    <section class="page page-reference">
      ${pageHeader('Project Manager', 'Project Aurora', 'Review responsibility, current status, related material and the complete activity history for this project.', `<button class="button compact" data-action="reference-edit">Edit project</button>`)}
      <section class="win2k-reference-grid details">
        <fieldset class="win2k-reference-group win2k-group"><legend>Summary</legend><dl class="win2k-description-list"><div><dt>Status</dt><dd><span class="win2k-info-status active"><i>✓</i>Active</span></dd></div><div><dt>Owner</dt><dd>Malik Khan</dd></div><div><dt>Area</dt><dd>Product</dd></div><div><dt>Start date</dt><dd>14 January 2026</dd></div><div><dt>Last changed</dt><dd>Today 09:42</dd></div><div><dt>Reference</dt><dd>PROJ-0024</dd></div></dl></fieldset>
        <fieldset class="win2k-reference-group win2k-group"><legend>Related records</legend><div class="win2k-link-list"><a href="?page=analysis" data-page-link="analysis"><span>01</span><div><strong>Executive report Q3</strong><small>Analytics · updated today</small></div><b>→</b></a><a href="?page=data" data-page-link="data"><span>02</span><div><strong>Nordic Launch</strong><small>Project · active</small></div><b>→</b></a><a href="?page=files" data-page-link="files"><span>03</span><div><strong>Project brief.pdf</strong><small>Document · 2.4 MB</small></div><b>→</b></a></div></fieldset>
        <fieldset class="win2k-reference-group win2k-group wide"><legend>Description</legend><div class="win2k-reading-panel"><h2>Purpose and scope</h2><p>Project Aurora brings together the product team’s work on the next generation of the digital service. The goal is to reduce friction, improve data quality and create a clearer experience.</p><h3>Next steps</h3><ul><li>Complete user testing</li><li>Validate the migration plan</li><li>Prepare the decision presentation</li></ul></div></fieldset>
        <fieldset class="win2k-reference-group win2k-group wide"><legend>Activity history</legend><div class="win2k-timeline"><div><time>09:42</time><strong>Malik updated the forecast</strong><span>Today</span></div><div><time>08:15</time><strong>Elin attached Project brief.pdf</strong><span>Today</span></div><div><time>16:28</time><strong>Alex changed the status to Active</strong><span>Yesterday</span></div></div></fieldset>
      </section>
    </section>`;

  const contentPage = () => `
    <section class="page page-reference page-newsroom">
      ${pageHeader('Publishing application', 'Newsroom', 'Review current stories, prepare announcements and demonstrate both feed and long-form article layouts.', `<button class="button compact" data-action="news-article">New article</button>`)}
      <div class="win2k-news-toolbar surface" role="toolbar" aria-label="News filters"><label>Section<select><option>All sections</option><option>Company</option><option>Projects</option><option>People</option></select></label><label>Search<input type="search" placeholder="Search newsroom…"></label><button class="button compact" data-action="news-refresh">Refresh</button></div>
      <section class="win2k-news-layout">
        <fieldset class="win2k-reference-group win2k-group"><legend>Latest stories</legend><div class="win2k-news-list">
          <button class="unread active"><span>i</span><div><strong>Project Aurora reaches its first delivery milestone</strong><small>Projects · Elin Larsson · Today 09:18</small></div></button>
          <button class="unread"><span>i</span><div><strong>August forecast updated after strong Nordic growth</strong><small>Company · Malik Khan · Today 08:04</small></div></button>
          <button><span>✓</span><div><strong>Welcome Sofia Berg to the product team</strong><small>People · Alex Holm · Yesterday</small></div></button>
          <button><span>i</span><div><strong>New document guidelines are now available</strong><small>Company · System · 4 Aug</small></div></button>
        </div><div class="win2k-file-status">4 stories · 2 unread</div></fieldset>
        <fieldset class="win2k-reference-group win2k-group"><legend>Article preview</legend><article class="win2k-article win2k-news-article"><p class="eyebrow">Projects · 6 August 2026</p><h2>Project Aurora reaches its first delivery milestone</h2><p class="lead">The first part of the new customer experience has been delivered for internal testing.</p><p>The team completed the planned service flow and migrated the first collection of project data. Early tests show faster navigation and fewer manual steps.</p><blockquote>“This milestone gives us a stable base for the remaining customer journeys.” — Elin Larsson, product lead</blockquote><h3>What happens next?</h3><ul><li>User testing begins on Monday.</li><li>The migration plan will be reviewed this week.</li><li>A complete progress report will be published on 18 August.</li></ul><p><a href="?page=details" data-page-link="details">Open Project Aurora in Project Manager</a></p></article></fieldset>
        <aside class="win2k-reference-stack"><fieldset class="win2k-reference-group win2k-group"><legend>Publishing status</legend><dl class="win2k-description-list"><div><dt>Status</dt><dd><span class="win2k-info-status active"><i>✓</i>Published</span></dd></div><div><dt>Audience</dt><dd>All employees</dd></div><div><dt>Comments</dt><dd>12</dd></div><div><dt>Views</dt><dd>284</dd></div></dl></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Related applications</legend><nav class="win2k-side-links"><a href="?page=forum" data-page-link="forum">Community Forum</a><a href="?page=messages" data-page-link="messages">Mail</a><a href="?page=files" data-page-link="files">File Explorer</a></nav></fieldset></aside>
      </section>
    </section>`;

  const forumPage = () => `
    <section class="page page-reference page-forum">
      ${pageHeader('Community application', 'Community Forum', 'Browse categories, follow active discussions and see how a complete forum can use the Win2k UI component system.', `<button class="button compact" data-action="forum-topic">New topic</button>`)}
      <section class="win2k-forum-layout">
        <fieldset class="win2k-reference-group win2k-group"><legend>Categories</legend><div class="win2k-forum-categories">
          <a href="#forum-thread"><span class="win2k-forum-icon">i</span><div><strong>Announcements</strong><small>Official updates and important information</small></div><b>12 topics<br><small>48 posts</small></b><time>Today 09:18<br><small>by Elin</small></time></a>
          <a href="#forum-thread"><span class="win2k-forum-icon">P</span><div><strong>Projects and planning</strong><small>Discuss current projects, decisions and deliveries</small></div><b>38 topics<br><small>214 posts</small></b><time>Today 08:52<br><small>by Malik</small></time></a>
          <a href="#forum-thread"><span class="win2k-forum-icon">?</span><div><strong>Help and questions</strong><small>Ask colleagues for advice and practical support</small></div><b>26 topics<br><small>137 posts</small></b><time>Yesterday<br><small>by Sofia</small></time></a>
          <a href="#forum-thread"><span class="win2k-forum-icon">☕</span><div><strong>General discussion</strong><small>Ideas, introductions and conversations</small></div><b>44 topics<br><small>302 posts</small></b><time>4 Aug<br><small>by Alex</small></time></a>
        </div></fieldset>
        <fieldset class="win2k-reference-group win2k-group"><legend>Active topics</legend><div class="win2k-forum-topics"><div class="head"><span>Topic</span><span>Replies</span><span>Last post</span></div><a href="#forum-thread"><strong>Ideas for the next Project Aurora workshop</strong><span>18</span><time>09:06</time></a><a href="#forum-thread"><strong>Which figures belong in the weekly report?</strong><span>11</span><time>08:42</time></a><a href="#forum-thread"><strong>New file structure for shared documents</strong><span>7</span><time>Yesterday</time></a></div></fieldset>
        <fieldset class="win2k-reference-group win2k-group wide" id="forum-thread"><legend>Selected discussion</legend><article class="win2k-forum-thread"><header><strong>Ideas for the next Project Aurora workshop</strong><span>Projects and planning</span></header><div><aside><b>EL</b><strong>Elin Larsson</strong><small>Product lead<br>126 posts</small></aside><section><time>Today 08:14</time><p>We are planning the next workshop for 18 August. Which customer journeys should we prioritise during the session?</p><p>I suggest account setup, saved searches and the new project overview.</p><div><button class="button compact" data-action="forum-reply">Reply</button><button class="button compact" data-action="forum-quote">Quote</button></div></section></div></article></fieldset>
      </section>
    </section>`;

  const filesPage = () => `
    <section class="page page-reference">
      ${pageHeader('Document application', 'File Explorer', 'Browse project folders, inspect documents and manage shared files from one familiar list view.', `<button class="button compact" data-action="reference-folder">New folder</button>`)}
      <div class="win2k-file-toolbar surface" role="toolbar"><button class="button compact" data-action="reference-back">Back</button><button class="button compact" data-action="reference-up">Up one level</button><label>Address<input value="C:\Projects\Aurora" readonly></label><button class="button compact" data-action="reference-go">Go</button></div>
      <section class="win2k-file-layout"><fieldset class="win2k-reference-group win2k-group"><legend>Folders</legend><nav class="win2k-tree"><a class="open" href="#"><span>−</span>Projects</a><a class="child active" href="#"><span>□</span>Aurora</a><a class="child" href="#"><span>□</span>Nordic Launch</a><a class="child" href="#"><span>□</span>Archive</a><a href="#"><span>+</span>Shared documents</a></nav></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Files</legend><div class="win2k-file-list" role="table" tabindex="0" aria-label="File list, scroll horizontally"><div class="head" role="row"><span>Name</span><span>Type</span><span>Size</span><span>Modified</span></div><button role="row"><span>□ Project brief.pdf</span><span>PDF</span><span>2.4 MB</span><span>Today</span></button><button role="row"><span>□ Budget 2026.xls</span><span>Spreadsheet</span><span>840 KB</span><span>Yesterday</span></button><button role="row"><span>□ Meeting notes.doc</span><span>Document</span><span>126 KB</span><span>4 Aug</span></button><button role="row"><span>□ Presentation.ppt</span><span>Presentation</span><span>5.8 MB</span><span>1 Aug</span></button></div><div class="win2k-file-status">4 objects · 9.1 MB</div></fieldset></section>
    </section>`;

  const calendarDays = ['27','28','29','30','31','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','1','2','3','4','5','6'];
  const calendarEvents = { '5': 'Team sync', '12': 'Delivery', '18': 'Workshop', '27': 'Report' };
  const calendarPage = () => `
    <section class="page page-reference">
      ${pageHeader('Planning application', 'Team Calendar', 'Coordinate meetings, project deliveries, workshops and other shared activities.', `<button class="button compact" data-action="reference-event">New event</button>`)}
      <section class="win2k-calendar-layout"><fieldset class="win2k-reference-group win2k-group"><legend>August 2026</legend><div class="win2k-calendar-toolbar"><button class="button compact">&lt;</button><strong>August 2026</strong><button class="button compact">&gt;</button></div><div class="win2k-calendar-week"><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span></div><div class="win2k-calendar-grid">${calendarDays.map((day,index)=>`<button class="${index<5||index>35?'outside':''} ${day==='6'&&index>5?'today':''}" type="button"><strong>${day}</strong>${calendarEvents[day]&&index>4&&index<36?`<small>${calendarEvents[day]}</small>`:''}</button>`).join('')}</div></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Upcoming events</legend><div class="win2k-agenda"><div><time>6 Aug<br>09:00</time><p><strong>Daily check-in</strong><span>Teams · 30 minutes</span></p></div><div><time>12 Aug<br>13:00</time><p><strong>Project delivery</strong><span>Room 4 · 2 hours</span></p></div><div><time>18 Aug<br>10:00</time><p><strong>Design workshop</strong><span>Studio · All day</span></p></div></div></fieldset></section>
    </section>`;

  const messagesPage = () => `
    <section class="page page-reference">
      ${pageHeader('Communication application', 'Mail', 'Read team messages, identify unread conversations and reply without leaving the application.', `<button class="button compact" data-action="reference-message">New message</button>`)}
      <section class="win2k-message-layout"><fieldset class="win2k-reference-group win2k-group"><legend>Inbox</legend><div class="win2k-inbox"><button class="unread active"><i></i><strong>Elin Larsson</strong><span>The project brief is ready</span><time>09:31</time></button><button class="unread"><i></i><strong>Malik Khan</strong><span>New forecast for August</span><time>08:04</time></button><button><i></i><strong>Sofia Berg</strong><span>Notes from the workshop</span><time>Yesterday</time></button><button><i></i><strong>System</strong><span>The weekly report has been created</span><time>4 Aug</time></button></div></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Message</legend><article class="win2k-message-reader"><header><div><strong>The project brief is ready</strong><p>From: Elin Larsson · To: Alex Holm</p></div><time>6 Aug 2026, 09:31</time></header><div><p>Hello Alex,</p><p>The project brief has now been updated with the latest decisions and is available in the shared folder.</p><p>Regards,<br>Elin</p></div><label>Reply<textarea rows="5" placeholder="Write your reply here…"></textarea></label><div><button class="button win2k-default-button" data-action="reference-send">Send</button><button class="button" data-action="reference-draft">Save draft</button></div></article></fieldset></section>
    </section>`;

  const statesPage = () => `
    <section class="page page-reference">
      ${pageHeader('Administration', 'System Monitor', 'Monitor data loading, service availability, permissions and decisions that require attention.')}
      <section class="win2k-state-grid"><fieldset class="win2k-reference-group win2k-group"><legend>Loading</legend><p>Loading project data…</p><span class="win2k-progress" role="progressbar" aria-valuenow="62" aria-valuemin="0" aria-valuemax="100"><i style="width:62%"></i></span><small>62% complete</small></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Empty result</legend><div class="win2k-state-message"><b>i</b><div><strong>No records found</strong><p>Change the search or create a new record.</p><button class="button compact">Create record</button></div></div></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Page not found</legend><div class="win2k-state-message error"><b>×</b><div><strong>404 — Page not found</strong><p>The address may be incorrect or the page may have moved.</p><button class="button compact">Go to home</button></div></div></fieldset><fieldset class="win2k-reference-group win2k-group"><legend>Access denied</legend><div class="win2k-state-message warning"><b>!</b><div><strong>You do not have permission</strong><p>Contact the administrator if you need access.</p><button class="button compact">Request access</button></div></div></fieldset><fieldset class="win2k-reference-group win2k-group wide"><legend>Confirmation dialog</legend><div class="win2k-confirmation"><div class="win2k-state-message warning"><b>!</b><div><strong>Do you want to delete this record?</strong><p>This action cannot be undone.</p></div></div><div><button class="button win2k-default-button">Cancel</button><button class="button">Delete</button></div></div></fieldset></section>
    </section>`;

  const helpSnippets = {
    setup: `<body data-style="windows-2000-mirc"
      data-style-name="Win2k UI"
      data-product-name="My Website"
      data-site-title="example.com - My site">
  <script src="assets/style-manifest.js" defer></script>
  <script src="assets/app.js" defer></script>
</body>`,
    disableHelp: `<script>
  window.WIN2K_UI_CONFIG = { help: false };
</script>
<script src="assets/app.js" defer></script>`,
    page: `<section class="page page-reference">
  <header class="page-heading">
    <div>
      <p class="eyebrow">Section name</p>
      <h1>Page title</h1>
      <p>A short explanation of this page.</p>
    </div>
  </header>
  <fieldset class="win2k-reference-group win2k-group">
    <legend>Content group</legend>
    <!-- Page content -->
  </fieldset>
</section>`,
    component: `<fieldset class="win2k-control-group win2k-group">
  <legend>Account settings</legend>
  <label>
    Display name
    <input type="text" value="Alex Morgan">
  </label>
  <button class="button win2k-default-button">Save</button>
</fieldset>`,
    container: `<fieldset class="win2k-reference-group win2k-group">
  <legend>Notification settings</legend>
  <p>Choose how the application should contact you.</p>

  <div class="win2k-form-grid">
    <label>
      Email address
      <input type="email" value="alex@example.com">
    </label>
    <label>
      Delivery frequency
      <select>
        <option>Immediately</option>
        <option>Daily summary</option>
      </select>
    </label>
  </div>
</fieldset>`,
    buttons: `<div class="win2k-form-actions" role="group" aria-label="Form actions">
  <button class="button win2k-default-button" type="submit">Save</button>
  <button class="button" type="button">Preview</button>
  <button class="button" type="button">Cancel</button>
  <button class="button" type="button" disabled>Unavailable</button>
</div>`,
    checkboxes: `<fieldset class="win2k-control-group win2k-group">
  <legend>Preferences</legend>

  <div class="win2k-choice-grid">
    <div>
      <strong>Notifications</strong>
      <label><input type="checkbox" checked> Product updates</label>
      <label><input type="checkbox"> Weekly report</label>
      <label class="disabled"><input type="checkbox" disabled> Administrator alerts</label>
    </div>

    <div>
      <strong>Density</strong>
      <label><input type="radio" name="density" checked> Normal</label>
      <label><input type="radio" name="density"> Compact</label>
    </div>

    <div>
      <strong>ON/OFF</strong>
      <label class="win2k-toggle-row">
        <span>Automatic sync</span>
        <input class="toggle" type="checkbox" checked>
      </label>
    </div>
  </div>
</fieldset>`,
    settingsForm: `<form class="win2k-reference-stack">
  <fieldset class="win2k-reference-group win2k-group">
    <legend>Profile</legend>
    <div class="win2k-form-grid">
      <label>Display name<input type="text" name="displayName" required></label>
      <label>Role<select name="role"><option>Editor</option><option>Administrator</option></select></label>
      <label class="wide">Biography<textarea name="bio" rows="4"></textarea></label>
    </div>
  </fieldset>

  <fieldset class="win2k-reference-group win2k-group">
    <legend>Notifications</legend>
    <label><input type="checkbox" name="emailUpdates" checked> Email updates</label>
    <label><input type="checkbox" name="weeklyReport"> Weekly report</label>
  </fieldset>

  <div class="win2k-form-actions">
    <button class="button win2k-default-button" type="submit">Save changes</button>
    <button class="button" type="reset">Reset</button>
  </div>
</form>`,
    chart: `<fieldset class="win2k-analysis-group win2k-group">
  <legend>Revenue by month</legend>
  <div class="chart-area" aria-label="Revenue bar chart">
    <!-- bars, labels and legend -->
  </div>
</fieldset>`,
    forum: `<section class="win2k-forum-list">
  <a class="win2k-forum-row" href="thread.html">
    <span class="win2k-info-status active"><i>i</i>Open</span>
    <div><strong>Announcements</strong><small>Product news and updates</small></div>
    <span>24 topics</span><time>Today 10:42</time>
  </a>
</section>`
  };
  const escapeHelpCode = (value) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  const helpCode = (id, caption) => `<figure class="win2k-help-code"><figcaption>${caption}<button class="button compact" type="button" data-help-copy="${id}">Copy</button></figcaption><pre><code>${escapeHelpCode(helpSnippets[id])}</code></pre></figure>`;
  const helpTopics = {
    welcome: { category: 'Getting started', title: 'Welcome to Win2k UI Help', keywords: 'welcome overview help framework', body: `<p class="lead">Win2k UI is a reusable Windows 2000-inspired interface framework for dashboards, databases, editorial sites, communities and internal tools.</p><div class="win2k-help-callout"><b>i</b><p><strong>Start here</strong>Use the Contents tab to browse guides, the Index tab to find a term, or Search to locate a phrase.</p></div><h2>What can you build?</h2><ul><li>Dashboards, metrics and analytics applications</li><li>News feeds, articles and content libraries</li><li>Forum categories, topic lists and threaded discussions</li><li>Forms, databases, profiles, calendars and file managers</li></ul><h2>Framework principle</h2><p>Every page uses the same application window, page introduction and bordered content groups. This keeps custom pages consistent without requiring a component framework.</p>` },
    'getting-started': { category: 'Getting started', title: 'Set up a Win2k UI page', keywords: 'install setup html assets scripts quick start', body: `<p class="lead">A Win2k UI page needs the shared styles, scripts and a configured body element.</p>${helpCode('setup', 'Minimal page setup')}<h2>Required assets</h2><ol><li>Load <code>base.css</code>.</li><li>Load <code>expanded-themes.css</code>.</li><li>Load <code>style-manifest.js</code> and <code>app.js</code>.</li><li>Set the product and window title with data attributes.</li></ol><p>The included demo accepts any username and password. Replace the demo session gate before using the framework for real authentication.</p>` },
    navigation: { category: 'Using Win2k UI', title: 'Navigate the desktop and Start menu', keywords: 'start menu programs settings search keyboard navigation', body: `<p class="lead">Applications are opened from Start, while page-specific commands live in the menu bar.</p><h2>Start menu</h2><ul><li><strong>Programs</strong> contains the eight complete sample applications.</li><li><strong>Settings</strong> contains the Component Catalog, My Account and System Monitor.</li><li><strong>Search</strong> opens Project Manager and focuses its search box.</li><li><strong>Help</strong> opens this Help and Support Center.</li></ul><h2>Keyboard navigation</h2><p>Press <kbd>Ctrl+Esc</kbd> to open Start. Use <kbd>Alt+F</kbd>, <kbd>Alt+V</kbd> or <kbd>Alt+H</kbd> to open application menus. Arrow keys move between commands and <kbd>Esc</kbd> closes the active menu.</p>` },
    'page-layout': { category: 'Building pages', title: 'Create a standard page', keywords: 'page template heading group fieldset layout standard', body: `<p class="lead">Use this structure for every new application page.</p>${helpCode('page', 'Standard page template')}<h2>Page introduction</h2><p>The white introduction area contains a green section label, a clear page title and a short description. Optional actions belong on its right side.</p><h2>Content groups</h2><p>Place related content inside a <code>fieldset</code> using <code>win2k-group</code>. The legend names the group. Avoid modern floating cards, rounded chips and decorative shadows.</p>` },
    components: { category: 'Building pages', title: 'Use controls and content groups', keywords: 'button input select checkbox radio controls components fieldset', body: `<p class="lead">Win2k UI components are regular semantic HTML elements styled by shared classes.</p>${helpCode('component', 'Form group example')}<h2>Interaction states</h2><ul><li>Buttons have raised, pressed, focused and disabled states.</li><li>Inputs and list boxes use recessed white surfaces.</li><li>Status information is text with a system icon, never a decorative pill.</li><li>Wide tables scroll inside their own recessed area on small screens.</li></ul><p>Open <strong>Settings → Component Catalog</strong> to inspect every base component.</p>` },
    'container-basics': { category: 'Component details', title: 'Build a content container', keywords: 'container fieldset legend group panel section content anatomy class', body: `<p class="lead">A Win2k UI container is a semantic <code>fieldset</code> with a visible <code>legend</code>. It replaces the rounded card pattern used by many modern interfaces.</p><div class="win2k-help-example"><p class="win2k-help-example-label">Live example</p><fieldset class="win2k-reference-group win2k-group"><legend>Notification settings</legend><p>Choose how the application should contact you.</p><div class="win2k-form-grid"><label>Email address<input type="email" value="alex@example.com"></label><label>Delivery frequency<select><option>Immediately</option><option>Daily summary</option></select></label></div></fieldset></div>${helpCode('container', 'Container with form fields')}<h2>Container anatomy</h2><table><thead><tr><th>Part</th><th>Purpose</th></tr></thead><tbody><tr><td><code>fieldset</code></td><td>Groups related content semantically.</td></tr><tr><td><code>win2k-group</code></td><td>Adds the shared grey surface and classic bevel.</td></tr><tr><td><code>win2k-reference-group</code></td><td>Adds spacing suitable for normal page content.</td></tr><tr><td><code>legend</code></td><td>Names the group in the border.</td></tr><tr><td><code>win2k-form-grid</code></td><td>Creates a responsive two-column field layout.</td></tr><tr><td><code>wide</code></td><td>Makes one grid item span both columns.</td></tr></tbody></table><h2>Rules</h2><ul><li>Give every container a short, specific legend.</li><li>Keep related controls together; split unrelated tasks into separate containers.</li><li>Do not nest multiple bevelled containers unless the inner group represents a real sub-section.</li><li>Use a white recessed inner area only for reading, data, code or charts.</li></ul>` },
    'buttons-commands': { category: 'Component details', title: 'Buttons and command rows', keywords: 'button primary default cancel disabled toolbar action submit command', body: `<p class="lead">Buttons use the same <code>button</code> class. Meaning comes from order, button type and the optional default-button class.</p><div class="win2k-help-example"><p class="win2k-help-example-label">Live example</p><div class="win2k-form-actions" role="group" aria-label="Example form actions"><button class="button win2k-default-button" type="button">Save</button><button class="button" type="button">Preview</button><button class="button" type="button">Cancel</button><button class="button" type="button" disabled>Unavailable</button></div></div>${helpCode('buttons', 'Button row')}<h2>Choose the correct button type</h2><table><thead><tr><th>Type</th><th>Use</th></tr></thead><tbody><tr><td><code>type="submit"</code></td><td>Submits the surrounding form.</td></tr><tr><td><code>type="button"</code></td><td>Runs a command without submitting.</td></tr><tr><td><code>type="reset"</code></td><td>Restores the form’s initial values.</td></tr><tr><td><code>disabled</code></td><td>Shows that the action is currently unavailable.</td></tr></tbody></table><h2>Default action</h2><p>Add <code>win2k-default-button</code> to the one action that should run when the user presses Enter. A dialog or form should normally have only one default button.</p><h2>Ordering</h2><p>Place the primary action first, related secondary actions next and Cancel last. Keep destructive actions visually separate and ask for confirmation when the result cannot be undone.</p>` },
    'checkboxes-choices': { category: 'Component details', title: 'Checkboxes, radio buttons and ON/OFF settings', keywords: 'checkbox check radio toggle on off checked disabled labels choices', body: `<p class="lead">Use a checkbox for independent choices, radio buttons for one choice from a set and the rectangular ON/OFF control for a persistent binary setting.</p><div class="win2k-help-example"><p class="win2k-help-example-label">Live example — try the controls</p><fieldset class="win2k-control-group win2k-group"><legend>Preferences</legend><div class="win2k-choice-grid"><div><strong>Notifications</strong><label><input type="checkbox" checked> Product updates</label><label><input type="checkbox"> Weekly report</label><label class="disabled"><input type="checkbox" disabled> Administrator alerts</label></div><div><strong>Density</strong><label><input type="radio" name="help-density" checked> Normal</label><label><input type="radio" name="help-density"> Compact</label></div><div><strong>ON/OFF</strong><label class="win2k-toggle-row"><span>Automatic sync</span><input class="toggle" type="checkbox" checked></label></div></div></fieldset></div>${helpCode('checkboxes', 'Choice controls')}<h2>Implementation rules</h2><ul><li>Wrap the input and visible text in the same <code>label</code> so the entire row is clickable.</li><li>Give radio buttons in one set the same <code>name</code>.</li><li>Use <code>checked</code> only for a meaningful default.</li><li>Use both <code>disabled</code> and the <code>disabled</code> label class when an unavailable choice needs the muted system treatment.</li><li>Do not use a toggle for an immediate command such as Save or Delete.</li></ul><h2>Reading values in JavaScript</h2><pre><code>const enabled = document.querySelector('[name="emailUpdates"]').checked;
const density = document.querySelector('[name="density"]:checked')?.value;</code></pre>` },
    'complete-settings-form': { category: 'Step-by-step tutorials', title: 'Build a complete settings form', keywords: 'complete settings form tutorial validation submit reset profile step by step', body: `<p class="lead">This example combines containers, fields, choices and buttons into one production-shaped form.</p>${helpCode('settingsForm', 'Complete settings form')}<h2>Step 1 — group by task</h2><p>Profile data and notification choices belong in separate containers. This makes the form easier to scan and keeps each legend useful.</p><h2>Step 2 — use native HTML</h2><p>Use <code>required</code>, suitable input types and proper labels before adding JavaScript validation. Native HTML remains usable when scripts fail.</p><h2>Step 3 — add behaviour</h2><pre><code>const form = document.querySelector('form');
form.addEventListener('submit', async (event) =&gt; {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const values = Object.fromEntries(new FormData(form));
  await saveSettings(values);
});</code></pre><h2>Step 4 — handle every state</h2><ul><li>Disable Save while the request is running.</li><li>Show progress in the status bar or a system message.</li><li>Move focus to the first invalid field on failure.</li><li>Show a clear success message after saving.</li><li>Preserve entered values when the server returns an error.</li></ul><div class="win2k-help-callout"><b>!</b><p><strong>Demo behaviour</strong>The snippets show interface structure. Connect them to your own validation, API and security model before production use.</p></div>` },
    'data-visualization': { category: 'Recipes', title: 'Build charts, statistics and analytics', keywords: 'charts graph statistics analytics kpi metrics visualization dashboard', body: `<p class="lead">Charts use white recessed plotting areas inside grey Windows content groups.</p>${helpCode('chart', 'Chart container')}<h2>Recommended structure</h2><ul><li>Put filters and time ranges in a compact toolbar.</li><li>Show key metrics in separate fieldsets.</li><li>Use dark blue for primary data and light blue for comparison data.</li><li>Always provide a legend, text labels and a table alternative.</li><li>Use system-style tooltips with square corners.</li></ul><p>The Analytics page demonstrates bars, forecasts, distribution, metrics and an insight panel.</p>` },
    'news-feed': { category: 'Recipes', title: 'Build a news or activity feed', keywords: 'news feed activity articles unread categories content', body: `<p class="lead">A feed should look like a Windows list view rather than a stack of modern cards.</p><h2>Feed layout</h2><ol><li>Use a toolbar for category, date and unread filters.</li><li>Separate rows with one continuous horizontal line.</li><li>Show unread state with a small system icon and bold title.</li><li>Open the selected item in a reading pane or article page.</li><li>Use the existing pagination control for longer feeds.</li></ol><p>Combine patterns from <strong>Messages</strong>, <strong>Article</strong> and <strong>Database</strong> to create a complete news application.</p>` },
    forum: { category: 'Recipes', title: 'Build a forum with categories and threads', keywords: 'forum phpbb categories threads topics posts replies moderation', body: `<p class="lead">A phpBB-style community can be built from list views, status icons, pagination and message layouts.</p>${helpCode('forum', 'Forum category row')}<h2>Recommended pages</h2><ul><li>Forum index with categories and last-post information</li><li>Topic list with pinned, locked, unread and resolved states</li><li>Thread view with author column, post body and moderation tools</li><li>New topic and reply forms</li><li>Member profile, search and private messages</li></ul><p>Keep posts rectangular, use uninterrupted separators and reuse the classic pagination buttons from Database.</p>` },
    'wordpress-integration': { category: 'Framework', title: 'Use Win2k UI with or without WordPress', keywords: 'wordpress standalone block theme plugin headless rest cms portable integration', body: `<p class="lead">Win2k UI Core has no WordPress dependency. WordPress support is supplied as optional adapters so a website can remain standalone or use WordPress for editing and content.</p><h2>Available modes</h2><table><thead><tr><th>Mode</th><th>Purpose</th></tr></thead><tbody><tr><td>Standalone</td><td>Plain HTML, CSS and JavaScript with content owned by the application.</td></tr><tr><td>WordPress block theme</td><td>WordPress renders pages, posts, archives and search using the shared Win2k UI core.</td></tr><tr><td>Content plugin</td><td>Optional portable Project records that survive a theme change.</td></tr><tr><td>Headless REST</td><td>A separate Win2k UI frontend reads public WordPress content as JSON.</td></tr></tbody></table><div class="win2k-form-actions"><a class="button compact" href="https://dev.bodbil.com/windows2000/win2k-ui/standalone/">Open standalone starter</a><a class="button compact" href="https://dev.bodbil.com/windows2000/win2k-ui/downloads/win2k-ui-wordpress-theme-0.1.0.zip">Download WordPress theme</a><a class="button compact" href="https://dev.bodbil.com/windows2000/win2k-ui/downloads/win2k-ui-content-plugin-0.1.0.zip">Download content plugin</a></div><h2>Responsibility boundaries</h2><ul><li><strong>Core</strong> owns design tokens, controls and generic interactions.</li><li><strong>Theme</strong> owns presentation and WordPress templates only.</li><li><strong>Plugin</strong> owns durable custom content and functionality.</li><li><strong>WordPress or the host application</strong> owns authentication, permissions and persistence.</li></ul><div class="win2k-help-callout"><b>!</b><p><strong>Authentication</strong>The Windows logon in this gallery is a demonstration. A WordPress installation must use WordPress authentication and must never validate WordPress passwords in browser JavaScript.</p></div>` },
    configuration: { category: 'Framework', title: 'Configure or disable Help', keywords: 'configuration disable help options product title settings', body: `<p class="lead">The Help Center is optional and can be removed without changing other pages.</p>${helpCode('disableHelp', 'Disable the Help Center')}<p>You can also set <code>data-help-enabled="false"</code> on the body element. When disabled, the Help page, Start-menu entry and Help menu are omitted.</p><h2>Brand configuration</h2><ul><li><code>data-product-name</code> sets the framework or product name.</li><li><code>data-site-title</code> sets the application title bar.</li><li><code>WIN2K_UI_CONFIG.help</code> enables or disables Help.</li></ul>` },
    accessibility: { category: 'Framework', title: 'Accessibility requirements', keywords: 'accessibility aria keyboard focus contrast mobile reduced motion', body: `<p class="lead">Custom pages must remain usable with keyboard, touch, screen readers and browser zoom.</p><ul><li>Use semantic headings, labels, tables and fieldsets.</li><li>Keep the dotted focus indicator visible.</li><li>Do not communicate status with color alone.</li><li>Give icon-only buttons an accessible name.</li><li>Respect reduced-motion preferences.</li><li>Keep mobile fields at least 40 pixels tall with 16-pixel text.</li><li>Place horizontal scrolling inside wide components, never on the entire page.</li></ul>` },
    shortcuts: { category: 'Reference', title: 'Keyboard shortcuts', keywords: 'keyboard shortcut keys alt ctrl escape f1', body: `<p class="lead">Win2k UI follows familiar Windows keyboard conventions.</p><table><thead><tr><th>Shortcut</th><th>Action</th></tr></thead><tbody><tr><td><kbd>Ctrl+Esc</kbd></td><td>Open or close Start</td></tr><tr><td><kbd>Alt+F</kbd></td><td>Open File</td></tr><tr><td><kbd>Alt+V</kbd></td><td>Open View</td></tr><tr><td><kbd>Alt+H</kbd></td><td>Open Help</td></tr><tr><td><kbd>Arrow keys</kbd></td><td>Move between menu commands</td></tr><tr><td><kbd>Esc</kbd></td><td>Close the active menu or dialog</td></tr></tbody></table>` }
  };
  const helpTopicOrder = Object.keys(helpTopics);
  const requestedHelpTopic = () => {
    const requested = new URLSearchParams(window.location.search).get('topic');
    const pageAliases = { home: 'welcome', analysis: 'data-visualization', data: 'components', controls: 'components', forms: 'components', details: 'page-layout', content: 'news-feed', forum: 'forum', files: 'components', calendar: 'components', messages: 'news-feed', states: 'components', help: 'welcome' };
    return helpTopics[requested] ? requested : pageAliases[requested] || 'welcome';
  };
  const helpArticle = (id) => {
    const topic = helpTopics[id] || helpTopics.welcome;
    return `<header><p>${topic.category}</p><h1>${topic.title}</h1></header><div class="win2k-help-article-body">${topic.body}</div><footer><button class="button compact" type="button" data-help-favorite="${id}">Add to Favorites</button><span>Topic ${helpTopicOrder.indexOf(id) + 1} of ${helpTopicOrder.length}</span></footer>`;
  };
  const helpPage = () => {
    const activeTopic = requestedHelpTopic();
    const categories = [...new Set(helpTopicOrder.map((id) => helpTopics[id].category))];
    return `<section class="page page-reference page-help">
      ${pageHeader('Help and Support', 'Win2k UI Help Center', 'Learn how to navigate Win2k UI, use its components and build your own pages and applications.')}
      <section class="win2k-help-shell" data-help-active-topic="${activeTopic}">
        <div class="win2k-help-titlebar"><strong>Win2k UI Help</strong><span>_ □ ×</span></div>
        <div class="win2k-help-toolbar" role="toolbar" aria-label="Help navigation"><button type="button" data-help-history="back">← Back</button><button type="button" data-help-home>⌂ Home</button><button type="button" data-help-print>▣ Print</button><span></span><button type="button" data-help-options>Options</button></div>
        <div class="win2k-help-layout">
          <aside class="win2k-help-navigation">
            <div class="win2k-help-tabs" role="tablist" aria-label="Help navigation tabs"><button class="is-active" type="button" role="tab" aria-selected="true" data-help-tab="contents">Contents</button><button type="button" role="tab" aria-selected="false" data-help-tab="index">Index</button><button type="button" role="tab" aria-selected="false" data-help-tab="search">Search</button><button type="button" role="tab" aria-selected="false" data-help-tab="favorites">Favorites</button></div>
            <div class="win2k-help-panel" data-help-panel="contents">${categories.map((category) => `<details open><summary>${category}</summary>${helpTopicOrder.filter((id) => helpTopics[id].category === category).map((id) => `<button class="${id === activeTopic ? 'is-active' : ''}" type="button" data-help-topic="${id}">${helpTopics[id].title}</button>`).join('')}</details>`).join('')}</div>
            <div class="win2k-help-panel" data-help-panel="index" hidden><label>Type a keyword:<input type="search" data-help-index-filter></label><div class="win2k-help-index">${[...helpTopicOrder].sort((a,b) => helpTopics[a].title.localeCompare(helpTopics[b].title)).map((id) => `<button type="button" data-help-topic="${id}"><strong>${helpTopics[id].title}</strong><small>${helpTopics[id].keywords}</small></button>`).join('')}</div></div>
            <div class="win2k-help-panel" data-help-panel="search" hidden><label>Search for:<span><input type="search" data-help-search><button class="button compact" type="button" data-help-search-button>List Topics</button></span></label><div class="win2k-help-search-results"><p>Enter one or more words, then select List Topics.</p></div></div>
            <div class="win2k-help-panel" data-help-panel="favorites" hidden><p>Save frequently used topics here.</p><div class="win2k-help-favorites" data-help-favorites></div></div>
          </aside>
          <article class="win2k-help-article" data-help-article tabindex="-1">${helpArticle(activeTopic)}</article>
        </div>
        <div class="win2k-help-status"><span>Ready</span><span>Win2k UI Help and Support Center</span></div>
      </section>
    </section>`;
  };

  const win2kLogonPage = () => `
    <section class="win2k-logon-screen" aria-labelledby="win2k-logon-heading">
      <form class="win2k-logon-dialog" id="win2k-logon-form">
        <div class="win2k-logon-titlebar"><strong id="win2k-logon-heading">Log On to Windows</strong></div>
        <header class="win2k-logon-banner">
          <div class="win2k-logon-flag" aria-hidden="true"><i></i><i></i><i></i><i></i></div>
          <div class="win2k-logon-wordmark"><small>www.bodbil.com</small><p><strong>Windows</strong><b>2000</b></p><em>Professional</em><span>A site for everyone</span></div>
          <b class="win2k-logon-corner">bodbil.com</b>
        </header>
        <div class="win2k-logon-rule" aria-hidden="true"></div>
        <div class="win2k-logon-content">
          <div class="win2k-logon-fields">
            <label><span>User name:</span><input id="win2k-logon-username" name="username" type="text" value="Admin" autocomplete="username"></label>
            <label><span>Password:</span><input name="password" type="password" autocomplete="current-password"></label>
            <label class="win2k-logon-dialup"><span></span><span><input type="checkbox"> Log on using dial-up connection</span></label>
          </div>
          <div class="win2k-logon-actions"><button class="button win2k-default-button" type="submit">OK</button><button class="button" type="button" disabled>Cancel</button><button class="button" type="button" data-logon-shutdown>Shut Down…</button><button class="button" type="button" data-logon-options>Options &lt;&lt;</button></div>
        </div>
      </form>
    </section>`;

  const bindPageEvents = () => {
    document.querySelectorAll('[data-page-link]').forEach((link) => {
      if (link.dataset.bound === 'true') return;
      link.dataset.bound = 'true';
      link.addEventListener('click', (event) => {
        const page = link.dataset.pageLink;
        const focusTarget = link.dataset.focusTarget;
        const loggingOut = link.dataset.logOut === 'true';
        if (!page) return;
        event.preventDefault();
        if (loggingOut && isWindowsMirc) {
          closeStartMenu();
          openSystemDialog({
            title: 'Log Off Windows',
            message: 'Do you want to log off from www.bodbil.com?',
            kind: 'question',
            confirmLabel: 'Log Off',
            cancelLabel: 'Cancel',
            onConfirm: () => {
              setWin2kAuthenticated(false);
              const url = new URL(window.location.href);
              url.searchParams.set('page', 'login');
              history.pushState({}, '', url);
              setWin2kBusy(180);
              renderAppRoute();
            }
          });
          return;
        }
        const url = new URL(window.location.href);
        url.searchParams.set('page', page);
        history.pushState({}, '', url);
        closeStartMenu();
        setWin2kBusy();
        renderAppRoute();
        if (focusTarget) requestAnimationFrame(() => document.getElementById(focusTarget)?.focus());
      });
    });

    document.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => {
      const messages = {
        report: 'The report is being prepared — demo action completed.',
        more: 'Additional options would open here in a production app.',
        insight: 'The recommendation was added to the team focus list.',
        'new-record': 'A new project form would open here.',
        export: 'The project list is ready for export.',
        'open-record': 'The project detail view would open here.',
        forgot: 'A reset link would be sent to your email address.',
        'edit-profile': 'Profile editing would open here.',
        'control-new': 'A new form was created.',
        'control-open': 'The Open dialog would appear here.',
        'control-save': 'Settings were saved.',
        'control-print': 'The Print dialog would open here.',
        'control-search': 'The search command was completed.',
        'control-confirm': 'The dialog was confirmed with OK.',
        'control-cancel': 'The action was cancelled.',
        'control-apply': 'Settings were applied.',
        'news-article': 'A new article editor would open here.',
        'news-refresh': 'The newsroom feed was refreshed.',
        'forum-topic': 'A new topic form would open here.',
        'forum-reply': 'The reply editor would open below the discussion.',
        'forum-quote': 'The selected post was added to a new reply.'
      };
      notify(messages[button.dataset.action] || 'Demo action completed.');
    }));

    const search = document.querySelector('#record-search');
    const filter = document.querySelector('#status-filter');
    const searchButton = document.querySelector('[data-search-submit]');
    if (search || filter || searchButton) {
      const updateTable = () => {
        const value = search?.value || '';
        const status = filter?.value || 'All';
        main.innerHTML = dataPage(value, status);
        bindPageEvents();
        const nextSearch = document.querySelector('#record-search');
        nextSearch?.focus();
        nextSearch?.setSelectionRange(value.length, value.length);
      };
      search?.addEventListener('input', updateTable);
      searchButton?.addEventListener('click', updateTable);
      filter?.addEventListener('change', updateTable);
    }

    const recordPagination = document.querySelector('[data-record-pagination]');
    recordPagination?.querySelectorAll('[data-record-page]').forEach((button) => button.addEventListener('click', () => {
      const currentPage = Number(recordPagination.dataset.currentPage) || 1;
      const totalPages = Number(recordPagination.dataset.totalPages) || 1;
      const action = button.dataset.recordPage;
      const requestedPage = action === 'first' ? 1 : action === 'prev' ? currentPage - 1 : action === 'next' ? currentPage + 1 : action === 'last' ? totalPages : Number(action);
      main.innerHTML = dataPage(search?.value || '', filter?.value || 'All', Math.min(Math.max(requestedPage, 1), totalPages));
      bindPageEvents();
    }));

    const loginForm = document.querySelector('#login-form');
    loginForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      const submit = loginForm.querySelector('.auth-submit');
      submit.classList.add('is-loading');
      submit.innerHTML = 'Signing in <span>•••</span>';
      setTimeout(() => {
        const url = new URL(window.location.href);
        url.searchParams.set('page', 'profile');
        history.pushState({}, '', url);
        renderPage();
        notify('Welcome back, Alex!');
      }, reducedMotion ? 50 : 650);
    });

    const showPassword = document.querySelector('#show-password');
    showPassword?.addEventListener('click', () => {
      const input = showPassword.previousElementSibling;
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      showPassword.textContent = visible ? 'Show' : 'Hide';
    });

    const controlPasswordButton = document.querySelector('[data-control-password]');
    controlPasswordButton?.addEventListener('click', () => {
      const input = document.querySelector('#control-password');
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      controlPasswordButton.textContent = visible ? 'Show' : 'Hide';
    });

    document.querySelectorAll('[data-win-range]').forEach((range) => range.addEventListener('input', () => {
      const output = range.closest('.win2k-range-row')?.querySelector('output');
      if (output) output.value = range.value;
    }));

    const tabCopy = {
      General: ['General settings', 'Tab content appears in a recessed white panel, just like a classic system dialog.'],
      Advanced: ['Advanced settings', 'Options that rarely need to be changed are collected here.'],
      About: ['About the control library', 'Components are designed to resemble Windows 2000 without modern visual shortcuts.']
    };
    document.querySelectorAll('.win2k-demo-tabs button').forEach((button) => button.addEventListener('click', () => {
      document.querySelectorAll('.win2k-demo-tabs button').forEach((item) => {
        const active = item === button;
        item.classList.toggle('is-active', active);
        item.setAttribute('aria-selected', String(active));
      });
      const panel = document.querySelector('.win2k-tab-panel');
      const [title, copy] = tabCopy[button.textContent.trim()];
      panel.innerHTML = `<p><strong>${title}</strong></p><p>${copy}</p>`;
    }));

    const helpShell = document.querySelector('.win2k-help-shell');
    if (helpShell) {
      const favoriteKey = `${productSlug}-help-favorites`;
      const readFavorites = () => {
        try { return JSON.parse(window.localStorage.getItem(favoriteKey) || '[]').filter((id) => helpTopics[id]); } catch { return []; }
      };
      const writeFavorites = (items) => {
        try { window.localStorage.setItem(favoriteKey, JSON.stringify(items)); } catch { /* Favorites remain optional. */ }
      };
      const renderFavorites = () => {
        const target = helpShell.querySelector('[data-help-favorites]');
        if (!target) return;
        const favorites = readFavorites();
        target.innerHTML = favorites.length ? favorites.map((id) => `<button type="button" data-help-topic="${id}">${helpTopics[id].title}</button>`).join('') : '<p>No favorite topics have been saved.</p>';
        bindHelpTopicButtons();
      };
      const showHelpTopic = (id, push = true) => {
        if (!helpTopics[id]) id = 'welcome';
        helpShell.dataset.helpActiveTopic = id;
        helpShell.querySelector('[data-help-article]').innerHTML = helpArticle(id);
        helpShell.querySelectorAll('[data-help-topic]').forEach((button) => button.classList.toggle('is-active', button.dataset.helpTopic === id));
        if (push) {
          const url = new URL(window.location.href);
          url.searchParams.set('topic', id);
          history.pushState({}, '', url);
        }
        bindHelpArticleActions();
        helpShell.querySelector('[data-help-article]')?.focus();
      };
      function bindHelpTopicButtons() {
        helpShell.querySelectorAll('[data-help-topic]').forEach((button) => {
          if (button.dataset.bound === 'true') return;
          button.dataset.bound = 'true';
          button.addEventListener('click', () => showHelpTopic(button.dataset.helpTopic));
        });
      }
      function bindHelpArticleActions() {
        helpShell.querySelectorAll('[data-help-copy]').forEach((button) => button.addEventListener('click', async () => {
          try { await navigator.clipboard.writeText(helpSnippets[button.dataset.helpCopy]); notify('Code copied to the clipboard.'); } catch { notify('Copy is unavailable in this browser context.'); }
        }));
        helpShell.querySelector('[data-help-favorite]')?.addEventListener('click', (event) => {
          const id = event.currentTarget.dataset.helpFavorite;
          const favorites = readFavorites();
          const next = favorites.includes(id) ? favorites.filter((item) => item !== id) : [...favorites, id];
          writeFavorites(next);
          event.currentTarget.textContent = next.includes(id) ? 'Remove from Favorites' : 'Add to Favorites';
          renderFavorites();
        });
        const favoriteButton = helpShell.querySelector('[data-help-favorite]');
        if (favoriteButton) favoriteButton.textContent = readFavorites().includes(favoriteButton.dataset.helpFavorite) ? 'Remove from Favorites' : 'Add to Favorites';
      }
      helpShell.querySelectorAll('[data-help-tab]').forEach((tab) => tab.addEventListener('click', () => {
        helpShell.querySelectorAll('[data-help-tab]').forEach((item) => { const active = item === tab; item.classList.toggle('is-active', active); item.setAttribute('aria-selected', String(active)); });
        helpShell.querySelectorAll('[data-help-panel]').forEach((panel) => { panel.hidden = panel.dataset.helpPanel !== tab.dataset.helpTab; });
        if (tab.dataset.helpTab === 'favorites') renderFavorites();
      }));
      const indexFilter = helpShell.querySelector('[data-help-index-filter]');
      indexFilter?.addEventListener('input', () => {
        const query = indexFilter.value.trim().toLowerCase();
        helpShell.querySelectorAll('.win2k-help-index [data-help-topic]').forEach((button) => { button.hidden = Boolean(query) && !button.textContent.toLowerCase().includes(query); });
      });
      const performHelpSearch = () => {
        const input = helpShell.querySelector('[data-help-search]');
        const target = helpShell.querySelector('.win2k-help-search-results');
        const query = input.value.trim().toLowerCase();
        const matches = query ? helpTopicOrder.filter((id) => `${helpTopics[id].title} ${helpTopics[id].keywords} ${helpTopics[id].body.replace(/<[^>]*>/g, ' ')}`.toLowerCase().includes(query)) : [];
        target.innerHTML = matches.length ? matches.map((id) => `<button type="button" data-help-topic="${id}"><strong>${helpTopics[id].title}</strong><small>${helpTopics[id].category}</small></button>`).join('') : `<p>${query ? 'No topics matched your search.' : 'Enter one or more words, then select List Topics.'}</p>`;
        bindHelpTopicButtons();
      };
      helpShell.querySelector('[data-help-search-button]')?.addEventListener('click', performHelpSearch);
      helpShell.querySelector('[data-help-search]')?.addEventListener('keydown', (event) => { if (event.key === 'Enter') performHelpSearch(); });
      helpShell.querySelector('[data-help-history="back"]')?.addEventListener('click', () => history.back());
      helpShell.querySelector('[data-help-home]')?.addEventListener('click', () => showHelpTopic('welcome'));
      helpShell.querySelector('[data-help-print]')?.addEventListener('click', () => window.print());
      helpShell.querySelector('[data-help-options]')?.addEventListener('click', () => openSystemDialog({ title: 'Help Options', message: 'Help can be disabled with WIN2K_UI_CONFIG.help or data-help-enabled="false".', kind: 'info' }));
      bindHelpTopicButtons();
      bindHelpArticleActions();
      renderFavorites();
    }

    document.querySelectorAll('.segmented button').forEach((button) => button.addEventListener('click', () => {
      document.querySelectorAll('.segmented button').forEach((item) => item.classList.remove('is-active'));
      button.classList.add('is-active');
      notify(`Analytics now shows ${button.textContent.toLowerCase()}.`);
    }));
  };

  const renderPage = () => {
    document.body.classList.remove('is-win2k-locked');
    document.title = appTitle;
    const page = getPage();
    const templates = {
      home: homePage,
      analysis: analysisPage,
      data: dataPage,
      login: loginPage,
      profile: profilePage,
      controls: controlsPage,
      forms: formsPage,
      details: detailsPage,
      content: contentPage,
      forum: forumPage,
      files: filesPage,
      calendar: calendarPage,
      messages: messagesPage,
      states: statesPage,
      help: helpPage
    };
    main.classList.remove('page-enter');
    main.innerHTML = templates[page]();
    updateWindowsChrome(page);
    if (!reducedMotion) requestAnimationFrame(() => main.classList.add('page-enter'));
    document.querySelectorAll('[data-page-link]').forEach((link) => link.classList.toggle('is-active', link.dataset.pageLink === page));
    bindPageEvents();
    window.scrollTo({ top: 0, behavior: reducedMotion ? 'auto' : 'smooth' });
  };

  const renderLoginScreen = () => {
    closeStartMenu();
    document.body.classList.add('is-win2k-locked');
    document.title = 'Log on — www.bodbil.com';
    main.classList.remove('page-enter');
    main.innerHTML = win2kLogonPage();
    const logonForm = document.querySelector('#win2k-logon-form');
    logonForm?.addEventListener('submit', (event) => {
      event.preventDefault();
      setWin2kBusy(380);
      setWin2kAuthenticated(true);
      const url = new URL(window.location.href);
      url.searchParams.set('page', 'home');
      history.pushState({}, '', url);
      renderPage();
      notify('Welcome to www.bodbil.com!');
    });
    document.querySelector('[data-logon-shutdown]')?.addEventListener('click', () => openSystemDialog({
      title: 'Shut Down Windows',
      message: 'Shutdown is disabled in demo mode.',
      kind: 'warning'
    }));
    document.querySelector('[data-logon-options]')?.addEventListener('click', (event) => {
      const dialup = document.querySelector('.win2k-logon-dialup');
      const hidden = dialup?.toggleAttribute('hidden');
      event.currentTarget.textContent = hidden ? 'Options >>' : 'Options <<';
    });
    requestAnimationFrame(() => document.querySelector('#win2k-logon-username')?.focus());
  };

  const renderAppRoute = () => {
    const requested = new URLSearchParams(window.location.search).get('page');
    if (isWindowsMirc && (!isWin2kAuthenticated || requested === 'login')) {
      renderLoginScreen();
      return;
    }
    renderPage();
  };

  document.querySelector('#style-picker')?.addEventListener('change', (event) => {
    const match = window.location.pathname.match(/^(.*\/styles\/)[^/]+(?:\/.*)?$/);
    if (!match) return;
    const page = getPage();
    window.location.href = `${match[1]}${event.target.value}/?page=${page}`;
  });

  window.addEventListener('popstate', renderAppRoute);
  if (isWindowsMirc) {
    window.addEventListener('blur', () => document.body.classList.add('is-win2k-inactive'));
    window.addEventListener('focus', () => document.body.classList.remove('is-win2k-inactive'));
  }
  renderAppRoute();
})();
