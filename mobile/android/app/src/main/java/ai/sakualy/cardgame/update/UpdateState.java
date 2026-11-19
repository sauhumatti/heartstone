package ai.sakualy.cardgame.update;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Which web bundle the app shows: the one built into it, or one it downloaded.
 *
 * A downloaded bundle is first "pending": chosen for the next start. At that start it becomes the
 * one shown and is "on trial" until the page reports that it started. If the app is started again
 * (or the watchdog runs out) while a bundle is still on trial, that bundle is given up for good and
 * the app goes back to what it showed before. Installing a new app (a new shell) wipes all of it,
 * so a new app always starts from its own built-in bundle.
 *
 * Plain Java on purpose: no Android in here, so the rules can be run and tested on any machine.
 */
public final class UpdateState {

    /** Where the few values are kept (on the phone: SharedPreferences, written at once). */
    public interface Store {
        String get(String key);

        /** A null or empty value removes the key. */
        void put(String key, String value);
    }

    private static final int MAX_FAILED = 12;

    private final Store store;
    private String rolledBack = "";
    private boolean freshShell = false;

    public UpdateState(Store store) {
        this.store = store;
    }

    private String get(String key) {
        String v = store.get(key);
        return v == null ? "" : v;
    }

    /** The downloaded bundle being shown; empty for the built-in one. */
    public String active() {
        return get("active");
    }

    /** A downloaded bundle waiting for the next start; empty if none. */
    public String pending() {
        return get("pending");
    }

    /** The bundle shown for the first time and not yet confirmed; empty if none. */
    public String trying() {
        return get("trying");
    }

    /** Bundles that did not start and will not be tried again. */
    public List<String> failed() {
        String v = get("failed");
        return v.isEmpty() ? new ArrayList<>() : new ArrayList<>(Arrays.asList(v.split(",")));
    }

    /** The bundle given up at this start (or by the watchdog), if any: for telling the player. */
    public String rolledBack() {
        return rolledBack;
    }

    /** True if this start found a different app version than the last one, and so forgot every download. */
    public boolean freshShell() {
        return freshShell;
    }

    /**
     * Call once when the app's process starts, before the page loads.
     *
     * @param shell identifies the installed app, e.g. "2/0.2.0"
     * @return the downloaded bundle to show, or empty for the built-in one
     */
    public String onStart(String shell) {
        if (!shell.equals(get("shell"))) {
            for (String key : new String[] { "active", "previous", "pending", "trying", "failed" }) store.put(key, "");
            store.put("shell", shell);
            freshShell = true;
            return "";
        }
        if (!trying().isEmpty()) giveUpTrial(); // the last start never confirmed it
        return applyPending();
    }

    /**
     * Switch to the pending bundle, if there is one, and put it on trial. Part of every start; also
     * called when the page is reloaded inside a running app ("Restart now").
     *
     * @return the downloaded bundle to show, or empty for the built-in one
     */
    public String applyPending() {
        String next = pending();
        if (!next.isEmpty()) {
            store.put("pending", "");
            if (!failed().contains(next) && !next.equals(active())) {
                // a bundle still on trial is replaced, not blamed: what it replaced stays the fallback
                if (trying().isEmpty()) store.put("previous", active());
                store.put("active", next);
                store.put("trying", next);
            }
        }
        return active();
    }

    /** The page started properly: the bundle on trial is kept. */
    public void confirm() {
        if (trying().isEmpty()) return;
        store.put("trying", "");
        store.put("previous", "");
    }

    /** Choose a downloaded bundle for the next start. */
    public void stage(String version) {
        if (version == null || version.isEmpty() || failed().contains(version)) return;
        store.put("pending", version);
    }

    /**
     * Give up the bundle on trial now (the watchdog: the page never reported in).
     *
     * @return true if there was one, in which case the app must be started again
     */
    public boolean giveUpTrial() {
        String bad = trying();
        if (bad.isEmpty()) return false;
        List<String> failed = failed();
        if (!failed.contains(bad)) failed.add(bad);
        while (failed.size() > MAX_FAILED) failed.remove(0);
        store.put("failed", String.join(",", failed));
        store.put("active", get("previous"));
        store.put("previous", "");
        store.put("trying", "");
        if (bad.equals(pending())) store.put("pending", "");
        rolledBack = bad;
        return true;
    }

    /** The files of the active bundle are missing or broken: fall back to the built-in one. */
    public void dropActive() {
        store.put("active", "");
        store.put("previous", "");
        store.put("trying", "");
    }

    /** Bundle folders that are still needed; every other one can be deleted. */
    public List<String> inUse() {
        List<String> keep = new ArrayList<>();
        for (String key : new String[] { "active", "previous", "pending" }) {
            String v = get(key);
            if (!v.isEmpty() && !keep.contains(v)) keep.add(v);
        }
        return keep;
    }

    /** Is `candidate` a newer bundle than `current`? Versions are digits (a date and time), compared as numbers. */
    public static boolean isNewer(String candidate, String current) {
        if (candidate == null || !candidate.matches("[0-9]{1,20}")) return false;
        if (current == null || !current.matches("[0-9]{1,20}")) return true;
        String a = candidate.replaceFirst("^0+(?=.)", "");
        String b = current.replaceFirst("^0+(?=.)", "");
        return a.length() != b.length() ? a.length() > b.length() : a.compareTo(b) > 0;
    }
}
