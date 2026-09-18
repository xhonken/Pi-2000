# Personal desktop

Development after Alpha 5 adds account-owned desktop controls. Existing icon
positions, shortcuts, files and backgrounds are retained. No new desktop server
or Linux graphical session is required.

## Opening and selecting

Single-click selects an icon; double-click or Enter opens it. To use the previous
single-click behaviour, right-click the background and choose **Desktop Options**.
Use Ctrl-click to toggle several icons, Shift-click to add an icon, or drag a
selection rectangle on empty desktop space. Ctrl+A selects all visible icons.
Arrow keys move focus; Home/End select the first/last icon, F2 renames, Delete
removes selected items after confirmation, and Shift+F10 opens the context menu.
Menus accept arrow keys, Home/End, Enter and Escape.

## Add, rename and remove

- Right-click the background → **Desktop Icons** to choose applications. The
  checkboxes and names belong to your account. Restore Defaults restores the
  initial application selection and names when you press Save.
- Right-click an application or web shortcut in Start → Programs → **Send to
  Desktop**. Programs remain available in Start when their desktop icon is hidden.
- Right-click an icon → **Rename** or press F2. Renaming a program changes only
  its desktop label. Renaming a file or folder changes the actual private file.
- Removing a program icon hides its shortcut. It does not uninstall the app.
  Files, folders and web shortcuts go to the existing Recycle Bin, where they can
  be restored. Removing a web shortcut also removes its Start entry until restored.
- **Properties** shows application/file details or edits a web shortcut's name,
  HTTP/HTTPS address and Desktop/Start visibility. User text is rendered as text.
- **New Folder**, **New Shortcut** and **Upload Files** use the existing private
  storage and Browser applications. Copy/Cut/Paste are available for real files
  and folders, including Ctrl+C/X/V and Paste into Folder. Program shortcuts and
  web shortcuts are managed separately, not treated as file contents.

## Arrangement

Sort by name, type, size or modified date; Reverse Sort Order changes direction.
Applications and web shortcuts have no file size or modification date and use
zero for these comparisons, with their names breaking ties. Auto Arrange keeps
icons in the selected order as items appear. Disable it to drag icons freely;
several selected icons move together. Align to Grid aligns current icons and
turns on grid snapping for later drags. Auto Arrange, snapping and click behaviour
can also be changed in Desktop Options.

Show Desktop Icons hides or reveals all desktop icons without deleting anything.
The Start menu remains available. Long labels have bounded two-line display with
the full name available in the tooltip and Properties. Narrow screens reflow
icons without overwriting saved positions; an overflowing desktop can scroll.

## Persistence and privacy

The existing `/api/desktop` store remains per authenticated user, including web
administrators. Bounded settings validation is in `server/desktop_settings.py`.
The desktop sends an account guard header on reads/writes. ETag/If-Match prevents
new clients from silently overwriting changes made by another open tab. A save
conflict displays a warning; Refresh Desktop asks before discarding unsaved
changes and loads the saved desktop. Legacy documents and clients remain readable.

`assets/desktop.js` owns account loading and saving; `desktop-manager.js` owns
selection, object commands and menus; `icon-layout.js` owns layout and dragging.
Real file operations continue through the account-scoped file manager. Appearance
lives in `desktop-manager.css`; no third-party desktop framework was introduced.

## Architecture choice

Pi-2000 remains an HTML/CSS/JavaScript desktop with its Python API. GNOME Remote
Desktop plus an HTML5 gateway such as Apache Guacamole is a different delivery
model: a server-side graphical session streamed into the browser. It can be a
future optional remote desktop application, but is not a prerequisite for personal
icons and would require separate session, resource and app-integration work.

This is not a Windows compatibility layer. Native executables, arbitrary host
filesystem access and OS administrator rights are not provided by desktop icons.
