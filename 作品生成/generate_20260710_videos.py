import asyncio
import math
import re
import subprocess
import sys
from pathlib import Path

import edge_tts
import imageio.v2 as imageio
import numpy as np
from moviepy import AudioFileClip
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/mnt/d/wtf1124/wyz")
MPT = Path("/mnt/d/wtf1124/project/MoneyPrinterTurbo")
OUT_DIR = ROOT / "作品生成" / "视频成片"
ASSET_DIR = ROOT / "作品生成" / "素材片段"
TASK_DIR = MPT / "storage" / "tasks"
FONT_BOLD = MPT / "resource" / "fonts" / "MicrosoftYaHeiBold.ttc"
FONT_NORMAL = MPT / "resource" / "fonts" / "MicrosoftYaHeiNormal.ttc"

W, H = 1080, 1920
FPS = 60
BRAND = "西安注册公司找峪诚"


def read_section(text, heading):
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.M | re.S)
    return match.group(1).strip() if match else ""


def load_voice(item):
    text = (ROOT / item["script"]).read_text(encoding="utf-8")
    voice = read_section(text, "口播稿")
    item["voice"] = re.sub(r"\s+", "", voice)
    return item


def font(size, bold=True):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_NORMAL), size)


F = {
    "brand": font(38),
    "small": font(30, False),
    "small_b": font(32),
    "body": font(48),
    "tag": font(42),
    "title": font(68),
    "hero": font(88),
    "num": font(74),
}


def clamp(v, a=0, b=1):
    return max(a, min(b, v))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) * (1 - x)


def wrap_text(text, draw, fnt, max_width):
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def rounded(d, xy, r, fill, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def center_text(d, box, text, fnt, fill=(255, 255, 255), spacing=8):
    x1, y1, x2, y2 = box
    lines = wrap_text(text, d, fnt, x2 - x1 - 30)
    heights = [d.textbbox((0, 0), line, font=fnt)[3] for line in lines]
    total = sum(heights) + spacing * (len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for line, h in zip(lines, heights):
        bbox = d.textbbox((0, 0), line, font=fnt)
        d.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y), line, font=fnt, fill=fill)
        y += h + spacing


def bg(style, t):
    if style == "detective":
        base, accent = (18, 14, 12), (209, 80, 44)
    elif style == "whiteboard":
        base, accent = (18, 23, 35), (46, 134, 193)
    else:
        base, accent = (7, 18, 32), (37, 99, 235)
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(18):
        y = int((i * 118 + t * 28) % (H + 160)) - 80
        d.line([(0, y), (W, y - 180)], fill=(*accent, 22), width=2)
    d.ellipse((-220, 140, 500, 860), fill=(*accent, 22))
    d.ellipse((650, 820, 1320, 1500), fill=(220, 38, 38, 18))
    return img


def shell(img, item, p):
    d = ImageDraw.Draw(img, "RGBA")
    rounded(d, (42, 44, 1038, 118), 20, (3, 8, 18, 218), (255, 255, 255, 34), 1)
    d.text((66, 68), BRAND, font=F["brand"], fill=(255, 255, 255, 245))
    d.text((870, 70), "2026-07-10", font=F["small"], fill=(156, 163, 175, 255))
    rounded(d, (62, 154, 1018, 246), 24, (*item["accent"], 230))
    center_text(d, (62, 154, 1018, 246), item["hook"], F["tag"])
    rounded(d, (62, 1740, 1018, 1848), 28, (3, 8, 18, 225), (255, 255, 255, 40), 1)
    d.text((98, 1772), f"需要自查表，私信：{item['keyword']}", font=F["body"], fill=(255, 255, 255))
    return d


def draw_avatar(d, x, y, scale=1.0, point="left"):
    # Rendered-person placeholder for the March 17 presenter reference.
    s = scale
    d.ellipse((x + 76*s, y, x + 184*s, y + 108*s), fill=(224, 185, 145, 255))
    d.pieslice((x + 66*s, y - 8*s, x + 194*s, y + 88*s), 180, 360, fill=(42, 31, 25, 255))
    d.ellipse((x + 106*s, y + 44*s, x + 116*s, y + 54*s), fill=(20, 20, 20, 255))
    d.ellipse((x + 146*s, y + 44*s, x + 156*s, y + 54*s), fill=(20, 20, 20, 255))
    d.arc((x + 118*s, y + 62*s, x + 154*s, y + 88*s), 0, 180, fill=(90, 48, 40, 230), width=max(1, int(3*s)))
    rounded(d, (x + 32*s, y + 110*s, x + 228*s, y + 352*s), int(34*s), (23, 37, 60, 255), (148, 163, 184, 110), 2)
    d.polygon([(x + 85*s, y + 112*s), (x + 175*s, y + 112*s), (x + 142*s, y + 182*s), (x + 118*s, y + 182*s)], fill=(238, 242, 247, 255))
    if point == "left":
        d.line((x + 48*s, y + 170*s, x - 50*s, y + 110*s), fill=(224, 185, 145, 255), width=max(5, int(12*s)))
        d.ellipse((x - 68*s, y + 96*s, x - 28*s, y + 136*s), fill=(224, 185, 145, 255))
    else:
        d.line((x + 214*s, y + 170*s, x + 318*s, y + 112*s), fill=(224, 185, 145, 255), width=max(5, int(12*s)))
        d.ellipse((x + 300*s, y + 96*s, x + 340*s, y + 136*s), fill=(224, 185, 145, 255))


