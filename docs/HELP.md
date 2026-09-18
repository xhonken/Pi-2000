# Pi-2000Web User Guide

Alpha 5 includes Pi++, Arduino Workshop and the network, display, archive, log
and serial plotting tools below. See the [release notes](releases/0.1.0-alpha.5.md)
for the test installer and remaining hardware checks.

## Getting started

Log in with your Pi-2000Web account. The desktop, files, connections and browser profile belong to that account. Start → Programs groups your applications by purpose. Start → Settings contains personal settings and, if permitted, User Management.

Up to twelve web logins can remain active for your account. A further login expires the oldest excess login; detached SSH jobs continue. If too many requests are active, let an operation finish and retry.

Drag desktop icons to arrange them. Right-click empty desktop space to create a folder, upload files, create a shortcut or change desktop properties. Your icon positions and background are saved for your account.

## Windows and menus

Drag the title bar to move a window or its border to resize it. Use the title-bar buttons to minimise, maximise/restore and close. Click a taskbar button to return to an application.

File contains open, create, save and close commands; Edit contains content actions; View controls presentation; Connection contains remote connections; Help describes the current application. Common actions also appear in toolbars. Disabled commands are unavailable in the current context. Actions menus on file/account rows contain commands for that item.

| Shortcut | Action |
| --- | --- |
| Ctrl+Esc | Open Start |
| Ctrl+Shift+Esc | Open Task Manager |
| Ctrl+Space | Search |
| F1 | Desktop Help |
| F10 | Focus the application menu |
| Alt+F / Alt+E / Alt+V | File / Edit / View |
| Arrow keys, Home, End, Enter, Escape | Navigate menus |
| Ctrl+S | Save the active editor file |
| Ctrl+Shift+S | Save As |
| Ctrl+F / Ctrl+H | Find / Find and Replace in Pi++ |

## My Files and Recycle Bin

Open My Files from the desktop. Double-click folders or files to open them. Drag files from your computer into the window or onto the desktop to upload them. Upload Folder preserves a folder hierarchy when supported by your browser.

Select checkboxes to copy, cut, paste, download a ZIP or delete multiple items. Use Actions on a row to rename or move an item. The desktop is also a file location. New Folder creates a folder in the current location.

Deleted files and folders enter the Recycle Bin. Restore returns them to their previous location when possible; restore parent folders first. Empty Recycle Bin deletes its contents permanently, including deleted shortcuts. Deleted files continue to use your quota until permanently removed.

New accounts have 50 MiB. An administrator can increase storage for a regular user. Notes, drawings, drafts and pending uploads also use this quota. Browser profiles and local backups use separate server space.

## My Devices and terminal sessions

Create folders and SSH connection profiles in My Devices. A profile stores its name, host/IP, port and SSH username. Enter the SSH password when connecting; it is not saved in the profile. Confirm unknown host keys only after checking the fingerprint on the device. A changed saved host key blocks the connection.

SSH jobs continue on the server when your client disconnects or you log off. Return through the restored workspace, My Activities or Task Manager. Explicitly ending a terminal stops its session and may stop its jobs. The Pi, session service, network and remote device must remain available for jobs to survive.

## Browser

Browser runs Chromium on the Pi with private tabs, cookies and site logins for your account. Click inside it to control it and enable audio. Resize the window to resize its content. Full Screen is available under View; Reconnect and End Session are under Connection.

Closing the window preserves the session. End Session stops the browser. Up to three browser sessions run simultaneously across the server. Inactive browser sessions expire after 24 hours without a connected client. uBlock Origin Lite is enforced through the browser policy; no ad blocker can guarantee removal of every advertisement.

If server memory is low, starting a new Browser may be refused. Status messages distinguish memory-limit stops, crashes, low disk space and idle timeouts. Use Connection → Reconnect after addressing the cause; saved profiles are retained, but unsaved page state may be lost.

Browser also pauses when the installed Chromium engine is older than the reviewed security minimum. The Pi operator must install a security update before Browser can reconnect. Your saved profile is retained. See [Security](SECURITY.md) for the current minimum and its limitations.

## Pi++ and SFTP

Pi++ is the former Code Editor, redesigned with a Notepad++-inspired document panel, toolbar and menus. Open a file from the folder panel or File → Open. File → Import from Computer opens UTF-8 files as unsaved tabs. Ctrl+S saves the active file; Save All saves changed documents in order and stops on a conflict or cancelled Save As. Download exports the active text.

Search contains Find/Replace, Find in Open Documents, Go to Line and bookmarks. Language selects syntax highlighting. Encoding converts Unix LF or Windows CR LF line endings. Settings → Preferences saves private appearance, completion and indentation defaults. View controls the sidebar, whitespace, line numbers, folding and zoom; Window selects and closes tabs. See [Pi++](PIPLUS.md) for shortcuts and limits.

Recovery drafts are saved automatically for your account. Reloading restores available drafts and tabs. Explicit saves still control the file contents. If a file changed elsewhere, save a new copy or inspect the other version to avoid overwriting work.

