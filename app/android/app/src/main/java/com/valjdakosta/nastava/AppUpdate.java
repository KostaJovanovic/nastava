package com.valjdakosta.nastava;

import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.os.Build;
import androidx.core.content.IntentCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.json.JSONArray;
import org.json.JSONObject;

/**
 * Updates of the APK (docs/PLAN-app.md step 10), after mbrd's MbrdUpdate, smaller. At most once a day, when the app
 * opens (load), one request to GitHub's API for the release "app" (.github/workflows/app.yml): its masinci.apk
 * carries the version as its label (0.N) and GitHub's SHA-256 as its digest. A newer one is kept in the prefs; the
 * site (site.js) asks available() and shows "Skini noviju verziju", whose tap is install(): download, check (the
 * digest, our package, a higher versionCode), then Android's PackageInstaller, which asks the user (and the first
 * time, to allow Mašinci to install apps). Android itself refuses an APK signed with another key.
 */
@CapacitorPlugin(name = "AppUpdate")
public class AppUpdate extends Plugin {

    private static final String PREFS = "update";
    private static final long DAY_MS = 24L * 60 * 60 * 1000;
    private static final int FEED_MAX = 256 * 1024;
    private static final Pattern DIGEST = Pattern.compile("^sha256:([0-9a-f]{64})$");
    private static final ExecutorService NET = Executors.newSingleThreadExecutor();
    private Future<?> checking;
    private volatile boolean busy;

    @Override
    public void load() {
        checking = NET.submit(this::check);
    }

    /** The day's check. Offline or a bad answer: nothing kept, the next opening tries again. */
    private void check() {
        SharedPreferences prefs = prefs();
        if (System.currentTimeMillis() - prefs.getLong("checked", 0) < DAY_MS) return;
        try {
            JSONObject release = new JSONObject(get(BuildConfig.UPDATE_FEED));
            JSONArray assets = release.optJSONArray("assets");
            JSONObject apk = null;
            for (int i = 0; assets != null && i < assets.length(); i++) {
                JSONObject a = assets.optJSONObject(i);
                if (a != null && "masinci.apk".equals(a.optString("name"))) apk = a;
            }
            SharedPreferences.Editor e = prefs.edit().putLong("checked", System.currentTimeMillis()).remove("version");
            if (apk != null && newer(apk.optString("label"), installedName())) {
                e.putString("version", apk.optString("label"))
                    .putString("url", apk.optString("browser_download_url"))
                    .putString("digest", apk.optString("digest"));
            }
            e.apply();
        } catch (Exception ignored) {}
    }

    /** {version} when a newer APK is out, else {}; waits for a check still running. */
    @PluginMethod
    public void available(PluginCall call) {
        NET.execute(() -> {
            try {
                if (checking != null) checking.get();
            } catch (Exception ignored) {}
            JSObject r = new JSObject();
            String v = prefs().getString("version", null);
            if (v != null && newer(v, installedName())) r.put("version", v);
            call.resolve(r);
        });
    }

    /** Downloads, checks and installs the newer APK; "progress" events ({percent}) while it downloads. Resolves when
     *  Android has it (its own screen follows), rejects on a failure. */
    @PluginMethod
    public void install(PluginCall call) {
        SharedPreferences prefs = prefs();
        String url = prefs.getString("url", "");
        Matcher digest = DIGEST.matcher(prefs.getString("digest", ""));
        if (busy || !digest.matches()) {
            call.reject("no update");
            return;
        }
        busy = true;
        Context app = getContext().getApplicationContext();
        new Thread(() -> {
            File file = new File(new File(app.getCacheDir(), "update"), "masinci.apk");
            try {
                save(url, file, digest.group(1));
                verify(app, file);
                write(app, file);
                call.resolve();
            } catch (Exception e) {
                call.reject(e.getMessage());
            } finally {
                file.delete(); // the session holds its own copy once written
                busy = false;
            }
        }).start();
    }

