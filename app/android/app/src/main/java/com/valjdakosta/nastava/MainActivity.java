package com.valjdakosta.nastava;

import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Display;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.widget.FrameLayout;
import androidx.core.splashscreen.SplashScreen;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;
import com.getcapacitor.WebViewListener;

public class MainActivity extends BridgeActivity {

    // The logo drawing on (LogoView) plays here, not in the system splash: Android 17 (Nothing Phone 4a) shows a
    // splash icon still, and an animated vector couldn't do the site's masks. The system splash is the blue under it.
    private static final long LOGO_MS = LogoView.MS, MAX_MS = 8000;
    private boolean shown = false;
    private FrameLayout logo;
    private long logoStart;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        SplashScreen.installSplashScreen(this).setOnExitAnimationListener(splash -> {
            splash.remove();
            showLogo();
        });
        registerPlugin(NotifySettings.class);
        registerPlugin(AppUpdate.class);
        super.onCreate(savedInstanceState);
        getBridge().addWebViewListener(new WebViewListener() {
            @Override
            public void onPageCommitVisible(WebView view, String url) {
                shown = true;
                hideLogo();
            }
        });
        fullRefreshRate();
        // No overscroll stretch: Android stretches the whole WebView, the site's sticky header and tab bar with it.
        getBridge().getWebView().setOverScrollMode(View.OVER_SCROLL_NEVER);
        // The offline page (errorPath) for no connection only: Capacitor also shows it for an HTTP error, where the
        // site's own 404 page says more.
        getBridge().setWebViewClient(new BridgeWebViewClient(getBridge()) {
            @Override
            public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {}

            // As Capacitor's (no listener here wants the error), but the offline page is told which page failed
            // (?u=): its "Pokušaj ponovo" loads that one, not the page before it.
            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                String page = getBridge().getErrorUrl();
                if (page != null && request.isForMainFrame()) {
                    view.loadUrl(page + "?u=" + Uri.encode(request.getUrl().toString()));
                }
            }
        });
    }

    /** The screen's fastest mode (120 Hz on the Nothing Phone 4a, which otherwise gives the app 90): the site's
     *  animations (the day and night switch) are smoother. Same resolution only; Android may still lower it (battery
     *  saver, heat). */
    private void fullRefreshRate() {
        Display display = getWindowManager().getDefaultDisplay();
        Display.Mode best = display.getMode();
        for (Display.Mode m : display.getSupportedModes()) {
            if (m.getPhysicalWidth() == best.getPhysicalWidth() && m.getPhysicalHeight() == best.getPhysicalHeight()
                    && m.getRefreshRate() > best.getRefreshRate()) best = m;
        }
        WindowManager.LayoutParams params = getWindow().getAttributes();
        params.preferredDisplayModeId = best.getModeId();
        getWindow().setAttributes(params);
    }

    /** The blue screen with the logo drawing on, where the system splash's icon was (288 dp, centred). */
    private void showLogo() {
        logo = new FrameLayout(this);
        logo.setBackgroundColor(0xFF0076B1);
        LogoView icon = new LogoView(this);
        int px = Math.round(288 * getResources().getDisplayMetrics().density);
        logo.addView(icon, new FrameLayout.LayoutParams(px, px, Gravity.CENTER));
        ((ViewGroup) getWindow().getDecorView()).addView(logo, new ViewGroup.LayoutParams(-1, -1));
        icon.start();
        logoStart = SystemClock.uptimeMillis();
        logo.postDelayed(this::hideLogo, LOGO_MS);
        logo.postDelayed(() -> {
            shown = true;
            hideLogo();
        }, MAX_MS);
    }

    /** Fades the logo screen out once the logo has drawn on and the page shows (or after 8 s with no page). */
    private void hideLogo() {
        if (logo == null || !shown || SystemClock.uptimeMillis() - logoStart < LOGO_MS) return;
        View gone = logo;
        logo = null;
        gone.animate().alpha(0).setDuration(250).withEndAction(() -> ((ViewGroup) gone.getParent()).removeView(gone));
    }
}