def subtitle(d, item, p):
    idx = min(len(item["subs"]) - 1, int(p * len(item["subs"])))
    lines = wrap_text(item["subs"][idx], d, F["body"], 900)[:2]
    y = 1515 - (len(lines) - 1) * 34
    rounded(d, (70, y - 24, 1010, y + 78 * len(lines)), 20, (3, 8, 18, 210))
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=F["body"])
        d.text(((W - (bbox[2] - bbox[0])) / 2, y), line, font=F["body"], fill=(255, 255, 255))
        y += 72


def detective_scene(d, p):
    board = (94, 300, 986, 1325)
    rounded(d, board, 34, (48, 35, 26, 238), (209, 80, 44, 155), 3)
    d.text((138, 340), "无货源证据链", font=F["title"], fill=(255, 246, 230))
    d.rectangle((132, 444, 948, 454), fill=(209, 80, 44, 180))
    points = [
        ("平台订单", (166, 520)),
        ("上游采购", (590, 520)),
        ("付款记录", (166, 760)),
        ("物流轨迹", (590, 760)),
        ("售后处理", (376, 1000)),
    ]
    centers = []
    for i, (label, (x, y)) in enumerate(points):
        appear = ease(p * 6 - i * 0.75)
        fill = (255, 248, 232, int(245 * appear))
        border = (34, 197, 94, 230) if appear > .75 else (220, 38, 38, 210)
        rounded(d, (x, y, x + 320, y + 120), 22, fill, border, 3)
        if appear > .15:
            center_text(d, (x, y, x + 320, y + 120), label, F["tag"], (35, 26, 20))
        centers.append((x + 160, y + 60, appear))
    for a, b in zip(centers, centers[1:]):
        if min(a[2], b[2]) > .55:
            d.line((a[0], a[1], b[0], b[1]), fill=(239, 68, 68, 220), width=7)
    if p > .7:
        rounded(d, (170, 1190, 910, 1280), 22, (22, 101, 52, 235))
        center_text(d, (170, 1190, 910, 1280), "抽 10 单，五样对齐", F["tag"])
    draw_avatar(d, 770, 1260, .72, "left")


def whiteboard_scene(d, p):
    rounded(d, (72, 300, 790, 1330), 34, (248, 250, 252, 242), (96, 165, 250, 160), 3)
    d.text((120, 350), "找代账前，先问 5 句", font=F["title"], fill=(15, 23, 42))
    questions = ["平台流水按店铺拆吗？", "退款补贴怎么算？", "无票成本留证据吗？", "私户收款会分类吗？", "每月给自查表吗？"]
    for i, q in enumerate(questions):
        y = 500 + i * 142
        active = p * 6 > i + .5
        color = (22, 101, 52) if active else (100, 116, 139)
        d.ellipse((122, y + 12, 168, y + 58), fill=(34, 197, 94, 245) if active else (226, 232, 240, 255))
        if active:
            d.line((134, y + 36, 148, y + 50, 169, y + 20), fill=(255, 255, 255, 255), width=5)
        d.text((190, y), q, font=F["tag"], fill=color)
    if p < .18:
        rounded(d, (180, 1180, 690, 1260), 18, (220, 38, 38, 230))
        center_text(d, (180, 1180, 690, 1260), "不要只问多少钱", F["tag"])
    draw_avatar(d, 770, 980, .82, "left")


def dashboard_scene(d, p):
    rounded(d, (76, 298, 1004, 1328), 36, (10, 18, 32, 236), (59, 130, 246, 155), 3)
    d.text((126, 346), "平台扣点驾驶舱", font=F["title"], fill=(226, 232, 240))
    gauges = [
        ("成交", "100000", (130, 505), (59, 130, 246)),
        ("扣点", "-8000", (590, 505), (239, 68, 68)),
        ("到账", "92000", (130, 820), (34, 197, 94)),
        ("申报", "?", (590, 820), (245, 158, 11)),
    ]
    for i, (label, value, (x, y), color) in enumerate(gauges):
        a = ease(p * 5 - i * .65)
        rounded(d, (x, y, x + 360, y + 220), 28, (248, 250, 252, int(235 * max(.35, a))), (*color, 180), 3)
        d.text((x + 35, y + 35), label, font=F["tag"], fill=(15, 23, 42))
        d.text((x + 35, y + 106), value, font=F["num"], fill=color)
        d.arc((x + 222, y + 60, x + 326, y + 164), 180, int(180 + 160 * a), fill=color, width=10)
    if p > .45:
        d.line((490, 610, 590, 610), fill=(239, 68, 68, 230), width=8)
        d.line((490, 925, 590, 925), fill=(245, 158, 11, 230), width=8)
    if p > .72:
        rounded(d, (150, 1168, 930, 1262), 22, (30, 64, 175, 235))
        center_text(d, (150, 1168, 930, 1262), "成交、扣点、到账、申报四个数对齐", F["tag"])
    draw_avatar(d, 735, 1250, .74, "left")


