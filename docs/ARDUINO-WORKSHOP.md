# Arduino Workshop

Arduino Workshop is a native Pi-2000Web application for writing sketches, installing board support and libraries, compiling on the Pi, uploading over the Pi's USB connection and using a serial monitor. Open **Start → Programs → Development and Drawing → Arduino Workshop**.

This feature is in the source checkout after Alpha 4; it is not included in the published Alpha 4 package.

## First use

1. Connect a development board to a **USB-A port on the Pi** using a data cable. For a USB-C ESP32 board, use a USB-A to USB-C data cable. The Pi 5's USB-C connector supplies power to the Pi.
2. Choose **File → New Project**. Start with Serial Hello, Empty Sketch or Blink. Blink requires setting the LED pin for your hardware.
3. Open **Tools → Boards Manager**, choose **Refresh Indexes**, and wait for the background job to finish. Reopen the manager, choose **ESP32 by Espressif Systems**, select a version and click **Install Version**. The first ESP32 installation downloads several GB and can take several minutes. Arduino AVR boards are also available.
4. Use **Tools → Select Board** to search installed models and set their options. Match the actual module, flash size, partition layout and USB settings. Select **Tools → Select Port** and choose the connected USB device.
5. Add libraries using **Tools → Library Manager**. Search by function or name, read the description and supported architectures, choose a version and click **Install Library**. The official CLI installs required library dependencies automatically.
6. Reopen Library Manager and choose **Installed Libraries**. Select the library and click **Include Library** to insert its published headers into the active source file. Board-bundled libraries appear when a board is selected; remove their board platform to uninstall them. A library without published header names requires the include statement from its documentation.
7. **Save Project** saves all files and the board configuration. **Verify** saves a snapshot and compiles it. **Upload** saves and compiles, then asks before replacing the connected board's firmware. Build output shows progress, errors and memory usage.
8. Open **Tools → Serial Monitor**, choose the baud rate used by `Serial.begin(...)`, then click **Connect**. Send text with selectable line endings, clear the output or save it to a file. Opening the port may reset the board.

If an ESP32 does not automatically enter its bootloader, follow its manufacturer's BOOT/RESET sequence. Refresh ports after reconnecting a board. The selected USB port is deliberately not restored after reopening the application: verify the physical target before uploading.

## Menus and editing

- **File:** New/Open/Save/Save As, import/export, download the current file, add/rename/delete files, delete a project and close the window.
- **Edit:** Undo/Redo, Cut/Copy/Paste, Select All, Find and Replace. Clipboard actions require browser permission where applicable.
- **Sketch:** Verify, Upload and Stop Job. Stopping an upload may leave incomplete firmware; upload again before using the board.
- **Tools:** Board selection with board-specific options, USB port selection, Boards Manager, Library Manager, Serial Monitor and Manage Storage.
- **View:** Word Wrap, build log clear/download, toolbar visibility and window maximisation.
- **Help:** Usage instructions and About Pi-2000Web.

The editor uses local Ace assets, C/C++ syntax highlighting and file tabs. Ctrl+S saves, Ctrl+R verifies and Ctrl+U uploads. The main `.ino` file must match the project name. Use Save Project As to rename the project and main file together. Supporting `.ino`, `.h`, `.hpp`, `.c`, `.cpp`, `.S` and `.txt` files are supported at the sketch's top level.

Import accepts one exported project JSON, or an `.ino` file with its supporting files. Export Project downloads all current files and board settings, including unsaved changes, as a Pi-2000 JSON file. Download Current File exports the selected source file. Imported projects become new private projects; they do not overwrite existing ones.

Unsaved edits trigger a warning before project replacement, close, logoff or page navigation. There is no automatic recovery draft for Arduino edits. Concurrent saves use a project revision: a stale window cannot overwrite a newer saved project. Export its edits before reopening the saved version.

## Ownership and resource limits

Projects, installed packages and the latest job log belong to the authenticated account. Every user can edit and compile. USB upload and Serial Monitor require the Pi-2000 **admin** role; this grants neither root nor general OS administration. Serial devices must be USB-backed `/dev/ttyUSB*` or `/dev/ttyACM*` devices detected on the Pi. Network upload addresses and client-computer USB are not supported.

