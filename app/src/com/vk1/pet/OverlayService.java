package com.vk1.pet;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.TextView;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Floating overlay host.
 *
 * The WebView renders on a full-screen window that never takes input, so the widget can
 * draw anywhere (rice falls from the top of the screen, props are draggable everywhere)
 * exactly like the desktop build. A second, tiny transparent window sits over the pixels
 * that currently matter — her and any loose bowl — and forwards touches into the WebView.
 * Everywhere else, taps go straight through to the app underneath.
 */
public class OverlayService extends Service {
    static final String TAG = "VK1";
    static final String CHANNEL = "vk1-pet";
    static final int NOTE_ID = 1001;
    private static final String LOG_NAME = "vk1.log";
    static final String EXTRA_ALPHA = "alpha";
    static final String EXTRA_COMPAT = "compat";
    static volatile boolean RUNNING;

    private WindowManager wm;
    private WebView web;
    private View touchSlot;
    private WindowManager.LayoutParams webParams;
    private WindowManager.LayoutParams touchParams;
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Object lock = new Object();

    private float appliedAlpha() {
        return Math.max(0.3f, Math.min(1f,
                getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
                        .getInt(MainActivity.KEY_ALPHA, 100) / 100f));
    }

    private int screenW, screenH;
    private float density = 2.75f;
    private boolean expanded;
    private int regionX, regionY, regionW = 1, regionH = 1;
    private final int[] webLoc = new int[2];

    private volatile String balanceJson = "{\"ok\":false}";
    private ScheduledExecutorService poller;
    private BroadcastReceiver screenReceiver;
    private volatile long lastFetchAt;
    private long lastBuzzAt;
    private long lastRegionLog;

    private float downX, downY, cx, cy, lpX, lpY;
    private boolean moved;
    private boolean gestureActive;
    private boolean petDrag;
    private float pendDx, pendDy;
    private boolean flushScheduled;

    private final Runnable flushMove = new Runnable() {
        @Override
        public void run() {
            flushScheduled = false;
            if (web == null || (pendDx == 0 && pendDy == 0)) return;
            String js = String.format(Locale.US,
                    "window.__vk1MovePet&&window.__vk1MovePet(%.2f,%.2f)", pendDx, pendDy);
            pendDx = 0;
            pendDy = 0;
            web.evaluateJavascript(js, null);
        }
    };
    private int pendingX = -1, pendingY, pendingW, pendingH;

    private TextView debugView;
    private String debugText = "";

    private final Runnable longPress = new Runnable() {
        @Override
        public void run() {
            if (web == null) return;
            String js = String.format(Locale.US,
                    "window.__vk1LongPress && window.__vk1LongPress(%.1f,%.1f)", lpX, lpY);
            web.evaluateJavascript(js, null);
            logFile("long-press -> " + js);
        }
    };

    // ------------------------------------------------------------- lifecycle ---
    @Override
    public void onCreate() {
        super.onCreate();
        RUNNING = true;
        CrashLog.install(this);
        startForeground(NOTE_ID, buildNotification("余额桌宠运行中"));
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        density = getResources().getDisplayMetrics().density;
        measureScreen();
        startPoller();
        watchScreen();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (web == null) showPet();
        if (intent != null && intent.hasExtra(EXTRA_ALPHA)) {
            final int pct = intent.getIntExtra(EXTRA_ALPHA, 100);
            main.post(new Runnable() {
                @Override
                public void run() {
                    if (web != null) web.setAlpha(Math.max(0.3f, Math.min(1f, pct / 100f)));
                }
            });
        }
        return START_STICKY;
    }

    private void measureScreen() {
        DisplayMetrics dm = new DisplayMetrics();
        if (Build.VERSION.SDK_INT >= 30) {
            android.view.WindowMetrics m = wm.getCurrentWindowMetrics();
            screenW = m.getBounds().width();
            screenH = m.getBounds().height();
        } else {
            wm.getDefaultDisplay().getRealMetrics(dm);
            screenW = dm.widthPixels;
            screenH = dm.heightPixels;
        }
    }

