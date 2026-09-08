(function loadStandaloneDemoContent() {
  'use strict';

  const projects = [
    { title: 'Project Aurora', area: 'Product', status: 'Active', updated: 'Today 09:42' },
    { title: 'Nordic Launch', area: 'Marketing', status: 'Review', updated: 'Yesterday 16:18' },
    { title: 'Atlas Migration', area: 'Technology', status: 'Active', updated: '5 Aug 2026' },
    { title: 'Signal Archive', area: 'Operations', status: 'Paused', updated: '1 Aug 2026' }
  ];

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  })[character]);

  const renderProjects = () => {
    const target = document.querySelector('[data-demo-projects]');
    if (!target) return;
    target.innerHTML = projects.map((project) => `<tr>
      <td><strong>${escapeHtml(project.title)}</strong></td>
      <td>${escapeHtml(project.area)}</td>
      <td><span class="win2k-status">${escapeHtml(project.status)}</span></td>
      <td>${escapeHtml(project.updated)}</td>
    </tr>`).join('');
  };

  const status = (message) => document.querySelector('[data-win2k-app]')?.dispatchEvent(new CustomEvent('win2k:status', { detail: { message } }));

  const bindDemoActions = () => {
    document.querySelector('[data-demo-settings]')?.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!event.currentTarget.reportValidity()) return;
      status('Settings saved locally for this demonstration.');
    });

    document.querySelectorAll('[data-demo-action]').forEach((button) => button.addEventListener('click', () => {
      const actions = {
        save: 'Snapshot saved.',
        print: 'Opening the browser print dialog…',
        about: 'Pi-2000Web UI Example 0.1.0 — standalone mode.'
      };
      status(actions[button.dataset.demoAction] || 'Command completed.');
      if (button.dataset.demoAction === 'print') window.print();
    }));
  };

  renderProjects();
  bindDemoActions();
})();
