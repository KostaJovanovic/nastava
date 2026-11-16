# Android app (Capacitor)

Status: planned in full (2026-11-16), nothing built. Goal: an Android app with easier notifications for followed
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
   `@capacitor/push-notifications`, `@capacitor/file-transfer`, `@capawesome/capacitor-file-opener` (pinned
   versions, `package-lock.json` committed).
2. `app/capacitor.config.json`:
   ```json
   {"appId": "com.valjdakosta.nastava", "appName": "Mašinci", "webDir": "www",
    "server": {"url": "https://masinci.org", "errorPath": "offline.html"},
    "android": {"appendUserAgent": "NastavaApp"}}
   ```
   `webDir` (`app/www/`) holds only `offline.html`: what the WebView shows with no network, instead of Chrome's error
   page (one Serbian line, "Nema interneta", and a retry link to `https://masinci.org/`).
3. `npx cap add android`, `npx cap sync`, `npx cap run android` with the phone on USB.
4. On the phone, in `chrome://inspect` on the PC: `Capacitor.isNativePlatform()` is `true` and
   `Capacitor.Plugins.AppLauncher` exists on a masinci.org page, also after following a link to another page.

If the bridge is not there: try `server.allowNavigation: ["masinci.org"]`; if still not, stop and rethink (back to
this plan, not onward).

### 1. Shell, icons, back button

- `pages/icons.py`: one more output, `app/assets/icon.png` at 1024 px (and `icon-foreground.png`, the logo alone on
  clear, for Android's adaptive icon; background `#0076b1`). `npx @capacitor/assets generate --android` makes
  `res/mipmap-*` from them. The generated icons are committed; `icons.py` is run again only when the logo changes.
- Notification icon: Android shows the small icon as a white silhouette. `static/badge.png` (white logo on clear) is
  that already: copied as `android/app/src/main/res/drawable/ic_notify.png`, named in `AndroidManifest.xml` as
  `com.google.firebase.messaging.default_notification_icon`, with `default_notification_color` `#0076b1`.
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
  - `@capawesome/capacitor-file-opener` `openFile({path})`: the intent with the file's MIME type, through a
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
4. `versionCode` = `github.run_number`, `versionName` = the tag without `app-v` (passed to `build.gradle` as
   `-P` properties).
5. The APK renamed `nastava.apk` and uploaded to the fixed release `app` with `--clobber` (step 7; permission
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
  `https://github.com/KostaJovanovic/nastava/releases/download/app/nastava.apk`. So `app.yml` (step 6) uploads to one
  fixed release `app` (`gh release upload app nastava.apk --clobber`), not a release per tag: `releases/latest`
  could be the `mail` release. The `app-v*` tag still starts the build and sets the version.
- The ⓘ opens a dialog like the notifications one (`.leave`), text to settle when building, roughly:
  "Browser na telefonu ponekad propusti obaveštenja: Android ga uspava kad ga ne koristiš, pa stignu kasno ili
  nikako. Aplikacija ih prima preko telefona, kao Viber ili Gmail, i otvara sajt kao i sada." Then the install
  steps: "Otvori preuzeti fajl → dozvoli instalaciju iz browsera kad telefon pita → Install." And a line that the
  phone may warn about an app from outside Google Play.
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
   steps of step 3). The web manifest's "Nastava" stays as it is.

All decided: next is step 0, the phone check.
