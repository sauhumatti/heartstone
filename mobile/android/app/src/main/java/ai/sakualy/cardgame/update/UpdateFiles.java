package ai.sakualy.cardgame.update;

import java.io.BufferedInputStream;
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
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * The network and file work of an update: ask the server, fetch a bundle, check it, unpack it.
 *
 * Plain Java on purpose (no Android in here), so it can be run and tested on any machine. Every
 * request carries the app's token in a header and goes to the one server the app was built for.
 */
public final class UpdateFiles {

    /** A problem worth telling the player in words; `kind` lets the page pick them. */
    public static final class Problem extends IOException {

        public final String kind; // offline | refused | server | checksum | size | archive | space | cancelled

        public Problem(String kind, String message) {
            super(message);
            this.kind = kind;
        }
    }

    public interface Progress {
        void at(long received, long total);
    }

    public static final long MAX_BUNDLE_BYTES = 200L * 1024 * 1024;
    private static final long MAX_UNPACKED_BYTES = 600L * 1024 * 1024;
    private static final int MAX_ENTRIES = 30_000;
    private static final int MAX_MANIFEST_BYTES = 64 * 1024;

    /** Tests on one machine talk plain http to themselves; the app never does. */
    public static boolean allowHttpForTests = false;

    private UpdateFiles() {}

    private static HttpURLConnection open(String url, String token, int timeoutMs) throws IOException {
        URL u = new URL(url);
        if (!"https".equals(u.getProtocol()) && !(allowHttpForTests && "http".equals(u.getProtocol()))) {
            throw new Problem("server", "The update address is not https.");
        }
        HttpURLConnection c = (HttpURLConnection) u.openConnection();
        c.setConnectTimeout(timeoutMs);
        c.setReadTimeout(timeoutMs);
        c.setInstanceFollowRedirects(false); // the token goes to this server and nowhere else
        c.setUseCaches(false);
        try {
            c.setRequestProperty("X-App-Token", token);
        } catch (IllegalArgumentException e) {
            throw new Problem("refused", "This app's token is not one a server could accept.");
        }
        c.setRequestProperty("Accept-Encoding", "identity");
        return c;
    }

    private static int status(HttpURLConnection c) throws IOException {
        int code;
        try {
            code = c.getResponseCode();
        } catch (IOException e) {
            throw new Problem("offline", "The update server could not be reached.");
        }
        if (code == 401 || code == 403 || code == 404) throw new Problem("refused", "The update server did not accept this app (" + code + ").");
        if (code != 200) throw new Problem("server", "The update server answered " + code + ".");
        return code;
    }