One CLI operation runs at a time across the Arduino service. Each account can hold one serial monitor; another account cannot take its open port. Upload closes the uploading account's monitor before compiling and flashing. Serial Monitor closes when its dialog closes, its login/permission ends or its viewer stops polling for 60 seconds. Only the selected device is exposed to the upload sandbox.

The `pi2000-arduino.service` worker has a separate systemd cgroup: MemoryHigh 1536 MiB, MemoryMax 2048 MiB, MemorySwapMax 128 MiB, CPUQuota 150% and TasksMax 128. CLI work runs in bubblewrap with private process/device namespaces, no host homes, installation, database, account sockets or other users' projects. Only index/package operations receive network access. Compilations use one compiler job and read a fixed source snapshot. A board package may execute its build tools inside that sandbox; arbitrary platform indexes and unsafe Git/ZIP library installations are disabled.

Use **Tools → Manage Storage → Clear Caches** to remove downloaded archives and cached builds while retaining installed packages and source projects.

Additional limits: 30 projects per account, 40 files and 2 MB source per project, 12 GB monitored package/cache storage per account, at least 1 GB free disk, 128 KB retained job output and 64 KB serial output. The disk check runs periodically; it is not a filesystem quota. CLI processes have CPU/address-space/file-descriptor/file-size limits. Index refresh, installation, compilation and upload have separate timeouts. The worker's cgroup is the aggregate memory limit in an installed system.

Jobs continue when the app window closes and can be inspected after reopening it. They stop when the initiating login expires or is revoked. Projects and the latest job output persist in SQLite. A worker restart marks an unfinished job **interrupted**; it never silently resumes flashing. Deleting an account removes its database rows and the running worker cleans up its package directory.

## Installation and backup

The source updater installs the checksum-pinned official **Arduino CLI 1.5.1 for Linux ARM64**, its license, pyserial 3.5 and the new worker. Run the normal `sudo ./scripts/update.sh`, followed by `sudo ./scripts/doctor.sh`, on the installation Pi. Source publication and the Debian package builder include the frontend, backend, CLI and service. A previously running Arduino worker is preserved by updates; restart it only after its active jobs have finished when deploying changed worker code. Existing SSH/Browser workers are not restarted by this feature.

CLI binaries live in `/opt/pi2000-arduino`. The worker's private Unix socket is `/run/pi2000-arduino/worker.sock`. Its OS account is `win2k-admin` with the supplementary `dialout` group; only the Arduino worker receives that additional group. The web API proxies authenticated requests and the worker independently validates them against the shared session database.

Project source, board configuration and the last job log are included in the normal SQLite backup. Downloaded board tools, libraries and caches in `arduino-runtime` are **not** included; reinstall their versions after restoring. Export project JSON separately when moving a sketch to another installation. No release tag or GitHub publication is required for local installation.

## Validation and current limits

Validated on the development Pi 5: real CLI 1.5.1, ESP32 core 3.3.11, ArduinoJson 7.4.3, successful isolated compilation and the native UI's Verify flow. Automated tests cover account isolation, source revision conflicts, path/argument rejection, job cancellation/errors, upload only after a successful compile, real serial read/write through a pseudo-terminal and sandbox filesystem boundaries. A separate user-service validation also exercised the API proxy, Unix worker and actual `memory.max=2147483648` cgroup with successful compilation (sampled memory use about 478 MiB), and retained projects/logs across worker restart. This validates the worker design in a disposable service; it is not evidence that the production unit has been installed. Physical USB flashing requires a connected board and is a separate hardware acceptance check.

This is a sketch development application, not full Arduino IDE parity: no hardware debugger, OTA flashing, custom platform URLs, ZIP/Git library import, nested sketch directories or serial plotter. It targets USB serial upload for ESP32 and AVR development boards. Other upload transports, devices that change USB identities during flashing and board-specific bootloader behaviour need separate validation.

References: [Arduino CLI integration](https://docs.arduino.cc/arduino-cli/integration-options/), [Arduino CLI releases](https://github.com/arduino/arduino-cli/releases), [Espressif Arduino installation](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html).
