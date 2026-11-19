import ai.sakualy.cardgame.update.UpdateFiles;
import ai.sakualy.cardgame.update.UpdateState;
import java.io.File;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Runs the app's own update code (the plain-Java part) from the command line, so the Python tests
 * can exercise it on this machine: see tests/test_updater_core.py.
 */
public class UpdateDriver {

    public static void main(String[] a) throws Exception {
        UpdateFiles.allowHttpForTests = true;
        try {
            switch (a[0]) {
                case "state": {
                    // each argument is one step; the state is printed after every step
                    final Map<String, String> kept = new HashMap<>();
                    UpdateState.Store store = new UpdateState.Store() {
                        public String get(String k) { return kept.get(k); }
                        public void put(String k, String v) { if (v == null || v.isEmpty()) kept.remove(k); else kept.put(k, v); }
                    };
                    UpdateState s = new UpdateState(store);
                    for (int i = 1; i < a.length; i++) {
                        String[] op = a[i].split("=", 2);
                        String shown = "";
                        switch (op[0]) {
                            case "start": s = new UpdateState(store); shown = s.onStart(op[1]); break; // a new process
                            case "apply": shown = s.applyPending(); break;
                            case "stage": s.stage(op[1]); break;
                            case "confirm": s.confirm(); break;
                            case "giveup": shown = String.valueOf(s.giveUpTrial()); break;
                            case "drop": s.dropActive(); break;
                            default: throw new IllegalArgumentException(op[0]);
                        }
                        System.out.println(a[i] + " -> shown=" + shown + " active=" + s.active() + " pending=" + s.pending() + " trying=" + s.trying()
                            + " failed=" + String.join(",", s.failed()) + " rolledBack=" + s.rolledBack() + " fresh=" + s.freshShell()
                            + " inUse=" + String.join(",", s.inUse()));
                    }
                    break;
                }
                case "newer":
                    System.out.println(UpdateState.isNewer(a[1], a[2]));
                    break;
                case "get":
                    System.out.println(UpdateFiles.getText(a[1], token(a[2]), 5000));
                    break;
                case "download": {
                    final long[] calls = { 0, 0 };
                    UpdateFiles.download(a[1], token(a[2]), new File(a[3]), Long.parseLong(a[4]), a[5], (r, t) -> { calls[0]++; calls[1] = r; }, new AtomicBoolean("cancel".equals(a.length > 6 ? a[6] : "")));
                    System.out.println("OK progress=" + calls[0] + " last=" + calls[1]);
                    break;
                }
                case "unzip":
                    UpdateFiles.unzip(new File(a[1]), new File(a[2]));
                    System.out.println("OK");
                    break;
                default:
                    throw new IllegalArgumentException(a[0]);
            }
        } catch (UpdateFiles.Problem p) {
            System.out.println("PROBLEM " + p.kind + ": " + p.getMessage());
        }
    }

    private static String token(String file) throws Exception {
        return file.isEmpty() ? "" : new String(Files.readAllBytes(new File(file).toPath())).trim();
    }
}