    void logFile(String line) {
        try {
            java.io.File dir = getExternalFilesDir(null);
            if (dir == null) return;
            if (!dir.exists()) dir.mkdirs();
            java.io.File f = new java.io.File(dir, LOG_NAME);
            if (f.length() > 200_000) f.delete();
            java.io.FileWriter w = new java.io.FileWriter(f, true);
            w.write(new SimpleDateFormat("MM-dd HH:mm:ss", Locale.US).format(new Date())
                    + " " + line + "\n");
            w.close();
        } catch (Exception ignored) {
        }
    }

    // ---------------------------------------------------------------- windows ---
    private void showPet() {
        measureScreen();

        web = new WebView(this);
        web.setBackgroundColor(Color.TRANSPARENT);
        web.setVerticalScrollBarEnabled(false);
        web.setHorizontalScrollBarEnabled(false);
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setAllowFileAccessFromFileURLs(true);
        s.setAllowUniversalAccessFromFileURLs(true);
        s.setTextZoom(100);
        s.setUseWideViewPort(false);
        s.setLoadWithOverviewMode(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);

        web.addJavascriptInterface(new Bridge(), "VK1");
        web.setWebViewClient(new android.webkit.WebViewClient() {
            @Override
            public void onReceivedError(WebView view, android.webkit.WebResourceRequest req,
                                        android.webkit.WebResourceError err) {
                logFile("web error " + req.getUrl() + " " + err.getDescription());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                logFile("page finished " + url);
            }
        });

        webParams = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN
                        | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT);
        webParams.alpha = 1f;
        webParams.gravity = Gravity.TOP | Gravity.START;
        webParams.x = 0;
        webParams.y = 0;
        wm.addView(web, webParams);

        touchSlot = new View(this);
        touchSlot.setBackgroundColor(Color.TRANSPARENT);
        touchParams = new WindowManager.LayoutParams(
                1, 1,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        touchParams.gravity = Gravity.TOP | Gravity.START;
        touchParams.x = 0;
        touchParams.y = 0;
        touchSlot.setOnTouchListener(this::onSlotTouch);
        wm.addView(touchSlot, touchParams);

        if (getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
                .getBoolean(MainActivity.KEY_DEBUG, false)) {
            showDebugView();
        }
        logFile("showPet screen=" + screenW + "x" + screenH + " density=" + density);
        web.loadUrl("file:///android_asset/vk1/index.html");
    }

    /** Forwards the gesture into the WebView, which sits at (0,0) covering the screen. */
    private boolean onSlotTouch(View v, MotionEvent e) {
        switch (e.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                downX = e.getRawX();
                downY = e.getRawY();
                moved = false;
                gestureActive = true;
                if (web != null) web.getLocationOnScreen(webLoc);
                lpX = (regionX - webLoc[0] + e.getX()) / density;
                lpY = (regionY - webLoc[1] + e.getY()) / density;
                main.removeCallbacks(longPress);
                main.postDelayed(longPress, 560);
                break;
            case MotionEvent.ACTION_POINTER_DOWN:
                main.removeCallbacks(longPress);
                petDrag = true;
                if (web != null) {
                    web.evaluateJavascript("window.__vk1NoPat && window.__vk1NoPat(true)", null);
                }
                cancelGesture();
                cx = centroidX(e);
                cy = centroidY(e);
                break;
            case MotionEvent.ACTION_MOVE:
                if (!moved && Math.hypot(e.getRawX() - downX, e.getRawY() - downY) > 8 * density) {
                    moved = true;
                    main.removeCallbacks(longPress);
                }
                if (petDrag && web != null) {
                    float nx = centroidX(e);
                    float ny = centroidY(e);
                    float dx = (nx - cx) / density;
                    float dy = (ny - cy) / density;
                    cx = nx;
                    cy = ny;
                    pendDx += dx;
                    pendDy += dy;
                    if (!flushScheduled) {
                        flushScheduled = true;
                        main.postDelayed(flushMove, 16);
                    }
                }
                break;
            case MotionEvent.ACTION_POINTER_UP:
                if (e.getPointerCount() - 1 < 2 && petDrag) {
                    petDrag = false;
                    if (web != null) {
                        web.evaluateJavascript("window.__vk1DropPet && window.__vk1DropPet()", null);
                        web.evaluateJavascript("window.__vk1NoPat && window.__vk1NoPat(false)", null);
                    }
                }
                break;
            case MotionEvent.ACTION_UP:
            case MotionEvent.ACTION_CANCEL:
                main.removeCallbacks(longPress);
                gestureActive = false;
                if (petDrag) {
                    petDrag = false;
                    if (web != null) {
                        web.evaluateJavascript("window.__vk1DropPet && window.__vk1DropPet()", null);
                        web.evaluateJavascript("window.__vk1NoPat && window.__vk1NoPat(false)", null);
                    }
                }
                // Resizing the slot mid-gesture makes the system cancel the touch, which
                // used to abort every drag; the deferred region lands here instead.
                if (pendingX >= 0) {
                    int px = pendingX, py = pendingY, pw = pendingW, ph = pendingH;
                    pendingX = -1;
                    applyRegion(px, py, pw, ph);
                }
                break;
            default:
                break;
        }
        if (web != null) web.getLocationOnScreen(webLoc);
        // While two fingers move her, the page already gets the movement through
        // __vk1MovePet; replaying every MOVE as a touch too doubles the work per frame.
        boolean skip = petDrag && e.getActionMasked() == MotionEvent.ACTION_MOVE;
        if (!skip) {
            MotionEvent copy = MotionEvent.obtain(e);
            copy.offsetLocation(regionX - webLoc[0], regionY - webLoc[1]);
            if (web != null) web.dispatchTouchEvent(copy);
            copy.recycle();
        }
        return true;
    }