    /** The manifest, as text. */
    public static String getText(String url, String token, int timeoutMs) throws IOException {
        HttpURLConnection c;
        try {
            c = open(url, token, timeoutMs);
            c.connect();
        } catch (Problem p) {
            throw p;
        } catch (IOException e) {
            throw new Problem("offline", "The update server could not be reached.");
        }
        try {
            status(c);
            try (InputStream in = c.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                    if (out.size() > MAX_MANIFEST_BYTES) throw new Problem("server", "The update server's answer is too long.");
                }
                return out.toString(StandardCharsets.UTF_8.name());
            } catch (Problem p) {
                throw p;
            } catch (IOException e) {
                throw new Problem("offline", "The connection was lost.");
            }
        } finally {
            c.disconnect();
        }
    }

    /**
     * Fetch a bundle into `dest` and make sure it is the one the manifest described: the right
     * length and the right SHA-256. Anything else leaves no file behind.
     */
    public static void download(String url, String token, File dest, long expectedSize, String expectedSha256, Progress progress, AtomicBoolean cancelled)
        throws IOException {
        if (expectedSize <= 0 || expectedSize > MAX_BUNDLE_BYTES) throw new Problem("size", "The update's size is not believable.");
        if (expectedSha256 == null || !expectedSha256.matches("[0-9a-fA-F]{64}")) throw new Problem("checksum", "The update has no checksum.");
        HttpURLConnection c;
        try {
            c = open(url, token, 20_000);
            c.connect();
        } catch (Problem p) {
            throw p;
        } catch (IOException e) {
            throw new Problem("offline", "The update server could not be reached.");
        }
        boolean ok = false;
        try {
            status(c);
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            long received = 0;
            long lastTold = -1;
            try (InputStream in = new BufferedInputStream(c.getInputStream()); OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[64 * 1024];
                int n;
                while ((n = in.read(buf)) > 0) {
                    if (cancelled != null && cancelled.get()) throw new Problem("cancelled", "The download was stopped.");
                    received += n;
                    if (received > expectedSize) throw new Problem("size", "The update is longer than it should be.");
                    sha.update(buf, 0, n);
                    out.write(buf, 0, n);
                    if (progress != null && (received - lastTold >= 256 * 1024 || received == expectedSize)) {
                        lastTold = received;
                        progress.at(received, expectedSize);
                    }
                }
            } catch (Problem p) {
                throw p;
            } catch (IOException e) {
                throw new Problem("offline", "The connection was lost during the download.");
            }
            if (received != expectedSize) throw new Problem("size", "The update is shorter than it should be.");
            if (!hex(sha.digest()).equalsIgnoreCase(expectedSha256)) throw new Problem("checksum", "The update did not match its checksum.");
            ok = true;
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new Problem("checksum", "This device cannot check the update.");
        } finally {
            c.disconnect();
            if (!ok) dest.delete();
        }
    }

    /**
     * Unpack a bundle into `destDir`. It is unpacked beside it first and moved into place when
     * complete, so a folder with that name is always a whole bundle. Entries that try to land
     * outside the folder, and archives without an index.html, are refused.
     */
    public static void unzip(File zip, File destDir) throws IOException {
        File work = new File(destDir.getParentFile(), destDir.getName() + ".part");
        deleteTree(work);
        deleteTree(destDir);
        if (!work.mkdirs()) throw new Problem("space", "The update could not be unpacked.");
        boolean ok = false;
        try {
            String root = work.getCanonicalPath() + File.separator;
            long total = 0;
            int entries = 0;
            try (ZipInputStream in = new ZipInputStream(new BufferedInputStream(new FileInputStream(zip)))) {
                ZipEntry entry;
                byte[] buf = new byte[64 * 1024];
                while ((entry = in.getNextEntry()) != null) {
                    if (++entries > MAX_ENTRIES) throw new Problem("archive", "The update has too many files.");
                    String name = entry.getName();
                    File target = new File(work, name);
                    if (name.startsWith("/") || name.contains("\\") || !(target.getCanonicalPath() + File.separator).startsWith(root)) {
                        throw new Problem("archive", "The update contains a file that does not belong in it.");
                    }
                    if (entry.isDirectory()) {
                        if (!target.isDirectory() && !target.mkdirs()) throw new Problem("space", "The update could not be unpacked.");
                        continue;
                    }
                    File parent = target.getParentFile();
                    if (parent != null && !parent.isDirectory() && !parent.mkdirs()) throw new Problem("space", "The update could not be unpacked.");
                    try (OutputStream out = new FileOutputStream(target)) {
                        int n;
                        while ((n = in.read(buf)) > 0) {
                            total += n;
                            if (total > MAX_UNPACKED_BYTES) throw new Problem("archive", "The update unpacks to more than it should.");
                            out.write(buf, 0, n);
                        }
                    }
                }
            } catch (Problem p) {
                throw p;
            } catch (IOException e) {
                throw new Problem("archive", "The update could not be unpacked.");
            }
            if (!new File(work, "index.html").isFile()) throw new Problem("archive", "The update is not a complete game.");
            if (!work.renameTo(destDir)) throw new Problem("space", "The update could not be put in place.");
            ok = true;
        } finally {
            if (!ok) deleteTree(work);
        }
    }

    public static void deleteTree(File f) {
        if (f == null || !f.exists()) return;
        File[] children = f.isDirectory() ? f.listFiles() : null;
        if (children != null) for (File child : children) deleteTree(child);
        f.delete();
    }

    private static String hex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) sb.append(String.format("%02x", b));
        return sb.toString();
    }
}
