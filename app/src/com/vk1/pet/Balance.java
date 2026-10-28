package com.vk1.pet;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/** Reads the DeepSeek account balance. Only talks to api.deepseek.com. */
final class Balance {
    static final String ENDPOINT = "https://api.deepseek.com/user/balance";

    static final class Result {
        final boolean ok;
        final double total;
        final String error;

        Result(boolean ok, double total, String error) {
            this.ok = ok;
            this.total = total;
            this.error = error;
        }
    }

    static String describe(int code) {
        if (code == 401 || code == 403) return "Key 被拒绝（" + code + "）";
        if (code == 429) return "请求太频繁（429）";
        if (code >= 500) return "服务器错误（" + code + "）";
        return "HTTP " + code;
    }

    static Result fetch(String key) {
        if (key == null || !key.startsWith("sk-") || key.length() < 20) {
            return new Result(false, Double.NaN, "没有有效的 API Key");
        }
        HttpURLConnection conn = null;
        try {
            URL url = new URL(ENDPOINT);
            conn = (HttpURLConnection) url.openConnection();
            conn.setConnectTimeout(12000);
            conn.setReadTimeout(15000);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("Authorization", "Bearer " + key);
            conn.setRequestProperty("Accept", "application/json");
            int code = conn.getResponseCode();
            if (code != 200) {
                return new Result(false, Double.NaN, describe(code));
            }
            InputStream in = conn.getInputStream();
            ByteArrayOutputStream buf = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int n;
            while ((n = in.read(chunk)) > 0) buf.write(chunk, 0, n);
            in.close();
            JSONObject root = new JSONObject(new String(buf.toByteArray(), StandardCharsets.UTF_8));
            JSONArray infos = root.optJSONArray("balance_infos");
            if (infos == null || infos.length() == 0) {
                return new Result(false, Double.NaN, "响应里没有 balance_infos");
            }
            JSONObject picked = infos.optJSONObject(0);
            for (int i = 0; i < infos.length(); i++) {
                JSONObject info = infos.optJSONObject(i);
                if (info != null && "CNY".equals(info.optString("currency"))) {
                    picked = info;
                    break;
                }
            }
            if (picked == null) return new Result(false, Double.NaN, "响应格式不对");
            double total = Double.parseDouble(picked.optString("total_balance", "NaN"));
            if (Double.isNaN(total) || Double.isInfinite(total)) {
                return new Result(false, Double.NaN, "余额不是数字");
            }
            return new Result(true, total, null);
        } catch (Exception e) {
            String msg = e.getClass().getSimpleName();
            if (e.getMessage() != null) msg += ": " + e.getMessage();
            return new Result(false, Double.NaN, msg);
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