    private SharedPreferences prefs() {
        return getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private String installedName() {
        try {
            String v = getContext().getPackageManager().getPackageInfo(getContext().getPackageName(), 0).versionName;
            return v == null ? "" : v;
        } catch (PackageManager.NameNotFoundException e) {
            return "";
        }
    }

    /** True when version a is newer than b, number by number: "0.730" over "0.723". A part that is not a number
     *  (an empty label, the local build's "dev") counts as -1. */
    static boolean newer(String a, String b) {
        String[] x = a.split("\\."), y = b.split("\\.");
        for (int i = 0; i < Math.max(x.length, y.length); i++) {
            int p = i < x.length ? number(x[i]) : 0, q = i < y.length ? number(y[i]) : 0;
            if (p != q) return p > q;
        }
        return false;
    }

    private static int number(String s) {
        try {
            return Integer.parseInt(s.trim());
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    private static HttpURLConnection open(String url) throws IOException {
        URL u = new URL(url);
        // The local build may test against the dev server (http through adb reverse); a release only over https.
        if (!"https".equals(u.getProtocol()) && !BuildConfig.DEBUG) throw new IOException("not https");
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setInstanceFollowRedirects(true); // github.com sends a download on to its asset host
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setRequestProperty("User-Agent", "Masinci-Android");
        c.setRequestProperty("Accept", "application/vnd.github+json");
        if (c.getResponseCode() != HttpURLConnection.HTTP_OK) {
            c.disconnect();
            throw new IOException("HTTP " + c.getResponseCode());
        }
        return c;
    }

    private static String get(String url) throws IOException {
        HttpURLConnection c = open(url);
        try (InputStream in = c.getInputStream()) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                if (out.size() + n > FEED_MAX) throw new IOException("reply too large");
                out.write(buf, 0, n);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        } finally {
            c.disconnect();
        }
    }

    /** Streams the APK to file, hashing as it goes, telling the page each whole percent. */
    private void save(String url, File file, String sha) throws Exception {
        File dir = file.getParentFile();
        if (dir != null && !dir.isDirectory() && !dir.mkdirs()) throw new IOException("no cache folder");
        HttpURLConnection c = open(url);
        try (InputStream in = c.getInputStream(); OutputStream out = new FileOutputStream(file)) {
            long total = c.getContentLengthLong(), got = 0;
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] buf = new byte[1 << 16];
            int n, told = -1;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
                md.update(buf, 0, n);
                got += n;
                int pct = total > 0 ? (int) (got * 100 / total) : 0;
                if (pct != told) {
                    told = pct;
                    JSObject p = new JSObject();
                    p.put("percent", pct);
                    notifyListeners("progress", p);
                }
            }
            StringBuilder hex = new StringBuilder();
            for (byte b : md.digest()) hex.append(String.format(Locale.ROOT, "%02x", b));
            if (!hex.toString().equals(sha)) throw new IOException("checksum");
        } finally {
            c.disconnect();
        }
    }

    /** Ours, and newer than the installed copy. */
    private static void verify(Context app, File file) throws IOException {
        PackageManager pm = app.getPackageManager();
        PackageInfo p = pm.getPackageArchiveInfo(file.getPath(), 0);
        if (p == null || !app.getPackageName().equals(p.packageName)) throw new IOException("not our package");
        try {
            if (code(p) <= code(pm.getPackageInfo(app.getPackageName(), 0))) throw new IOException("not newer");
        } catch (PackageManager.NameNotFoundException e) {
            throw new IOException("no installed copy");
        }
    }

    @SuppressWarnings("deprecation")
    private static long code(PackageInfo p) {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.P ? p.getLongVersionCode() : p.versionCode;
    }

    /** Writes the APK into a PackageInstaller session and commits it; Android answers in Status. */
    private static void write(Context app, File file) throws IOException {
        PackageInstaller installer = app.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams params = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        params.setAppPackageName(app.getPackageName());
        params.setSize(file.length());
        int id = installer.createSession(params);
        try (PackageInstaller.Session session = installer.openSession(id)) {
            try (InputStream in = new FileInputStream(file); OutputStream out = session.openWrite("masinci.apk", 0, file.length())) {
                byte[] buf = new byte[1 << 16];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                session.fsync(out);
            }
            int flags = PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ? PendingIntent.FLAG_MUTABLE : 0);
            session.commit(PendingIntent.getBroadcast(app, id, new Intent(app, Status.class), flags).getIntentSender());
        } catch (IOException | RuntimeException e) {
            installer.abandonSession(id);
            throw e;
        }
    }

    /** Android's answer on the session (manifest, not exported). Wanting a yes, it hands over its own screen (and,
     *  the first time, the one to allow Mašinci to install apps): the app is on screen, so it opens it. On success
     *  Android replaces the app; a no on its screen needs nothing. */
    public static final class Status extends BroadcastReceiver {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE) != PackageInstaller.STATUS_PENDING_USER_ACTION) return;
            Intent confirm = IntentCompat.getParcelableExtra(intent, Intent.EXTRA_INTENT, Intent.class);
            if (confirm != null) context.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
        }
    }
}
