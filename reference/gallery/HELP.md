# Win2k UI framework help

The in-app Help Center is the primary guide. Open it from **Start → Help**, the application Help menu or `F1`.

## Explore the demo applications

Open **Start → Programs** to inspect complete examples for operations dashboards, analytics, project databases, news publishing, forums, mail, calendars and file management. Open **Start → Settings** for the Component Catalog, My Account and System Monitor. The project editor and project-detail view are reached through Project Manager, just as secondary windows would normally belong to their parent application.

## Build a page

Use the application shell supplied by `app.js`. A custom page should contain one page introduction and one or more named content groups:

```html
<section class="page page-reference">
  <header class="page-heading">
    <div>
      <p class="eyebrow">Section name</p>
      <h1>Page title</h1>
      <p>A short explanation of this page.</p>
    </div>
  </header>

  <fieldset class="win2k-reference-group win2k-group">
    <legend>Content group</legend>
    <!-- Your content -->
  </fieldset>
</section>
```

## Build a container

A Win2k UI container is a semantic `fieldset` with a visible `legend`. Use `win2k-group` for the shared Windows surface and `win2k-reference-group` for standard page spacing:

```html
<fieldset class="win2k-reference-group win2k-group">
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
</fieldset>
```

Use `wide` on a label or item that should span both columns. Split unrelated tasks into separate containers and avoid nesting bevelled containers unless the inner group is a genuine sub-section.

## Add buttons

```html
<div class="win2k-form-actions" role="group" aria-label="Form actions">
  <button class="button win2k-default-button" type="submit">Save</button>
  <button class="button" type="button">Preview</button>
  <button class="button" type="button">Cancel</button>
  <button class="button" type="button" disabled>Unavailable</button>
</div>
```

- Use `type="submit"` for the form’s save action.
- Use `type="button"` for commands that must not submit a form.
- Use `win2k-default-button` for the one action that should run when Enter is pressed.
- Put the primary action first and Cancel last.
- Confirm destructive actions that cannot be undone.

## Add checkboxes, radio buttons and ON/OFF settings

```html
<fieldset class="win2k-control-group win2k-group">
  <legend>Preferences</legend>

  <label><input type="checkbox" checked> Product updates</label>
  <label><input type="checkbox"> Weekly report</label>

  <label><input type="radio" name="density" value="normal" checked> Normal</label>
  <label><input type="radio" name="density" value="compact"> Compact</label>

  <label class="win2k-toggle-row">
    <span>Automatic sync</span>
    <input class="toggle" type="checkbox" checked>
  </label>
</fieldset>
```

Use checkboxes for independent choices, radio buttons for exactly one choice from a set and the rectangular ON/OFF control for a persistent binary setting. Wrap every input and its text in the same `label` so the complete row is clickable.

## Read control values

```js
const updatesEnabled = document.querySelector('[name="emailUpdates"]').checked;
const density = document.querySelector('[name="density"]:checked')?.value;
const values = Object.fromEntries(new FormData(document.querySelector('form')));
```

Use native validation such as `required`, suitable input types and `form.reportValidity()` before adding custom validation messages.

## Reuse existing patterns

- Use **Overview** for dashboard metrics and activity.
- Use **Analytics** for charts, statistics and forecasts.
- Use **Database** for search, filters, tables and pagination.
- Combine **Messages**, **Article** and **Database** for a news feed.
- Combine list views, status indicators, pagination, profiles and messages for a phpBB-style forum.
- Use **Controls** as the source of truth for inputs, buttons, selectors and messages.

## Configuration

The body supports:

- `data-product-name`: product or website name.
- `data-site-title`: title-bar domain and slogan.
- `data-help-enabled`: `true` or `false`.

JavaScript configuration can override Help:

```html
<script>
  window.WIN2K_UI_CONFIG = { help: false };
</script>
```

## Accessibility checklist

- Use semantic headings, labels, tables and fieldsets.
- Keep the dotted focus indicator visible.
- Never communicate status with colour alone.
- Give icon-only buttons an accessible name.
- Respect reduced-motion preferences.
- Keep mobile inputs at least 40 pixels tall with 16-pixel text.
- Confine horizontal scrolling to wide components.

## Production checklist

- Replace the demo logon gate with real authentication.
- Remove example content and configure the product name and title.
- Keep Help enabled for user-facing products, or disable it cleanly if documentation is provided elsewhere.
- Test custom pages with keyboard, touch, browser zoom and narrow screens.
- Use original artwork and properly licensed assets for public distribution.

## Standalone and WordPress packages

The distributable framework lives in the top-level `win2k-ui/` package. Its `core/` directory contains platform-independent CSS and JavaScript and never imports WordPress.

- `win2k-ui/standalone/` is the plain HTML starter.
- `win2k-ui/integrations/wordpress/theme/` is the optional block-theme adapter.
- `win2k-ui/integrations/wordpress/plugin/` contains optional portable content types.
- `win2k-ui/integrations/wordpress/headless/` is the optional read-only REST adapter.

The WordPress theme controls presentation only. Durable content and functionality remain in plugins, while authentication and permissions remain the responsibility of WordPress. The Windows logon shown in the design gallery must never be used as production authentication.
