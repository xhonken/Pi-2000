# Pi-2000Web Design Rules

Preserve the Windows 2000 visual language while making the applications usable in a modern browser. The product name is Pi-2000Web; Microsoft and Windows identify historical references, not this product.

## Shared appearance

- Desktop background: `#3a6ea5`; system surfaces: `#d4d0c8`.
- Active title bars use `#0a246a` to `#1084d0`; inactive windows have muted title bars.
- Square corners, thin raised borders, recessed white input fields and visible keyboard focus.
- Tahoma, Arial, Liberation Sans, sans-serif at 13 px by default. Honour the user setting from 12 to 18 px across desktop, menus, dialogs and applications.
- Keep monospace fonts for code and terminals.
- Original SVG icons share a 32-unit design grid: 32 px on the desktop, 16 px in menus, title bars and the taskbar.
- Use local assets; do not require external fonts or an icon CDN.

## Application behaviour

Use the shared window manager and classic controls. File, Edit, View, Connection and Help menus must invoke real application commands and preserve permission checks and disabled states. Common commands also belong in compact toolbars. Group secondary row commands under Actions.

Support keyboard navigation, including F10, English menu mnemonics, arrow keys, Home/End, Enter and Escape. Give controls meaningful accessible names. Avoid making essential commands depend on hover. Keep menus and dialogs within the viewport, including with larger text or a narrow screen.

Start → Programs has Accessories, Development and Drawing, Internet and Connections, System Tools, and My Shortcuts. Limit nesting to two submenu levels. Preserve saved icon positions and user workspace state.

## Language and naming

All maintained product UI, accessibility labels, errors, installer output and documentation use English. Keep menu and toolbar labels consistent because the menu adapter maps commands to existing controls by label. Use English mnemonics: File F, Edit E, View V, Connection C, Account A, Help H.

Do not translate user-authored file names, notes, shortcut names, connection names or document contents. Do not rename database keys, service units, stored paths or JavaScript namespaces solely for branding. The legacy `win2k` identifiers are a compatibility interface.

## Verification

Check actual menu actions, keyboard access, file operations, editor saves, SFTP operations, drawing, ordinary-user permissions, large fonts and small viewports. Inspect screenshots, then compare deployed assets over HTTPS. A successful file copy alone is not deployment verification.

See [the visual reference record](design/windows-2000-ui.md). The archived upstream gallery under `reference/` is not part of the installed desktop.