async def tts(text, out, voice):
    communicate = edge_tts.Communicate(text, voice, rate="-2%", volume="+0%")
    await communicate.save(str(out))


def duration(path):
    clip = AudioFileClip(str(path))
    dur = clip.duration
    clip.close()
    return dur


def bgm(path, dur):
    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    expr = "aevalsrc=0.012*sin(2*PI*174*t)+0.009*sin(2*PI*220*t)+0.006*sin(2*PI*330*t):s=44100"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", expr, "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(path)], check=True)


def render(item):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    task = TASK_DIR / item["task"]
    task.mkdir(parents=True, exist_ok=True)
    audio = task / "audio.mp3"
    if not audio.exists():
        asyncio.run(tts(item["voice"], audio, item["voice_name"]))
    dur = max(duration(audio), item.get("min_duration", 42))
    bgm_path = task / "bgm.wav"
    if not bgm_path.exists():
        bgm(bgm_path, dur)
    raw = ASSET_DIR / f"{item['slug']}_20260710_raw.mp4"
    final = OUT_DIR / f"{item['name']}_20260710.mp4"
    writer = imageio.get_writer(str(raw), fps=FPS, codec="libx264", quality=8, pixelformat="yuv420p", macro_block_size=1)
    frames = int(math.ceil(dur * FPS))
    for n in range(frames):
        t = n / FPS
        p = t / dur
        img = bg(item["style"], t)
        d = shell(img, item, p)
        if item["style"] == "detective":
            detective_scene(d, p)
        elif item["style"] == "whiteboard":
            whiteboard_scene(d, p)
        else:
            dashboard_scene(d, p)
        subtitle(d, item, p)
        writer.append_data(np.asarray(img))
    writer.close()
    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    subprocess.run([
        ffmpeg, "-y", "-i", str(raw), "-i", str(audio), "-i", str(bgm_path),
        "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.055[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[aout]",
        "-map", "0:v:0", "-map", "[aout]",
        "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)
    ], check=True)
    return final, dur


ITEMS = [
    {
        "name": "无货源电商证据链",
        "slug": "wuhuoyuan_zhengjulian",
        "script": "scripts/2026-07-10_e777010db6fe_无货源电商证据链.md",
        "task": "wyz_20260710_wuhuoyuan_zhengjulian",
        "style": "detective",
        "keyword": "证据链",
        "hook": "无货源缺的不是票，是证据链",
        "accent": (209, 80, 44),
        "voice_name": "zh-CN-YunjianNeural",
        "subs": ["别只盯着有没有票", "卡住你的，是生意说不清", "订单有了，采购记录呢？", "代发要有聊天和付款", "物流和售后也要对上", "抽十单做自查", "五样证据连起来", "私信：证据链"],
    },
    {
        "name": "电商代账前五问",
        "slug": "dianshang_daizhang_wuwen",
        "script": "scripts/2026-07-10_9dc9207f5a2d_电商代账前五问.md",
        "task": "wyz_20260710_daizhang_wuwen",
        "style": "whiteboard",
        "keyword": "代账",
        "hook": "找代账前，先问这 5 句",
        "accent": (46, 134, 193),
        "voice_name": "zh-CN-YunxiNeural",
        "subs": ["别只问一个月多少钱", "电商账不是普通账", "平台流水按店铺拆吗？", "退款补贴怎么算？", "无票成本留证据吗？", "私户收款会分类吗？", "有没有每月自查表？", "私信：代账"],
    },
    {
        "name": "平台扣点技术服务费",
        "slug": "pingtai_koudian_jishufuwufei",
        "script": "scripts/2026-07-10_5feca26a0ebb_平台扣点技术服务费.md",
        "task": "wyz_20260710_koudian",
        "style": "dashboard",
        "keyword": "扣点",
        "hook": "平台扣点，别只看到账",
        "accent": (37, 99, 235),
        "voice_name": "zh-CN-YunyangNeural",
        "subs": ["不要只当少到账", "成交十万，到账九万多", "扣掉的是平台费用", "技术服务费要说清", "成交、扣点、到账、申报", "四个数对不上就麻烦", "先拉后台结算单", "私信：扣点"],
    },
]


if __name__ == "__main__":
    selected = set(sys.argv[1:])
    for item in ITEMS:
        if selected and item["slug"] not in selected and item["name"] not in selected:
            continue
        item = load_voice(item)
        final, dur = render(item)
        print(f"{final} {dur:.2f}s")
