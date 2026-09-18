# Personal Pi-Vault

Pi-Vault is a separate Pi-2000 application, available on the desktop and under
Start → Programs → System Tools → Pi-Vault. It is private to the signed-in account.
Pi-Vault is included in Alpha 6.

## Two independent unlock levels

Create your Pi-Vault with two different passphrases of at least 14 characters.
These are separate from your Pi-2000 login password.

- **Password A** unlocks titles, categories, creation dates and modification dates.
  Search and category filtering happen locally in the unlocked list.
- **Password B** unlocks one selected entry. Closing, switching or saving the entry
  ends that unlock. Reopening the same entry also requires B again. B is never
  remembered for the next entry.
- An open entry or private operation locks after **30 seconds of inactivity**.
  Typing and clicking inside Pi-Vault renew this period. The list locks after five
  minutes of inactivity. Hiding the browser tab, minimising Pi-Vault, closing Pi-Vault
  or logging out locks it. Leaving the browser window locks an open entry.
- Save edits before leaving. Closing or automatic locking discards unsaved edits;
  Pi-Vault deliberately does not send plaintext drafts to other editor/storage apps.

Each entry has a title, category (Password, API key, Text or Link), username, URL,
secret and notes. Content fields remain encrypted until B is entered. The main
secret is masked until Show Secret is selected. URLs are stored as text, without
previews, automatic network requests or automatic opening.

Copy Secret writes to the local system clipboard after content unlock. The browser
cannot guarantee removal from clipboard history or other applications. Generate
Password creates a cryptographically random 24-character password locally.

File → Export Encrypted downloads the complete encrypted Pi-Vault after B unlock.
Import Encrypted requires both passwords of the imported file, verifies every
entry and requires explicit replacement confirmation. Imports replace only the
current account's Pi-Vault. Export This Entry inside an unlocked entry is a separate,
explicitly confirmed **plaintext** download; protect or delete that file yourself.

Security → Change Passwords requires the current A and B and two new passphrases.
Both data keys are replaced and every entry is re-encrypted under a new Pi-Vault ID.
A new recovery key is generated. Old encrypted exports/backups still require their
old passwords or recovery key; a password change cannot revoke an existing copy.

## Recovery and backups

At creation and after password changes/recovery, save the displayed recovery key
outside the Pi. It can unlock both encryption levels and must be protected like a
master secret. Only its encrypted recovery envelope is stored on the server; the
readable recovery key is not uploaded. The display is temporary and hides on lock.
If you missed saving it, use your current A and B to change the Pi-Vault passwords
and generate a new recovery key.

Security → Recovery accepts your recovery key and new A/B passphrases. An
administrator cannot reset these Pi-Vault passwords to read old data. If you lose
both access to the necessary password(s) and the recovery key, their protected
content cannot be recovered through Pi-2000 administration.

The normal application SQLite backup includes the encrypted Pi-Vault records. An
account's storage quota includes its ciphertext. Deleting a Pi-2000 account deletes
its live Pi-Vault row through a foreign key; existing backups/exports retain copies.
A Pi-2000 login password reset does not change the Pi-Vault's encryption passwords.

## Security design and limits

`server/vault.py` exposes only the authenticated user's `/api/vault` and
`/api/vault/status`. Every query/write uses the authenticated numeric user ID;
there is no administrator bypass or route for selecting another account. The
`X-Vault-Owner` header detects a stale page after a cookie/account change; it does
not grant permission to choose an owner. Session validity is checked again after
reading write bodies. Revision checks reject stale writes. APIs disable caching.
A five-second status check locks a window when its session cannot be verified or
its saved Pi-Vault has changed elsewhere. A local logout/account-change event clears
it immediately; a BroadcastChannel also closes Pi-Vault windows in other tabs when
a Pi-2000 page announces a login/session change. The app keeps no plaintext in localStorage, sessionStorage,
workspace snapshots or server drafts.

Format 1 uses independently generated 256-bit keys for list metadata and content.
Each is wrapped under its corresponding password using Argon2id v1.3 (64 MiB,
three iterations, one lane, 16-byte random salt, 32-byte output) and AES-256-GCM.
AES-GCM uses a fresh 96-bit random IV, a 128-bit tag and authenticated context
binding the format, random Pi-Vault ID and purpose/entry ID. Password derivation runs
in a fresh Web Worker that is terminated after each operation. The pinned local
hash-wasm 4.12.0 Argon2 bundle and MIT license are included; there is no CDN fetch.
Web Crypto performs encryption using non-extractable working CryptoKeys. Parameters
and size bounds are validated before imported KDF work. No weaker fallback exists.

The random 256-bit recovery key wraps both underlying keys. Password changes
and recovery replace both data keys, salts and the Pi-Vault ID, authenticate every
old entry and re-encrypt the complete snapshot before a single revision-checked
write. Keys obtained from an older export cannot decrypt later rotated content.
A damaged entry aborts the operation without replacing the saved Pi-Vault. B provides the same authority over all entries, but the normal
client decrypts only the requested entry and releases its working content key when
that operation closes. This is two-level password unlocking, **not MFA**.

Content confidentiality depends on strong passphrases and a trusted client. A
stolen encrypted database permits offline password guessing. The server still
sees account ownership, ciphertext size, entry count, revisions and request timing.
An OS administrator controlling the server can replace delivered JavaScript; a
compromised browser/device or other malicious same-origin code can capture data
when unlocked. Use the Pi-Vault in your own trusted browser, not the Pi-hosted streamed
Browser if the Pi administrator is outside your trust boundary. A separate trusted
client is needed for stronger protection against a malicious server operator.
JavaScript/garbage collection cannot promise physical erasure of every memory copy.
Authenticated encryption detects tampering but does not prevent deletion or replay
of an entire older encrypted snapshot by a server operator.

This implementation has automated isolation/crypto/UI regression coverage, not an
independent cryptographic audit. Tests use disposable accounts and secrets. See
[TESTING.md](TESTING.md). Design references:
[hash-wasm](https://github.com/Daninet/hash-wasm),
[OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html),
[Web Crypto AES-GCM](https://developer.mozilla.org/en-US/docs/Web/API/AesGcmParams).
