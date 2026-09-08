# Win UI

Win UI is a reusable Windows 2000-inspired web framework built with plain HTML, CSS and JavaScript. It combines a classic desktop, application window, Start menu, system dialogs, reusable controls and an optional Windows Help-style documentation center.

## Quick start

Load `base.css`, `expanded-themes.css`, `style-manifest.js` and `app.js`, then configure the body:

```html
<body
  data-style="windows-2000-mirc"
  data-style-name="Win UI"
  data-product-name="My Website"
  data-site-title="example.com - My site"
  data-help-enabled="true">
</body>
```

The demo accepts any username and password. Replace the demo session gate before using Win UI for real authentication.

## Help Center

Open **Start → Help** or press `F1`. The Help Center includes Contents, Index, Search and Favorites, plus detailed, copyable examples for containers, buttons, checkboxes, radio buttons, ON/OFF settings, complete forms, charts, news feeds and forum layouts.

Help can be disabled without changing the rest of the framework:

```html
<script>
  window.WIN_UI_CONFIG = { help: false };
</script>
```

Alternatively, set `data-help-enabled="false"` on the body. The Help page, Start-menu entry and Help menu are then omitted.

## Included patterns

- Windows 2000-inspired logon screen
- Desktop icons, application chrome, menus and Start menu
- Overview, analytics, database, profile and sign-in pages
- Forms, detail view, articles, files, calendar and messages
- Controls, tables, pagination, status states and system dialogs
- Responsive mobile layouts and keyboard navigation
- Optional Help and Support Center

See [HELP.md](./HELP.md) for framework usage and [DESIGN-RULES.md](./DESIGN-RULES.md) for the visual contract.

## Trademark note

Win UI is an independent, unofficial project and is not developed, approved or sponsored by Microsoft. A public release should use original icons and graphics, document third-party asset licences and include an appropriate open-source licence.
