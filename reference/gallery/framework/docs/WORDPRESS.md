# Win2k UI for WordPress

WordPress support is optional. The platform-independent files in `../../core/` remain the source of truth, and the standalone starter works without PHP, MySQL or WordPress.

## Choose a mode

### WordPress block theme

Use `theme/` when WordPress should render the public website. It supplies templates for the front page, pages, posts, archives, search, 404 and optional Project records. The Site Editor can edit content groups and dashboard patterns.

### Content plugin

Use `plugin/win2k-ui-content/` only when the site needs a portable Project post type. Project data, areas and statuses remain in WordPress if the Win2k UI theme is replaced.

### Headless REST adapter

Use `headless/` when a separate Win2k UI frontend should read public WordPress content over JSON. The adapter is read-only by design. Authentication, mutations, caching, previews and SEO remain application responsibilities.

## Build and install the theme

1. Run `npm run build` in the `win2k-ui` directory.
2. Copy the `theme` directory to `wp-content/themes/win2k-ui`.
3. Activate **Win2k UI** under Appearance → Themes.
4. Open the Site Editor to customise templates and patterns.

The build synchronises `core/win2k-ui.css` and `core/win2k-ui.js` into `theme/assets/`.

## Install the optional plugin

1. Copy `plugin/win2k-ui-content` to `wp-content/plugins/`.
2. Activate **Win2k UI Content**.
3. Add projects from the Projects menu.

The plugin does not delete content on deactivation or removal.

## Disable Help

Add this to a small site plugin or child theme:

```php
add_filter( 'win2k_help_enabled', '__return_false' );
```

The generic core then hides Help entries and disables the `F1` Help action.

## Authentication

The Windows-style logon in the design gallery is a demonstration and is not part of this theme. Production WordPress sites must use WordPress authentication, capabilities, sessions and nonces. The adapter must never collect or validate WordPress passwords in browser JavaScript.

## Responsibility boundaries

- Core: design tokens, components and generic interactions.
- Theme: templates and presentation.
- Plugin: durable data types and functionality.
- WordPress: users, permissions, content, media and persistence.
- Host application: business rules, external APIs and deployment.
