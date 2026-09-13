# Pi++

Pi++ is Pi-2000Web's text and source editor, inspired by the familiar Notepad++ layout. It replaces the Code Editor presentation while keeping your existing files, workspace tabs, SFTP profiles and recovery drafts. Open **Pi++** on the desktop or **Start → Programs → Development and Drawing → Pi++**.

## Working with documents

Use **File → Open** to filter your private files by name or folder. The **Folder Workspace** panel also opens files and selects the destination for new files. Click the selected folder again to collapse or expand it. **File → Import from Computer** reads one or more UTF-8 files into unsaved tabs. Use **Save** or **Save As** to put them in My Files or Desktop. **Download** exports the active tab's current text, including unsaved edits.

The tab strip and **Document List** select open documents. An orange tab edge and dot identify unsaved changes; a green edge identifies the active saved tab. Navigate a focused tab strip with Left/Right or Home/End. **Window** lists every document, switches tabs and closes the active, other or all documents. Closing a changed tab asks before discarding it. Closing the application preserves changed documents as private recovery drafts.

**Save All** saves changed tabs in order. A new file opens Save As; cancelling stops the sequence. A file conflict or connection failure also stops the sequence, preserving unsaved text. Files saved before that point remain saved. SFTP tabs save to their named remote device; local tabs save to your private Pi-2000 files.

## Editing and searching

- **Edit:** Undo/redo, clipboard, indentation, line comments, duplicate line/selection, upper/lower case and trailing-space removal. Trailing-space removal applies to selected text or the whole document when nothing is selected. Text changes can be undone.
- **Search:** Find and Replace use the editor's search bar, including case, whole-word and regular-expression options. Find in Open Documents searches the current text of all tabs, including unsaved edits, and displays up to 500 matching lines. Click a result to select its text; rerun the search if the document has changed.
- **Bookmarks:** Toggle a bookmark on the current line, then navigate forwards or backwards. Bookmarks follow inserted/deleted text while the tab is open. They are not saved across application restarts.
- **Language:** Choose a common syntax mode directly or filter the complete language list. This changes highlighting, not the file extension. Reopening a saved file detects its mode from the file name.
- **Encoding:** Files use UTF-8; an existing UTF-8 BOM is preserved. Convert the active tab's line endings to Unix LF or Windows CR LF, then save. Other character encodings need conversion before opening. Mixed line endings are normalized by the editor.
- **Code → Check Syntax:** Check Python, JavaScript or JSON without running the program. File extensions determine the checker. This is separate from Arduino Workshop's compile/upload workflow.

## View and preferences

**View** toggles the document panel, toolbar, line numbers, whitespace and word wrap, folds/unfolds code, changes the theme and adjusts zoom. The sidebar can be resized by its lower corner. The status bar shows language, document length, line count, cursor, selected character count, line endings, UTF-8, insert/overwrite mode and saved state.

**Settings → Preferences** saves appearance, completion and indentation defaults privately to your account. Existing characters and line endings are not converted by changing the indentation default. Quick View/Settings menu choices affect the current editor; use Save Preferences to retain them after reopening. The code font honours a larger desktop text-size setting.

| Shortcut | Action |
| --- | --- |
| Ctrl+N / Ctrl+O | New document / Open private file |
| Ctrl+S / Ctrl+Shift+S | Save / Save As |
| Ctrl+Alt+S | Save All |
| Ctrl+F / Ctrl+H | Find / Replace |
| F3 / Shift+F3 | Find next / previous |
| Ctrl+Shift+F | Find in Open Documents |
| Ctrl+G | Go to Line |
| Ctrl+F2 | Toggle bookmark |
| F2 / Shift+F2 | Next / previous bookmark |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous document |
| F10 | Focus application menus |

Editor shortcuts apply while the editor has focus; the browser may reserve some key combinations. Every action is available graphically in the menus.

## Privacy, remote files and limits

Files, preferences and recovery drafts remain account-scoped on the server. Drafts count toward storage quota and do not replace explicit saves. Existing file-version checks prevent overwriting a newer copy. If a save conflicts, preserve your changes with Save As or inspect the other version.

**Connection → SFTP – Open Device** opens one of your own SSH profiles. Verify its host key and enter its password. Tabs marked **[SFTP]** save to that device. **Open Device Version** opens the remote copy separately; **Save Copy on Device** creates a new remote file. Credentials are held only for the current editor session and are not put in recovery drafts. See [Help](HELP.md#pi-and-sftp) for the general file-transfer workflow.

Pi++ supports UTF-8 text up to **1 MB per file** and **100 tabs**. It is an independent web application, not a port of Notepad++; Windows plugins, macros, arbitrary character-encoding conversion and split editing are not implemented.
