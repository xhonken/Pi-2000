# Windows 2000 UI references — 2026-09-08

Reference searches and image review preceded the UI implementation:

- https://guidebookgallery.org/screenshots/win2000pro/
- https://guidebookgallery.org/pics/gui/desktop/full/win2000pro.png
- https://guidebookgallery.org/pics/gui/applications/office/notepad/win2000pro.png
- https://guidebookgallery.org/pics/gui/system/managers/filemanager/win2000pro.png
- https://guidebookgallery.org/pics/gui/applications/office/calculator/win2000pro.png
- https://guidebookgallery.org/pics/gui/system/managers/tasks/win2000pro-1-1.png
- https://guidebookgallery.org/pics/gui/system/managers/tasks/win2000pro-1-2.png
- https://guidebookgallery.org/pics/gui/system/managers/tasks/win2000pro-1-3.png
- https://learn.microsoft.com/en-us/windows/win32/uxguide/vis-fonts
- https://learn.microsoft.com/en-us/windows/win32/uxguide/cmd-menus

These images are visual references, not distributed application assets. The current icons are original SVG drawings on a shared 32-unit canvas.

## Decisions

Use Tahoma, Arial, Liberation Sans, sans-serif; 13 px by default with account settings from 12 to 18 px across the desktop, Start menu, dialogs and applications. Code and terminals retain monospace fonts. No external fonts or network resources are required for the shell.

Use grey `#d4d0c8`, blue selection `#0a246a`, white document surfaces and thin raised edges. No rounded corners or glass effects. Menu and window icons are 16 px, desktop icons 32 px. Standardise inputs, buttons, tables and status bars.

Application menus match actual commands, invoke existing actions and respect disabled controls. Common commands also appear in compact toolbars. Support menu mnemonics, F10, arrows, Home/End, Enter and Escape. Keep menus inside the visible viewport.

Start → Programs groups Accessories, Development and Drawing, Internet and Connections, System Tools, and My Shortcuts. Administration follows existing permissions. Support clicks, pointer navigation and the keyboard, with at most two submenu levels. Preserve user icon positions and application functions.

Task Manager uses the historical tabbed layout, black graph backgrounds, green grids and traces, segmented resource meters and compact statistics. Its measurements and permission boundaries match the actual server architecture.

Verification covers real menu commands, keyboard navigation, large text, narrow viewports, owner/regular-user differences, SFTP editing, files, drawing and screenshot review. Published assets are verified over HTTPS.
