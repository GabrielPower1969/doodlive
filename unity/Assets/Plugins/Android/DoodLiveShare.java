// Book-page sheet actions (docs/LIBRARY.md, "Sheet actions"): save / share / print a story's blank colouring-sheet PDF
// with the system's own screens. Called from C# (ARColoringController.SheetActions.cs) through AndroidJavaClass:
//   DoodLiveShare.run(activity, action, assetPath, displayName, title)  ->  "saved:<where>" | "shared" | "printing" | "error:<why>"
// assetPath is relative to the APK's assets/ folder, i.e. Unity's StreamingAssets (e.g. "sheets/exodus-A4.pdf").
//   save  : MediaStore.Downloads (API 29+, no storage permission) -> Download/<displayName>; below API 29 it opens
//           the share sheet instead (writing to public Downloads there would need WRITE_EXTERNAL_STORAGE).
//   share : copy to <cacheDir>/shared/<displayName>, content:// URI from DoodLiveFileProvider, ACTION_SEND
//           application/pdf through Intent.createChooser.
//   print : PrintManager.print with a PrintDocumentAdapter that streams the PDF unchanged, A4 preselected, so the
//           sheet prints at real size (the markers must stay square for scanning).
package today.onemorething.doodlive.share;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Environment;
import android.os.ParcelFileDescriptor;
import android.print.PageRange;
import android.print.PrintAttributes;
import android.print.PrintDocumentAdapter;
import android.print.PrintDocumentInfo;
import android.print.PrintManager;
import android.provider.MediaStore;
import android.util.Log;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public final class DoodLiveShare {
    private static final String TAG = "DoodLiveShare";
    private static final String MIME = "application/pdf";

    private DoodLiveShare() {}

    public static String run(final Activity a, String action, String assetPath, String displayName, final String title) {
        try {
            if ("save".equals(action)) return save(a, assetPath, displayName, title);
            final File f = copyToCache(a, assetPath, displayName);
            if ("share".equals(action)) { share(a, f, title); return "shared"; }
            if ("print".equals(action)) { print(a, f, title); return "printing"; }
            return "error:unknown action " + action;
        } catch (Throwable t) {
            Log.e(TAG, action + " failed", t);
            return "error:" + t.getClass().getSimpleName() + ": " + t.getMessage();
        }
    }

    // ---------------- save to Downloads ----------------
    private static String save(Activity a, String assetPath, String displayName, String title) throws IOException {
        if (Build.VERSION.SDK_INT < 29) {   // no MediaStore.Downloads: let the share sheet save it (Files, Drive, ...)
            share(a, copyToCache(a, assetPath, displayName), title);
            return "shared";
        }
        ContentResolver cr = a.getContentResolver();
        ContentValues v = new ContentValues();
        v.put(MediaStore.MediaColumns.DISPLAY_NAME, displayName);
        v.put(MediaStore.MediaColumns.MIME_TYPE, MIME);
        v.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
        v.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
        if (uri == null) return "error:MediaStore insert returned null";
        try (InputStream in = a.getAssets().open(assetPath); OutputStream out = cr.openOutputStream(uri)) {
            if (out == null) throw new IOException("no output stream for " + uri);
            pipe(in, out);
        } catch (IOException e) {
            cr.delete(uri, null, null);
            throw e;
        }
        ContentValues done = new ContentValues();
        done.put(MediaStore.MediaColumns.IS_PENDING, 0);
        cr.update(uri, done, null, null);
        return "saved:" + Environment.DIRECTORY_DOWNLOADS + "/" + displayName;
    }

    // ---------------- share sheet ----------------
    private static void share(final Activity a, File f, String title) {
        final Uri uri = DoodLiveFileProvider.uriFor(a, f);
        final Intent send = new Intent(Intent.ACTION_SEND);
        send.setType(MIME);
        send.putExtra(Intent.EXTRA_STREAM, uri);
        send.putExtra(Intent.EXTRA_SUBJECT, f.getName());
        send.setClipData(ClipData.newRawUri(f.getName(), uri));   // lets the chooser preview it and carries the grant
        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        final Intent chooser = Intent.createChooser(send, title);
        chooser.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        a.runOnUiThread(new Runnable() {
            @Override public void run() {
                try { a.startActivity(chooser); } catch (Throwable t) { Log.e(TAG, "share chooser failed", t); }
            }
        });
    }

    // ---------------- print ----------------
    private static void print(final Activity a, final File f, final String jobName) {
        a.runOnUiThread(new Runnable() {
            @Override public void run() {
                try {
                    PrintManager pm = (PrintManager) a.getSystemService(Context.PRINT_SERVICE);
                    PrintAttributes attrs = new PrintAttributes.Builder()
                            .setMediaSize(PrintAttributes.MediaSize.ISO_A4)
                            .setMinMargins(PrintAttributes.Margins.NO_MARGINS)
                            .build();
                    pm.print(jobName, new PdfAdapter(f, jobName), attrs);
                } catch (Throwable t) { Log.e(TAG, "print failed", t); }
            }
        });
    }

    /** Hands the finished PDF to the print system unchanged (no re-rendering, so the A4 page keeps its real size). */
    private static final class PdfAdapter extends PrintDocumentAdapter {
        private final File file; private final String name;
        PdfAdapter(File file, String name) { this.file = file; this.name = name; }

        @Override public void onLayout(PrintAttributes oldAttrs, PrintAttributes newAttrs, CancellationSignal cancel,
                                       LayoutResultCallback cb, Bundle extras) {
            if (cancel.isCanceled()) { cb.onLayoutCancelled(); return; }
            PrintDocumentInfo info = new PrintDocumentInfo.Builder(safeName(name) + ".pdf")
                    .setContentType(PrintDocumentInfo.CONTENT_TYPE_DOCUMENT)
                    .setPageCount(PrintDocumentInfo.PAGE_COUNT_UNKNOWN)
                    .build();
            cb.onLayoutFinished(info, oldAttrs == null || !oldAttrs.equals(newAttrs));
        }

        @Override public void onWrite(PageRange[] pages, ParcelFileDescriptor dest, CancellationSignal cancel,
                                      WriteResultCallback cb) {
            try (InputStream in = new FileInputStream(file); OutputStream out = new FileOutputStream(dest.getFileDescriptor())) {
                byte[] buf = new byte[64 * 1024]; int n;
                while ((n = in.read(buf)) > 0) {
                    if (cancel.isCanceled()) { cb.onWriteCancelled(); return; }
                    out.write(buf, 0, n);
                }
                cb.onWriteFinished(new PageRange[] { PageRange.ALL_PAGES });
            } catch (IOException e) {
                cb.onWriteFailed(e.getMessage());
            }
        }
    }

    // ---------------- helpers ----------------
    private static File copyToCache(Context c, String assetPath, String displayName) throws IOException {
        File dir = new File(c.getCacheDir(), DoodLiveFileProvider.DIR);
        if (!dir.isDirectory() && !dir.mkdirs()) throw new IOException("cannot create " + dir);
        File f = new File(dir, safeName(displayName));
        try (InputStream in = c.getAssets().open(assetPath); OutputStream out = new FileOutputStream(f)) { pipe(in, out); }
        return f;
    }

    private static String safeName(String s) {
        String r = s == null ? "DoodLive.pdf" : s.replaceAll("[\\\\/:*?\"<>|\\x00-\\x1f]", "_").trim();
        return r.isEmpty() || r.startsWith(".") ? "DoodLive.pdf" : r;
    }

    private static void pipe(InputStream in, OutputStream out) throws IOException {
        byte[] buf = new byte[64 * 1024]; int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        out.flush();
    }
}
