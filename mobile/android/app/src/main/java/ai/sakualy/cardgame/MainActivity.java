package ai.sakualy.cardgame;

import ai.sakualy.cardgame.update.Updater;
import ai.sakualy.cardgame.update.UpdaterPlugin;
import android.app.AlertDialog;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.WebViewListener;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;

/**
 * The whole app is one full-screen page (the web build of the game, served from the app's own files).
 * This adds what a page cannot do for itself: staying full screen, drawing around a camera cutout,
 * keeping the screen on during a match, a back button that behaves, and updates (see the update package:
 * a newer version of the page is downloaded into the app's storage and shown from there).
 */
public class MainActivity extends BridgeActivity {

    /** How long a newly downloaded version of the page has to report that it started. */
    private static final long TRIAL_MS = 30_000;

    private String shim = "";
    private final Handler handler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(UpdaterPlugin.class);
        // Which version of the page to show is settled before Capacitor loads it.
        Updater.beforePageLoads(this);
        super.onCreate(savedInstanceState);
        if (getBridge() == null) return; // no WebView on this device; Capacitor shows its own notice

        // A new version that never reports in is dropped, and the page reloads with the one before it.
        if (Updater.onTrial(this)) {
            handler.postDelayed(
                () -> {
                    if (!isFinishing() && !isDestroyed() && Updater.giveUpTrial(this)) recreate();
                },
                TRIAL_MS
            );
        }

        drawAroundCutout();
        hideSystemBars();

        shim = readAsset("app-shim.js");
        WebView webView = getBridge().getWebView();
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.addJavascriptInterface(new AppHost(), "AndroidApp");
        getBridge().addWebViewListener(
            new WebViewListener() {
                @Override
                public void onPageLoaded(WebView view) {
                    view.evaluateJavascript(shim, null);
                }
            }
        );

        getOnBackPressedDispatcher().addCallback(
            this,
            new OnBackPressedCallback(true) {
                @Override
                public void handleOnBackPressed() {
                    askPageThenLeave();
                }
            }
        );
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        // The bars come back after a dialog or a visit to another app.
        if (hasFocus) hideSystemBars();
    }

    /** Full screen; a swipe from the edge shows the bars for a moment. */
    private void hideSystemBars() {
        WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(getWindow(), getWindow().getDecorView());
        bars.setSystemBarsBehavior(WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);
        bars.hide(WindowInsetsCompat.Type.systemBars());
    }

    /** Use the strip beside a camera cutout too; the page keeps its controls clear of it (safe-area insets). */
    private void drawAroundCutout() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) return;
        WindowManager.LayoutParams params = getWindow().getAttributes();
        params.layoutInDisplayCutoutMode = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R
            ? WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS
            : WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        getWindow().setAttributes(params);
    }

    /** The page gets the back button first (window.onAppBack); if it has no use for it, ask before leaving. */
    private void askPageThenLeave() {
        getBridge()
            .getWebView()
            .evaluateJavascript(
                "(function(){try{return !!(window.onAppBack&&window.onAppBack())}catch(e){return false}})()",
                handled -> {
                    if (!"true".equals(handled)) confirmLeave();
                }
            );
    }

    private void confirmLeave() {
        if (isFinishing()) return;
        new AlertDialog.Builder(this)
            .setTitle(R.string.leave_question)
            .setMessage(R.string.leave_detail)
            .setPositiveButton(R.string.leave_yes, (dialog, which) -> finish())
            .setNegativeButton(R.string.leave_no, null)
            .show();
    }

    private String readAsset(String name) {
        try (InputStream in = getAssets().open(name); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int n;
            while ((n = in.read(buffer)) > 0) out.write(buffer, 0, n);
            return out.toString(StandardCharsets.UTF_8.name());
        } catch (Exception e) {
            return "";
        }
    }

    /** What the page can ask of the app: window.AndroidApp. */
    private class AppHost {

        /** Keep the screen from dimming and locking (during a match). */
        @JavascriptInterface
        public void keepAwake(final boolean on) {
            runOnUiThread(() -> {
                if (on) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            });
        }

        /** The app's version, e.g. "0.1.0". */
        @JavascriptInterface
        public String version() {
            return BuildConfig.VERSION_NAME;
        }
    }
}
