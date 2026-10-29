#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 macOS 版的三只角色素材合成为网页版用的 768x768 四表情图。

思路（详见 ../实验-角色移植.md）：
  1. mac 素材是 1536x1024 立绘 + 330x300 的表情贴片，贴片左上角固定 (1010, 330)；
  2. mac 版用「平板四边形的三个角点」(PetCharacter.tabletCorners) 把 400x220 的
     铁盆贴图贴到角色手上；
  3. 网页版（安卓）的铁盆是另一张图，四个角点写死在 widget.js 的 QX / QY；
  4. 于是三对对应点求仿射，整张 1536x1024 立绘一起变换到 768x768。
     这样身体、脸、手的相对位置一次对齐，不会再「瘦」或「脸模错位」。

用法：
    python3 tools/make_chars.py --src /tmp/chars --out app/src/assets/vk1
    python3 tools/make_chars.py --src /tmp/chars --out /tmp/chars/out --only gpt
"""
import argparse
import os

from PIL import Image

ART_W, ART_H = 1536, 1024          # mac 立绘尺寸
OUT = 768                          # 安卓网页版画布边长
FACE_RECT = (1010, 330, 330, 300)  # 表情贴片（左上角 + 宽高，mac 坐标）

# 网页版铁盆的四边形（widget.js 里的 QX / QY），720 坐标系
QX = [549.6, 949.7, 984.7, 584.6]
QY = [706.2, 642.0, 860.2, 924.3]

# mac 版每只角色手上「平板」的三角点，顺序 = 左上 / 右上 / 左下
TABLET = {
    "gpt":    [(1060, 699), (1413, 644), (1090, 889)],
    "claude": [(1060, 699), (1413, 644), (1090, 889)],
    "gemini": [(1065, 699), (1400, 646), (1095, 889)],
}

# 对应网页版盆的左上 / 右上 / 左下
DST = [(QX[0], QY[0]), (QX[1], QY[1]), (QX[3], QY[3])]

# 网页版四表情文件名里的后缀：11 开心 / 12 傲娇 / 21 冷脸 / 22 紧张
SUFFIX_STATE = {"11": "happy", "12": "aloof", "21": "calm", "22": "nervous"}


def affine3(src, dst):
    """三点仿射：返回 (a, b, c, d, e, f)，使 dst = M * src。"""
    (x1, y1), (x2, y2), (x3, y3) = src
    (X1, Y1), (X2, Y2), (X3, Y3) = dst

    ux, uy = x2 - x1, y2 - y1
    vx, vy = x3 - x1, y3 - y1
    det = ux * vy - uy * vx
    if abs(det) < 1e-9:
        raise ValueError("三个源点共线，无法求仿射")

    a = ((X2 - X1) * vy - (X3 - X1) * uy) / det
    b = ((X3 - X1) * ux - (X2 - X1) * vx) / det
    d = ((Y2 - Y1) * vy - (Y3 - Y1) * uy) / det
    e = ((Y3 - Y1) * ux - (Y2 - Y1) * vx) / det
    c = X1 - a * x1 - b * y1
    f = Y1 - d * x1 - e * y1
    return a, b, c, d, e, f


def invert(m):
    a, b, c, d, e, f = m
    det = a * e - b * d
    if abs(det) < 1e-9:
        raise ValueError("仿射矩阵不可逆")
    ia = e / det
    ib = -b / det
    id_ = -d / det
    ie = a / det
    ic = -(ia * c + ib * f)
    if_ = -(id_ * c + ie * f)
    return ia, ib, ic, id_, ie, if_


def build(character, src_dir, out_dir):
    sprite_path = os.path.join(src_dir, "sprite-%s.png" % character)
    if not os.path.isfile(sprite_path):
        raise SystemExit("缺少立绘：%s" % sprite_path)

    base = Image.open(sprite_path).convert("RGBA")
    if base.size != (ART_W, ART_H):
        raise SystemExit("%s 尺寸是 %s，应为 %dx%d"
                         % (sprite_path, base.size, ART_W, ART_H))

    fx, fy, fw, fh = FACE_RECT
    inv = invert(affine3(TABLET[character], DST))

    for suffix, state in SUFFIX_STATE.items():
        if state == "happy":
            art = base  # 开心 = 立绘原表情，不贴片
        else:
            patch_path = os.path.join(src_dir, "face-%s-%s.png" % (character, state))
            if not os.path.isfile(patch_path):
                raise SystemExit("缺少表情贴片：%s" % patch_path)
            patch = Image.open(patch_path).convert("RGBA")
            if patch.size != (fw, fh):
                print("  ! %s 尺寸 %s，期望 %dx%d，按左上角贴"
                      % (os.path.basename(patch_path), patch.size, fw, fh))
            art = base.copy()
            art.alpha_composite(patch, dest=(fx, fy))

        out = art.transform((OUT, OUT), Image.AFFINE, inv,
                            resample=Image.BICUBIC)
        name = "expression_%s_%s.png" % (character, suffix)
        path = os.path.join(out_dir, name)
        out.save(path, optimize=True)
        print("  -> %s" % path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="/tmp/chars", help="mac 素材目录")
    ap.add_argument("--out", default="app/src/assets/vk1", help="输出目录")
    ap.add_argument("--only", choices=sorted(TABLET) + ["all"], default="all")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    targets = sorted(TABLET) if args.only == "all" else [args.only]
    for character in targets:
        print("[%s]" % character)
        build(character, args.src, args.out)


if __name__ == "__main__":
    main()
