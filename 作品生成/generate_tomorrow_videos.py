import asyncio
import math
import os
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
OUTPUT_FPS = 60
BRAND = "西安注册公司找峪诚"


def read_section(text, heading):
    pattern = rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.M | re.S)
    return match.group(1).strip() if match else ""


def load_script_config(item):
    script_path = ROOT / item["script"]
    text = script_path.read_text(encoding="utf-8")
    voice = read_section(text, "口播稿")
    keyword_match = re.search(r"私信关键词[：:]\s*([^\n]+)", text)
    if voice:
        item["voice"] = re.sub(r"\s+", "", voice)
    if keyword_match:
        item["keyword"] = keyword_match.group(1).strip(" `。")
    return item


def font(size, bold=True):
    path = FONT_BOLD if bold else FONT_NORMAL
    return ImageFont.truetype(str(path), size)


F = {
    "brand": font(38),
    "small": font(34),
    "body": font(52),
    "body2": font(46),
    "title": font(76),
    "hero": font(92),
    "tag": font(42),
    "num": font(72),
}


def ease(x):
    return 1 - (1 - x) * (1 - x)


def clamp(v, a=0, b=1):
    return max(a, min(b, v))


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


def rounded(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def center_text(draw, box, text, fnt, fill=(255, 255, 255), spacing=12):
    x1, y1, x2, y2 = box
    lines = wrap_text(text, draw, fnt, x2 - x1 - 30)
    heights = [draw.textbbox((0, 0), line, font=fnt)[3] for line in lines]
    total = sum(heights) + spacing * (len(lines) - 1)
    y = y1 + (y2 - y1 - total) / 2
    for line, h in zip(lines, heights):
        bbox = draw.textbbox((0, 0), line, font=fnt)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y), line, font=fnt, fill=fill)
        y += h + spacing


def bg(draw, t, palette):
    base = palette.get("base", (9, 18, 34))
    accent = palette.get("accent", (38, 119, 255))
    img = Image.new("RGB", (W, H), base)
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(14):
        y = int((i * 128 + t * 38) % (H + 180)) - 90
        d.line([(0, y), (W, y - 220)], fill=(*accent, 22), width=2)
    for i in range(32):
        x = int((i * 197 + t * 17) % W)
        y = int((i * 311 + t * 29) % H)
        d.ellipse((x, y, x + 3, y + 3), fill=(255, 255, 255, 36))
    d.ellipse((-260, 180, 500, 940), fill=(*accent, 26))
    d.ellipse((640, 760, 1320, 1480), fill=(*palette.get("accent2", (239, 68, 68)), 20))
    return img.convert("RGB")


def draw_frame_shell(img, idx, total, keyword):
    d = ImageDraw.Draw(img, "RGBA")
    rounded(d, (42, 44, 1038, 118), 20, (5, 10, 22, 210), (255, 255, 255, 30), 1)
    d.text((66, 68), BRAND, font=F["brand"], fill=(255, 255, 255, 245))
    d.text((888, 68), f"{idx}/{total}", font=F["small"], fill=(148, 163, 184, 255))
    rounded(d, (62, 1740, 1018, 1848), 28, (5, 10, 22, 220), (255, 255, 255, 42), 1)
    d.text((98, 1772), f"需要自查工具，私信：{keyword}", font=F["body2"], fill=(255, 255, 255, 255))
    return d


def subtitle(draw, text):
    if not text:
        return
    lines = wrap_text(text, draw, F["body"], 900)[:2]
    y = 1516 - (len(lines) - 1) * 36
    max_w = max(draw.textbbox((0, 0), line, font=F["body"])[2] for line in lines)
    rounded(draw, (70, y - 26, 1010, y + 82 * len(lines)), 20, (3, 7, 18, 210))
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=F["body"])
        draw.text(((W - (bbox[2] - bbox[0])) / 2, y), line, font=F["body"], fill=(255, 255, 255))
        y += 76


