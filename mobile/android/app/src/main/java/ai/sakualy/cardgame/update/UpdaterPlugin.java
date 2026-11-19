package ai.sakualy.cardgame.update;

import ai.sakualy.cardgame.BuildConfig;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/**
 * What the page can ask about updates (as the Capacitor plugin "AppUpdater"):
 *
 *   info()       what is installed and shown, and the state of the connection
 *   check()      ask the server; the answer says whether a newer bundle or a newer app exists
 *   download()   fetch the newest bundle, verify it, unpack it, choose it for the next start; answers
 *                { pending: its version } (sends "progress" events: { received, total })
 *   cancel()     stop a download
 *   ready()      the page started properly: keep the bundle on trial
 *   restart()    reload the page now, with the pending bundle
 *   openShell()  open the newer app's download link in the phone's browser
 *
 * The page never names an address: every request goes to the server this app was built for.
 * Failures are rejected with a code (offline, refused, server, checksum, size, archive, space,
 * cancelled, busy, disabled) and a sentence.
 */
@CapacitorPlugin(name = "AppUpdater")
public class UpdaterPlugin extends Plugin {

    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private final AtomicBoolean cancelled = new AtomicBoolean(false);

    private JSObject describe() {
        Context ctx = getContext();
        JSObject out = new JSObject();
        UpdateState s = Updater.state(ctx);
        JSObject shell = new JSObject();
        shell.put("versionCode", BuildConfig.VERSION_CODE);
        shell.put("versionName", BuildConfig.VERSION_NAME);
        out.put("enabled", Updater.enabled());
        out.put("shell", shell);
        JSArray failed = new JSArray();
        synchronized (Updater.LOCK) {
            out.put("bundle", Updater.current(ctx));
            out.put("builtIn", Updater.builtIn(ctx));
            out.put("pending", s.pending());
            out.put("rolledBack", s.rolledBack());
            for (String v : s.failed()) failed.put(v);
        }
        out.put("failed", failed);
        boolean[] net = Updater.network(ctx);
        out.put("online", net[0]);
        out.put("metered", net[1]);
        return out;
    }

    private JSONObject fetchManifest() throws Exception {
        String text = UpdateFiles.getText(BuildConfig.UPDATE_URL + "latest", BuildConfig.APP_TOKEN, 15_000);
        JSONObject m;
        try {
            m = new JSONObject(text);
        } catch (Exception e) {
            throw new UpdateFiles.Problem("server", "The update server's answer could not be read.");
        }
        return m;
    }

    private void fail(PluginCall call, Throwable t) {
        if (t instanceof UpdateFiles.Problem) call.reject(t.getMessage(), ((UpdateFiles.Problem) t).kind);
        else call.reject("The update did not work.", "server");
    }

    @PluginMethod
    public void info(PluginCall call) {
        try {
            call.resolve(describe());
        } catch (Throwable t) {
            fail(call, t);
        }
    }

    @PluginMethod
    public void check(final PluginCall call) {
        if (!Updater.enabled()) {
            call.reject("This app was built without updates.", "disabled");
            return;
        }
        worker.execute(() -> {
            try {
                JSONObject m = fetchManifest();
                JSObject out = describe();
                int installed = BuildConfig.VERSION_CODE;
                Context ctx = getContext();

                JSONObject b = m.optJSONObject("bundle");
                JSObject latest = new JSObject();
                if (b != null) {
                    String version = b.optString("version", "");
                    boolean failed, staged;
                    String current;
                    synchronized (Updater.LOCK) {
                        UpdateState s = Updater.state(ctx);
                        failed = s.failed().contains(version);
                        staged = version.equals(s.pending());
                        current = Updater.current(ctx);
                    }
                    latest.put("version", version);
                    latest.put("size", b.optLong("size", 0));
                    latest.put("newer", UpdateState.isNewer(version, current) && !failed);
                    latest.put("failedBefore", failed);
                    latest.put("runsHere", b.optInt("minShell", 1) <= installed);
                    latest.put("staged", staged);
                }
                out.put("latest", latest);

                JSONObject sh = m.optJSONObject("shell");
                JSObject latestShell = new JSObject();
                if (sh != null) {
                    latestShell.put("versionCode", sh.optInt("versionCode", 0));
                    latestShell.put("versionName", sh.optString("versionName", ""));
                    latestShell.put("size", sh.optLong("size", 0));
                    latestShell.put("newer", sh.optInt("versionCode", 0) > installed);
                }
                out.put("latestShell", latestShell);
                out.put("notes", m.optString("notes", ""));
                call.resolve(out);
            } catch (Throwable t) {
                fail(call, t);
            }
        });
    }