    private void setTouchRegion(int x, int y, int w, int h) {
        synchronized (lock) {
            if (expanded || touchSlot == null) return;
            if (gestureActive) {
                pendingX = x;
                pendingY = y;
                pendingW = w;
                pendingH = h;
                return;
            }
            applyRegion(x, y, w, h);
        }
    }

    private void applyRegion(int x, int y, int w, int h) {
        synchronized (lock) {
            if (touchSlot == null) return;
            // x/y arrive in page pixels; the WebView itself may sit a status bar below
            // the screen origin, which is exactly the offset that made every small hit
            // target (the menu button, the bowls) need a tap "above" it.
            if (web != null) web.getLocationOnScreen(webLoc);
            x += webLoc[0];
            y += webLoc[1];
            x = clamp(x, 0, screenW - 1);
            y = clamp(y, 0, screenH - 1);
            w = clamp(w, 1, screenW - x);
            h = clamp(h, 1, screenH - y);
            if (x == regionX && y == regionY && w == regionW && h == regionH) return;
            logToView("webLoc " + webLoc[0] + "," + webLoc[1]);
            regionX = x;
            regionY = y;
            regionW = w;
            regionH = h;
            long nowLog = System.currentTimeMillis();
            if (nowLog - lastRegionLog > 1200) {
                lastRegionLog = nowLog;
                logToView("region " + x + "," + y + " " + w + "x" + h);
            }
            touchParams.x = x;
            touchParams.y = y;
            touchParams.width = w;
            touchParams.height = h;
            try {
                wm.updateViewLayout(touchSlot, touchParams);
            } catch (Exception ignored) {
            }
        }
    }

    private static float centroidX(MotionEvent e) {
        float sum = 0;
        for (int i = 0; i < e.getPointerCount(); i++) sum += e.getRawX(i);
        return sum / Math.max(1, e.getPointerCount());
    }

    private static float centroidY(MotionEvent e) {
        float sum = 0;
        for (int i = 0; i < e.getPointerCount(); i++) sum += e.getRawY(i);
        return sum / Math.max(1, e.getPointerCount());
    }

    private void cancelGesture() {
        if (web == null) return;
        web.evaluateJavascript("window.__vk1CancelGesture && window.__vk1CancelGesture()", null);
    }

