# Win2k UI

Win2k UI is a reusable Windows 2000-inspired web framework built with plain HTML, CSS and JavaScript. It combines a classic desktop, application window, Start menu, system dialogs, reusable controls and an optional Windows Help-style documentation center.

## Quick start

Load `base.css`, `expanded-themes.css`, `style-manifest.js` and `app.js`, then configure the body:

```html
<body
  data-style="windows-2000-mirc"
  data-style-name="Win2k UI"
  data-product-name="My Website"
  data-site-title="example.com - My site"
  data-help-enabled="true">
</body>
```

The demo accepts any username and password. Replace the demo session gate before using Win2k UI for real authentication.

## Demo applications

The demo is organised as a small Windows-style office suite instead of a list of disconnected component tests:

- **Operations Center** — application launcher, overview metrics and activity.
- **Insight Center** — charts, statistics, filters and forecasts.
- **Project Manager** — database search, pagination, record details and editing forms.
- **Newsroom** — news feed, article reading and publishing information.
- **Community Forum** — categories, topic lists and threaded discussions.
- **Mail**, **Team Calendar** and **File Explorer** — communication, planning and documents.
- **Settings** — Component Catalog, My Account and System Monitor.

The Start menu contains end-user applications under **Programs** and reusable framework/reference tools under **Settings**.

## Help Center

Open **Start → Help** or press `F1`. The Help Center includes Contents, Index, Search and Favorites, plus detailed, copyable examples for containers, buttons, checkboxes, radio buttons, ON/OFF settings, complete forms, charts, news feeds and forum layouts.

Help can be disabled without changing the rest of the framework:

```html
<script>
  window.WIN2K_UI_CONFIG = { help: false };
</script>
```

Alternatively, set `data-help-enabled="false"` on the body. The Help page, Start-menu entry and Help menu are then omitted.

## Included patterns

- Windows 2000-inspired logon screen
- Desktop icons, application chrome, menus and Start menu
- Operations, analytics, project management, newsroom and community applications
- Forms, detail views, articles, files, calendar, mail and user profiles
- Controls, tables, pagination, status states and system dialogs
- Responsive mobile layouts and keyboard navigation
- Optional Help and Support Center

See [HELP.md](./HELP.md) for framework usage and [DESIGN-RULES.md](./DESIGN-RULES.md) for the visual contract.

## Trademark note

Win2k UI is an independent, unofficial project and is not developed, approved or sponsored by Microsoft. A public release should use original icons and graphics, document third-party asset licences and include an appropriate open-source licence.
