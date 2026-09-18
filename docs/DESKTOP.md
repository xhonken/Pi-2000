# Personal desktop

Alpha 6 adds account-owned desktop controls. Existing icon
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

## Restore after restart or power loss

The desktop continuously saves an account-private workspace checkpoint to the Pi.
After login, it restores open application windows, their order, positions, sizes,
minimized/maximized state, folders and supported application content. This also
works from a different browser. Saving does not depend on a clean logout or a
shutdown notification. The taskbar indicator shows **Saving…**, **Saved**,
**Not saved**, **Recovery paused** or **Save conflict**; its tooltip provides
more detail. Click it to retry a failed save or flush supported drafts now.

Changes normally reach the server within about two seconds while connected;
Pi++ and Notes have their own short draft timers. A sudden loss of power or
network can lose edits that have not reached the server yet. An acknowledged
checkpoint uses SQLite transactions and survives an application/server restart;
this is not protection against failed storage hardware. Keep verified backups.

| Application | Restored content and limits |
| --- | --- |
| Pi++ | Open saved files, server recovery drafts (including unsaved new text/SFTP drafts), active document, cursor and scroll. Drafts do not overwrite the original file. |
| Notes | Autosaved notes and task list. |
| Arduino Workshop | Open project, selected source tab, unsaved source/board changes and cursor. Original project revision is retained so a later Save still detects conflicts. Builds, uploads and serial monitoring are not restarted automatically. |
| Display Studio | Composition, embedded images, unsaved changes, selected layer, grid and zoom. Saving the project file remains explicit. |
| Dimension Drawing | Drawing, cutouts and control values, including changes not yet saved with Save Drawing. |
| Calculator | Expression, output, memory and recent history. |
| Terminal | Existing processes reconnect when available. After a reboot, the window returns with Reconnect; a new authenticated connection is required. Commands and terminal passwords are never checkpointed or replayed. |
| Browser | The window reopens using the existing private Chromium profile. Live website state, unfinished forms and media playback are not guaranteed to recover. |
| Vault | Window only; it always opens locked. Unlocked keys, passwords and unsaved secret forms are excluded. |
| Database tools | Windows and the SQL workspace's existing saved drafts. Connections and transactions must be reopened; phpMyAdmin forms/unsent SQL are not checkpointed. |
| Other applications | The window returns. Content is restored only where the app already saves it; unsaved API Tester credentials/requests, Git edits and open modal dialogs are not included. Use each app's Save command. |

One failed application does not stop the others from restoring. Failed recovery
retains its checkpoint rather than replacing it with a default window. A failed
initial workspace read pauses automatic writes until Retry succeeds. A terminal
service outage does not prevent ordinary windows and drafts from returning.

Each account has its own checkpoint, including administrators. There is no
administrator read override. New clients send an account guard and conditional
ETag on writes. If two tabs diverge, saving pauses in the stale tab: reload to
use the server's version, or click **Save conflict** and explicitly confirm
replacing it with that tab's workspace. Only the confirmed version becomes the
next recovery checkpoint. This is not a historical version browser.

Recovery data is limited to 4 MB per workspace and counts toward account storage
quota. Large Display Studio images may reach this limit; save project files and
reduce embedded images if the taskbar reports that recovery data is too large.
Existing file quotas and app-specific limits still apply.

## Architecture choice

Pi-2000 remains an HTML/CSS/JavaScript desktop with its Python API. GNOME Remote
Desktop plus an HTML5 gateway such as Apache Guacamole is a different delivery
model: a server-side graphical session streamed into the browser. It can be a
future optional remote desktop application, but is not a prerequisite for personal
icons and would require separate session, resource and app-integration work.

This is not a Windows compatibility layer. Native executables, arbitrary host
filesystem access and OS administrator rights are not provided by desktop icons.