Connection → SFTP – Open Device opens a remote file tree from one of your own SSH profiles. Enter its password and verify its host key. Create remote files/folders or open UTF-8 text files up to 1 MB. Tabs marked [SFTP] save to that device. Open Device Version reads the current remote copy; Save Copy on Device creates a new remote file. Passwords must be entered again after reloading.

SFTP – File Transfer sends a saved local file to a remote directory or downloads a remote file into My Files. Overwrite requires an explicit choice. Transfers need the page to remain open and support files up to 50 MB.

Use **Code → Check Syntax** for Python, JavaScript or JSON. Click a reported problem to reach its line. This checks syntax without running your program; it does not check types or runtime behavior.

## Network, display, archives, logs and serial graphs

**Network Tools** saves private host/port targets and runs DNS, ping and TCP checks from the Pi. **Display Studio** draws layered screen designs with a round GC9A01A preset and exports PNG, RGB565 or Arduino headers. **Archive Manager** creates ZIP downloads and safely extracts selected ZIP entries into a new private folder. **Log Viewer** filters and follows private files or logs accessible through your SSH profiles.

**Arduino Workshop → Tools → Serial Plotter** graphs up to eight numeric channels from the selected Pi USB serial device, with pause, scale controls and CSV export. USB access requires an administrator. See [workflows, sample firmware and limits](UTILITY-TOOLS.md).

## Everyday tools

Notes and Tasks saves your notes and checklist automatically. Search and Favourites searches your own files, folders, apps and SSH connections. Use stars for favourites or filter to recent items. My Activities lists terminal sessions, browser controls, transfers and open windows.

Calculator accepts arithmetic expressions and scientific functions. Angles use degrees; decimal points or commas are accepted. For example, `sqrt(300^2 + 400^2)` returns 500. `%` divides the entire expression by 100. Scientific Functions and History are available under View.

Dimension Drawing supports common outer shapes and cutouts. Enter dimensions in millimetres, position cutouts by their centres and rotate them as needed. Select a cutout in the drawing or table to edit it. Use frame or grid patterns for circular holes. Check warnings and the displayed approximation tolerance before exporting. Save Drawing stores the drawing privately; SVG and CSV export download copies.

## Task Manager

Use Start → Programs → System Tools, right-click the taskbar, or press Ctrl+Shift+Esc.

- Programs lists your open windows and terminal sessions; switch to them or close them.
- Processes lists your browser processes. Only the installation owner can view all server processes. Individual OS processes are read-only.
- Performance shows server CPU and memory, 120-second graphs, per-core graphs, uptime, cache and swap. Updates run every two seconds and can be paused under View.
- Storage shows your quota and the shared server data volume, including reserved disk space.

These measurements describe the Pi, not your viewing computer. SSH jobs run on their remote device and are not in the Pi process list.

## Settings and account management

For managed accounts, passwords use Linux-PAM and must contain at least 12 characters and at most 512 UTF-8 bytes. Existing linked Linux accounts change their password locally with `passwd`; the web interface cannot reset them.

My Settings changes text size and the default text-file application, opens background settings, changes your password and lists signed-in sessions. You can log off another session belonging to your account.

User Management is available to administrators and the protected installation creator. Administrators manage regular users; only the creator changes roles or manages other administrators. Disable preserves data. Delete requires the exact username and removes managed Linux accounts and homes as well as web data; existing linked Linux accounts are preserved. The creator cannot be disabled, deleted or demoted.


## MariaDB Manager

Open **Start → Programs → Development and Drawing → MariaDB Manager**. Use **File → New Connection** for a local or external MariaDB server, select the saved connection and Connect. The server address is reached from the Pi; `127.0.0.1` means the Pi itself. Verified TLS is the default, and saving an encrypted password is optional.

The manager opens phpMyAdmin with the Pi-2000 appearance. Select a database or table to browse rows, edit structure, run SQL, search or import/export. Account and privilege administration requires the corresponding database permissions. Optional metadata features require configuration storage. See [phpMyAdmin integration](PHPMYADMIN.md) for setup and limits.

**File → Saved SQL Workspace** opens existing native SQL drafts and tools. Table Data and SQL Queries are separate views. Close or select query tabs using the query controls; the guided SELECT/JOIN builder helps choose tables, joins, columns and filters. Row forms apply changes on OK; when using an explicit transaction, commit or roll back as appropriate. Read [MariaDB Manager](MARIADB-MANAGER.md) for detailed workflows.

## Git Projects

Open **Start → Programs → Development and Drawing → Git Projects**. Create a project or clone an HTTPS repository. Edit files, inspect diffs, stage changes and commit with your author details. A commit saves locally; use the Remote commands to fetch, pull or explicitly push. Projects belong to your account and are isolated from the Pi-2000 installation.

## Arduino Workshop

Open the **Arduino Workshop** desktop icon or **Start → Programs → Development and Drawing → Arduino Workshop**. Create a project, install ESP32 support through **Tools → Boards Manager**, then choose a board and USB port. **Tools → Library Manager** searches and installs library versions and dependencies; **Installed Libraries → Include Library** adds the headers to your code. Save Project stores every file and the board configuration. Verify compiles on the Pi; Upload compiles and flashes the Pi-connected board after confirmation. Serial Monitor receives and sends text at the selected baud rate.