    @PluginMethod
    public void download(final PluginCall call) {
        if (!Updater.enabled()) {
            call.reject("This app was built without updates.", "disabled");
            return;
        }
        if (!busy.compareAndSet(false, true)) {
            call.reject("A download is already running.", "busy");
            return;
        }
        cancelled.set(false);
        worker.execute(() -> {
            File zip = null;
            try {
                Context ctx = getContext();
                // asked afresh: the server only hands out the bundle its manifest names right now
                JSONObject m = fetchManifest();
                JSONObject b = m.optJSONObject("bundle");
                if (b == null) throw new UpdateFiles.Problem("server", "The server has no update.");
                String version = b.optString("version", "");
                String url = b.optString("url", "");
                long size = b.optLong("size", 0);
                if (!version.matches("[0-9]{1,20}") || !url.matches("bundle/[0-9A-Za-z._-]+\\.zip")) {
                    throw new UpdateFiles.Problem("server", "The update server's answer could not be read.");
                }
                if (b.optInt("minShell", 1) > BuildConfig.VERSION_CODE) {
                    throw new UpdateFiles.Problem("server", "This update needs a newer app.");
                }
                synchronized (Updater.LOCK) {
                    UpdateState s = Updater.state(ctx);
                    if (version.equals(s.pending()) && new File(Updater.bundleDir(ctx, version), "index.html").isFile()) {
                        JSObject done = new JSObject();
                        done.put("pending", version);
                        call.resolve(done);
                        return;
                    }
                }
                // room for the archive and for what it unpacks to
                if (ctx.getFilesDir().getUsableSpace() < size * 4 + 20L * 1024 * 1024) {
                    throw new UpdateFiles.Problem("space", "There is not enough free space on the phone for the update.");
                }
                zip = new File(ctx.getCacheDir(), "update-" + version + ".zip");
                UpdateFiles.download(
                    BuildConfig.UPDATE_URL + url,
                    BuildConfig.APP_TOKEN,
                    zip,
                    size,
                    b.optString("sha256", ""),
                    (received, total) -> {
                        JSObject p = new JSObject();
                        p.put("received", received);
                        p.put("total", total);
                        notifyListeners("progress", p);
                    },
                    cancelled
                );
                File dir = Updater.bundleDir(ctx, version);
                Updater.bundlesDir(ctx).mkdirs();
                UpdateFiles.unzip(zip, dir);
                synchronized (Updater.LOCK) {
                    Updater.state(ctx).stage(version);
                }
                JSObject done = new JSObject();
                done.put("pending", version);
                call.resolve(done);
            } catch (Throwable t) {
                fail(call, t);
            } finally {
                if (zip != null) zip.delete();
                busy.set(false);
            }
        });
    }

    @PluginMethod
    public void cancel(PluginCall call) {
        cancelled.set(true);
        call.resolve();
    }

    @PluginMethod
    public void ready(PluginCall call) {
        try {
            synchronized (Updater.LOCK) {
                Updater.state(getContext()).confirm();
            }
            if (!busy.get()) worker.execute(() -> {
                try {
                    Updater.tidy(getContext());
                } catch (Throwable ignored) {
                    // old files stay a little longer
                }
            });
            call.resolve(describe());
        } catch (Throwable t) {
            fail(call, t);
        }
    }

    @PluginMethod
    public void restart(PluginCall call) {
        call.resolve();
        getActivity().runOnUiThread(() -> getActivity().recreate());
    }

    @PluginMethod
    public void openShell(final PluginCall call) {
        if (!Updater.enabled()) {
            call.reject("This app was built without updates.", "disabled");
            return;
        }
        worker.execute(() -> {
            try {
                // asked afresh: the link is signed and only good for a short while
                JSONObject sh = fetchManifest().optJSONObject("shell");
                String url = sh == null ? "" : sh.optString("url", "");
                if (!url.matches("shell/[0-9]+\\.apk\\?e=[0-9]+&s=[0-9a-f]+")) {
                    throw new UpdateFiles.Problem("server", "The server has no newer app.");
                }
                Intent view = new Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.UPDATE_URL + url));
                view.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                getContext().startActivity(view);
                call.resolve();
            } catch (android.content.ActivityNotFoundException e) {
                call.reject("No browser was found to download the new app with.", "server");
            } catch (Throwable t) {
                fail(call, t);
            }
        });
    }
}