    private static int clamp(int v, int lo, int hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    private void applyWebParams() {
        if (web == null || web.getParent() == null) return;
        try {
            wm.updateViewLayout(web, webParams);
        } catch (Exception e) {
            logFile("updateViewLayout failed: " + e);
        }
    }

    // ------------------------------------------------------------- bridge ---
    private final class Bridge {
        @JavascriptInterface
        public String balanceJson() {
            try {
                if (System.currentTimeMillis() - lastFetchAt > 6000) refresh();
                return balanceJson;
            } catch (Throwable t) {
                logFile("balanceJson failed: " + t);
                return "{\"ok\":false}";
            }
        }

        @JavascriptInterface
        public void refresh() {
            try {
                ScheduledExecutorService p = poller;
                if (p != null) p.execute(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            fetchBalance();
                        } catch (Throwable t) {
                            logFile("fetchBalance failed: " + t);
                        }
                    }
                });
            } catch (Throwable t) {
                logFile("refresh failed: " + t);
            }
        }

        /** CSS-pixel rectangle that currently needs to swallow touches. */
        @JavascriptInterface
        public void touchRegion(float x0, float y0, float x1, float y1) {
            try {
                final int px = Math.round(x0 * density);
                final int py = Math.round(y0 * density);
                final int pw = Math.max(8, Math.round((x1 - x0) * density));
                final int ph = Math.max(8, Math.round((y1 - y0) * density));
                // WindowManager calls must run on the UI thread; this bridge does not.
                main.post(new Runnable() {
                    @Override
                    public void run() {
                        setTouchRegion(px, py, pw, ph);
                    }
                });
            } catch (Throwable t) {
                logFile("touchRegion failed: " + t);
            }
        }

        /** Kept for compatibility; sizing is the page's business now. */
        @JavascriptInterface
        public void resize(float cssSize) {
        }

        /** True = modal UI is up: the render window takes input itself, no forwarding. */
        @JavascriptInterface
        public String setExpanded(boolean on) {
            try {
                synchronized (lock) {
                    if (expanded == on) return "";
                    expanded = on;
                }
                main.post(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            synchronized (lock) {
                                if (web == null) return;
                                if (on) {
                                    webParams.flags &= ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                                    webParams.flags &= ~WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
                                    webParams.softInputMode = WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE;
                                    touchParams.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                                    try {
                                        wm.updateViewLayout(touchSlot, touchParams);
                                    } catch (Exception ignored) {
                                    }
                                } else {
                                    webParams.flags |= WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                                    webParams.flags |= WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE;
                                    touchParams.flags &= ~WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE;
                                    try {
                                        wm.updateViewLayout(touchSlot, touchParams);
                                    } catch (Exception ignored) {
                                    }
                                }
                                applyWebParams();
                                if (!on) {
                                    main.postDelayed(new Runnable() {
                                        @Override
                                        public void run() {
                                            if (web != null) {
                                                web.evaluateJavascript(
                                                        "window.__vk1ReportRegion && window.__vk1ReportRegion(performance.now())", null);
                                            }
                                        }
                                    }, 40);
                                }
                            }
                        } catch (Throwable t) {
                            logFile("setExpanded apply failed: " + t);
                        }
                    }
                });
                return "";
            } catch (Throwable t) {
                logFile("setExpanded failed: " + t);
                return "";
            }
        }

        @JavascriptInterface
        public void buzz() {
            try {
                if (!getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE)
                        .getBoolean(MainActivity.KEY_VIBRATE, true)) return;
                long now = System.currentTimeMillis();
                if (now - lastBuzzAt < 400) return;
                lastBuzzAt = now;
                Vibrator vib = (Vibrator) getSystemService(VIBRATOR_SERVICE);
                if (vib == null || !vib.hasVibrator()) return;
                if (Build.VERSION.SDK_INT >= 26) {
                    vib.vibrate(VibrationEffect.createOneShot(16, VibrationEffect.DEFAULT_AMPLITUDE));
                }
            } catch (Throwable t) {
                logFile("buzz failed: " + t);
            }
        }

        @JavascriptInterface
        public void openSetup() {
            try {
                Intent i = new Intent(OverlayService.this, MainActivity.class);
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(i);
            } catch (Throwable t) {
                logFile("openSetup failed: " + t);
            }
        }

        @JavascriptInterface
        public void log(String msg) {
            try {
                Log.i(TAG, "js: " + msg);
                logFile("js: " + msg);
                logToView(msg);
            } catch (Throwable ignored) {
            }
        }
    }

    // -------------------------------------------------------------- polling ---
    private void startPoller() {
        poller = Executors.newSingleThreadScheduledExecutor();
        poller.scheduleWithFixedDelay(new Runnable() {
            @Override
            public void run() {
                // Nothing on screen is watching a dark display: skip the call instead of
                // waking the radio every ten seconds all night.
                if (!screenOn) return;
                fetchBalance();
            }
        }, 0, 10, TimeUnit.SECONDS);
    }

    private volatile boolean screenOn = true;

    private void watchScreen() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        screenOn = pm == null || pm.isInteractive();
        screenReceiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                boolean on = Intent.ACTION_SCREEN_ON.equals(intent.getAction());
                screenOn = on;
                if (on) {
                    // Catch up right away so the tablet is never showing last night's number.
                    final ScheduledExecutorService p = poller;
                    if (p != null && !p.isShutdown()) {
                        try {
                            p.execute(new Runnable() {
                                @Override
                                public void run() {
                                    fetchBalance();
                                }
                            });
                        } catch (Throwable ignored) {
                        }
                    }
                }
            }
        };
        IntentFilter f = new IntentFilter(Intent.ACTION_SCREEN_ON);
        f.addAction(Intent.ACTION_SCREEN_OFF);
        registerReceiver(screenReceiver, f);
    }

    private void fetchBalance() {
        SharedPreferences sp = getSharedPreferences(MainActivity.PREFS, MODE_PRIVATE);
        String key = sp.getString(MainActivity.KEY_API, "");
        Balance.Result r = Balance.fetch(key);
        lastFetchAt = System.currentTimeMillis();
        if (r.ok) {
            String iso = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US)
                    .format(new Date(lastFetchAt));
            balanceJson = "{\"ok\":true,\"totalBalance\":" + r.total
                    + ",\"serverTime\":\"" + iso + "\"}";
        } else {
            boolean needKey = key == null || !key.startsWith("sk-") || key.length() < 20;
            balanceJson = "{\"ok\":false,\"needKey\":" + needKey + ",\"error\":\""
                    + r.error.replace("\"", "") + "\"}";
            logFile("balance: " + r.error);
        }
    }

    // ------------------------------------------------------------ debug view ---
    private void showDebugView() {
        debugView = new TextView(this);
        debugView.setTextSize(9);
        debugView.setTextColor(Color.WHITE);
        debugView.setBackgroundColor(0x99000000);
        debugView.setPadding(12, 8, 12, 8);
        debugView.setMaxLines(12);
        debugView.setText("");
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                Math.round(300 * density), WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.x = 0;
        lp.y = Math.round(120 * density);
        try {
            wm.addView(debugView, lp);
        } catch (Exception e) {
            debugView = null;
        }
    }

    private void logToView(String line) {
        if (debugView == null) return;
        main.post(new Runnable() {
            @Override
            public void run() {
                String t = new SimpleDateFormat("HH:mm:ss", Locale.US).format(new Date()) + " " + line;
                debugText = t + "\n" + debugText;
                String[] lines = debugText.split("\n");
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < Math.min(lines.length, 12); i++) sb.append(lines[i]).append('\n');
                if (debugView != null) debugView.setText(sb.toString());
            }
        });
    }

    // --------------------------------------------------------- notification ---
    private Notification buildNotification(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, "余额桌宠",
                    NotificationManager.IMPORTANCE_MIN);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder b = (Build.VERSION.SDK_INT >= 26)
                ? new Notification.Builder(this, CHANNEL)
                : new Notification.Builder(this);
        return b.setContentTitle("余额桌宠")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.stat_notify_chat)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        main.postDelayed(new Runnable() {
            @Override
            public void run() {
                measureScreen();
            }
        }, 300);
    }

    @Override
    public void onDestroy() {
        RUNNING = false;
        if (poller != null) poller.shutdownNow();
        if (screenReceiver != null) {
            try {
                unregisterReceiver(screenReceiver);
            } catch (Throwable ignored) {
            }
            screenReceiver = null;
        }
        if (debugView != null) {
            try {
                wm.removeView(debugView);
            } catch (Exception ignored) {
            }
            debugView = null;
        }
        if (touchSlot != null) {
            try {
                wm.removeView(touchSlot);
            } catch (Exception ignored) {
            }
            touchSlot = null;
        }
        if (web != null) {
            try {
                wm.removeView(web);
            } catch (Exception ignored) {
            }
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
