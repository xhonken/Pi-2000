# IPTV Player

Development after Alpha 5. Open the desktop icon or **Start → Programs →
Internet and Connections → IPTV Player**. The player uses your own sources;
Pi-2000 does not supply a subscription or bypass provider authentication/DRM.

## Add a private source

Choose **Add Playlist**, give it a name, and choose:

- **M3U / M3U8 URL:** paste the complete playlist address. Query credentials such
  as `username`/`password`, percent-encoded characters and HTTP Basic credentials
  in an HTTP(S) URL are supported. The field is masked and is not saved in desktop
  recovery data. `get.php` links offer automatic Xtream import; clear that option
  if the provider supplies M3U but does not implement the Xtream API.
- **Xtream server + login:** enter the server URL and separate IPTV username and
  password. Import includes live channels, films and series. Episodes load when
  opening a series. The Pi-2000 login and IPTV login are separate accounts.
- **M3U file:** select a UTF-8 M3U file up to 6 MB containing absolute HTTP(S) URLs.

**Use Free-TV Sample** fills the public
[Free-TV list](https://github.com/Free-TV/IPTV). It contains both direct streams
and entries pointing to websites; website entries cannot be decoded as media.
Some channels are offline, geo-restricted or otherwise unavailable from the Pi.
HTTP providers transmit their credentials without TLS even though the desktop
uses HTTPS. Prefer the provider's HTTPS endpoint when available.

Each Pi-2000 account has its own playlists, favorites and viewing positions.
Other accounts, including web administrators, cannot read them through this API.
Use **File → Refresh Playlist** to update the catalogue atomically; a failed
import retains the previous catalogue. **Rename Playlist** changes its label.
**Remove Playlist** deletes its entries, guide, favorites and history.

## Find and play

The library has **Live TV**, **Movies**, **Series**, **Favorites**, **Continue
Watching** and **All Media** views. Search names and filter by group or country.
M3U `group-title`, `EXTGRP`, `tvg-country` and `tvg-id` are read directly. Countries
are metadata supplied by the provider, not guessed from a channel's language.
M3U movie/series classification uses stream paths, extensions and category names;
an incorrectly labelled provider entry may appear under All Media instead.
Xtream supplies explicit media types and categories.

Select a row and choose **Play**, or double-click it. Open a series to browse
season/episode labels. **Favorite** toggles the selected entry. On-demand positions
are saved approximately every ten seconds and when pausing/stopping; seekable
files resume where possible. Playback does not start automatically after login,
page reload or server restart. The source/filter view and window layout recover.
There is no recording service or server-side playback checkpoint.

Native video controls provide pause, volume, seek and fullscreen. **Picture**
selects Fit, Fill or Stretch. HLS **Quality**, **Audio** and **Subtitles** show
tracks exposed by that manifest. Raw TS compatibility conversion selects the
first video/audio stream; it does not provide alternative audio or subtitles.
Use **Playback → Reconnect** after an interruption. Closing the app or stopping
ends playback; minimizing leaves it playing.

## Playback modes and limits

| Mode | Behaviour |
| --- | --- |
| Original quality | HLS.js for HLS, mpegts.js for direct MPEG-TS, and native media elements for MP4/WebM/audio. Preserves original encoding/quality; decodability depends on the client browser and OS. |
| Compatible audio (AAC) | Direct TS/file input through a network-isolated FFmpeg process. Video is copied; the first audio track becomes stereo AAC. Useful for AC-3 or another audio codec the browser cannot decode. |
| Compatible video + audio (720p) | Direct TS/file input converted to H.264/AAC, at most 1280×720, using two codec threads. Helps with unsupported video codecs, at a CPU/quality cost. |

One compatibility converter runs at a time on the Pi and does not overlap a
catalogue import. HLS uses the browser playback path; compatibility conversion
does not currently support HLS input. Conversion takes a non-seekable input pipe:
some file containers, notably MP4 with its index at the end, cannot convert this
way. Original mode supports provider byte ranges for seekable media. A TS stream
or conversion does not guarantee seeking/resuming like an indexed MP4 file.
Provider connection limits, internet bandwidth, unsupported codecs, DRM, expired
subscriptions and geo-blocking remain outside the player's control. This is not
complete VLC format/protocol coverage. UDP, RTSP, filesystem URLs and local/LAN
provider addresses are intentionally unsupported.

## Programme guide and TV archive

Select a live channel and choose **Load Guide**. Xtream requests programme data
for that channel. For M3U, use **File → Programme Guide** to select a playlist's
XMLTV feed or enter a custom `.xml`/`.xml.gz` URL. Choose a country-specific feed
instead of an enormous all-country feed. A guide import replaces that source's
current XMLTV guide, and channel IDs must match the playlist's `tvg-id`.

**Watch Archive** appears for completed programmes within the provider's declared
archive window. Xtream timeshift uses the provider's timezone; M3U supports
`catchup-source` templates with UTC/start/end/duration and date placeholders,
including append templates. Merely having programme data does not create an
archive: the provider must supply and authorize that service. Proprietary catchup
formats, missing historical guide rows and unsupported templates are reported.

## Security and operator details

Source URLs, credentials and stream URLs are encrypted using the server's existing
credential key. Browser media links contain random resource IDs bound to the
current login and playlist revision, not provider URLs. They are not shareable
public links. Lists, guide operations and saved settings also carry an account
header to prevent a stale window writing into a newly signed-in account. Stream
reads periodically revalidate login state; expiry/disconnect checks are bounded
by the upstream read timeout. Refresh/removal invalidates that source's players.

Every network hop resolves and pins public IP addresses. Redirects, child HLS
manifests, segments and encryption keys pass through the same checks. Local,
private, link-local, metadata and platform addresses are rejected. No upstream
cookies or arbitrary response headers are relayed. Provider URLs and upstream
error bodies are excluded from user-visible errors. HLS URL variables/content
steering are currently rejected rather than bypassing the gateway.

The converter sees read-only system binaries, a private temporary directory and
stdin/stdout pipes. It has no network, provider URL, user homes or Pi-2000 state.
Decoder protocols are restricted to pipes; process address space, threads and
runtime are bounded. It is stopped on disconnect or revoked playback. Keep the
OS FFmpeg and browser security updates current.

Imports: eight sources/account, 50,000 M3U entries/source, 500,000 Xtream entries/
source and 600,000 total entries/account, with 512 MB per encrypted staged
catalogue. Xtream arrays are streamed with ijson; source imports are serialized.
The UI displays 200 rows/page, at most 2,000 group filter choices and 256 country
choices. Catalogue metadata uses separately bounded service storage rather than
the My Files quota. XMLTV is limited to 24 MB expanded and 50,000 programmes.
Playback allows three players/account, twelve overall, and bounded simultaneous
media downloads. Paused/inactive handles expire after two minutes without reads;
reconnect if necessary. All stored catalogue data participates in the existing
database backup and account deletion cascade. Media content is streamed, not
recorded or cached to disk.

Server-key encryption does not protect against OS root/service compromise or a
malicious application update. The operator and administrative login-reset trust
boundaries in [SECURITY.md](SECURITY.md) still apply.

Local browser bundles: [HLS.js](https://github.com/video-dev/hls.js) 1.7.3 (Apache
2.0) and [mpegts.js](https://github.com/xqq/mpegts.js) 1.8.2 (Apache 2.0), with
their upstream licenses beside the bundled files. No runtime CDN is used.
The source/package installers include FFmpeg and pinned ijson 3.5.1.

## Verification

`test_iptv.py` exercises parsing, private account boundaries, encrypted credentials,
atomic failed refresh, favorites/history, HLS URI rewriting, login-bound playback,
DNS/private redirects, XML entity/decompression rejection, streaming catalogue
parsing, series/guide/timeshift construction and real sandboxed FFmpeg conversion.
`iptv_ui.cjs` uses generated H.264/AAC test media and a disposable provider to check
decoded HLS/TS/MP4 audio/video, compatibility playback, controls, private URLs,
episodes/archive, recovery, keyboard-accessible menus and narrow 18 px layouts.
Real-provider catalogues and installed HTTPS checks are separate acceptance;
fixtures do not establish that every external channel or codec works.