def draw_report_scene(d, progress):
    x, y, ww, hh = 92, 260, 896, 1080
    rounded(d, (x, y, x + ww, y + hh), 34, (248, 250, 252, 245), (59, 130, 246, 140), 3)
    d.text((x + 50, y + 52), "电商店铺涉税体检", font=F["title"], fill=(15, 23, 42))
    rows = [("平台成交金额", "订单总额，不只看到账"), ("退款售后金额", "收入别被算高"), ("已申报收入", "和平台数据对齐")]
    for i, (a, b) in enumerate(rows):
        yy = y + 220 + i * 230
        p = clamp(progress * 3 - i)
        rounded(d, (x + 58, yy, x + ww - 58, yy + 156), 24, (255, 255, 255, 255), (203, 213, 225, 255), 2)
        d.ellipse((x + 86, yy + 42, x + 150, yy + 106), fill=(37, 99, 235, int(255 * p)))
        if p > 0.55:
            d.line((x + 104, yy + 72, x + 124, yy + 94, x + 154, yy + 48), fill=(255, 255, 255, 255), width=8)
        d.text((x + 182, yy + 34), a, font=F["tag"], fill=(15, 23, 42))
        d.text((x + 182, yy + 94), b, font=F["small"], fill=(71, 85, 105))
    yy = y + 920
    rounded(d, (x + 58, yy, x + ww - 58, yy + 96), 18, (220, 38, 38, 230))
    center_text(d, (x + 58, yy, x + ww - 58, yy + 96), "差额不是问题，说不清才危险", F["tag"], (255, 255, 255))


def draw_triage_scene(d, progress):
    cards = [
        ("货款进私卡", "高风险", (220, 38, 38)),
        ("老板临时垫款", "要说明", (245, 158, 11)),
        ("亲友临时代收", "最说不清", (220, 38, 38)),
    ]
    for i, (title, risk, color) in enumerate(cards):
        p = clamp(progress * 3 - i)
        yy = 305 + i * 320
        offset = 0
        rounded(d, (96 + offset, yy, 984 + offset, yy + 230), 30, (248, 250, 252, 242), (*color, 170), 3)
        d.text((136 + offset, yy + 42), f"病例 {i + 1}", font=F["small"], fill=(100, 116, 139))
        d.text((136 + offset, yy + 94), title, font=F["title"], fill=(15, 23, 42))
        rounded(d, (700 + offset, yy + 52, 930 + offset, yy + 122), 18, (*color, 235))
        center_text(d, (700 + offset, yy + 52, 930 + offset, yy + 122), risk, F["tag"])
    rounded(d, (108, 1300, 972, 1425), 24, (5, 10, 22, 230), (255, 255, 255, 40), 1)
    center_text(d, (108, 1300, 972, 1425), "先分性质，再谈风险", F["title"])