Projects and installed packages are private. All users can compile; USB upload and Serial Monitor require an administrator account. See [Arduino Workshop](ARDUINO-WORKSHOP.md) for first-use steps, imports/exports, job recovery, installation and limits.

## API Tester

Open **Start → Programs → Development and Drawing → API Tester**. Enter a URL, method, headers and optional body, then Send. **Request → Authentication** configures Basic or Bearer authentication. Inspect the response status, headers, body and timing; save requests to your private encrypted collection if needed. Requests originate from the Pi, so the destination must be reachable from it.

See [Development Tools](DEVELOPMENT-TOOLS.md) for Git, API Tester and syntax-check limits.

## Installed version and unsaved development work

Open **Help → About Pi-2000Web** in an application, or **Start → Programs →
System Tools → About Pi-2000Web**, to see the installed version, build ID and source
revision. Local modifications are indicated separately. The build identity is
created by the server publisher; reloading the browser does not change it.

API Tester warns before replacing or closing an unsaved request and before logoff.
A failed save keeps the entered content available for retry. Save Request stores
credentials encrypted on the server; unsaved request text is not copied to browser
storage. Git file dialogs likewise warn before discarding edited text through
Cancel, Escape, logoff or browser reload. Save File writes the project file; stage
and commit remain separate steps.

The native SQL workspace saves drafts before logoff and warns before leaving an
active connection. Browser reload warnings cannot guarantee recovery after a
browser crash, forced close or server-side account revocation. Save work regularly;
active database transactions are not restored after disconnect or restart.

## Local Terminal and initial database

**Start → Programs → System Tools → Local Terminal** and its desktop icon are available to all administrators. Each uses their own Linux identity and password. Managed accounts receive no sudo automatically; the OS administrator grants that separately. Ordinary users receive a private Linux home and web access, including saved remote SSH connections, but no Local Terminal.

The terminal installer asks for a protected creator username and password and creates a private **Local MariaDB** connection for that creator. Its initial SQL password matches the chosen password; subsequent Linux/web password changes do not change MariaDB credentials. Existing accounts migrate to PAM at their next successful login. Explicitly linked Linux accounts use the existing OS password; change it locally with `passwd`.

See [system account operations](SYSTEM-ACCOUNTS.md) and the [Debian installation guide](DEB-INSTALLATION.md).

### Pending service updates

In development builds after Alpha 5, About and System Status also show the build
actually loaded by each service. **Update pending** means the installed files are
newer than the running worker. **Waiting for existing jobs** means maintenance is
blocking new work while existing jobs finish. **Unknown** means an older worker
cannot report its loaded version. Finish work before asking the OS administrator
to activate the update; web administrator access does not grant service restart
permission. See [maintenance](MAINTENANCE.md) and [recovery](RECOVERY.md).

## Personal Vault

Open the Vault desktop icon or Start → Programs → System Tools → Vault. Create two
different passphrases: A opens titles/categories/dates; B opens one entry and must
be entered again after closing or switching entries. Secrets lock after 30 seconds
of inactivity and the list after five minutes. Save edits before leaving.
Keep the recovery key outside the Pi. File and Security menus provide encrypted
export/import, password changes and recovery. Other web users and administrators
have no access to your Vault contents. Read the [Vault guide](VAULT.md) for clipboard,
backup, plaintext export and trusted-browser boundaries. Development after Alpha 5.

Changing Vault passphrases or using recovery also rotates the encryption keys and
re-encrypts the saved entries. Keep the new recovery key; previous exports remain
separate copies protected by their previous passphrases and recovery key.

## Personal desktop controls (development after Alpha 5)

Double-click icons to open; single-click selects. Right-click the desktop for
Desktop Icons, sorting, grid alignment, new items and Desktop Options. Right-click
an icon to rename, remove, copy/cut private files or view Properties. Use Ctrl-click
for multiple selection, F2 to rename and Delete to remove. Start-menu applications
can be sent to the desktop. Removing a program icon keeps the application installed.
Settings are private to your account; see [Desktop](DESKTOP.md) for all commands
and how to choose single-click opening or resolve a two-tab save conflict.


## Desktop recovery after a restart

Your open windows and supported application recovery state are saved continuously
for your account. Log in after the Pi restarts to restore them. Check the taskbar's
**Saved** indicator; **Not saved** means recent changes have not been confirmed
on the Pi. Click the indicator to retry or save supported drafts now. A save
conflict means another tab changed the checkpoint: reload, or explicitly confirm
replacing it with this tab's workspace. Do not assume a power failure can preserve
edits made since the last successful save.

Pi++, Notes, Arduino source, Display Studio, Dimension Drawing and Calculator have
recovery support. Original files and projects still use their normal Save command.
Terminal windows offer Reconnect after a reboot; previous commands/jobs are not
replayed. Vault opens locked. Database transactions, phpMyAdmin forms, unsaved API
Tester/Git edits, modal dialogs and arbitrary website state are not recovered.
See [Desktop recovery](DESKTOP.md#restore-after-restart-or-power-loss) for exact
coverage and the 4 MB per-account checkpoint limit.
