# Win2k UI design rules

This document is the design contract for **Win2k UI**, an independent Windows 2000-inspired web framework. New pages should reuse these rules and avoid modern cards, rounded chips and decorative shadows.

## Application window

- Use a Windows 2000 bevel with no outer drop shadow.
- Keep the title bar 2 pixels inside the outer frame.
- Lock the title gradient to `#0a246a` → `#1084d0`, left to right.
- Use the website domain and slogan as the title, for example `example.com - My site`.
- Place page-specific commands in the menu bar below the title bar.
- Keep the grey divider below the menu bar.
- Reserve the taskbar notification area for the clock and date only.
- Open pages from the Start menu; do not add taskbar quick links.

## Start menu and navigation

- The primary order is `Programs`, `Settings`, `Search…`, `Help` and `Log Off…`.
- `Programs` contains the website’s application pages.
- `Settings` contains controls, personal settings and system states.
- Cascades open on hover on desktop and on tap or keyboard activation everywhere.
- `Search…` opens Database and focuses the search field.
- `Help` opens the optional Help and Support Center.
- `Log Off…` ends the demo session and returns to the logon screen.

## Logon flow

- A new browser-tab session begins at the Windows 2000-style logon screen.
- The demo accepts any user name and password and does not send or store credentials.
- Successful logon opens Overview for the current tab only.
- Replace this demo gate with a proper server-side authentication flow in production.

## Standard page structure

Every page begins with the same recessed white introduction area:

1. A small green section label.
2. A large black page title.
3. A shorter description of the page.
4. An optional action on the right.

Group the remaining content in `fieldset`-style containers with black legend text. Groups use `#d4d0c8`, square corners and the shared Windows bevel. A white inner surface is allowed for data, text or charts, but not as a floating modern card.

## Controls

- Inputs, list boxes and text areas are white and recessed.
- Buttons are grey and raised; selected or active buttons look pressed.
- Check boxes use a centred, two-pixel cross.
- Radio buttons remain round because that is their native Windows form.
- Binary settings use rectangular `ON`/`OFF` buttons.
- Sliders use a square thumb and recessed track.
- Progress bars use segmented dark-blue fill.
- Focus uses a visible dotted black inner outline.
- Disabled controls use grey text with a white highlight.
- Status is presented as text with a system icon, never as a decorative pill.

## Typography

- Use `Segoe UI`, `Tahoma`, `Arial`, `sans-serif` for interface text.
- Reserve pixel styling for CSS-drawn system icons.
- Use 12-pixel controls on desktop and at least 16-pixel inputs on mobile to avoid automatic zoom.

## Data and analysis

- Put filters and time ranges in a compact toolbar.
- Place metrics in separate bordered groups.
- Draw charts on white recessed plotting areas inside grey content groups.
- Provide legends, text labels and a table alternative for visualised data.
- Database result rows use a grey system background and one uninterrupted separator.
- Row numbers are plain text; status uses a small system indicator and status name.
- Pagination uses standard square Windows buttons.

## Responsive behaviour

- Switch content grids to one column below 900 pixels.
- Never create global horizontal scrolling; scroll tables and file lists inside their own recessed surfaces.
- Let toolbars and action rows wrap when necessary.
- Use touch targets of at least 40 pixels for mobile form controls.
- Keep cascaded menus within the viewport and allow vertical scrolling in the Start menu.

## Help Center

- Help is an optional application page with Contents, Index, Search and Favorites.
- Pressing `F1` opens a context-appropriate Help topic.
- Help topics explain both navigation and framework construction.
- Disable Help with `window.WIN2K_UI_CONFIG = { help: false }` or `data-help-enabled="false"`.
- When disabled, omit the Help route, Start entry and Help menu without leaving empty UI.

## Reference pages

- **Overview:** metrics, team focus and recent activity.
- **Analytics:** metrics, revenue chart, distribution and insight.
- **Database:** search, filtering, records, status and pagination.
- **Sign in:** account form and security information.
- **My profile:** profile, personal metrics, preferences and saved views.
- **Controls:** the visual reference for all form and system components.
- **Forms:** longer editing and publishing flows.
- **Detail view:** metadata, related records, description and history.
- **Article:** headings, links, quotations, lists and tables.
- **Files:** address bar, tree, list view and status bar.
- **Calendar:** month view, selected day, events and agenda.
- **Messages:** inbox, unread state, reading pane and reply form.
- **System states:** loading, empty, 404, denied access and confirmation.
- **Help:** framework documentation and practical recipes.

Together these pages cover navigation, reading, editing, data, analysis, files, time, communication, accessibility and error handling.
