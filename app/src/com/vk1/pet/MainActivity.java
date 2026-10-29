package com.vk1.pet;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Setup screen: API key, overlay permission, start/stop. */
public class MainActivity extends Activity {
    static final String PREFS = "vk1";
    static final String KEY_API = "api_key";
    static final String KEY_DEBUG = "debug";
    static final String KEY_ALPHA = "alpha";
    static final String KEY_COMPAT = "compat";
    static final String KEY_VIBRATE = "vibrate";
    static final String KEY_RADAR = "radar";
    static final String KEY_MAGNET = "magnet";

    private EditText keyInput;
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        setTheme(android.R.style.Theme_DeviceDefault_Light_NoActionBar);
        super.onCreate(savedInstanceState);

        float d = getResources().getDisplayMetrics().density;
        int pad = (int) (20 * d);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.WHITE);

        TextView title = new TextView(this);
        title.setText("余额桌宠");
        title.setTextSize(24);
        title.setTextColor(Color.rgb(32, 48, 82));
        root.addView(title);

        TextView sub = new TextView(this);
        sub.setText("贴在桌面上的小挂件：她举着平板显示 DeepSeek 余额。扣费会红闪 + 震动，充值会掉一盆米饭，拖到她身上才入账。");
        sub.setTextSize(14);
        sub.setTextColor(Color.rgb(100, 110, 130));
        sub.setPadding(0, (int) (8 * d), 0, (int) (16 * d));
        root.addView(sub);

        TextView keyLabel = new TextView(this);
        keyLabel.setText("DeepSeek API Key（sk- 开头，只存在本机）");
        keyLabel.setTextSize(15);
        root.addView(keyLabel);

        keyInput = new EditText(this);
        keyInput.setHint("sk-...");
        keyInput.setSingleLine(true);
        keyInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
        keyInput.setTextSize(14);
        root.addView(keyInput);

        LinearLayout row1 = row();
        row1.addView(button("保存 Key", v -> saveKey()));
        row1.addView(button("测试余额", v -> testBalance()));
        root.addView(row1);

        LinearLayout row2 = row();
        row2.addView(button("授权悬浮窗", v -> requestOverlay()));
        row2.addView(button("启动桌宠", v -> startPet()));
        root.addView(row2);

        LinearLayout row3 = row();
        row3.addView(button("停止桌宠", v -> stopPet()));
        row3.addView(button("隐藏本页", v -> moveTaskToBack(true)));
        row3.addView(button("导出日志", v -> exportLog()));
        root.addView(row3);

        TextView alphaLabel = new TextView(this);
        alphaLabel.setText("挂件不透明度");
        alphaLabel.setTextSize(15);
        alphaLabel.setPadding(0, (int) (16 * d), 0, 0);
        root.addView(alphaLabel);

        final int savedAlpha = getSharedPreferences(PREFS, MODE_PRIVATE).getInt(KEY_ALPHA, 100);

        final android.widget.SeekBar alphaBar = new android.widget.SeekBar(this);
        alphaBar.setMax(70);                       // 30% .. 100%
        alphaBar.setProgress(Math.max(0, savedAlpha - 30));
        root.addView(alphaBar);

        alphaBar.setOnSeekBarChangeListener(new android.widget.SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(android.widget.SeekBar bar, int progress, boolean fromUser) {
                if (!fromUser) return;
                int value = progress + 30;
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putInt(KEY_ALPHA, value).apply();
                if (OverlayService.RUNNING) {
                    Intent i = new Intent(MainActivity.this, OverlayService.class);
                    i.putExtra(OverlayService.EXTRA_ALPHA, value);
                    startService(i);
                }
            }

            @Override
            public void onStartTrackingTouch(android.widget.SeekBar bar) {
            }

            @Override
            public void onStopTrackingTouch(android.widget.SeekBar bar) {
            }
        });

        android.widget.CheckBox vibrate = new android.widget.CheckBox(this);
        vibrate.setText("扣费时震动");
        vibrate.setTextSize(14);
        vibrate.setChecked(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_VIBRATE, true));
        vibrate.setOnCheckedChangeListener((v, checked) ->
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(KEY_VIBRATE, checked).apply());
        root.addView(vibrate);

        android.widget.CheckBox magnet = new android.widget.CheckBox(this);
        magnet.setText("自动吸饭（锁定后饭自己飞过去被吃掉）");
        magnet.setTextSize(14);
        magnet.setChecked(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_MAGNET, true));
        magnet.setOnCheckedChangeListener((v, checked) -> {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(KEY_MAGNET, checked).apply();
            pushFlags();
        });
        root.addView(magnet);

        android.widget.CheckBox radar = new android.widget.CheckBox(this);
        radar.setText("火控雷达显示（绿括号 + 距离/接近率）");
        radar.setTextSize(14);
        radar.setChecked(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_RADAR, true));
        radar.setOnCheckedChangeListener((v, checked) -> {
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(KEY_RADAR, checked).apply();
            pushFlags();
        });
        root.addView(radar);

        android.widget.CheckBox debug = new android.widget.CheckBox(this);
        debug.setText("显示调试信息（排查问题用，平时关着）");
        debug.setTextSize(13);
        debug.setChecked(getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_DEBUG, false));
        debug.setOnCheckedChangeListener((v, checked) ->
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(KEY_DEBUG, checked).apply());
        root.addView(debug);

        status = new TextView(this);
        status.setTextSize(13);
        status.setTextColor(Color.rgb(80, 90, 110));
        status.setPadding(0, (int) (16 * d), 0, 0);
        status.setTextIsSelectable(true);
        root.addView(status);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(root);
        setContentView(scroll);

        CrashLog.install(this);
        String crash = CrashLog.take(this);
        if (!crash.isEmpty()) {
            toastStatus("上次崩溃了，堆栈在下面（截图发我）：\n\n" + crash);
        }

        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        keyInput.setText(sp.getString(KEY_API, ""));
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS")
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"}, 1);
        }
    }

    private void pushFlags() {
        if (!OverlayService.RUNNING) return;
        startService(new Intent(this, OverlayService.class)
                .putExtra(OverlayService.EXTRA_FLAGS, true));
    }

    // The widget log lives in Android/data, which no file manager can open on Android 11+,
    // so hand the user a copy they can actually send.
    private void exportLog() {
        try {
            StringBuilder sb = new StringBuilder();
            java.io.File ext = getExternalFilesDir(null);
            java.io.File widgetLog = ext == null ? null : new java.io.File(ext, "vk1.log");
            if (widgetLog != null && widgetLog.exists()) {
                sb.append(readFile(widgetLog));
            }
            java.io.File crash = new java.io.File(getFilesDir(), CrashLog.FILE);
            if (crash.exists()) sb.append("\n---- crash ----\n").append(readFile(crash));
            if (sb.length() == 0) {
                toastStatus("还没有日志：把挂件跑一会儿，出过问题再来导出。");
                return;
            }
            String name = "vk1-log-" + new java.text.SimpleDateFormat("MMdd-HHmm", java.util.Locale.US)
                    .format(new java.util.Date()) + ".log";
            String where;
            if (Build.VERSION.SDK_INT >= 29) {
                android.content.ContentValues cv = new android.content.ContentValues();
                cv.put(android.provider.MediaStore.MediaColumns.DISPLAY_NAME, name);
                cv.put(android.provider.MediaStore.MediaColumns.MIME_TYPE, "text/plain");
                cv.put(android.provider.MediaStore.MediaColumns.RELATIVE_PATH,
                        android.os.Environment.DIRECTORY_DOWNLOADS);
                android.net.Uri uri = getContentResolver().insert(
                        android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI, cv);
                if (uri == null) throw new java.io.IOException("MediaStore insert failed");
                java.io.OutputStream os = getContentResolver().openOutputStream(uri);
                if (os == null) throw new java.io.IOException("no output stream");
                os.write(sb.toString().getBytes("UTF-8"));
                os.close();
                where = "Download/" + name;
            } else {
                java.io.File dir = new java.io.File(
                        android.os.Environment.getExternalStoragePublicDirectory(
                                android.os.Environment.DIRECTORY_DOWNLOADS), name);
                java.io.FileOutputStream fo = new java.io.FileOutputStream(dir);
                fo.write(sb.toString().getBytes("UTF-8"));
                fo.close();
                where = dir.getAbsolutePath();
            }
            toastStatus("日志已导出：" + where);
        } catch (Throwable t) {
            toastStatus("导出失败：" + t);
        }
    }

    private static String readFile(java.io.File f) throws java.io.IOException {
        java.io.BufferedReader r = new java.io.BufferedReader(
                new java.io.InputStreamReader(new java.io.FileInputStream(f), "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String line;
        while ((line = r.readLine()) != null) sb.append(line).append('\n');
        r.close();
        return sb.toString();
    }

    private LinearLayout row() {
        LinearLayout r = new LinearLayout(this);
        r.setOrientation(LinearLayout.HORIZONTAL);
        r.setGravity(Gravity.START);
        r.setPadding(0, (int) (8 * getResources().getDisplayMetrics().density), 0, 0);
        return r;
    }

    private Button button(String text, View.OnClickListener onClick) {
        Button b = new Button(this);
        b.setText(text);
        b.setAllCaps(false);
        b.setOnClickListener(onClick);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, (int) (8 * getResources().getDisplayMetrics().density), 0);
        b.setLayoutParams(lp);
        return b;
    }

    private boolean saveKey() {
        String key = keyInput.getText().toString().trim();
        if (!key.startsWith("sk-") || key.length() < 20) {
            toastStatus("Key 看起来不对：应该以 sk- 开头。\n未保存。");
            return false;
        }
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_API, key).apply();
        toastStatus("Key 已保存（只存在这台手机上）。");
        return true;
    }

    private void testBalance() {
        if (!saveKey()) return;
        final String key = keyInput.getText().toString().trim();
        toastStatus("正在读余额…");
        new Thread(() -> {
            final Balance.Result r = Balance.fetch(key);
            runOnUiThread(() -> {
                if (r.ok) {
                    toastStatus(String.format(java.util.Locale.US, "余额 ¥%.2f（接口正常）", r.total));
                } else {
                    toastStatus("读取失败：" + r.error);
                }
            });
        }).start();
    }

    private void requestOverlay() {
        if (Settings.canDrawOverlays(this)) {
            toastStatus("悬浮窗权限已授权。");
            return;
        }
        Intent i = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + getPackageName()));
        startActivity(i);
    }

    private void startPet() {
        if (!Settings.canDrawOverlays(this)) {
            toastStatus("先给「显示在其他应用上层」权限，再启动。");
            requestOverlay();
            return;
        }
        // A key is optional: without one she still shows up and just reads "未连接".
        String key = keyInput.getText().toString().trim();
        if (!key.isEmpty()) {
            if (key.startsWith("sk-") && key.length() >= 20) {
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_API, key).apply();
            } else {
                toastStatus("Key 格式看起来不对（应该 sk- 开头）。\n仍然会启动，平板会显示「未连接」，之后可以回来重填。");
            }
        }
        Context ctx = getApplicationContext();
        Intent svc = new Intent(ctx, OverlayService.class);
        if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(svc);
        else ctx.startService(svc);
        toastStatus("桌宠已启动。可以按 Home 键退回桌面。\n（本页可以「隐藏」，不影响挂件）");
    }

    private void stopPet() {
        stopService(new Intent(this, OverlayService.class));
        toastStatus("已停止。");
    }

    private void toastStatus(String text) {
        if (status != null) status.setText(text);
    }

    @Override
    protected void onResume() {
        super.onResume();
        StringBuilder sb = new StringBuilder();
        sb.append("悬浮窗权限：").append(Settings.canDrawOverlays(this) ? "已授权" : "未授权");
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        sb.append("\nAPI Key：").append(sp.getString(KEY_API, "").isEmpty() ? "未设置" : "已保存");
        sb.append("\n\n用完想关掉挂件：点「停止桌宠」。");
        if (status != null && status.getText().length() == 0) status.setText(sb.toString());
    }
}
