package com.vk1.pet;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;

/** Keeps the last crash trace inside the app sandbox so the setup screen can show it. */
final class CrashLog {
    private static final String FILE = "crash.txt";

    static void install(final Context ctx) {
        final Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, error) -> {
            try {
                StringWriter sw = new StringWriter();
                error.printStackTrace(new PrintWriter(sw));
                FileOutputStream out = ctx.openFileOutput(FILE, Context.MODE_PRIVATE);
                out.write((thread.getName() + "\n" + sw).getBytes("UTF-8"));
                out.close();
            } catch (Throwable ignored) {
            }
            if (previous != null) previous.uncaughtException(thread, error);
        });
    }

    /** Returns the stored trace and clears it. */
    static String take(Context ctx) {
        File f = new File(ctx.getFilesDir(), FILE);
        if (!f.exists()) return "";
        try {
            FileInputStream in = new FileInputStream(f);
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] tmp = new byte[4096];
            int n;
            while ((n = in.read(tmp)) > 0) buf.write(tmp, 0, n);
            in.close();
            f.delete();
            return buf.toString("UTF-8");
        } catch (Throwable t) {
            return "";
        }
    }
}
