# Pi-2000Web User Guide

## Getting started

Log in with your Pi-2000Web account. The desktop, files, connections and browser profile belong to that account. Start → Programs groups your applications by purpose. Start → Settings contains personal settings and, if permitted, User Management.

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
| Ctrl+F / Ctrl+H | Find / Find and Replace in Code Editor |

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

## Code Editor and SFTP

Open a file from the tree, or use File → New Local File / New Local Folder. Choose a syntax mode, enable word wrap or change the theme. Ctrl+S saves the active file. Save As chooses a local name and folder. Download exports a copy to your computer.

Recovery drafts are saved automatically for your account. Reloading restores available drafts and tabs. Explicit saves still control the file contents. If a file changed elsewhere, save a new copy or inspect the other version to avoid overwriting work.

Connection → SFTP – Open Device opens a remote file tree from one of your own SSH profiles. Enter its password and verify its host key. Create remote files/folders or open UTF-8 text files up to 1 MB. Tabs marked [SFTP] save to that device. Open Device Version reads the current remote copy; Save Copy on Device creates a new remote file. Passwords must be entered again after reloading.

SFTP – File Transfer sends a saved local file to a remote directory or downloads a remote file into My Files. Overwrite requires an explicit choice. Transfers need the page to remain open and support files up to 50 MB.

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

My Settings changes text size and the default text-file application, opens background settings, changes your password and lists signed-in sessions. You can log off another session belonging to your account.

User Management is available to administrators and the owner. Administrators manage regular users; only the owner changes roles or manages other administrators. Account deletion is permanent. Disabling an account, resetting its password or changing its role ends its sessions. The owner account is protected.
