# Win2k UI Framework

Win2k UI is a platform-independent Windows 2000-inspired interface framework. The framework core contains only CSS and progressive JavaScript behaviour. Content, routing, authentication and persistence belong to the host application or an optional adapter.

## Packages

- `core/` — source CSS and JavaScript with no WordPress dependency.
- `dist/` — generated portable assets.
- `standalone/` — plain HTML starter with separate demo content.
- `integrations/wordpress/theme/` — optional WordPress block theme adapter.
- `integrations/wordpress/plugin/` — optional content plugin for portable project data.
- `integrations/wordpress/headless/` — read-only REST adapter for a separate frontend.

## Build

Run `npm run build` from this folder. The build creates portable assets and synchronises them into the WordPress theme.

## Core contract

The core owns visual tokens, components, menus, Start-menu behaviour, clock/date, Help visibility, focus handling and status messages. It does not own page content, authentication, database schemas or WordPress APIs.

The existing design-gallery demo remains a compatibility showcase. New applications should start from `standalone/` or one of the adapters in `integrations/`.
