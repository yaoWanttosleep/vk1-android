#!/usr/bin/env python3
"""Build the VK-1 Android widget APK without Gradle/aapt (hand-written AXML + d8 + apksig)."""
import os
import shutil
import subprocess
import sys
import struct
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/tools")
import axml  # noqa: E402
import arsc  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
DEPS = os.path.join(ROOT, "deps")
FALLBACK = os.path.join(os.path.dirname(ROOT), "依赖")


def _dep(name, fallback):
    local = os.path.join(DEPS, name)
    return local if os.path.exists(local) else os.path.join(FALLBACK, fallback)


ANDROID_JAR = _dep("android.jar", "platform35/android-35/android.jar")
R8_JAR = _dep("r8-8.13.25.jar", "r8-8.13.25.jar")
APKSIG_JAR = _dep("apksig-8.13.2.jar", "apksig-8.13.2.jar")
KEYSTORE = os.path.join(ROOT, "debug.p12")
if not os.path.exists(KEYSTORE):
    KEYSTORE = os.path.join(ROOT, "build/debug.p12")
STORE_PASS = "vk1debug"
ALIAS = "vk1"

PACKAGE = "com.vk1.pet"


def el(tag, attrs=None, children=None):
    return axml.Element(tag, attrs, children)


def manifest(app_label):
    activity = el("activity", [
        ("android", "name", "string", PACKAGE + ".MainActivity"),
        ("android", "exported", "bool", True),
        ("android", "label", "string", app_label),
    ], [
        el("intent-filter", [], [
            el("action", [("android", "name", "string", "android.intent.action.MAIN")]),
            el("category", [("android", "name", "string", "android.intent.category.LAUNCHER")]),
        ]),
    ])
    service = el("service", [
        ("android", "name", "string", PACKAGE + ".OverlayService"),
        ("android", "exported", "bool", False),
    ])
    application = el("application", [
        ("android", "label", "string", app_label),
        ("android", "icon", "ref", 0x7F010000),
        ("android", "allowBackup", "bool", False),
        ("android", "usesCleartextTraffic", "bool", False),
    ], [activity, service])
    perms = ["android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE",
             "android.permission.SYSTEM_ALERT_WINDOW", "android.permission.FOREGROUND_SERVICE",
             "android.permission.VIBRATE", "android.permission.POST_NOTIFICATIONS"]
    children = [
        el("uses-sdk", [
            ("android", "minSdkVersion", "int", 26),
            ("android", "targetSdkVersion", "int", 33),
        ]),
    ]
    children += [el("uses-permission", [("android", "name", "string", p)]) for p in perms]
    children.append(application)
    return el("manifest", [
        (None, "package", "string", PACKAGE),
        ("android", "versionCode", "int", 2),
        ("android", "versionName", "string", "1.4.4"),
    ], children)


def add_stored_aligned(zf, name, data):
    """resources.arsc has to be stored (not deflated) and 4-byte aligned, like aapt does."""
    zi = zipfile.ZipInfo(name, date_time=time.localtime()[:6])
    zi.compress_type = zipfile.ZIP_STORED
    offset = zf.fp.tell()
    base = offset + 30 + len(name.encode())
    pad = (4 - (base % 4)) % 4
    if pad < 4:
        pad += 4
    zi.extra = struct.pack("<HH", 0xD935, pad - 4) + b"\x00" * (pad - 4)
    zf.writestr(zi, data)


def sh(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def keystore():
    if os.path.exists(KEYSTORE):
        return
    os.makedirs(os.path.dirname(KEYSTORE), exist_ok=True)
    sh(["keytool", "-genkeypair", "-keystore", KEYSTORE, "-storetype", "PKCS12",
        "-alias", ALIAS, "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", STORE_PASS, "-keypass", STORE_PASS,
        "-dname", "CN=VK-1, O=VK-1, C=CN"])


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "余额桌宠"
    build = os.path.join(ROOT, "build")
    classes = os.path.join(build, "classes")
    dex = os.path.join(build, "dex")
    for d in (classes, dex):
        shutil.rmtree(d, ignore_errors=True)
        os.makedirs(d)

    sources = []
    for base, _, files in os.walk(os.path.join(ROOT, "app/src")):
        sources += [os.path.join(base, f) for f in files if f.endswith(".java")]
    sh(["javac", "-nowarn", "-Xlint:none", "--release", "11",
        "-classpath", ANDROID_JAR, "-d", classes] + sources)

    signer_dir = os.path.join(build, "signer")
    os.makedirs(signer_dir, exist_ok=True)
    sh(["javac", "-cp", APKSIG_JAR, "-d", signer_dir, os.path.join(ROOT, "tools/SignTool.java")])

    all_classes = []
    for base, _, files in os.walk(classes):
        all_classes += [os.path.join(base, f) for f in files if f.endswith(".class")]
    all_classes.sort()
    sh(["java", "-cp", R8_JAR, "com.android.tools.r8.D8",
        "--min-api", "26", "--lib", ANDROID_JAR, "--output", dex] + all_classes)

    unsigned = os.path.join(build, "unsigned.apk")
    if os.path.exists(unsigned):
        os.remove(unsigned)
    with zipfile.ZipFile(unsigned, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("AndroidManifest.xml", axml.build(manifest(label)))
        z.write(os.path.join(dex, "classes.dex"), "classes.dex")
        add_stored_aligned(z, "resources.arsc", arsc.build())
        icon = os.path.join(ROOT, "res/icon.png")
        if os.path.exists(icon):
            z.write(icon, "res/mipmap/ic_launcher.png")
        assets = os.path.join(ROOT, "app/src/assets")
        if os.path.isdir(assets):
            for base, _, files in os.walk(assets):
                for f in sorted(files):
                    full = os.path.join(base, f)
                    rel = os.path.relpath(full, assets)
                    z.write(full, "assets/" + rel.replace(os.sep, "/"))

    keystore()
    signed = os.path.join(build, "vk1-pet.apk")
    if os.path.exists(signed):
        os.remove(signed)
    sh(["java", "-cp", APKSIG_JAR + ":" + signer_dir, "SignTool",
        unsigned, signed, KEYSTORE, STORE_PASS, ALIAS])
    print("APK:", signed, os.path.getsize(signed))


if __name__ == "__main__":
    main()
