#!/usr/bin/env python3
"""把纯色（默认绿幕）背景的图抠成透明 PNG。

gpt-image-2 渠道不支持 background 透明参数，且对"transparent background"会画出
假棋盘格。对策：prompt 要求纯绿幕底，再用本脚本按"到角落色的距离"键控成透明，
并对保留像素做去绿边（despill）。主体是暖色系、无绿，所以不会误抠脸/衣服。

用法： cutout.py --in raw.png --out final.png [--hard 70] [--soft 150]
"""
import argparse
import numpy as np
from PIL import Image


def corner_key(arr):
    """取四角小块的中位色作为背景键色（角落基本一定是背景）。"""
    h, w = arr.shape[:2]
    s = max(6, min(h, w) // 80)
    patches = [arr[0:s, 0:s], arr[0:s, w - s:w], arr[h - s:h, 0:s], arr[h - s:h, w - s:w]]
    cols = np.concatenate([p.reshape(-1, arr.shape[2]) for p in patches], axis=0)[:, :3]
    return np.median(cols.astype(np.float32), axis=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--hard", type=float, default=70.0, help="距离<=hard 完全透明")
    ap.add_argument("--soft", type=float, default=150.0, help="距离>=soft 完全不透明")
    a = ap.parse_args()

    im = Image.open(a.inp).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    rgb = arr[:, :, :3].copy()

    key = corner_key(arr)
    dist = np.sqrt(((rgb - key) ** 2).sum(axis=2))

    # 软边 alpha 斜坡
    denom = max(1e-3, (a.soft - a.hard))
    alpha = np.clip((dist - a.hard) / denom, 0.0, 1.0) * 255.0

    # 去绿边：键色偏绿时，把保留像素里"绿明显高于红蓝"的绿压回去
    if key[1] > key[0] and key[1] > key[2]:
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
        cap = np.maximum(r, b)
        rgb[:, :, 1] = np.where(g > cap, cap, g)

    out = np.dstack([rgb, alpha]).astype(np.uint8)
    Image.fromarray(out).save(a.out)

    transp = float((alpha < 10).mean() * 100.0)
    kept = float((alpha > 245).mean() * 100.0)
    print(f"[cutout] key={[int(x) for x in key.round()]} 透明={transp:.1f}% 保留={kept:.1f}%")


if __name__ == "__main__":
    main()
