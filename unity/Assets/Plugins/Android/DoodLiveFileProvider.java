// A minimal read-only content provider for the colouring-sheet PDF (docs/LIBRARY.md, "Sheet actions").
// Serves files from <cacheDir>/shared/ only, as content://<applicationId>.doodlive.files/<name>, so the system share
// sheet (Drive, Gmail, WeChat, Files, printer apps) can read the PDF the app copied out of its APK. It does what
// androidx FileProvider does for one directory, without adding an androidx dependency to the Unity gradle build.
// Declared in Assets/Plugins/Android/DoodLiveShare.androidlib/AndroidManifest.xml (exported=false, grantUriPermissions).
package today.onemorething.doodlive.share;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.FileNotFoundException;
import java.io.IOException;

public class DoodLiveFileProvider extends ContentProvider {
    public static final String DIR = "shared";

    public static String authority(android.content.Context c) { return c.getPackageName() + ".doodlive.files"; }

    public static Uri uriFor(android.content.Context c, File f) {
        return new Uri.Builder().scheme("content").authority(authority(c)).appendPath(f.getName()).build();
    }

    @Override public boolean onCreate() { return true; }

    private File fileFor(Uri uri) throws FileNotFoundException {
        String name = uri.getLastPathSegment();
        if (name == null || name.contains("/") || name.startsWith(".")) throw new FileNotFoundException(String.valueOf(uri));
        try {
            File dir = new File(getContext().getCacheDir(), DIR).getCanonicalFile();
            File f = new File(dir, name).getCanonicalFile();
            if (!dir.equals(f.getParentFile()) || !f.isFile()) throw new FileNotFoundException(String.valueOf(uri));
            return f;
        } catch (IOException e) {
            throw new FileNotFoundException(e.getMessage());
        }
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (mode != null && !mode.equals("r")) throw new SecurityException("read-only");
        return ParcelFileDescriptor.open(fileFor(uri), ParcelFileDescriptor.MODE_READ_ONLY);
    }

    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        File f;
        try { f = fileFor(uri); } catch (FileNotFoundException e) { return null; }
        String[] cols = projection != null ? projection : new String[] { OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE };
        MatrixCursor c = new MatrixCursor(cols, 1);
        Object[] row = new Object[cols.length];
        for (int i = 0; i < cols.length; i++) {
            if (OpenableColumns.DISPLAY_NAME.equals(cols[i])) row[i] = f.getName();
            else if (OpenableColumns.SIZE.equals(cols[i])) row[i] = f.length();
        }
        c.addRow(row);
        return c;
    }

    @Override public String getType(Uri uri) {
        String n = uri.getLastPathSegment();
        if (n == null) return null;
        if (n.endsWith(".pdf")) return "application/pdf";
        if (n.endsWith(".png")) return "image/png";
        return "application/octet-stream";
    }

    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException("read-only"); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException("read-only"); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException("read-only"); }
}
