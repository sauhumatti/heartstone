package ai.sakualy.cardgame.update;

import ai.sakualy.cardgame.BuildConfig;
import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;

/**
 * The Android side of updates: where the bundles and the few remembered values live on the phone,
 * and the hand-over to Capacitor, which can show the page from a folder instead of from the app's
 * own files (it reads the folder from its settings when it starts; a new app version clears it).
 *
 * The rules are in UpdateState and the network and file work in UpdateFiles; both are plain Java.
 */
public final class Updater {

    // Capacitor's own names (com.getcapacitor.plugin.WebView): the folder the page is served from.
    private static final String CAP_PREFS = "CapWebViewSettings";
    private static final String CAP_SERVER_PATH = "serverBasePath";
    private static final String PREFS = "AppUpdater";

    static final Object LOCK = new Object();
    private static UpdateState state;
    private static boolean startedThisProcess = false;
    private static String builtIn;

    private Updater() {}

    /** Updates are on only in an app built with a server address and a token. */
    public static boolean enabled() {
        return !BuildConfig.UPDATE_URL.isEmpty() && !BuildConfig.APP_TOKEN.isEmpty();
    }

    static UpdateState state(Context ctx) {
        synchronized (LOCK) {
            if (state == null) {
                final SharedPreferences prefs = ctx.getApplicationContext().getSharedPreferences(PREFS, Activity.MODE_PRIVATE);
                state = new UpdateState(
                    new UpdateState.Store() {
                        @Override
                        public String get(String key) {
                            return prefs.getString(key, "");
                        }

                        @Override
                        public void put(String key, String value) {
                            SharedPreferences.Editor e = prefs.edit();
                            if (value == null || value.isEmpty()) e.remove(key);
                            else e.putString(key, value);
                            e.commit(); // at once: the next thing to happen may be the app being closed
                        }
                    }
                );
            }
            return state;
        }
    }

    static File bundlesDir(Context ctx) {
        return new File(ctx.getFilesDir(), "bundles");
    }

    static File bundleDir(Context ctx, String version) {
        return new File(bundlesDir(ctx), version.replaceAll("[^0-9A-Za-z._-]", "_"));
    }

    static String shellId() {
        return BuildConfig.VERSION_CODE + "/" + BuildConfig.VERSION_NAME;
    }

    /**
     * Decide which bundle this start shows and tell Capacitor, before it loads the page. Must not
     * fail: whatever goes wrong here, the app opens with the bundle it was built with.
     */
    public static void beforePageLoads(Context ctx) {
        SharedPreferences cap = ctx.getSharedPreferences(CAP_PREFS, Activity.MODE_PRIVATE);
        try {
            String path = "";
            synchronized (LOCK) {
                UpdateState s = state(ctx);
                String active;
                if (!startedThisProcess) {
                    startedThisProcess = true;
                    active = s.onStart(shellId());
                    if (s.freshShell()) UpdateFiles.deleteTree(bundlesDir(ctx));
                } else {
                    active = s.applyPending(); // the page is being reloaded inside a running app
                }
                if (!active.isEmpty()) {
                    File dir = bundleDir(ctx, active);
                    if (new File(dir, "index.html").isFile()) path = dir.getAbsolutePath();
                    else s.dropActive();
                }
            }
            cap.edit().putString(CAP_SERVER_PATH, path).commit();
        } catch (Throwable t) {
            try {
                cap.edit().putString(CAP_SERVER_PATH, "").commit();
            } catch (Throwable ignored) {
                // nothing more can be done; Capacitor falls back to the built-in files if the folder is missing
            }
        }
    }

    /** Is a bundle being shown for the first time, still waiting for the page to report in? */
    public static boolean onTrial(Context ctx) {
        try {
            synchronized (LOCK) {
                return !state(ctx).trying().isEmpty();
            }
        } catch (Throwable t) {
            return false;
        }
    }

    /** The watchdog: the page never reported in. True if the app should now reload (with the earlier bundle). */
    public static boolean giveUpTrial(Context ctx) {
        try {
            synchronized (LOCK) {
                return state(ctx).giveUpTrial();
            }
        } catch (Throwable t) {
            return false;
        }
    }

    /** The version of the bundle built into the app (bundle.json beside its index.html). */
    static String builtIn(Context ctx) {
        if (builtIn == null) {
            String v = "";
            try (InputStream in = ctx.getAssets().open("public/bundle.json"); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[1024];
                int n;
                while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
                v = new JSONObject(out.toString(StandardCharsets.UTF_8.name())).optString("version", "");
            } catch (Exception e) {
                // an app built without one: every bundle on the server counts as newer
            }
            builtIn = v;
        }
        return builtIn;
    }

    /** The bundle on screen: a downloaded one, or the built-in one. */
    static String current(Context ctx) {
        String active = state(ctx).active();
        return active.isEmpty() ? builtIn(ctx) : active;
    }

    /** Delete downloaded bundles nothing refers to any more, and leftovers of interrupted work. */
    static void tidy(Context ctx) {
        java.util.List<String> keep;
        synchronized (LOCK) {
            keep = state(ctx).inUse();
        }
        File[] dirs = bundlesDir(ctx).listFiles();
        if (dirs != null) {
            for (File d : dirs) {
                boolean wanted = false;
                for (String v : keep) if (bundleDir(ctx, v).getName().equals(d.getName())) wanted = true;
                if (!wanted) UpdateFiles.deleteTree(d);
            }
        }
        File[] cached = ctx.getCacheDir().listFiles();
        if (cached != null) for (File f : cached) if (f.getName().startsWith("update-") && f.getName().endsWith(".zip")) f.delete();
    }

    /** { online, metered }: metered means a connection the player may be paying for by the megabyte. */
    static boolean[] network(Context ctx) {
        try {
            ConnectivityManager cm = (ConnectivityManager) ctx.getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo info = cm == null ? null : cm.getActiveNetworkInfo();
            boolean online = info != null && info.isConnected();
            return new boolean[] { online, cm == null || cm.isActiveNetworkMetered() };
        } catch (Throwable t) {
            return new boolean[] { true, true }; // unknown: try, but ask before a large download
        }
    }
}
