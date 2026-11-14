# Android app (Capacitor)

Status: planning, nothing built. Goal: an Android app with easier notifications for followed subjects, with external
links opening in the phone's default browser.

## Why a second push path

The site already has web push: `site.js` subscribes, the Worker's `/push` keeps subscriptions in KV, and `ci/push.py`
sends after each deploy. An Android WebView has no Web Push, so a Capacitor app needs native push through Firebase
Cloud Messaging (FCM) next to it.

## Design

1. **Shell loads the live site.** `capacitor.config` sets `server.url` to `https://masinci.org`, so there is
   no bundled copy to go stale after a deploy. Capacitor gives that page its native bridge, so `site.js` uses the
   global `Capacitor.Plugins` (no npm build in `pages/`). The project lives in `app/` (package.json, capacitor.config,
   generated `android/`). The back button goes back through history by default.

2. **Notifications (FCM).**
   - `site.js`: when `Capacitor.isNativePlatform()`, the existing switch uses `PushNotifications.requestPermissions()`
     and `register()` instead of `PushManager`, and sends `{fcm: token, s: [...]}` to `/push` through the same
     debounced `save`/`resave`. A listener for notification taps opens the notification's `url` in the app.
   - Worker (`pages/src/index.js`): `/push` also accepts an FCM token, stored under the key `fcm:<token>` with the
     subjects, validated like the endpoints are now.
   - `ci/push.py`: `fcm:` subscriptions go out through the FCM HTTP v1 API with a service account (new dependency
     `google-auth`, new repo secret). A token FCM reports as unregistered is dropped, as 404/410 are now. `message()`
     and the grouping by subject stay as they are.
   - Once, by hand: a Firebase project, `google-services.json` in `app/android/app/`, and the service account JSON as a
     GitHub secret.

3. **External links: always the phone's browser app, never inside the app** (the user's requirement: a link that
   opens in the app makes it feel half-done). Not left to Capacitor's defaults: in the app, `site.js` catches every
   click on a link to another host (`target=_blank` too) and hands it to `AppLauncher.openUrl` (`@capacitor/app-launcher`),
   an Android intent to the default browser. No "leaving the site" dialog in the app. Not `@capacitor/browser`: that
   is a Custom Tab, inside the app. Downloads too: the WebView does not download by itself, so `/files/` (mail and
   Teams attachments) and the faculty site's PDFs also go to the browser. Check on a phone: a link in a post, a
   PDF attachment, a `/files/` download, the faculty site's links in /link/.

4. **Icons and build.** The manifest only has `favicon.svg`; `@capacitor/assets` makes the Android icons from one
   1024px PNG. Current Capacitor (7/8) needs JDK 21 (installed: 17; for builds on this PC, the phone check and
   testing). Release builds run on GitHub (decision 4).

## Effort

About a day with a phone plugged in, roughly 100 lines of code; most of the time goes to setup and testing on the
device.

| Part | New code | Difficulty |
|---|---|---|
| Capacitor project loading the live site | ~20 lines of config, generated `android/` | Easy |
| `site.js`: native push alongside web push | ~30 lines | Easy |
| Worker: accept FCM tokens | ~10 lines | Easy |
| `push.py`: send through FCM v1 | ~30 lines + `google-auth` | Medium (OAuth token, error codes) |
| External links and downloads to the browser app | ~15 lines in `site.js` + `@capacitor/app-launcher` | Easy; check on a phone |
| `app.yml`: build, sign, publish on a tag | ~40 lines of workflow | Medium (first run is the test) |
| JDK 21, Firebase, secrets, icons, signing key | none | Tedious |

Risks:
- Capacitor might not give its bridge to the remote site (extra config).
- A navigation `site.js` does not see (a redirect, a form) could still open another host in the WebView; Capacitor
  hands those to an intent by default, to confirm on the phone.
- Google Play's 14-day closed test, if the app goes there.

## Ruled out (2026-11-14)

- **TWA (Bubblewrap):** the current web push would work unchanged, but outside links open in a Custom Tab, inside
  the app. That is the half-done feel the user does not want.
- **Tauri 2:** no official push plugin on Android (community ones only), a remote site needs its own permission
  config, and Rust + NDK is a heavier setup. Its gain, desktop apps from the same project, is not wanted: a desktop
  browser already has the site's web push.

## Open decisions

1. ~~Capacitor or TWA~~: Capacitor (above).
2. ~~Distribution~~: an APK in a GitHub release, installed by hand (decided 2026-11-14). Not Google Play ($25, 12
   testers for 14 days on a new personal account, possible rejection as a website wrapper). The app loads the live
   site, so only a change to the native shell needs a new APK.
3. ~~App ID~~: `com.valjdakosta.nastava` (decided 2026-11-14; fixed once installed).
4. ~~Build~~: GitHub Actions builds, signs and publishes it (decided 2026-11-14). A new workflow `app.yml`, started
   by pushing a tag `app-v<version>`: JDK 21 and the runner's Android SDK, `npm ci` and `npx cap sync` in `app/`,
   `gradlew assembleRelease`, signed with the release key, the APK uploaded to the tag's release with `gh`.
   - The release key: made once on the user's PC (`keytool`), stored as repo secrets (the keystore as base64, its
     passwords). The user keeps a backup outside the repo: with the key lost, an update can't install over the old
     app, everyone has to uninstall first.
   - `google-services.json` (Firebase's client config, not a secret) is committed in `app/android/app/`.
   - The version: `versionCode` from the run number, `versionName` from the tag.

All decided: next is the phone check below, then the build.

## Check first

On a phone, before any `site.js` work: does Capacitor 8 give the bridge (`Capacitor.Plugins`) to a remote
`server.url` without extra settings? The link catching above depends on it.
