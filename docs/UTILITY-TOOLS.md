# Network, display, archive, log and serial tools

These tools are included in Alpha 5 source and the arm64 test package. Follow the update procedure for your installation method; finish Arduino jobs and disconnect Serial Monitor before restarting the Arduino worker to activate worker changes.

All controls use the classic desktop window, toolbar and menus. Network targets and project/files belong to the signed-in account. A web administrator does not gain access to another user's files or SSH profiles.

## Network Tools

Open the desktop icon or Start → Programs → Internet and Connections → Network Tools. Enter a name, host/IP and TCP port, then Save Target. File → Import SSH Device copies a host and port from one of your own saved profiles.

Ping sends three ICMP requests. DNS Lookup resolves a name using the Pi's resolver. Check TCP Port opens and closes a TCP connection without sending application commands. These checks originate on the Pi, so they can diagnose a device which is accessible from the Pi's network. A failed ping can mean ICMP is blocked even when a TCP service works.

View → Start Monitoring checks up to 12 saved TCP targets every 15 seconds while the window stays open. Stop Monitoring stops the timer. Save Results downloads the latest 50 result blocks. Accounts can save up to 100 targets; tests have a 12-second overall timeout and a per-account concurrency limit. Multicast, unspecified and link-local targets are rejected. Source and Debian dependencies include `iputils-ping`.

## Display Studio

Open the desktop icon or Start → Programs → Development and Drawing → Display Studio. Display Settings chooses the screen size, background and optional round mask. Presets include a GC9A01A-style 240 × 240 round screen, 240 × 240 square, 128 × 64 and 240 × 320.

Use the Drawing tool list to draw rectangles, ellipses, lines, pencil strokes or text. Object also provides buttons through menus for new objects. Select / Move selects and drags a layer; the properties panel edits exact coordinates, dimensions, colors and text. The top layer in the list is drawn last. Edit duplicates/removes layers, and Object changes their order. Undo/Redo retains 20 edits. View controls the grid and actual-size preview.

Import Image embeds a PNG, JPEG or WebP, scaled to fit the screen. Save Display stores an editable `.display.json` in your private files; Save Display As makes a separate project. Existing saves detect conflicting edits. Unsaved changes prompt before closing or reloading.

File exports:

- **PNG:** the rendered screen, excluding the grid and selection outline.
- **RGB565:** two bytes per pixel, little-endian, left-to-right and top-to-bottom. The 240 × 240 export is 115,200 bytes.
- **Arduino Header:** a `const uint16_t[] PROGMEM` image with width/height constants, ready to include in a sketch using Adafruit GFX `drawRGBBitmap()` and the appropriate display driver.

The corners outside the round mask are black in all exports. The header contains rasterized text and images, so browser fonts are baked into pixels. It does not contain GPIO wiring, a display driver or a complete sketch. Choose those in Pi-Arduino's board/library managers.

Limits: 16–512 pixels per dimension, 100 layers, 500 points per pencil stroke and a 1 MB saved project. Imported images may be up to 10 MB and 4,096 × 4,096 pixels; large embedded images can reach the project limit. No executable project content or external image URLs are accepted.

## Archive Manager

Open the desktop icon or Start → Programs → Accessories → Archive Manager. Upload a ZIP to My Files, then Open Archive to inspect its names and sizes. Filter entries by path/name; select individual entries or Edit → Select All. Extract Selected chooses a private destination parent and a **new** folder. Selecting a folder includes its children. Open Destination opens the resulting folder in My Files.

Extraction preserves directory structure, checks the account quota and publishes the new folder only after all selected files have been read successfully. It does not overwrite existing files. Unsafe paths, symbolic links, encrypted archives, duplicate/colliding names and excessive expansion are rejected. Supported input: Store/Deflate ZIP, up to 50 MB archive and individual file, 100 MB expanded, 2,000 entries and 20 path levels. Expansion above 1 MB is limited to a 200:1 ratio.

File → Create Archive selects private files/folders and downloads a ZIP. Use Ctrl/Shift for multiple selection. Existing My Files ZIP limits apply: up to 100 selected roots, 1,000 total items and 50 MB. Other formats such as RAR, 7z and tar are not supported in this version.

## Log Viewer

Open the desktop icon or Start → Programs → System Tools → Log Viewer. Open Local Log reads a text file from My Files. Open SSH Log selects your SSH profile, password and remote path. Verify an unknown host fingerprint before accepting it; changed keys are rejected. Remote permissions are those of the SSH account. The password remains only in the open viewer's memory and is cleared when it closes.

The viewer reads the latest 256 KiB, omits a partial leading line where possible and displays up to 3,000 matching lines. It accepts UTF-8 text, replacing invalid byte sequences. Binary files containing NUL bytes are rejected. Filter text is a literal case-insensitive match; Level classifies common error, warning and informational words. Original timestamps stay unchanged and line numbers are relative to the loaded tail.

Start Following refreshes every five seconds while the window is open; Stop Following pauses it. Each refresh reopens the path, handling normal log rotation and truncation. Save Filtered Log downloads all matching lines in the loaded tail; Save Loaded Tail downloads that tail. This is not unrestricted access to the Pi's system journal: use a permitted SSH account for host logs.

## Serial Plotter

In Pi-Arduino choose Tools → Select Port, then Tools → Serial Plotter. Connect at the baud rate used by the sketch. Show Monitor and Show Plotter switch views of the same connection. Pi-connected USB serial access retains the existing administrator requirement and exclusive-port lock. Opening the serial port may reset the board.

Send one sample per newline, with up to eight numeric channels:

```cpp
void setup() { Serial.begin(115200); }
void loop() {
  Serial.print("temperature:"); Serial.print(23.5);
  Serial.print(" humidity:"); Serial.println(48.2);
  delay(100);
}
```

Unlabelled samples such as `23.5,48.2` become CH1/CH2; spaces, commas and semicolons are accepted separators. Decimal points and scientific notation are supported. Ordinary log messages are ignored. Partial incoming lines are assembled between polls, and buffer overruns discard an incomplete sample.

Choose automatic/fixed Y scale and 100, 500 or 2,000 visible samples; legend checkboxes hide individual curves. Pause Capture stops collecting plotted samples while the serial connection stays open. Clear Plot clears the retained values. Export CSV downloads up to 2,000 retained samples with sample number, receive time and channel values. Receive time is measured at the browser, not a hardware sampling timestamp. For precise timing include the device's own timestamp as another channel.

The plotter is verified with actual serial I/O through a disposable pseudo-terminal. A connected ESP32, its firmware and physical display still require hardware acceptance checks.
