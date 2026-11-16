# Android app (Capacitor)

Status (2026-11-16): all steps written, committed and checked on the phone (LAN builds, over adb); waiting on the
deploy (Worker and site) and the first `app-v` tag, which test step 6's `app.yml` and the real chain. Step 0 passed
(the bridge on the live site). Step 1: icons, notification icon, the logo splash (`LogoView`), the header clear of
the status bar, the offline page (the site's look, a sky and a meadow). Steps 4 and 5: the Worker keeps `fcm:`
tokens, `push.py` sends through FCM (tests pass). Steps 2, 3 and 7 in `site.js`. Phone checks passed: a PDF, .docx
and faculty PDF open in Moon Reader, an .xlsx offers Sheets, a .rar a chooser (Total Commander takes any file, so
no type is left without an app here), an outside link goes to Firefox, a Drive link to Drive, mailto: to Gmail; no
"Skini aplikaciju" in the app, it and its ⓘ show in Firefox; a notification from the dev server (`/push/test`,
through `push.py`) arrives with the icon and colour, and its tap opens its page in the app; refused notifications
open the steps with "Otvori podešavanja" (the app's own settings page), and allowing them there un-greys the bell
on return. The content-only stretch seen working (header and tab bar still), its feel to tune. Found on the way:
the dev server redirected `/files/` from http to https, which Android's downloader doesn't follow (it fetches them
now, and `site.js` never opens an empty download); Capacitor's offline page showed on a 404 (`MainActivity`). Builds use the JDK 21
in `C:\Users\Kosta\.jdks\jdk-21.0.12.1+1` (`JAVA_HOME` for `gradlew`). Goal: an Android app with easier notifications for followed
subjects, with external links opening in the phone's default browser.

## Why a second push path

The site already has web push: `site.js` subscribes, the Worker's `/push` keeps subscriptions in KV, and `ci/push.py`
sends after each deploy. An Android WebView has no Web Push (no `PushManager`: today the app would show the switch
greyed, "Ovaj browser ne može da prima obaveštenja"), so a Capacitor app needs native push through Firebase Cloud
Messaging (FCM) next to it.

## What is on this PC

- Android SDK in `C:\Android\sdk` (platforms 34, 36, 37; build-tools up to 37; `adb`): enough, nothing to install.
- Node 25: fine for the Capacitor CLI.
- JDK 17: Capacitor 7/8 needs **JDK 21**. Install it (Temurin 21) next to 17 and point `JAVA_HOME` at it for builds.
- Icons: `pages/icons.py` already renders `static/app-icon.svg` to PNGs (180/192/512 and the badge). The app's 1024 px
  source comes from the same script (step 1).

## Steps

Each step ends in something checkable; the order is the order of the risks.

### 0. Phone check (before any site change)

The one unknown the rest stands on: does Capacitor 8 give its bridge (`window.Capacitor`, `Capacitor.Plugins`) to a
remote `server.url`?

1. `app/` with `npm init`, `@capacitor/core`, `@capacitor/cli`, `@capacitor/android`, `@capacitor/app-launcher`,
   `@capacitor/push-notifications`, `@capacitor/file-transfer` with `@capacitor/filesystem` (the cache path),
   `@capawesome-team/capacitor-file-opener` (pinned versions, `package-lock.json` committed; all checked for
   Capacitor 8 on 2026-11-16).
2. `app/capacitor.config.json`:
   ```json
   {"appId": "com.valjdakosta.nastava", "appName": "Mašinci", "webDir": "www",
    "server": {"url": "https://masinci.org", "errorPath": "offline.html"},
    "android": {"appendUserAgent": "NastavaApp"}}
   ```
   `webDir` (`app/www/`) holds only `offline.html`: what the WebView shows with no network, instead of Chrome's error
   page (one Serbian line, "Nema interneta", and a retry link to `https://masinci.org/`).
3. `npx cap add android`, `npx cap sync`, `npx cap run android` with the phone on USB. The user's phone won't
   connect over USB (2026-11-16): the APK goes over by hand (Desktop → phone), and `adb` reaches the phone through
   Android's Wireless debugging (`adb pair`, then `adb connect`, same Wi-Fi), which chrome://inspect sees as well.
   Neither (the phone is the PC's VPN, the user won't connect it): checks on the phone are test builds that say
   what they find in a toast (the bridge check: `native`, `AppLauncher`, `PushNotifications`, `FileOpener` on each
   page), never committed.
4. On the phone, in `chrome://inspect` on the PC: `Capacitor.isNativePlatform()` is `true` and
   `Capacitor.Plugins.AppLauncher` exists on a masinci.org page, also after following a link to another page.

**Passed 2026-11-16**: on the live masinci.org, `native`, `AppLauncher`, `PushNotifications` and `FileOpener` all
there (Nothing Phone 4a, Android 17). The bridge after a link is seen again in step 2's checks.

If the bridge is not there: try `server.allowNavigation: ["masinci.org"]`; if still not, stop and rethink (back to
this plan, not onward).

### 1. Shell, icons, back button

- `pages/icons.py`: one more output, `app/assets/icon.png` at 1024 px (and `icon-foreground.png`, the logo alone on
  clear, for Android's adaptive icon; background `#0076b1`). `npx @capacitor/assets generate --android` makes
  `res/mipmap-*` from them. The generated icons are committed; `icons.py` is run again only when the logo changes.
- Notification icon: Android shows the small icon as a white silhouette. `static/badge.png` (white logo on clear) is
  that already: copied as `android/app/src/main/res/drawable/ic_notify.png`, named in `AndroidManifest.xml` as
  `com.google.firebase.messaging.default_notification_icon`, with `default_notification_color` `#0076b1`.
- Splash (decided 2026-11-16): the header logo draws on as on the site (ring → line → diagonal → M, 1.65 s, same
  easing, the gaps opening as the crossing line arrives). The system splash is the blue (`#0076b1`) alone: Android 17
  on the user's phone (Nothing Phone 4a) showed its icon still, and an animated vector drawable, tried first, showed
  the gaps from the start and chipped the M. So `LogoView` draws it in code as the browser does (each line on a
  layer, the crossing lines' cut strokes cleared out of it, the site's paths, widths, `--len`s and timings), and
  `MainActivity` shows it over the same blue until it has drawn on and the page shows (at most 8 s), then fades it.
- The page under the status bar (found on the phone): the site's `viewport-fit=cover` makes Capacitor 8 draw it
  edge to edge, so `style.css`'s header adds `env(safe-area-inset-top)` (0 in a browser). Android's overscroll stretch
  pulled the sticky header and tab bar: off in `MainActivity` (`OVER_SCROLL_NEVER`).
- The offline page (found on the phone): Capacitor 8 loads `errorPath` on any HTTP error too
  (`BridgeWebViewClient.onReceivedHttpError`), so a dead link said "Nema interneta". `MainActivity` replaces the
  client with one that ignores HTTP errors: a 404 shows the site's own page, no connection still the offline page.
- Content-only stretch (decided 2026-11-16; after the step 0 gate, it is `site.js`): in the app only, a pull past the
  top or bottom stretches the content between the header and the tab bar (`scaleY`, damped by the pull, anchored at
  the pulled edge) and springs back on release; the header and tab bar stay still. ~30 lines, tuned on the phone
  against Android's own stretch; `prefers-reduced-motion` gets none.
- Back button: Capacitor's default goes back in the WebView's history and closes the app at the first page. Check
  with an open dialog (the leave dialog, the notifications dialog): if back leaves the page instead of closing the
  dialog, `site.js` listens to `App.addListener('backButton')` and closes the open `dialog` first (`@capacitor/app`).
  Only if the phone shows the problem.

### 2. Links to the browser, attachments to the phone's apps (site.js)

Today (`site.js:1094`): a link to another host opens the "Napuštate arhivu" dialog, then a new tab; a same-host PDF
opens in a new tab. In the app, `site.js` adds one branch at the top of that handler, with two outcomes:

- **An attachment** (a PDF, Word, Excel, PowerPoint, zip/rar, DWG…, by the path's extension; or anything under
  `/files/`, the mail and Teams attachments; on any host, so the faculty site's PDFs too): opens in the phone's app
  for that file (a PDF reader, Word, Excel…), not the browser. A `http` URL handed to Android goes to the browser, so
  the file is first downloaded natively into the app's cache, then opened from there with an "open with" intent:
  - `@capacitor/file-transfer` `downloadFile` (native, so no CORS on the faculty's hosts) into `Directory.Cache` (no
    storage permission, Android clears it when space runs low);
  - `@capawesome-team/capacitor-file-opener` `openFile({path})`: the intent with the file's MIME type, through a
    FileProvider (`content://` URI) the plugin brings. Android picks the default app, or asks once which.
  - While it downloads: the link gets `aria-busy` and the side message "Preuzimam…"; a big file takes a moment.
  - No app for that type, or the download fails: falls back to the browser (`AppLauncher.openUrl`), which can still
    save it.
- **Any other link to another host**: `AppLauncher.openUrl({url})`, an intent to the default browser. No "Napuštate
  arhivu" dialog in the app: the browser opening is the leaving itself. Not `@capacitor/browser` (a Custom Tab,
  inside the app).

```js
var app = window.Capacitor && Capacitor.isNativePlatform();
var FILE = /\.(pdf|docx?|xlsx?|pptx?|odt|ods|zip|rar|7z|dwg|dxf|step|stp|txt)$/i;
...
if (app && (FILE.test(a.pathname) || a.pathname.indexOf('/files/') === 0)) { e.preventDefault(); openFile(a); return; }
if (app && out) { e.preventDefault(); Capacitor.Plugins.AppLauncher.openUrl({ url: a.href }); return; }
```

`openFile` (~20 lines): the file name from the URL's last part (a `/files/` name is already safe; others go through
the same cleaning), download, open, fall back. A second tap on the same file while it is cached opens it at once.

Check on the phone: a PDF attachment, a `.docx` and an `.xlsx` from `/files/`, a faculty PDF from /link/, a type with
no app installed (falls back to the browser), a link in a post, the footer's drive link (`data-domain`), a `mailto:`
(should open the mail app: Capacitor hands non-http schemes to an intent; confirm).

### 3. Native push in site.js

The notifications block (`site.js:953`) gets a native branch **before** the `PushManager` test, sharing `save`'s
shape, the queue, the debounced `resave` on `moji`, and `showPush`/`said`:

- `current()`: the FCM token, from `PushNotifications.register()` and its `registration` event, kept in
  `localStorage('fcm')`; `null` when permission is not `granted`.
- `save(token, list)`: posts `{fcm: token, s, t}` to `/push`, same body cache (`localStorage('push')`) so an unchanged
  list is not written again.
- The switch "on": `PushNotifications.requestPermissions()` (Android 13+ asks; older grants at once), then
  `register()`, then `save`. "Off": `save(token, [])` then `unregister()`.
- Each app start: `register()` again when permission is granted; a new token (FCM rotates them) is saved under its own
  key, and the old one is dropped when FCM later says it is gone (step 5).
- On by itself (decided 2026-11-16): in the app, choosing the first subject with posts turns the bell on (the
  permission asked) unless the reader turned it off before (`push-off` in localStorage). Not in a browser: Chrome
  asks only right after a tap on its own switch, and blocks sites that ask unprompted.
- Denied: a new `pushSteps` kind `'app'`: "Settings na telefonu → Apps → Mašinci → Notifications → uključi", then
  "Vrati se ovde i uključi prekidač". The RSS part of the dialog stays.
- A tap on a notification: `pushNotificationActionPerformed` gives the message's `data.url`; `location.href = url`
  when it is on masinci.org (the same rule as `sw.js`'s click, which opens it).
- With the app in front, Android shows no FCM notification (`pushNotificationReceived` fires instead): left so. The
  reader is in the app already; the home page lists the new posts. (shortcut, upgrade with
  `@capacitor/local-notifications` if readers miss them.)

### 4. Worker (pages/src/index.js)

- `/push` accepts `{fcm, s, t}` beside `{endpoint, keys, s, t}`: `fcm` checked with `/^[A-Za-z0-9_:-]{100,300}$/`
  (FCM tokens: ~150–180 characters of that set), stored at the key `fcm:<token>` as `{s, t}` (no `k`/`a`). `s` and
  `t` validated as now; `s = []` deletes it.
- `/push/subs` unchanged: it lists every key, so `fcm:` entries come out with `endpoint: "fcm:…"`.
- D1's `push_subs` counts them too (the key is the "endpoint"): /statistika/'s number becomes browsers and phones.
  No schema change.
- `test/worker_test.mjs`: a valid FCM body is stored under `fcm:`, a bad token is 400, `s: []` deletes.

### 5. Sending (ci/push.py)

- `fcm-secret.json` (git-ignored, like `push-secret.json`): the Firebase service account's JSON. `sync.yml` writes it
  from a new repo secret `FCM_SECRET`, as it does `PUSH_SECRET`; without it, `fcm:` subscriptions are skipped (counted
  as skipped in the log), web push goes on.
- In `send()`'s loop: an `endpoint` starting with `fcm:` goes to `fcm(token, message(posts))` instead of `webpush`:
  ```
  POST https://fcm.googleapis.com/v1/projects/<project_id>/messages:send
  {"message": {"token": …, "notification": {"title": …, "body": …}, "data": {"url": …},
               "android": {"ttl": "86400s"}}}
  ```
  The bearer token from `google.oauth2.service_account.Credentials` (scope
  `https://www.googleapis.com/auth/firebase.messaging`), made once per run. New dependency `google-auth` in the
  script header.
- Gone: a 404 with `UNREGISTERED` (or 400 `INVALID_ARGUMENT` on the token) drops it, posting `{fcm: token, s: []}` to
  `/push`, as 404/410 drop a browser's. Other errors count as `failed`, as now.
- `message()`, `wanted()` and the grouping by subject stay as they are: the same notification text in both paths.
- `test/push_test.py`: the `fcm:` branch with `requests` mocked: the body's shape, a gone token posts the drop, a
  failure counts.

### 6. Build and release (GitHub Actions)

`.github/workflows/app.yml`, on a pushed tag `app-v*`:

1. `actions/setup-java` (Temurin 21), `actions/setup-node`; the runner's Android SDK.
2. In `app/`: `npm ci`, `npx cap sync android`.
3. One secret `APP_SIGNING`, `{"keystore": <base64>, "password": …}` (as `PUSH_SECRET` is one JSON): `jq` writes
   the keystore to a file; `./gradlew assembleRelease` with `-Pandroid.injected.signing.*`, the alias `nastava` in
   the workflow, the password for both store and key (PKCS12 has one). No signing config in the repo.
4. The site's version (/verzije/, decided 2026-11-16): `versionName` = `0.<commit count>` of the tagged commit,
   `versionCode` = the count (always growing), from a full-history checkout; passed to `build.gradle` as `-P`
   properties. The tag's name only starts the build (`app-v0.<count>` by habit).
5. The APK renamed `masinci.apk` and uploaded to the fixed release `app` with `--clobber` (step 7; permission
   `contents: write`). The first run creates that release.

`google-services.json` (Firebase's client config, not a secret) is committed in `app/android/app/`. The generated
`android/` is committed whole (Capacitor's advice: it is the app's native source), minus `build/` and
`local.properties` (`.gitignore`).

### 7. "Skini aplikaciju" on the site

In the side panel's Obaveštenja group (`sidebar.html`), under the "Prikaži moje predmete" switch: a button
**Skini aplikaciju** with an info button (ⓘ) beside it.

- Shown only in an Android browser (`site.js`'s `android`, and not in the app itself): `hidden` in the template,
  `site.js` shows it. iPhone and desktop never see it.
- The button links to the APK at a fixed URL:
  `https://github.com/KostaJovanovic/nastava/releases/download/app/masinci.apk`. So `app.yml` (step 6) uploads to one
  fixed release `app` (`gh release upload app masinci.apk --clobber`), not a release per tag: `releases/latest`
  could be the `mail` release. The `app-v*` tag still starts the build and sets the version.
- The ⓘ opens a dialog like the notifications one (`.leave`), its text settled 2026-11-16: "Browser na telefonu
  ponekad propusti obaveštenja: Android ga uspava kad ga ne koristiš, pa stignu kasno ili ne uopšte. Aplikacija nema
  taj problem." Then the install steps (open masinci.apk, allow installs from the browser, Install), and a line that
  the phone may warn about an app from outside Google Play. The file is `masinci.apk`: the site is Mašinci now (the
  repo, the package ID and the signing key's alias keep "nastava", unseen by readers).
- Notifications blocked for the app: "Uređaj ne dozvoljava notifikacije od ove aplikacije." with a button that opens
  the app's notification settings (a small plugin in `MainActivity`; Capacitor has none), and the four steps kept.
- `style.css`: the button and ⓘ in the group's existing button style (`.moji__open .btn`); check the phone's grid
  and the narrow (<360 px) layout, where the group already hides words.

### 8. By hand, once (the user)

- Firebase project (free), an Android app in it with ID `com.valjdakosta.nastava` → `google-services.json`.
- Firebase → Project settings → Service accounts → a new key → `FCM_SECRET` (repo secret) and `fcm-secret.json`
  locally for tests.
- `keytool -genkeypair -v -keystore nastava.jks -storetype PKCS12 -alias nastava -keyalg RSA -keysize 2048
  -validity 10000 -dname "CN=Masinci"`; the keystore's base64 and the password as the one secret `APP_SIGNING`
  above (GitHub's web page: Settings → Secrets and variables → Actions). **Done 2026-11-16**: `APP_SIGNING` is set,
  the keystore and its password are in the user's KeePass.
- Firebase project `masinci-28d17` made (2026-11-16); its `google-services.json` waits in the user's Downloads,
  to be copied into `app/android/app/` in step 0. The service account key is the repo secret `FCM_SECRET` and in
  KeePass (2026-11-16). Firebase's Gradle lines are not needed: Capacitor's generated project applies the plugin. **Backup outside the repo**: a lost key means no update
  installs over the old app.
- JDK 21 on this PC.

### 9. Offline (planning, 2026-11-16; no code until agreed)

What the app keeps (decided): every professor, katedra and subject page, kalendar and rasporedi (pages and their
PDFs), the last 7 days of nastava (posts and topics) and vesti, and the files of the last 7 days' posts in the
reader's followed subjects only. Measured on the last build (2026-11-16): pages about 10 MB gzipped (57 MB raw),
schedule PDFs 7.2 MB, the site's CSS/JS/fonts 3.4 MB; the 7 days' files 18 MB across all subjects, so a few MB for
one reader's subjects. Professor photos 13.3 MB (open question).

Facts that shape it: every request goes through the Worker (100,000 a day on the free plan), so the app can't fetch
some 2,500 pages one by one per reader per day; the build already writes pages as fragments that the Worker joins
into `shell.html` (`index.js` `join`); `sw.js` has only push.

Two kinds of page (found 2026-11-16): `/predmeti/<slug>/` is a subject's description (ESPB, exam, katedra; ~9 KB,
changes rarely), `/predmet/<smer>/<slug>/` its thread list (every thread it ever had: Matematika 1's is 1.2 MB),
which changes with each post, for ~18 subjects a week (25 in 30 days) of 949.

The draft (decided 2026-11-16: the APK base, and the user's picks 1, 2, 4, 5, 6, 7 of the optimisations):
- **The base, downloaded once** (changed 2026-11-16, see below): every subject description, professor, katedra
  and the lists, and every thread page cut to its newest 50 threads (5), as one `/offline/base-<build>.json.gz`
  (~10 MB), fetched on the app's first opening and again only when the copy is older than 14 days. Nothing new in
  the APK.
- **Daily, one request**: the build writes `/offline/changed-<build>.json.gz`, the fragments of every page that
  changed in the last 14 days (1), with the last 7 days of nastava and vesti and the shell, and
  `/offline/version.json` (the build's id, the changed pack's name, a full pack's for an app older than 14 days).
  Cached at Cloudflare's edge like any page.
- **When the app opens** (7), at most once a day: site.js reads `version.json`; only if the site changed does the
  service worker fetch the pack. Notifications don't depend on it (FCM reaches the phone either way); only the
  offline copy waits for the next opening.
- **Stored gzipped** (2), unpacked when a page is shown (`DecompressionStream`).
- **Schedules**: only the reader's smer's PDFs, the smer known from the followed subjects (4). The rasporedi page
  is checked for updates at each refresh; a schedule already downloaded is kept, and only a new or changed one is
  fetched.
- **Files**: the last 7 days' posts' files in the followed subjects, each up to 5 MB (a bigger one opens online),
  each downloaded once, into the service worker's cache, so an offline tap gets it there: a PDF in the site's own
  viewer (PLAN-pdf.md); other types need the bridge, which offline pages lack (below), so they open online only (6).
- **Online is always live**: `sw.js` answers from the copy only when the network fails, joining shell and fragment
  as the Worker does (`join` shared). Browsers never get a pack, so for them nothing changes.
- Offline and not in the copy (an older post, the search, which is Pagefind's 99 MB): the offline page.

Expected: the APK unchanged, ~10 MB once at the first opening, a daily download of a few hundred KB, 15–20 MB on
the phone.

How it is served (decided 2026-11-16, replacing "in the APK"): a service worker can't read the APK's own files, and
the native alternative needs a Capacitor internal, so the user chose the service worker with the base downloaded.
`sw.js` is registered in the app too. Online, its fetch goes through Capacitor (`resolveServiceWorkerRequests`,
on by default), which still adds the app's bridge to each page; **first check on the phone, before the rest: online
pages keep the bridge (files to apps, links to the browser, the bell) while the service worker is in control.**
Offline, a page from the copy has no bridge: the site works as in a browser (no file opens in a phone app, an
outside link fails as offline). Not in the copy: the service worker returns an error, and Capacitor shows
`offline.html` as now.

Photos (decided 2026-11-16): the site serves every teacher photo at most 300 px wide (JPEG 85, 4:2:2; the
originals stay in `nastava.db`), 13.3 MB → 9.9 MB, and the build writes a 150 px copy of each at
`/foto/mala/<name>.jpg` (3.8 MB for all; `load_teachers.fit_photo`). The APK ships the 300 px photo for teachers on
the faculty's current list, the 150 px copy for the rest (former, emeriti, the past).

Settled 2026-11-16: the refresh runs on any network (mobile data too). A page shown from the copy gets a slim line
under the header, offline only: "Bez interneta · sačuvano 16. 11. u 19:17" (the copy's time). An unfollowed
subject's saved files stay until they age out of the 7 days, like any other; refollowing costs nothing. Only the
prefetched files age out; a file the reader tapped stays in the app's cache as now.

## Effort

About a day with a phone plugged in. New code roughly 150 lines plus the workflow.

| Step | New code | Difficulty |
|---|---|---|
| 0. Phone check | config + `offline.html` | Easy, decides the rest |
| 1. Shell, icons | a few lines in `icons.py`, manifest meta | Easy |
| 2. Links to the browser, files to apps | ~35 lines in `site.js` | Medium; check each file type on a phone |
| 3. Native push in `site.js` | ~50 lines | Medium (token events, the queue) |
| 4. Worker | ~10 lines + tests | Easy |
| 5. `push.py` FCM | ~35 lines + `google-auth` + tests | Medium (OAuth, error codes) |
| 6. `app.yml` | ~45 lines | Medium (first run is the test) |
| 7. "Skini aplikaciju" | button + dialog, ~25 lines | Easy; layout check |
| 8. Firebase, key, secrets | none | Tedious |

Risks:
- Capacitor might not give its bridge to the remote site (step 0 finds out first).
- `server.url` is documented as a dev setting; it works in release builds, but a future Capacitor could warn on it.
- A navigation `site.js` does not see (a redirect, a form) could open another host in the WebView; Capacitor hands
  those to an intent by default, to confirm on the phone.
- An attachment link without an extension in its URL (a faculty download script, `?id=`) is not recognized as a file
  and goes to the browser. Fine at first; if it is common, ask the server for its `Content-Type` before choosing.
- The token's lifetime: an app unused for 270 days has its token expire; FCM says `UNREGISTERED`, it is dropped,
  the switch shows "off" on the next start (permission granted, but no saved token: `register()` again turns it back on
  by itself).

## Ruled out (2026-11-14)

- **TWA (Bubblewrap):** the current web push would work unchanged, but outside links open in a Custom Tab, inside
  the app. That is the half-done feel the user does not want.
- **Tauri 2:** no official push plugin on Android (community ones only), a remote site needs its own permission
  config, and Rust + NDK is a heavier setup. Its gain, desktop apps from the same project, is not wanted: a desktop
  browser already has the site's web push.

## Decisions

1. Capacitor, not TWA (above).
2. Distribution: an APK in a GitHub release, installed by hand (2026-11-14). Not Google Play ($25, 12 testers for 14
   days on a new personal account, possible rejection as a website wrapper). The app loads the live site, so only a
   change to the native shell needs a new APK.
3. App ID: `com.valjdakosta.nastava` (2026-11-14; fixed once installed).
4. Build: GitHub Actions on an `app-v*` tag (2026-11-14, step 6).

5. Finding the APK: a "Skini aplikaciju" button with an ⓘ under "Prikaži moje predmete", Android browsers only
   (2026-11-16, step 7).
6. Attachments in the app open in the phone's apps (PDF reader, Word…), not the browser (2026-11-16, step 2).

7. The app's name under the icon: **Mašinci** (2026-11-16; `appName` in step 0, and "Apps → Mašinci" in the denied
   steps of step 3). The web manifest's "Nastava" stays as it is. The long name, **Mašinci - Mašinski fakultet, na
   jednom mestu**, is the release's title (`app.yml`), as a store listing's; Android itself says "Mašinci" everywhere.

All decided: next is step 0, the phone check.
