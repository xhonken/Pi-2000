# Win2k UI architecture

## Goals

1. Keep the framework usable without WordPress.
2. Share one visual and behavioural core across every adapter.
3. Keep durable content out of themes.
4. Let authentication and persistence remain the responsibility of the host platform.
5. Allow adapters to be removed without breaking the core package.

## Dependency direction

```text
standalone ─────────────┐
WordPress theme ────────┼──> Win2k UI core
headless REST frontend ─┘

WordPress content plugin ──> WordPress only
```

The core never imports an adapter. Adapters may import or package the core.

## Content versus behaviour

- `core/win2k-ui.js` enhances pre-rendered HTML and never creates product pages.
- `standalone/demo-content.js` owns sample records and demo actions.
- WordPress templates own server-rendered posts, pages, archives and search.
- The REST adapter maps public JSON to safe DOM nodes for a separate frontend.

## Compatibility note

The original design-gallery runtime in `design/demo/shared/app.js` remains intact for the 99-style comparison library. It is a gallery compatibility layer, not the distributable framework core. New Win2k UI implementations should use this package.