def draw_relation_scene(d, progress):
    left = 80
    top = 300
    nodes = {
        "店铺A": (left, top),
        "店铺B": (left, top + 260),
        "个人卡": (720, top + 130),
        "公司": (720, top + 420),
        "开票主体": (392, top + 640),
    }
    for name, (x, y) in nodes.items():
        color = (248, 250, 252, 245)
        border = (239, 68, 68, 220) if name == "个人卡" else (59, 130, 246, 160)
        rounded(d, (x, y, x + 270, y + 112), 22, color, border, 3)
        center_text(d, (x, y, x + 270, y + 112), name, F["tag"], (15, 23, 42))
    def arrow(a, b, color):
        ax, ay = a; bx, by = b
        d.line((ax, ay, bx, by), fill=color, width=8)
        ang = math.atan2(by - ay, bx - ax)
        for off in (2.5, -2.5):
            d.line((bx, by, bx - 32 * math.cos(ang + off), by - 32 * math.sin(ang + off)), fill=color, width=8)
    red = (239, 68, 68, 230)
    blue = (59, 130, 246, 230)
    if progress < 0.58:
        arrow((350, top + 56), (720, top + 186), red)
        arrow((350, top + 316), (720, top + 186), red)
        arrow((850, top + 242), (520, top + 640), red)
        rounded(d, (148, 1160, 932, 1268), 24, (127, 29, 29, 230))
        center_text(d, (148, 1160, 932, 1268), "店多不可怕，钱混才可怕", F["title"])
    else:
        arrow((350, top + 56), (720, top + 476), blue)
        arrow((350, top + 316), (520, top + 640), blue)
        rounded(d, (120, 1160, 960, 1268), 24, (30, 64, 175, 230))
        center_text(d, (120, 1160, 960, 1268), "一店一主体一账户一口径", F["title"])
    labels = ["订单归属", "收款账户", "开票主体", "成本归集"]
    for i, label in enumerate(labels):
        x = 102 + (i % 2) * 455
        y = 1335 + (i // 2) * 92
        rounded(d, (x, y, x + 372, y + 66), 16, (15, 23, 42, 230), (255, 255, 255, 36), 1)
        center_text(d, (x, y, x + 372, y + 66), label, F["tag"])


def draw_evidence_scene(d, progress):
    folder = (96, 330, 984, 1225)
    rounded(d, folder, 36, (248, 250, 252, 238), (34, 197, 94, 120), 3)
    d.rectangle((146, 275, 500, 365), fill=(226, 232, 240, 245))
    d.text((150, 292), "费用证据夹", font=F["tag"], fill=(15, 23, 42))
    rounded(d, (140, 430, 940, 540), 26, (254, 242, 242, 255), (239, 68, 68, 190), 3)
    center_text(d, (140, 430, 940, 540), "只有转账，证据不够", F["title"], (127, 29, 29))
    questions = ["为哪个店花？", "谁收的钱？", "能不能入账？"]
    for i, q in enumerate(questions):
        yy = 610 + i * 95
        rounded(d, (150, yy, 930, yy + 68), 18, (127, 29, 29, 220), (255, 255, 255, 40), 1)
        center_text(d, (150, yy, 930, yy + 68), q, F["tag"])
    cards = ["合作截图", "合同协议", "结算单", "后台数据", "付款流水", "发票/收据"]
    for i, label in enumerate(cards):
        p = clamp(progress * 7 - i - 1.4)
        x = 130 + (i % 2) * 420
        y = 900 + (i // 2) * 132
        fill = (240, 253, 244, 245) if p > 0.45 else (241, 245, 249, 170)
        border = (34, 197, 94, 230) if p > 0.45 else (148, 163, 184, 140)
        rounded(d, (x, y, x + 370, y + 92), 20, fill, border, 3)
        if p > 0.45:
            d.ellipse((x + 24, y + 24, x + 68, y + 68), fill=(34, 197, 94, 255))
            d.line((x + 34, y + 47, x + 47, y + 60, x + 68, y + 30), fill=(255, 255, 255, 255), width=6)
        else:
            d.text((x + 32, y + 24), "缺", font=F["small"], fill=(220, 38, 38, 255))
        d.text((x + 92, y + 24), label, font=F["tag"], fill=(15, 23, 42))
    if progress > 0.72:
        rounded(d, (118, 1288, 962, 1396), 24, (20, 83, 45, 235))
        center_text(d, (118, 1288, 962, 1396), "证据能串起来，成本才说得清", F["tag"])


def draw_revenue_scene(d, progress):
    rounded(d, (84, 292, 996, 1268), 34, (248, 250, 252, 238), (59, 130, 246, 145), 3)
    d.text((132, 335), "收入对账台", font=F["title"], fill=(15, 23, 42))
    labels = ["成交", "退款", "补贴", "优惠券", "到账", "申报"]
    values = ["100000", "-12000", "+3000", "-5000", "86000", "82000"]
    for i, (label, value) in enumerate(zip(labels, values)):
        p = clamp(progress * 7 - i)
        x = 132 + (i % 2) * 420
        y = 470 + (i // 2) * 170
        color = (37, 99, 235) if label in ["成交", "到账", "申报"] else (245, 158, 11)
        if p < 0.35:
            color = (148, 163, 184)
        rounded(d, (x, y, x + 350, y + 118), 22, (255, 255, 255, 250), (*color, 180), 3)
        d.text((x + 28, y + 24), label, font=F["tag"], fill=(15, 23, 42))
        d.text((x + 166, y + 24), value, font=F["tag"], fill=color)
    diff_alpha = int(255 * clamp(progress * 3 - 1.1))
    rounded(d, (145, 1010, 935, 1110), 24, (127, 29, 29, diff_alpha), (255, 255, 255, 40), 1)
    if diff_alpha:
        center_text(d, (145, 1010, 935, 1110), "差额不是问题，说不清才危险", F["tag"])
    if progress > 0.76:
        rounded(d, (145, 1155, 935, 1252), 22, (30, 64, 175, 235))
        center_text(d, (145, 1155, 935, 1252), "收入不是看一个数", F["title"])


def draw_threshold_scene(d, progress):
    cx, cy = 540, 620
    d.arc((190, 270, 890, 970), 200, 340, fill=(59, 130, 246, 230), width=28)
    d.arc((190, 270, 890, 970), 315, 340, fill=(239, 68, 68, 240), width=34)
    angle = math.radians(205 + 128 * clamp(progress * 1.05))
    x = cx + 300 * math.cos(angle)
    y = cy + 300 * math.sin(angle)
    d.line((cx, cy, x, y), fill=(255, 255, 255, 255), width=12)
    d.ellipse((cx - 24, cy - 24, cx + 24, cy + 24), fill=(255, 255, 255, 255))
    d.text((338, 480), "500万临界仪表盘", font=F["tag"], fill=(255, 255, 255, 245))
    rounded(d, (370, 700, 710, 790), 22, (127, 29, 29, 230))
    center_text(d, (370, 700, 710, 790), "500 万红线", F["tag"])
    cards = [
        ("进项票", "够不够"),
        ("毛利率", "高不高"),
        ("客户专票", "要不要"),
        ("供应链开票", "配不配合"),
    ]
    for i, (a, b) in enumerate(cards):
        p = clamp(progress * 5 - i - 0.6)
        x = 110 + (i % 2) * 430
        y = 1030 + (i // 2) * 150
        color = (34, 197, 94) if p > 0.55 else (245, 158, 11)
        rounded(d, (x, y, x + 390, y + 106), 22, (248, 250, 252, 242), (*color, 190), 3)
        d.ellipse((x + 24, y + 30, x + 68, y + 74), fill=(*color, 255))
        d.text((x + 92, y + 18), a, font=F["tag"], fill=(15, 23, 42))
        d.text((x + 92, y + 65), b, font=F["small"], fill=(71, 85, 105))
    if progress > 0.78:
        rounded(d, (120, 1345, 960, 1448), 24, (30, 64, 175, 235))
        center_text(d, (120, 1345, 960, 1448), "快到 500 万，先算四件事", F["tag"])


def scene_subtitle(script_lines, p):
    idx = min(len(script_lines) - 1, int(p * len(script_lines)))
    return script_lines[idx]


async def tts(text, out):
    communicate = edge_tts.Communicate(text, "zh-CN-YunyangNeural", rate="+12%")
    await communicate.save(str(out))


def audio_duration(path):
    clip = AudioFileClip(str(path))
    dur = clip.duration
    clip.close()
    return dur


def create_bgm(path, dur):
    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    expr = (
        "aevalsrc=0.018*sin(2*PI*196*t)+"
        "0.012*sin(2*PI*247*t)+"
        "0.008*sin(2*PI*392*t):s=44100"
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", expr, "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(path)],
        check=True,
    )


def render_video(item):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    task = TASK_DIR / item["task"]
    task.mkdir(parents=True, exist_ok=True)
    audio = task / "audio.mp3"
    if not audio.exists():
        asyncio.run(tts(item["voice"], audio))
    dur = max(audio_duration(audio), item.get("min_duration", 38))
    bgm = task / "bgm.wav"
    if item.get("bgm") and not bgm.exists():
        create_bgm(bgm, dur)
    raw = ASSET_DIR / f"{item['slug']}_premium_raw.mp4"
    final = OUT_DIR / f"{item['name']}_premium.mp4"
    writer = imageio.get_writer(
        str(raw),
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    frames = int(math.ceil(dur * FPS))
    for n in range(frames):
        t = n / FPS
        p = t / dur
        img = bg(None, t, item["palette"])
        d = draw_frame_shell(img, item["idx"], item.get("total", 3), item["keyword"])
        rounded(d, (62, 154, 1018, 244), 24, (*item["palette"]["accent"], 230))
        center_text(d, (62, 154, 1018, 244), item["hook"], F["tag"])
        if item["kind"] == "report":
            draw_report_scene(d, p)
        elif item["kind"] == "triage":
            draw_triage_scene(d, p)
        elif item["kind"] == "evidence":
            draw_evidence_scene(d, p)
        elif item["kind"] == "revenue":
            draw_revenue_scene(d, p)
        elif item["kind"] == "threshold":
            draw_threshold_scene(d, p)
        else:
            draw_relation_scene(d, p)
        subtitle(d, scene_subtitle(item["subs"], p))
        writer.append_data(np.asarray(img))
    writer.close()
    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    cmd = [ffmpeg, "-y", "-i", str(raw), "-i", str(audio)]
    if item.get("bgm"):
        cmd += ["-i", str(bgm), "-filter_complex", "[1:a]volume=1.0[a1];[2:a]volume=0.08[a2];[a1][a2]amix=inputs=2:duration=first:dropout_transition=0[aout]", "-map", "0:v:0", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    cmd += [
        "-r", str(OUTPUT_FPS),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)
    ]
    subprocess.run(cmd, check=True)
    return final, dur


ITEMS = [
    {
        "name": "涉税报送三数",
        "script": "scripts/2026-07-07_35708346e2ba_涉税报送三数.md",
        "slug": "shetui_baosong_sanshu",
        "task": "wyz_20260708_shetui_baosong",
        "idx": "01",
        "kind": "report",
        "keyword": "报送",
        "hook": "平台报送后，先查这 3 个数",
        "palette": {"base": (8, 20, 38), "accent": (37, 99, 235), "accent2": (239, 68, 68)},
        "subs": ["平台报送后，先别慌", "先核对三个数", "平台成交金额", "退款和售后金额", "账上已申报收入", "三个数差太多，要能解释", "先看差额，再补证据", "私信：报送"],
    },
    {
        "name": "私户收款三种情况",
        "script": "scripts/2026-07-07_271ed3ef0f93_私户收款三种情况.md",
        "slug": "sihu_shoukuan_sanzhong",
        "task": "wyz_20260708_sihu_shoukuan",
        "idx": "02",
        "kind": "triage",
        "keyword": "私户",
        "hook": "私户收款，先分类型再判断",
        "palette": {"base": (17, 24, 39), "accent": (245, 158, 11), "accent2": (220, 38, 38)},
        "subs": ["私户收款一定有问题吗？", "别先下结论，先分类型", "货款长期进私卡：高风险", "老板临时垫款：要说明", "亲友临时代收：最说不清", "长期、大额、无说明才危险", "先分货款、借款、垫付、报销", "私信：私户"],
    },
    {
        "name": "多店铺多主体",
        "script": "scripts/2026-07-07_13f24bab427f_多店铺多主体.md",
        "slug": "duodianpu_duozhuti",
        "task": "wyz_20260708_duodianpu_duozhuti",
        "idx": "03",
        "kind": "relation",
        "keyword": "多店铺",
        "hook": "店多不可怕，钱混才可怕",
        "palette": {"base": (10, 19, 34), "accent": (59, 130, 246), "accent2": (239, 68, 68)},
        "subs": ["店多不可怕，钱混才可怕", "两个店，一张私卡", "订单和发票错位", "税务看四件事", "订单归属", "收款账户", "开票主体", "成本归集", "先画关系图", "私信：多店铺"],
        "min_duration": 44,
    },
    {
        "name": "达人佣金推广费",
        "script": "scripts/2026-07-09_8d7d9f2c287b_达人佣金推广费.md",
        "slug": "daren_yongjin_tuiguangfei",
        "task": "wyz_20260709_daren_yongjin",
        "idx": "04",
        "total": "04",
        "kind": "evidence",
        "keyword": "佣金",
        "hook": "钱花了，不等于能入账",
        "palette": {"base": (9, 18, 34), "accent": (34, 197, 94), "accent2": (239, 68, 68)},
        "subs": ["钱花了，不等于能入账", "只有转账，证据不够", "达人佣金", "投流推广费", "私域分佣", "为哪个店花？", "谁收的钱？", "能不能入账？", "证据要串成一条线", "私信：佣金"],
        "min_duration": 44,
        "bgm": True,
    },
    {
        "name": "退款补贴优惠券收入",
        "script": "scripts/2026-07-09_716d936cffa6_退款补贴优惠券收入.md",
        "slug": "tuikuan_butie_youhuiquan",
        "task": "wyz_20260709_tuikuan_butie",
        "idx": "05",
        "total": "06",
        "kind": "revenue",
        "keyword": "收入",
        "hook": "到账不等于收入，先对这 6 个数",
        "palette": {"base": (8, 20, 38), "accent": (37, 99, 235), "accent2": (245, 158, 11)},
        "subs": ["别只看到账", "几个数经常不一样", "订单金额", "退款金额", "平台补贴", "优惠券", "实际到账", "已申报收入", "差额要能解释", "私信：收入"],
        "min_duration": 44,
        "bgm": True,
    },
    {
        "name": "五百万一般纳税人",
        "script": "scripts/2026-07-09_b83bc5ff244a_五百万一般纳税人.md",
        "slug": "wubaiwan_yibannashuiren",
        "task": "wyz_20260709_wubaiwan",
        "idx": "06",
        "total": "06",
        "kind": "threshold",
        "keyword": "五百万",
        "hook": "快到 500 万，别等超过才想",
        "palette": {"base": (10, 19, 34), "accent": (59, 130, 246), "accent2": (239, 68, 68)},
        "subs": ["快到 500 万，别等超过才想", "不是只看税率", "进项票够不够", "毛利率高不高", "客户要不要专票", "供应链能不能开票", "不是马上慌", "也不是拖着不管", "先算四件事", "私信：五百万"],
        "min_duration": 44,
        "bgm": True,
    },
]


if __name__ == "__main__":
    selected = set(sys.argv[1:])
    for item in ITEMS:
        if selected and item["slug"] not in selected and item["name"] not in selected:
            continue
        item = load_script_config(item)
        final, dur = render_video(item)
        print(f"{final} {dur:.2f}s")
