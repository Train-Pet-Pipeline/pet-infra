"""Generate Train-Pet-Pipeline-Technical-Overview.pptx next to OVERVIEW.md.

Design brief: professional technical PPT — every slide has a diagram /
table / chart; bullets are supporting, not primary. Consistent color
palette, visual grid, typography hierarchy. Mirrors the 9-chapter
architecture.md template across 9 repos.

Regenerate:
    python pet-infra/docs/architecture/generate_technical_overview_ppt.py
"""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Pt

# ----------------------------------------------------------------------------
# Theme
# ----------------------------------------------------------------------------

# Slide size — widescreen 16:9 in EMUs (1 inch = 914400 EMU)
SLIDE_W = Emu(12192000)  # 13.333 in
SLIDE_H = Emu(6858000)   #  7.5 in

# Color palette (hex → RGB)
NAVY        = RGBColor(0x1A, 0x2A, 0x44)  # primary dark
BLUE        = RGBColor(0x36, 0x7B, 0xD6)  # accent
TEAL        = RGBColor(0x26, 0xA2, 0x9C)  # success / stable
AMBER       = RGBColor(0xED, 0xA8, 0x3E)  # warning / deferred
CORAL       = RGBColor(0xE0, 0x5E, 0x5E)  # breaking / removed
GRAY_700    = RGBColor(0x3C, 0x40, 0x4C)
GRAY_500    = RGBColor(0x78, 0x78, 0x82)
GRAY_300    = RGBColor(0xC8, 0xCC, 0xD2)
GRAY_100    = RGBColor(0xF0, 0xF1, 0xF4)
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)

# Repo-specific accent hues (each ~10% darker variant of a teal/blue family)
REPO_COLORS = {
    "pet-schema":     RGBColor(0x43, 0x5E, 0xB8),
    "pet-infra":      RGBColor(0x2F, 0x6A, 0xB8),
    "pet-data":       RGBColor(0x29, 0x85, 0xA8),
    "pet-annotation": RGBColor(0x26, 0xA2, 0x9C),
    "pet-train":      RGBColor(0x5A, 0xA3, 0x5E),
    "pet-eval":       RGBColor(0x8E, 0xA4, 0x3A),
    "pet-quantize":   RGBColor(0xC2, 0x8E, 0x2E),
    "pet-ota":        RGBColor(0xC2, 0x5E, 0x3E),
    "pet-id":         RGBColor(0x7A, 0x57, 0xA8),
}

# Fonts
FONT_SANS = "Helvetica"
FONT_MONO = "Menlo"


# ----------------------------------------------------------------------------
# Low-level helpers
# ----------------------------------------------------------------------------

def add_rect(slide, x, y, w, h, fill=WHITE, line=None, line_w=0.75, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Emu(x), Emu(y), Emu(w), Emu(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    s.shadow.inherit = False
    return s


def add_text(slide, x, y, w, h,
             text, *,
             size=14, color=NAVY, bold=False, italic=False,
             font=FONT_SANS, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, line_spacing=1.15, wrap=True):
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    tf.vertical_anchor = anchor
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        f = r.font
        f.name = font
        f.size = Pt(size)
        f.color.rgb = color
        f.bold = bold
        f.italic = italic
    return tb


def add_bullets(slide, x, y, w, h, items, *,
                size=14, color=NAVY, bullet_color=BLUE,
                line_spacing=1.35, font=FONT_SANS):
    """Each item is str OR (main_str, sub_str_italic)."""
    tb = slide.shapes.add_textbox(Emu(x), Emu(y), Emu(w), Emu(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Emu(0)
    tf.margin_top = tf.margin_bottom = Emu(0)
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = line_spacing
        # Bullet mark as a small colored square
        r_mark = p.add_run()
        r_mark.text = "▪  "
        r_mark.font.name = font
        r_mark.font.size = Pt(size)
        r_mark.font.color.rgb = bullet_color
        r_mark.font.bold = True
        # Body
        if isinstance(item, tuple):
            main, sub = item
            r_main = p.add_run()
            r_main.text = main
            r_main.font.name = font
            r_main.font.size = Pt(size)
            r_main.font.color.rgb = color
            r_sub = p.add_run()
            r_sub.text = "  — " + sub
            r_sub.font.name = font
            r_sub.font.size = Pt(size - 1)
            r_sub.font.color.rgb = GRAY_500
            r_sub.font.italic = True
        else:
            r = p.add_run()
            r.text = item
            r.font.name = font
            r.font.size = Pt(size)
            r.font.color.rgb = color
    return tb


def add_box(slide, x, y, w, h, text, *,
            fill=WHITE, border=GRAY_300, text_color=NAVY,
            size=13, bold=False, font=FONT_SANS, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            align=PP_ALIGN.CENTER, border_w=0.75, radius=None):
    s = slide.shapes.add_shape(shape, Emu(x), Emu(y), Emu(w), Emu(h))
    s.fill.solid(); s.fill.fore_color.rgb = fill
    s.line.color.rgb = border
    s.line.width = Pt(border_w)
    s.shadow.inherit = False
    # If rounded rect, reduce corner radius for a subtler look
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE and hasattr(s, "adjustments"):
        try:
            s.adjustments[0] = radius if radius is not None else 0.12
        except IndexError:
            pass
    tf = s.text_frame
    tf.margin_left = tf.margin_right = Emu(40000)
    tf.margin_top = tf.margin_bottom = Emu(30000)
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = 1.2
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.color.rgb = text_color
        r.font.bold = bold
    return s


def add_arrow_right(slide, x, y, w, h=None, color=BLUE):
    """Right-facing arrow shape for pipeline flows."""
    if h is None:
        h = 200_000  # slim
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Emu(x), Emu(y), Emu(w), Emu(h))
    s.fill.solid(); s.fill.fore_color.rgb = color
    s.line.fill.background()
    s.shadow.inherit = False
    return s


def add_header_bar(slide, title, subtitle=None, *, accent=BLUE, section_num=None):
    """Consistent top bar: section number tab + title."""
    # Top accent strip
    add_rect(slide, 0, 0, SLIDE_W, 80_000, fill=accent)
    # Section number tab
    if section_num:
        add_text(slide, 460_000, 200_000, 2_000_000, 350_000,
                 section_num, size=11, color=accent, bold=True, font=FONT_SANS)
    # Title
    add_text(slide, 460_000, 420_000, SLIDE_W.emu - 920_000, 600_000,
             title, size=26, color=NAVY, bold=True)
    if subtitle:
        add_text(slide, 460_000, 1_020_000, SLIDE_W.emu - 920_000, 400_000,
                 subtitle, size=13, color=GRAY_500, italic=True)
    # Divider line below header
    add_rect(slide, 460_000, 1_460_000, SLIDE_W.emu - 920_000, 15_000,
             fill=GRAY_300)


def add_footer(slide, repo=None, slide_num=None, total=None):
    # Small footer text
    y = SLIDE_H.emu - 440_000
    add_text(slide, 460_000, y, 5_000_000, 300_000,
             "Train-Pet-Pipeline · Technical Overview · matrix 2026.10-ecosystem-cleanup",
             size=9, color=GRAY_500)
    if slide_num and total:
        add_text(slide, SLIDE_W.emu - 1_400_000, y, 900_000, 300_000,
                 f"{slide_num} / {total}",
                 size=9, color=GRAY_500, align=PP_ALIGN.RIGHT)
    if repo:
        # Repo accent chip, bottom-left
        color = REPO_COLORS.get(repo, BLUE)
        add_rect(slide, 460_000, y - 60_000, 50_000, 220_000, fill=color)
        add_text(slide, 540_000, y - 50_000, 2_000_000, 300_000,
                 repo, size=10, color=color, bold=True, font=FONT_MONO)


# ----------------------------------------------------------------------------
# Slide builders
# ----------------------------------------------------------------------------

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]  # blank


def new_slide():
    return prs.slides.add_slide(BLANK)


# ---- Slide 1: Title ----

def slide_title():
    s = new_slide()
    # Full-bleed navy panel
    add_rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    # Accent strip
    add_rect(s, 0, 4_700_000, SLIDE_W, 8_000, fill=BLUE)
    # Eyebrow
    add_text(s, 820_000, 2_000_000, 8_000_000, 400_000,
             "TECHNICAL OVERVIEW · TRAIN-PET-PIPELINE",
             size=12, color=BLUE, bold=True, font=FONT_SANS)
    # Title
    add_text(s, 820_000, 2_460_000, 10_000_000, 1_100_000,
             "智能宠物喂食器 AI 流水线",
             size=44, color=WHITE, bold=True)
    # Sub-title
    add_text(s, 820_000, 3_550_000, 10_000_000, 600_000,
             "9-repo monorepo · VLM + Audio + On-device Deployment",
             size=18, color=GRAY_300, italic=True)
    # Meta strip
    add_text(s, 820_000, 5_050_000, 10_000_000, 400_000,
             "matrix 2026.10-ecosystem-cleanup",
             size=13, color=BLUE, bold=True, font=FONT_MONO)
    add_text(s, 820_000, 5_420_000, 10_000_000, 400_000,
             "Post-Phase-10 ecosystem optimization closeout · 2026-04-23",
             size=12, color=GRAY_500)
    # Decorative corner mark
    add_rect(s, SLIDE_W.emu - 1_600_000, 800_000, 800_000, 8_000, fill=BLUE)
    add_rect(s, SLIDE_W.emu - 1_600_000, 900_000, 400_000, 4_000, fill=GRAY_500)


# ---- Slide 2: 项目概览 ----

# ---- Slide: Pipeline dataflow diagram (hero) ----

def slide_pipeline_flow():
    s = new_slide()
    add_header_bar(s, "数据流水线",
                   "契约 → 数据 → 标注 → 训练 → 评估 → 量化 → 发布",
                   section_num="§ 0.1 · Pipeline Flow")

    chain = [
        ("pet-schema", "契约"),
        ("pet-data", "采集\n清洗"),
        ("pet-annotation", "4 范式\n打标"),
        ("pet-train", "SFT+DPO\n+Audio"),
        ("pet-eval", "8 指标\n+gate"),
        ("pet-quantize", "RKLLM\n+RKNN"),
        ("pet-ota", "canary\nrollout"),
    ]
    # Horizontal row of labeled boxes
    box_w = 1_340_000
    box_h = 1_050_000
    gap = 140_000
    row_y = 2_300_000
    start_x = (SLIDE_W.emu - (box_w * len(chain) + gap * (len(chain) - 1))) // 2
    for i, (name, role) in enumerate(chain):
        x = start_x + i * (box_w + gap)
        color = REPO_COLORS[name]
        # Box
        add_rect(s, x, row_y, box_w, box_h, fill=WHITE, line=color, line_w=1.5)
        # Top colored strip
        add_rect(s, x, row_y, box_w, 80_000, fill=color)
        # Name (mono)
        add_text(s, x, row_y + 170_000, box_w, 340_000,
                 name, size=12, color=color, bold=True, font=FONT_MONO, align=PP_ALIGN.CENTER)
        # Role
        add_text(s, x, row_y + 540_000, box_w, 480_000,
                 role, size=13, color=NAVY, align=PP_ALIGN.CENTER, line_spacing=1.2)
        # Arrow
        if i < len(chain) - 1:
            arrow_x = x + box_w
            arrow_y = row_y + box_h // 2 - 100_000
            add_arrow_right(s, arrow_x + 10_000, arrow_y, gap - 20_000, 200_000, color=GRAY_500)

    # Side-branch: pet-infra runtime
    infra_color = REPO_COLORS["pet-infra"]
    infra_x = start_x + (box_w * 3 + gap * 3)
    infra_y = row_y - 1_200_000
    add_box(s, infra_x - box_w // 2, infra_y, box_w * 2 + gap, 750_000,
            "pet-infra\n共享运行时 · 7 registries · orchestrator",
            fill=GRAY_100, border=infra_color, text_color=NAVY, size=12, bold=True)
    # Connector down to the main chain (dashed-feel via thin line)
    conn_x = infra_x + box_w // 2 + gap // 2 + 10_000
    add_rect(s, conn_x, infra_y + 750_000, 8_000, row_y - infra_y - 750_000, fill=infra_color)

    # Side-branch: pet-id independent
    pid_color = REPO_COLORS["pet-id"]
    pid_y = row_y + box_h + 500_000
    add_box(s, 660_000, pid_y, SLIDE_W.emu - 1_320_000, 550_000,
            "pet-id · 独立 CLI 工具 · 零 pet-* 运行时依赖 · PetCard registry + petid CLI",
            fill=WHITE, border=pid_color, text_color=pid_color, size=12, bold=True)

    # Legend
    legend_y = pid_y + 750_000
    add_text(s, 660_000, legend_y, 4_000_000, 280_000,
             "实线方块 = 流水线节点 · 虚框 = 独立工具 · pet-infra 作 runtime 贯穿",
             size=10, color=GRAY_500, italic=True)

    add_footer(s, slide_num=3)


# ---- Slide 4: Version matrix ----

def slide_version_matrix():
    s = new_slide()
    add_header_bar(s, "最终版本表",
                   "compatibility_matrix.yaml · 2026.10-ecosystem-cleanup · 9 仓 tag 已推",
                   section_num="§ 0.2 · Versions")

    rows = [
        ("pet-schema",     "v3.2.1", "链首 · 无上游",                "Phase 5 additive: SFTSample + DPOSample"),
        ("pet-infra",      "v2.6.0", "β peer-dep chain",             "Phase 2 compose merge + StageRunner DRY"),
        ("pet-data",       "v1.3.0", "β peer-dep + α for schema",    "Phase 3 ingester_name / default_provenance split"),
        ("pet-annotation", "v2.1.1", "β peer-dep",                    "Phase 4+5 α exporter + F11 validator"),
        ("pet-train",      "v2.0.2", "β peer-dep",                    "Phase 5 β dual guard + JSONL consumer"),
        ("pet-eval",       "v2.3.0", "β + runtime peer for quantize", "Phase 6 ~533 LOC dead-code removal"),
        ("pet-quantize",   "v2.1.0", "β peer-dep (migrated)",         "Phase 7 7A pet-infra hardpin → peer-dep"),
        ("pet-ota",        "v2.2.0", "β peer-dep · signing=optional", "Phase 8 8A + 8B + no-hardcode"),
        ("pet-id",         "v0.2.0", "独立 · 无 pet-* deps",          "Phase 9 first CI + spec §5.2"),
    ]

    # Table-like styled rows
    col_x = [660_000, 2_860_000, 4_200_000, 6_500_000]
    col_w = [2_150_000, 1_300_000, 2_250_000, 4_400_000]
    header_y = 1_800_000
    row_h = 380_000

    # Header
    for i, head in enumerate(["仓库", "版本", "依赖形态", "本轮关键交付"]):
        add_rect(s, col_x[i], header_y, col_w[i], row_h, fill=NAVY)
        add_text(s, col_x[i] + 100_000, header_y, col_w[i] - 100_000, row_h,
                 head, size=12, color=WHITE, bold=True,
                 anchor=MSO_ANCHOR.MIDDLE)

    # Rows
    for ri, (name, ver, mode, delta) in enumerate(rows):
        y = header_y + row_h + ri * row_h
        fill = GRAY_100 if ri % 2 else WHITE
        for ci, w in enumerate(col_w):
            add_rect(s, col_x[ci], y, w, row_h, fill=fill, line=GRAY_300, line_w=0.4)
        # Repo color dot
        color = REPO_COLORS[name]
        add_rect(s, col_x[0] + 80_000, y + row_h // 2 - 80_000, 160_000, 160_000,
                 fill=color, shape=MSO_SHAPE.OVAL)
        add_text(s, col_x[0] + 300_000, y, col_w[0] - 320_000, row_h,
                 name, size=11, color=NAVY, bold=True, font=FONT_MONO,
                 anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, col_x[1] + 100_000, y, col_w[1] - 100_000, row_h,
                 ver, size=11, color=BLUE, bold=True, font=FONT_MONO,
                 anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, col_x[2] + 100_000, y, col_w[2] - 100_000, row_h,
                 mode, size=10.5, color=GRAY_700,
                 anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, col_x[3] + 100_000, y, col_w[3] - 100_000, row_h,
                 delta, size=10, color=GRAY_500, italic=True,
                 anchor=MSO_ANCHOR.MIDDLE)

    add_footer(s, slide_num=4)


# ---- Section divider helper ----

def slide_section_divider(num, title, subtitle, page_range):
    s = new_slide()
    # Dark hero panel
    add_rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    # Accent vertical bar
    add_rect(s, 820_000, 2_000_000, 14_000, 2_800_000, fill=BLUE)
    # Section number
    add_text(s, 1_000_000, 2_000_000, 8_000_000, 550_000,
             f"SECTION {num}", size=13, color=BLUE, bold=True, font=FONT_SANS)
    # Title
    add_text(s, 1_000_000, 2_500_000, 10_000_000, 1_100_000,
             title, size=40, color=WHITE, bold=True)
    # Subtitle
    add_text(s, 1_000_000, 3_750_000, 10_000_000, 500_000,
             subtitle, size=16, color=GRAY_300, italic=True)
    # Page range
    add_text(s, 1_000_000, 4_450_000, 10_000_000, 400_000,
             page_range, size=12, color=BLUE, bold=True, font=FONT_MONO)


# ---- Repo "position" diagram helper (highlight current node in the 9-chain) ----

def draw_position_strip(s, y, current):
    """Mini 9-box strip at given y, highlighting current repo."""
    chain = ["pet-schema", "pet-data", "pet-annotation", "pet-train",
             "pet-eval", "pet-quantize", "pet-ota"]
    # pet-id shown as a floating chip; pet-infra as a band below
    box_w = 950_000
    box_h = 360_000
    gap = 60_000
    total_w = len(chain) * box_w + (len(chain) - 1) * gap
    start_x = (SLIDE_W.emu - total_w) // 2
    for i, name in enumerate(chain):
        x = start_x + i * (box_w + gap)
        is_current = (name == current)
        color = REPO_COLORS[name] if is_current else GRAY_300
        fill = color if is_current else WHITE
        border = color if is_current else GRAY_300
        tcol = WHITE if is_current else GRAY_500
        add_rect(s, x, y, box_w, box_h,
                 fill=fill, line=border, line_w=1.2 if is_current else 0.6)
        add_text(s, x, y, box_w, box_h, name,
                 size=10, color=tcol, bold=is_current,
                 font=FONT_MONO, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        if i < len(chain) - 1:
            add_rect(s, x + box_w + 5_000, y + box_h // 2 - 5_000,
                     gap - 10_000, 10_000, fill=GRAY_300)
    # pet-infra band
    band_y = y + box_h + 120_000
    add_rect(s, start_x, band_y, total_w, 140_000,
             fill=REPO_COLORS["pet-infra"] if current == "pet-infra" else GRAY_100,
             line=REPO_COLORS["pet-infra"],
             line_w=1.2 if current == "pet-infra" else 0.6)
    add_text(s, start_x, band_y, total_w, 140_000,
             "pet-infra · shared runtime",
             size=9,
             color=WHITE if current == "pet-infra" else GRAY_500,
             bold=(current == "pet-infra"),
             font=FONT_MONO, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    # pet-id chip
    chip_x = start_x + total_w - 1_400_000
    chip_y = band_y + 220_000
    is_pid = current == "pet-id"
    add_rect(s, chip_x, chip_y, 1_400_000, 180_000,
             fill=REPO_COLORS["pet-id"] if is_pid else WHITE,
             line=REPO_COLORS["pet-id"],
             line_w=1.2 if is_pid else 0.6,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE)
    add_text(s, chip_x, chip_y, 1_400_000, 180_000,
             "pet-id · independent",
             size=9,
             color=WHITE if is_pid else REPO_COLORS["pet-id"],
             bold=is_pid,
             font=FONT_MONO, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)


# ---- Per-repo slide templates ----

def slide_repo_intro(repo, section_num, title, tagline,
                     does, does_not, page):
    s = new_slide()
    color = REPO_COLORS[repo]
    add_header_bar(s, title, tagline, section_num=section_num, accent=color)

    # Position strip
    draw_position_strip(s, 1_650_000, current=repo)

    # Two-column: Does / Does not
    col_y = 2_600_000
    col_h = 2_900_000
    col_w = 5_100_000
    gap = 280_000
    left_x = 660_000
    right_x = left_x + col_w + gap

    # "做什么"
    add_rect(s, left_x, col_y, col_w, 70_000, fill=color)
    add_text(s, left_x + 160_000, col_y + 140_000, col_w, 380_000,
             "做什么", size=15, color=color, bold=True)
    add_bullets(s, left_x + 160_000, col_y + 560_000, col_w - 160_000, col_h - 600_000,
                does, size=12.5, bullet_color=color)

    # "不做什么"
    add_rect(s, right_x, col_y, col_w, 70_000, fill=GRAY_300)
    add_text(s, right_x + 160_000, col_y + 140_000, col_w, 380_000,
             "不做什么", size=15, color=GRAY_500, bold=True)
    add_bullets(s, right_x + 160_000, col_y + 560_000, col_w - 160_000, col_h - 600_000,
                does_not, size=12.5, color=GRAY_500, bullet_color=GRAY_300)

    add_footer(s, repo=repo, slide_num=page)


def slide_repo_modules(repo, section_num, title, tagline, modules, page, notes=None):
    """modules: list of (category, items) where items is list of (name, desc)."""
    s = new_slide()
    color = REPO_COLORS[repo]
    add_header_bar(s, title, tagline, section_num=section_num, accent=color)

    # Modules as grid of cards grouped by category
    start_y = 1_750_000
    avail_h = SLIDE_H.emu - start_y - 800_000
    n = len(modules)
    col_gap = 220_000
    total_w = SLIDE_W.emu - 1_320_000
    col_w = (total_w - col_gap * (n - 1)) // n

    for ci, (cat, items) in enumerate(modules):
        x = 660_000 + ci * (col_w + col_gap)
        # Category header
        add_rect(s, x, start_y, col_w, 70_000, fill=color)
        add_text(s, x + 160_000, start_y + 120_000, col_w - 160_000, 360_000,
                 cat, size=13, color=color, bold=True)
        # Items
        row_y = start_y + 500_000
        row_h = (avail_h - 500_000) // max(len(items), 1)
        for ri, (name, desc) in enumerate(items):
            y = row_y + ri * row_h
            add_rect(s, x, y + 20_000, col_w, row_h - 60_000,
                     fill=WHITE, line=GRAY_300, line_w=0.5)
            # Name line
            add_text(s, x + 160_000, y + 80_000, col_w - 160_000, 340_000,
                     name, size=11.5, color=NAVY, bold=True, font=FONT_MONO)
            # Desc
            add_text(s, x + 160_000, y + 420_000, col_w - 160_000, row_h - 500_000,
                     desc, size=10, color=GRAY_500, line_spacing=1.3)

    if notes:
        add_text(s, 660_000, SLIDE_H.emu - 720_000, SLIDE_W.emu - 1_320_000, 280_000,
                 notes, size=10, color=GRAY_500, italic=True)

    add_footer(s, repo=repo, slide_num=page)


def slide_repo_design(repo, section_num, title, tagline, designs, page):
    """designs: list of (point, rationale_if_removed)."""
    s = new_slide()
    color = REPO_COLORS[repo]
    add_header_bar(s, title, tagline, section_num=section_num, accent=color)

    # Design points as 2-col rows: point | what would be lost if removed
    table_y = 1_750_000
    row_h = (SLIDE_H.emu - table_y - 900_000) // len(designs)
    left_col_w = 4_600_000
    right_col_w = SLIDE_W.emu - 1_320_000 - left_col_w - 200_000

    for ri, (pt, why) in enumerate(designs):
        y = table_y + ri * row_h
        # Left: point
        add_rect(s, 660_000, y + 40_000, left_col_w, row_h - 80_000,
                 fill=WHITE, line=color, line_w=1.0)
        # Accent strip on left
        add_rect(s, 660_000, y + 40_000, 100_000, row_h - 80_000, fill=color)
        add_text(s, 830_000, y + 100_000, left_col_w - 200_000, row_h - 150_000,
                 pt, size=12, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.3)
        # Right: why / rationale
        right_x = 660_000 + left_col_w + 200_000
        add_rect(s, right_x, y + 40_000, right_col_w, row_h - 80_000,
                 fill=GRAY_100)
        add_text(s, right_x + 180_000, y + 100_000, right_col_w - 300_000, row_h - 150_000,
                 why, size=11, color=GRAY_700, italic=True, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.35)

    add_footer(s, repo=repo, slide_num=page)


# ============================================================================
# Pitch-deck front matter (non-technical framing)
# ============================================================================

def slide_problem():
    """pitch-style: single bold statement + 3 concrete pain cards."""
    s = new_slide()
    # Full-bleed subtle background
    add_rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=GRAY_100)
    # Eyebrow
    add_text(s, 820_000, 700_000, 10_000_000, 400_000,
             "THE PROBLEM", size=12, color=BLUE, bold=True)
    # Hero statement
    add_text(s, 820_000, 1_150_000, 11_500_000, 1_500_000,
             "养宠家庭最大的智能化缺口：\n摄像头能看见，却看不懂。",
             size=34, color=NAVY, bold=True, line_spacing=1.25)

    # Three pain cards
    pains = [
        {
            "num": "01",
            "title": "监控盲区",
            "body": "传统 IP cam 只记录画面；是不是在吃饭 / 有没有呕吐 /\n情绪是否低落，需要主人自己看回放判断",
            "color": CORAL,
        },
        {
            "num": "02",
            "title": "异常事后发现",
            "body": "呕吐、拒食、行为异常往往延时几小时才被察觉；\n急症（异物 / 中毒 / 胰腺炎）黄金窗口错失",
            "color": AMBER,
        },
        {
            "num": "03",
            "title": "投喂与状态脱节",
            "body": "现有喂食器靠定时；宠物状态（刚吐完 / 正在吃 / 外出）\n无法反馈投喂策略。IoT ≠ 智能",
            "color": BLUE,
        },
    ]
    card_y = 3_700_000
    card_h = 2_200_000
    card_w = 3_500_000
    gap = 300_000
    start_x = (SLIDE_W.emu - card_w * 3 - gap * 2) // 2
    for i, p in enumerate(pains):
        x = start_x + i * (card_w + gap)
        add_rect(s, x, card_y, card_w, card_h, fill=WHITE, line=GRAY_300, line_w=0.75)
        # Top color bar
        add_rect(s, x, card_y, card_w, 80_000, fill=p["color"])
        # Big number
        add_text(s, x + 280_000, card_y + 250_000, 1_500_000, 600_000,
                 p["num"], size=36, color=p["color"], bold=True, font=FONT_MONO)
        # Title
        add_text(s, x + 280_000, card_y + 900_000, card_w - 560_000, 450_000,
                 p["title"], size=18, color=NAVY, bold=True)
        # Body
        add_text(s, x + 280_000, card_y + 1_400_000, card_w - 560_000, card_h - 1_500_000,
                 p["body"], size=12, color=GRAY_700, line_spacing=1.5)
    add_footer(s)


def slide_market_why_now():
    """pitch-style: market size 国内+国外 + why now."""
    s = new_slide()
    add_header_bar(s, "市场概况 · 为什么是现在",
                   "宠物经济规模 × 端侧 AI 成熟期 = 新一代智能硬件机会窗",
                   section_num="MARKET & TIMING")

    # Two market columns
    start_y = 1_800_000
    col_h = 2_600_000
    col_w = 5_500_000
    gap = 300_000
    start_x = 660_000
    markets = [
        {
            "region": "中国",
            "color": CORAL,
            "headline": "千亿级别 · 宠物智能硬件年增双位数",
            "facts": [
                "养宠家庭渗透率 持续上升",
                "宠物经济年规模：千亿元量级",
                "智能宠物家居品类：年增 20 – 30%",
                "一线城市高端用户愿付费：健康 / 行为管理",
            ],
        },
        {
            "region": "海外",
            "color": TEAL,
            "headline": "北美/欧洲成熟市场 · AI 是下一增长轴",
            "facts": [
                "北美养宠渗透率 > 60%（全球最高）",
                "人均宠物支出数倍于亚洲",
                "Pet tech 板块获 VC 持续加注",
                "智能摄像头 / 猫砂盆已 commodity，AI 差异化是新维度",
            ],
        },
    ]
    for i, m in enumerate(markets):
        x = start_x + i * (col_w + gap)
        add_rect(s, x, start_y, col_w, col_h, fill=WHITE, line=GRAY_300)
        # Color strip left
        add_rect(s, x, start_y, 110_000, col_h, fill=m["color"])
        # Region title
        add_text(s, x + 280_000, start_y + 200_000, col_w - 400_000, 450_000,
                 m["region"], size=22, color=m["color"], bold=True)
        add_text(s, x + 280_000, start_y + 720_000, col_w - 400_000, 400_000,
                 m["headline"], size=13, color=GRAY_700, italic=True)
        # Facts
        add_bullets(s, x + 280_000, start_y + 1_280_000, col_w - 400_000, col_h - 1_350_000,
                    m["facts"], size=13, bullet_color=m["color"], color=NAVY)

    # Why now band
    why_y = start_y + col_h + 280_000
    add_rect(s, 660_000, why_y, SLIDE_W.emu - 1_320_000, 1_100_000, fill=NAVY)
    add_text(s, 820_000, why_y + 140_000, 6_000_000, 400_000,
             "WHY NOW · 三个因素第一次合流",
             size=12, color=BLUE, bold=True)
    triggers = [
        ("1. VLM 可用", "Qwen2-VL / LLaVA 等开源 VLM 2023-24 成熟\n可在端侧量化后跑行为理解"),
        ("2. 端侧芯片", "RK3576 / 海思 / 高通 等 NPU 量产\n4-6 TOPS 满足 VLM + 音频多模态"),
        ("3. 消费需求", "主人要离线 / 低延迟 / 隐私\n云端方案开始被拒绝"),
    ]
    trig_w = (SLIDE_W.emu - 1_640_000) // 3
    for i, (title, body) in enumerate(triggers):
        tx = 820_000 + i * trig_w
        add_text(s, tx, why_y + 520_000, trig_w - 120_000, 300_000,
                 title, size=13, color=BLUE, bold=True, font=FONT_MONO)
        add_text(s, tx, why_y + 830_000, trig_w - 120_000, 550_000,
                 body, size=10, color=GRAY_300, line_spacing=1.35)

    add_footer(s)


def slide_competitive_map():
    """2×2 positioning map: AI depth × deployment location."""
    s = new_slide()
    add_header_bar(s, "竞品定位 · 2×2 Positioning",
                   "X 轴 · AI 能力深度　|　Y 轴 · 部署位置",
                   section_num="COMPETITIVE LANDSCAPE")

    # Chart area
    chart_x = 2_400_000
    chart_y = 1_850_000
    chart_w = 7_400_000
    chart_h = 4_000_000

    # Chart bg + border
    add_rect(s, chart_x, chart_y, chart_w, chart_h, fill=WHITE, line=GRAY_500, line_w=1.0)
    # Midlines (dashed feel: thin gray)
    mid_x = chart_x + chart_w // 2
    mid_y = chart_y + chart_h // 2
    add_rect(s, mid_x, chart_y, 3_000, chart_h, fill=GRAY_300)
    add_rect(s, chart_x, mid_y, chart_w, 3_000, fill=GRAY_300)

    # Axis labels
    # X-axis
    add_text(s, chart_x, chart_y + chart_h + 140_000, chart_w, 320_000,
             "AI 能力深度  →  基础检测 · · · RFID · · · 云端分类 · · · 端侧 VLM + 多模态",
             size=11, color=GRAY_500, italic=True, align=PP_ALIGN.CENTER)
    # Y-axis (rotate via two ends)
    add_text(s, chart_x - 1_900_000, chart_y + 80_000, 1_800_000, 280_000,
             "☁️  云端部署", size=11, color=GRAY_500, italic=True, align=PP_ALIGN.RIGHT, bold=True)
    add_text(s, chart_x - 1_900_000, chart_y + chart_h - 400_000, 1_800_000, 280_000,
             "📟  端侧部署", size=11, color=GRAY_500, italic=True, align=PP_ALIGN.RIGHT, bold=True)

    # Quadrant labels (subtle, in corners)
    add_text(s, chart_x + 80_000, chart_y + 80_000, 3_000_000, 300_000,
             "Q1  基础 IoT / 云 · · 红海", size=9, color=GRAY_500, bold=True)
    add_text(s, mid_x + 80_000, chart_y + 80_000, 3_000_000, 300_000,
             "Q2  云端 AI · · 隐私与延迟待解", size=9, color=GRAY_500, bold=True)
    add_text(s, chart_x + 80_000, mid_y + 80_000, 3_000_000, 300_000,
             "Q3  端侧但 AI 弱 · · 空档", size=9, color=GRAY_500, bold=True)
    add_text(s, mid_x + 80_000, mid_y + 80_000, 3_000_000, 300_000,
             "Q4  端侧 VLM · · 我们", size=10, color=BLUE, bold=True)

    # Plot competitors (x, y are 0-1 within chart)
    competitors = [
        # (label, x_frac, y_frac, color, size)
        ("Furbo",        0.20, 0.25, GRAY_500, 10),
        ("Petcube",      0.30, 0.20, GRAY_500, 10),
        ("Sure Petcare", 0.15, 0.75, GRAY_500, 10),  # RFID endpoint (端 + 基础)
        ("WOpet",        0.25, 0.28, GRAY_500, 10),
        ("Petnet",       0.28, 0.30, GRAY_500, 10),
        ("PETKIT 小佩",    0.35, 0.60, GRAY_500, 10),
        ("米家",          0.22, 0.68, GRAY_500, 10),
        ("CATLINK",      0.30, 0.63, GRAY_500, 10),
        ("凡米",          0.18, 0.70, GRAY_500, 10),
        # Our position: high AI + edge
        ("Train-Pet-Pipeline", 0.80, 0.80, BLUE, 13),
    ]
    for label, xf, yf, color, fsize in competitors:
        is_us = label == "Train-Pet-Pipeline"
        # Dot
        dot_d = 240_000 if is_us else 160_000
        px = chart_x + int(xf * chart_w) - dot_d // 2
        py = chart_y + int(yf * chart_h) - dot_d // 2
        add_rect(s, px, py, dot_d, dot_d,
                 fill=color if not is_us else BLUE,
                 shape=MSO_SHAPE.OVAL)
        if is_us:
            # Outer ring for emphasis
            ring = 360_000
            add_rect(s, chart_x + int(xf * chart_w) - ring // 2,
                     chart_y + int(yf * chart_h) - ring // 2,
                     ring, ring,
                     fill=WHITE, line=BLUE, line_w=2, shape=MSO_SHAPE.OVAL)
            # Redraw dot on top
            add_rect(s, px, py, dot_d, dot_d, fill=BLUE, shape=MSO_SHAPE.OVAL)
        # Label
        lbl_x = chart_x + int(xf * chart_w) + dot_d // 2 + 50_000
        lbl_y = chart_y + int(yf * chart_h) - 160_000
        add_text(s, lbl_x, lbl_y, 2_400_000, 260_000,
                 label,
                 size=fsize if not is_us else 11,
                 color=BLUE if is_us else GRAY_700,
                 bold=is_us,
                 font=FONT_SANS if is_us else FONT_SANS)

    # Caveat
    add_text(s, 660_000, SLIDE_H.emu - 600_000, SLIDE_W.emu - 1_320_000, 280_000,
             "位置为定性估计；竞品产品线多元，此处以旗舰 AI 品类为代表定位",
             size=9, color=GRAY_500, italic=True)
    add_footer(s)


def slide_competitor_foreign():
    """Table: foreign main competitors."""
    s = new_slide()
    add_header_bar(s, "国外主流竞品 · 能力矩阵",
                   "5 个代表性玩家 × 6 维度 · 数据来自公开产品页 + 用户评测",
                   section_num="FOREIGN COMPETITION")

    headers = ["产品", "定位", "AI 能力", "端侧 / 云", "多模态", "价格带"]
    rows = [
        ["Furbo",         "狗主摄像头 + 零食投掷",   "云端 bark 检测 / 宠物识别",   "☁️ 云端为主",      "视频 + 零食",        "¥1500 – 3000"],
        ["Petcube",       "互动摄像头 + 激光逗猫",   "云端基础识别",                "☁️ 云端",          "视频 + 双向音频",     "¥1000 – 2500"],
        ["Petnet",        "智能喂食器 (初创)",        "基本 IoT + 云端调度",         "☁️ 云端",          "仅投喂",             "¥800 – 2000"],
        ["Sure Petcare",  "Microchip 识别喂食",       "RFID 硬件识别",               "📟 端侧 RFID",    "仅 RFID + 秤",       "¥1200 – 3000"],
        ["WOpet",         "喂食器 + 摄像头捆绑",      "基础动物检测",                "☁️ 云端",          "视频 + 投喂",         "¥600 – 1500"],
    ]
    _draw_comp_table(s, headers, rows, y_start=1_820_000)

    # Takeaway band
    tk_y = SLIDE_H.emu - 1_000_000
    add_rect(s, 660_000, tk_y, SLIDE_W.emu - 1_320_000, 480_000, fill=GRAY_100)
    add_text(s, 820_000, tk_y + 120_000, SLIDE_W.emu - 1_640_000, 280_000,
             "共性 · AI 层级普遍停留在云端基础检测；端侧 VLM 级别行为理解 = 空白市场",
             size=12, color=NAVY, bold=True)
    add_footer(s)


def slide_competitor_china():
    """Table: China competitors."""
    s = new_slide()
    add_header_bar(s, "国内主流竞品 · 能力矩阵",
                   "5 个代表性玩家 × 6 维度 · 国产智能宠物硬件头部阵营",
                   section_num="CHINA COMPETITION")

    headers = ["产品", "定位", "AI 能力", "端侧 / 云", "多模态", "价格带"]
    rows = [
        ["PETKIT 小佩",   "全品类智能宠物硬件",       "摄像头基础识别 + 云端",       "☁️ 云端为主",      "视频 + 投喂 + 饮水",    "¥500 – 2500"],
        ["米家 / 小米",   "米家生态 IoT 产品",        "基础动作识别",                "☁️ 云端",          "视频 + 投喂",           "¥200 – 1000"],
        ["CATLINK 凯特灵", "智能猫砂 + 投喂",         "基础检测 / 数据统计",         "☁️ 云端",          "猫砂 + 体重 + 投喂",    "¥800 – 2500"],
        ["凡米 Fami",     "喂食器专精品牌",           "定时 + 基础识别",             "☁️ 云端",          "仅投喂",                "¥300 – 1200"],
        ["米家生态链 / 其他", "多个白牌",             "基础 IoT",                    "☁️ 云端",          "视频 + 投喂",           "¥200 – 800"],
    ]
    _draw_comp_table(s, headers, rows, y_start=1_820_000)

    tk_y = SLIDE_H.emu - 1_000_000
    add_rect(s, 660_000, tk_y, SLIDE_W.emu - 1_320_000, 480_000, fill=GRAY_100)
    add_text(s, 820_000, tk_y + 120_000, SLIDE_W.emu - 1_640_000, 280_000,
             "共性 · 硬件创新领先，AI 算法栈薄弱；行为理解 / 音频事件 / 结构化报告是下一代竞争点",
             size=12, color=NAVY, bold=True)
    add_footer(s)


def _draw_comp_table(s, headers, rows, y_start):
    """Shared competitor-table renderer."""
    col_widths = [1_700_000, 2_500_000, 2_700_000, 1_700_000, 1_900_000, 1_800_000]
    x0 = (SLIDE_W.emu - sum(col_widths)) // 2
    row_h = 500_000
    header_h = 500_000
    # Header
    cx = x0
    for i, (head, w) in enumerate(zip(headers, col_widths)):
        add_rect(s, cx, y_start, w, header_h, fill=NAVY)
        add_text(s, cx + 120_000, y_start, w - 240_000, header_h,
                 head, size=11, color=WHITE, bold=True, anchor=MSO_ANCHOR.MIDDLE,
                 align=PP_ALIGN.CENTER)
        cx += w
    # Rows
    for ri, row in enumerate(rows):
        y = y_start + header_h + ri * row_h
        fill = GRAY_100 if ri % 2 else WHITE
        cx = x0
        for ci, (val, w) in enumerate(zip(row, col_widths)):
            add_rect(s, cx, y, w, row_h, fill=fill, line=GRAY_300, line_w=0.4)
            bold = ci == 0
            color = NAVY if ci == 0 else GRAY_700
            add_text(s, cx + 120_000, y, w - 240_000, row_h,
                     val, size=10.5, color=color, bold=bold,
                     anchor=MSO_ANCHOR.MIDDLE,
                     align=PP_ALIGN.LEFT if ci <= 1 else PP_ALIGN.LEFT)
            cx += w


def slide_differentiation():
    """Side-by-side: majority of competitors vs us."""
    s = new_slide()
    add_header_bar(s, "我们的差异化",
                   "唯一在端侧落地 VLM-grade 行为理解 + 音频事件 + 签名 OTA 的方案",
                   section_num="DIFFERENTIATION")

    # Two columns: 大多数竞品 vs 我们
    start_y = 1_750_000
    col_h = 3_700_000
    gap = 300_000
    col_w = (SLIDE_W.emu - 1_320_000 - gap) // 2
    left_x = 660_000
    right_x = left_x + col_w + gap

    dimensions = [
        ("AI 能力",          "云端基础动作识别",               "端侧 VLM 行为理解 + 结构化 JSON"),
        ("多模态",           "视频为主，音频不做处理",         "视频 + 音频事件 (呕吐/吃饭/饮水/...)"),
        ("隐私",             "视频传云；隐私合规压力",         "全程端侧推理，视频不出设备"),
        ("延迟",             "2 – 5 秒起（往返云）",           "< 4 秒 P95（本地）"),
        ("可升级",           "厂商云服务耦合",                  "签名 OTA + canary 灰度 + 回滚"),
        ("离线可用",         "断网基本失效",                    "纯端侧能力；网络只用于 OTA"),
    ]

    # Left — majority
    add_rect(s, left_x, start_y, col_w, 90_000, fill=GRAY_500)
    add_text(s, left_x + 200_000, start_y + 160_000, col_w - 400_000, 450_000,
             "大多数竞品", size=18, color=GRAY_500, bold=True)
    add_text(s, left_x + 200_000, start_y + 660_000, col_w - 400_000, 300_000,
             "基础 IoT + 云端", size=11, color=GRAY_500, italic=True)
    # Right — us
    add_rect(s, right_x, start_y, col_w, 90_000, fill=BLUE)
    add_text(s, right_x + 200_000, start_y + 160_000, col_w - 400_000, 450_000,
             "Train-Pet-Pipeline", size=18, color=BLUE, bold=True)
    add_text(s, right_x + 200_000, start_y + 660_000, col_w - 400_000, 300_000,
             "端侧 VLM + 多模态 + 签名 OTA", size=11, color=BLUE, italic=True)

    # Dimension rows
    rows_y = start_y + 1_100_000
    row_h = (col_h - 1_200_000) // len(dimensions)
    for ri, (dim, them, us) in enumerate(dimensions):
        y = rows_y + ri * row_h
        # Dimension tag
        add_text(s, left_x - 700_000, y + 60_000, 640_000, row_h - 80_000,
                 dim, size=10, color=GRAY_500, italic=True, bold=True, align=PP_ALIGN.RIGHT,
                 anchor=MSO_ANCHOR.MIDDLE)
        # Left cell
        add_rect(s, left_x, y + 40_000, col_w, row_h - 80_000,
                 fill=WHITE, line=GRAY_300, line_w=0.5)
        add_text(s, left_x + 200_000, y + 60_000, col_w - 400_000, row_h - 80_000,
                 them, size=11.5, color=GRAY_700, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.3)
        # Right cell
        add_rect(s, right_x, y + 40_000, col_w, row_h - 80_000,
                 fill=WHITE, line=BLUE, line_w=1)
        add_rect(s, right_x, y + 40_000, 60_000, row_h - 80_000, fill=BLUE)
        add_text(s, right_x + 200_000, y + 60_000, col_w - 400_000, row_h - 80_000,
                 us, size=11.5, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE, line_spacing=1.3)

    add_footer(s)


def slide_solution():
    """Big-picture solution: 3-pillar + hardware diagram + stats strip."""
    s = new_slide()
    add_header_bar(s, "解决方案",
                   "一台端侧 AI 设备 · 三大能力柱 · 签名 OTA 闭环",
                   section_num="OUR SOLUTION")

    # Three pillar cards (reused structure from earlier stats-card pattern)
    base_y = 1_800_000
    card_h = 1_700_000
    card_w = 3_450_000
    gap = 320_000
    start_x = (SLIDE_W.emu - card_w * 3 - gap * 2) // 2
    pillars = [
        {
            "icon": "👁",
            "title": "VLM 视觉语言",
            "body": "Qwen2-VL-2B LoRA SFT / DPO\n结构化 JSON (schema_compliance 0.99)\n端侧 RKLLM W4A16",
            "color": BLUE,
        },
        {
            "icon": "🎧",
            "title": "音频事件",
            "body": "PANNs MobileNetV2 AudioSet CNN\n5 类（呕吐 / 吃饭 / 饮水 / 环境 / 其他）\n端侧 RKNN INT8",
            "color": TEAL,
        },
        {
            "icon": "📦",
            "title": "签名 OTA",
            "body": "bsdiff4 差分更新\n5 状态 canary rollout + 48h 观察窗\nSHA-256 manifest + optional RSA 签名",
            "color": AMBER,
        },
    ]
    for i, p in enumerate(pillars):
        x = start_x + i * (card_w + gap)
        add_rect(s, x, base_y, card_w, card_h, fill=WHITE, line=GRAY_300, line_w=0.75)
        add_rect(s, x, base_y, card_w, 110_000, fill=p["color"])
        add_text(s, x + 260_000, base_y + 250_000, 800_000, 600_000,
                 p["icon"], size=28, color=p["color"])
        add_text(s, x + 1_100_000, base_y + 280_000, card_w - 1_300_000, 500_000,
                 p["title"], size=18, color=NAVY, bold=True)
        add_text(s, x + 260_000, base_y + 900_000, card_w - 500_000, card_h - 1_000_000,
                 p["body"], size=11.5, color=GRAY_700, line_spacing=1.5)

    # Hardware side-bar: chip + camera + mic icons
    hw_y = base_y + card_h + 320_000
    add_rect(s, 660_000, hw_y, SLIDE_W.emu - 1_320_000, 1_100_000, fill=NAVY)
    add_text(s, 820_000, hw_y + 140_000, 5_000_000, 400_000,
             "HARDWARE · 设备内置", size=12, color=BLUE, bold=True)
    components = [
        ("🔲", "RK3576 SoC", "6 TOPS NPU · VLM + Audio\n同时推理"),
        ("📷", "Camera", "1080p · 广角\n端侧流入 VLM"),
        ("🎤", "Microphone", "高采样率 mic\n音频事件检测"),
        ("🥣", "Feeder Motor", "定量投喂\n受 VLM 决策驱动"),
    ]
    cw = (SLIDE_W.emu - 1_640_000) // 4
    for i, (icon, name, desc) in enumerate(components):
        cx = 820_000 + i * cw
        add_text(s, cx, hw_y + 560_000, 400_000, 400_000,
                 icon, size=22, color=WHITE)
        add_text(s, cx + 440_000, hw_y + 570_000, cw - 500_000, 300_000,
                 name, size=12, color=WHITE, bold=True, font=FONT_MONO)
        add_text(s, cx + 440_000, hw_y + 840_000, cw - 500_000, 280_000,
                 desc, size=9.5, color=GRAY_300, line_spacing=1.3)

    add_footer(s)


def slide_user_journey():
    """5-step user flow diagram."""
    s = new_slide()
    add_header_bar(s, "用户旅程",
                   "从开箱到日常预警 · 5 步体验",
                   section_num="USER JOURNEY")

    steps = [
        {
            "num": "1",
            "title": "开箱",
            "body": "扫码联网\nLabel Studio 同级简单 setup",
            "color": BLUE,
        },
        {
            "num": "2",
            "title": "注册宠物",
            "body": "录 5-10 秒视频绕宠物一圈\n→ PetCard 生成 (pet-id)",
            "color": TEAL,
        },
        {
            "num": "3",
            "title": "日常监控",
            "body": "VLM 每帧读画面\n音频 CNN 听环境声\n结构化 JSON 上传 App",
            "color": AMBER,
        },
        {
            "num": "4",
            "title": "异常预警",
            "body": "呕吐 / 拒食 / 行为异常\napp 即时通知 + 视频段\n首 30 秒 free",
            "color": CORAL,
        },
        {
            "num": "5",
            "title": "固件升级",
            "body": "签名 OTA canary 推送\n5% → 48h 观察 → 全量\n失败自动回滚",
            "color": REPO_COLORS["pet-ota"],
        },
    ]
    # Horizontal flow with arrows
    box_w = 2_000_000
    box_h = 2_600_000
    gap = 260_000
    total_w = len(steps) * box_w + (len(steps) - 1) * gap
    start_x = (SLIDE_W.emu - total_w) // 2
    row_y = 2_100_000

    for i, st in enumerate(steps):
        x = start_x + i * (box_w + gap)
        # Card
        add_rect(s, x, row_y, box_w, box_h, fill=WHITE, line=GRAY_300, line_w=0.75)
        # Color top band
        add_rect(s, x, row_y, box_w, 100_000, fill=st["color"])
        # Step circle
        circle_d = 560_000
        circle_x = x + box_w // 2 - circle_d // 2
        circle_y = row_y + 200_000
        add_rect(s, circle_x, circle_y, circle_d, circle_d,
                 fill=st["color"], shape=MSO_SHAPE.OVAL)
        add_text(s, circle_x, circle_y, circle_d, circle_d,
                 st["num"], size=26, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=FONT_MONO)
        # Title
        add_text(s, x + 100_000, row_y + 900_000, box_w - 200_000, 400_000,
                 st["title"], size=16, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
        # Body
        add_text(s, x + 200_000, row_y + 1_400_000, box_w - 400_000, box_h - 1_500_000,
                 st["body"], size=10.5, color=GRAY_700, align=PP_ALIGN.CENTER, line_spacing=1.5)
        # Arrow between
        if i < len(steps) - 1:
            arrow_x = x + box_w + 20_000
            arrow_y = row_y + box_h // 2 - 100_000
            add_arrow_right(s, arrow_x, arrow_y, gap - 40_000, 200_000, color=GRAY_300)

    add_footer(s)


# ============================================================================
# Content composition
# ============================================================================

# Front-matter: pitch-deck style
slide_title()
slide_problem()
slide_market_why_now()
slide_competitive_map()
slide_competitor_foreign()
slide_competitor_china()
slide_differentiation()
slide_solution()
slide_user_journey()

# Transition to technical
slide_pipeline_flow()
slide_version_matrix()

# ---- Section A: Contract + Runtime ----

slide_section_divider("A", "契约与运行时", "pet-schema · pet-infra", "Slides 6 – 11")

# pet-schema
slide_repo_intro(
    "pet-schema", "§1 · pet-schema (1/3)", "pet-schema — 契约单一真理源",
    "整个生态的 chain head：所有跨仓数据类型 / 验证规则 / 迁移文件的权威出处",
    does=[
        ("Pydantic v2 数据模型", "Sample / Annotation / ModelCard / ExperimentRecipe / Metric"),
        ("Alembic 数据库迁移", "历史文件 immutable，只能追加新文件"),
        ("SCHEMA_VERSION 常量", "pyproject.toml parity-checked"),
        ("HuggingFace datasets.Features 适配器", "adapters/hf_features.py"),
        ("VLM JSON 运行时校验", "validator.py + SFT/DPO JSONL 契约"),
    ],
    does_not=[
        ("业务逻辑", "训练循环 / 推理 / 标注路由在各下游"),
        ("I/O 操作", "下游通过 store.py，不直连 DB"),
        ("插件注册表", "住在 pet-infra"),
        ("pet-id PetCard", "pet-id 有自己的独立 registry"),
    ],
    page=6,
)

slide_repo_modules(
    "pet-schema", "§1 · pet-schema (2/3)", "pet-schema — 核心模块",
    "5 个域模型 + 验证器 + 迁移，全部 extra='forbid'",
    modules=[
        ("训练契约", [
            ("Sample", "VisionSample / AudioSample\n多模态采样帧"),
            ("SFTSample / ShareGPTSFTSample", "LLaMA-Factory JSONL 契约"),
            ("DPOSample", "preference alignment 对"),
        ]),
        ("编排 + 产物", [
            ("ExperimentRecipe", "Hydra composable recipe\nstages + variations"),
            ("ModelCard", "训练 → eval → quantize → ota\n全链 artifact 元数据"),
            ("EdgeArtifact + QuantConfig", "on-device 产物"),
        ]),
        ("运行时", [
            ("validator.py", "VLM JSON schema 合规检查"),
            ("render_prompt", "train / infer 同源 prompt"),
            ("Alembic migrations/", "DB schema 演化\n历史 immutable"),
        ]),
    ],
    page=7,
)

slide_repo_design(
    "pet-schema", "§1 · pet-schema (3/3)", "pet-schema — 关键设计决策",
    "为什么是链头，为什么 Alembic 历史 immutable",
    designs=[
        ("零 pet-* 上游依赖\nchain head 地位",
         "失去 SSOT — 任何下游可以擅自定义重复的 ModelCard，\n8 仓分别维护契约 → 版本协商地狱"),
        ("Alembic 历史文件 immutable\n只允许追加",
         "失去生产 DB 可重放性 — 修旧 migration 会让历史 deploy\n无法 replay，debug 不了过往数据损坏"),
        ("extra='forbid' 严格校验\nstrict=True pydantic",
         "拒绝未知字段 = 早失败。宽松模式会让下游\n默默累积未验证字段，运行时惊吓"),
    ],
    page=8,
)

# pet-infra
slide_repo_intro(
    "pet-infra", "§2 · pet-infra (1/3)", "pet-infra — 共享运行时",
    "7 个 registry + plugin discovery + compose + orchestrator + storage + replay + CLI",
    does=[
        ("7 个全局 Registry", "TRAINERS / EVALUATORS / CONVERTERS / METRICS / DATASETS / STORAGE / OTA"),
        ("Plugin Discovery", "entry-point group: pet_infra.plugins"),
        ("Config Composition", "compose_recipe() Hydra defaults-list + override"),
        ("Orchestrator", "BaseStageRunner + 5 runners · pet_run()"),
        ("Storage 抽象", "Local / S3 / HTTP 三后端"),
        ("ClearMLLogger + Replay", "W&B 已于 Phase 4 完全移除"),
    ],
    does_not=[
        ("不实现具体 trainer / evaluator", "下游仓注册为 plugin"),
        ("不定义契约类型", "pet-schema 负责"),
        ("不做硬件推理", "pet-quantize 负责"),
        ("不保存训练数据", "pet-data 负责"),
    ],
    page=9,
)

slide_repo_modules(
    "pet-infra", "§2 · pet-infra (2/3)", "pet-infra — 7 Registries + 编排",
    "所有下游仓通过 entry-point 注册 · DAG 驱动 · ClearML 唯一 tracker",
    modules=[
        ("注册表层", [
            ("TRAINERS", "llamafactory_sft / dpo / tiny_test"),
            ("EVALUATORS / METRICS", "8 metrics + 6 evaluators\n(vlm/audio/quantized + 3 fusion)"),
            ("CONVERTERS / DATASETS", "4 + 3 plugins\npet-quantize"),
            ("OTA / STORAGE", "local / s3 / http\n共用 STORAGE schema"),
        ]),
        ("编排层", [
            ("compose.py", "compose_recipe()\nHydra + override"),
            ("orchestrator/", "BaseStageRunner\nDAG 执行器"),
            ("pet_run()", "串行 stage 执行\nResume-from-cache"),
            ("replay.py", "ModelCard 确定性重放"),
        ]),
        ("基础设施", [
            ("storage/", "Local + S3 + HTTP\nURI scheme dispatch"),
            ("ClearMLLogger", "唯一实验追踪"),
            ("cli.py", "pet run / replay / sweep"),
            ("registry.py", "mmengine Registry 基座"),
        ]),
    ],
    page=10,
)

slide_repo_design(
    "pet-infra", "§2 · pet-infra (3/3)", "pet-infra — 关键设计决策",
    "peer-dep 模式 · cross-repo-smoke-install CI 契约",
    designs=[
        ("β peer-dep 模式\n(非 pyproject.dependencies)",
         "失去 CI / dev 装序清晰 — hardpin 会把 pet-infra\n每次 bump 扩散到 7 个下游 pyproject diff"),
        ("cross-repo-smoke-install.yml\n装序矩阵 = 实际行为",
         "失去「文档 = 实际」契约 — OVERVIEW §4 装序表\n会悄悄和各仓 CI 漂移，Phase-N 再发现"),
        ("ClearML 单一 tracker\nno-wandb-residue guard",
         "失去「一套日志工具」确定性 — W&B 加回来就要\n同步 6 仓的 config + logger 抽象"),
    ],
    page=11,
)

# ---- Section B: Data Pipeline ----

slide_section_divider("B", "数据流", "pet-data · pet-annotation", "Slides 13 – 16")

# pet-data
slide_repo_intro(
    "pet-data", "§3 · pet-data (1/2)", "pet-data — 数据采集 + 清洗",
    "7 个 ingester · dedup · quality filter · anomaly scoring · SQLite store",
    does=[
        ("7 种 Ingester", "youtube / community / selfshot / mock / ..."),
        ("Dedup + QualityFilter", "相似度 + 模糊 + 亮度三联闸"),
        ("Anomaly Scoring", "弱监督打分 → 标注任务优先级"),
        ("SQLite Store", "frames + audio_samples 两表\nAlembic 004 migration"),
        ("DATASETS plugin", "VisionSample / AudioSample export"),
    ],
    does_not=[
        ("不做结构化标注", "pet-annotation 负责"),
        ("不训练", "pet-train 负责"),
        ("不 skip dedup", "feedback_no_manual_workaround 铁律"),
        ("不直连 DB", "只通过 store.py"),
    ],
    page=13,
)

slide_repo_design(
    "pet-data", "§3 · pet-data (2/2)", "pet-data — 关键设计决策",
    "概念分离 · immutable migrations · 不跳 dedup",
    designs=[
        ("ingester_name (类名) vs\ndefault_provenance (语义)",
         "Phase 3 生态优化抽出。合并会让 CommunityIngester 默认打\nprovenance=community，SelfshotIngester 继承后变 selfshot,\n混编历史数据的 provenance 永远错"),
        ("dedup 强制执行\n不给 skip 旗标",
         "失去数据质量底线 — 重复帧流入标注会被打多次\n（钱浪费）+ 训练集偏斜"),
        ("Alembic 004 migration 路径\n历史不变只加",
         "生产 DB 的 schema 演化可追溯 + downgrade/upgrade 可重放\n删旧 migration 会让过去的 deploy 无法恢复"),
    ],
    page=14,
)

# pet-annotation
slide_repo_intro(
    "pet-annotation", "§4 · pet-annotation (1/2)", "pet-annotation — 4 范式打标引擎",
    "LLM / classifier / rule / human 并行打标 · SFT/DPO JSONL 导出",
    does=[
        ("拉 pending targets", "从 pet-data frames 表只读"),
        ("4 范式并行打标", "LLM + classifier + rule + human"),
        ("AnnotationOrchestrator", "并发调度 (target × annotator) 组合"),
        ("写 4 范式各自表", "每 annotator 独立列不融合"),
        ("export SFT/DPO JSONL", "sft_dpo.py → pet-train 消费"),
        ("Label Studio 1.23 integration", "session auth + import/export"),
    ],
    does_not=[
        ("不 ingest 原始数据", "pet-data 负责"),
        ("不训练模型", "pet-train 负责"),
        ("不写 pet-data DB", "只读跨仓"),
        ("不跨 annotator reconcile", "D4 决策：独立存储"),
    ],
    page=15,
)

slide_repo_design(
    "pet-annotation", "§4 · pet-annotation (2/2)", "pet-annotation — 关键设计决策",
    "4 范式独立存 · α 导出 · producer-side 校验",
    designs=[
        ("4 annotator 各写各表\n不做 majority-vote 融合",
         "失去真值集构建灵活度 — 融合策略应属评估阶段\n而不是固化在数据层。未来 voting / bayesian fusion\n可以上层做，下层保留原始数据是前提"),
        ("α 方向导出\n重写为 LLaMA-Factory JSONL",
         "Phase 5 决策：pet-annotation 内部不做 backward compat shim\n消费方 pet-train 直接用 LlamaFactory run_sft/run_dpo 契约"),
        ("F11 producer-side validator\n导出前 DPOSample.model_validate()",
         "失去与下游 consumer (pet-train) 的验证冗余 —\n分工契约是「双端都验」，单端跳过坏数据流到训练"),
    ],
    page=16,
)

# ---- Section C: Training + Eval ----

slide_section_divider("C", "训练与评估", "pet-train · pet-eval", "Slides 18 – 23")

# pet-train
slide_repo_intro(
    "pet-train", "§5 · pet-train (1/3)", "pet-train — 训练引擎",
    "3 trainer 插件 + audio PANNs · 输出 ModelCard 给下游",
    does=[
        ("llamafactory_sft", "VLM SFT fine-tuning (LoRA)"),
        ("llamafactory_dpo", "preference alignment (pref_beta=0.1)"),
        ("tiny_test", "CPU-only smoke (< 2min)"),
        ("PANNs audio", "MobileNetV2AudioSet + AudioInference\n被 pet-eval 跨仓 import"),
        ("F11 consumer validator", "SFT/DPO JSONL 训练前校验"),
        ("ModelCard output", "checkpoint_uri + 运行时 metrics"),
    ],
    does_not=[
        ("不标注数据", "pet-annotation 负责"),
        ("不评估 gate", "pet-eval 负责"),
        ("不转换端侧格式", "pet-quantize 负责"),
        ("不维护 LLaMA-Factory 上游", "vendor 只冻结 v0.9.4"),
    ],
    page=18,
)

slide_repo_modules(
    "pet-train", "§5 · pet-train (2/3)", "pet-train — 核心模块",
    "vendor/LLaMA-Factory@v0.9.4 · lazy import 屏蔽上游脆弱",
    modules=[
        ("Trainer Plugins", [
            ("llamafactory_sft", "run_sft 包装\nlora_r/alpha/lr from params"),
            ("llamafactory_dpo", "run_dpo 包装\npref_beta + sft_adapter_path"),
            ("tiny_test", "CPU 2min smoke\nPR-gate 验证"),
        ]),
        ("Audio 子系统", [
            ("MobileNetV2AudioSet", "PANNs 527 class head\nhardcoded (不可改)"),
            ("AudioInference", "zero-shot classification\n5 类 → eating/drinking/..."),
            ("from_params", "factory · 所有数值\n从 params.yaml 读"),
        ]),
        ("数据 + 契约", [
            ("data_validation.py", "validate_sft_jsonl\nvalidate_dpo_jsonl F11"),
            ("Lazy run_sft import", "module-load 不拉\nllamafactory (脆弱)"),
            ("_register.py", "β dual guard\n+ fail-fast"),
        ]),
    ],
    page=19,
    notes="vendored LLaMA-Factory：git clone 即有，无需 submodule update；NOTICE 记录 Apache-2.0 来源",
)

slide_repo_design(
    "pet-train", "§5 · pet-train (3/3)", "pet-train — 关键设计决策",
    "vendor / lazy import / num_classes=527 / JSONL 后缀校验",
    designs=[
        ("LLaMA-Factory plain-directory vendor\n(不做 submodule)",
         "git clone + git pull 即完整可跑。submodule 要\nrecursive update 每步都有人忘 → CI 红。NOTICE\n记 Apache-2.0 attribution"),
        ("num_classes=527 硬编码\ndocstring 显式警告",
         "PANNs AudioSet 固定 527 类 taxonomy。改这数就导致\n模型 load_state_dict 形状不匹配。从 params 传会\n让运维默默 load 一个随机初始化 head，静默退化"),
        ("JSONL validator 只校 .jsonl 后缀\n非 .jsonl 静默通过",
         "未来 Parquet / Arrow 是合理演进 —— 到时候给新格式\n注册新 validator。现在强制 .jsonl 会挡住所有新格式"),
    ],
    page=20,
)

# pet-eval
slide_repo_intro(
    "pet-eval", "§6 · pet-eval (1/3)", "pet-eval — 评估 + gate",
    "8 metrics + 6 evaluators (3 primary + 3 fusion) · rule-based only",
    does=[
        ("8 metrics", "schema / anomaly / mood / narrative\nlatency / audio / kl / calibration"),
        ("VLMEvaluator", "LoRA adapter merge + gold set"),
        ("AudioEvaluator", "跨仓 import pet_train.audio"),
        ("QuantizedVlmEvaluator", "跨仓 import pet_quantize.rkllm_runner"),
        ("3 rule-based fusion", "single_modal / and_gate / weighted"),
        ("apply_gate(min_*/max_*)", "通过/失败 + reason"),
    ],
    does_not=[
        ("不训练 checkpoint", "pet-train 负责"),
        ("不量化转换", "pet-quantize 负责"),
        ("不做 learned fusion", "feedback_no_learned_fusion"),
        ("不做实验 tracking", "orchestrator + ClearMLLogger"),
    ],
    page=21,
)

slide_repo_modules(
    "pet-eval", "§6 · pet-eval (2/3)", "pet-eval — Registry 全景",
    "METRICS × 8 + EVALUATORS × 6 · 所有通过 @register_module 装饰注册",
    modules=[
        ("Metrics (8)", [
            ("schema_compliance", "VLM JSON 合规率 + 分布和差"),
            ("anomaly_recall", "异常召回 + FPR"),
            ("mood_correlation", "mood_spearman 3 维"),
            ("narrative_quality", "BERTScore F1 (Chinese)"),
            ("latency / audio / kl / calibration", "P95 / accuracy / KL / ECE"),
        ]),
        ("Primary Evaluators (3)", [
            ("vlm_evaluator", "LoRA merge + gold set inference"),
            ("audio_evaluator", "classify 5 class via pet_train"),
            ("quantized_vlm_evaluator", "RKLLMRunner lifecycle\ninit/generate/release"),
        ]),
        ("Fusion Evaluators (3)", [
            ("single_modal_fusion", "pass-through"),
            ("and_gate_fusion", "全 ≥ threshold\n否则 0"),
            ("weighted_fusion", "normalized weighted sum"),
        ]),
    ],
    page=22,
)

slide_repo_design(
    "pet-eval", "§6 · pet-eval (3/3)", "pet-eval — 关键设计决策",
    "_FALLBACK_OUTPUT / 双 prompt_source / 跨仓 lazy import",
    designs=[
        ("_FALLBACK_OUTPUT 50-line\n硬编码安全 JSON",
         "retry_on_failure=true 且重试仍无效时 emit。\n换 None 会让所有 metric 都要 null 分支;\n换 skip 会让合规率分母错"),
        ("prompt_source: 'gold_set' | 'pet_schema'\n双轨支持",
         "sft_v2 embeds full prompt in gold records;\nsft_v3+ 用 pet_schema.render_prompt 的短 prompt。\n两代模型都要能评估"),
        ("跨仓 runtime import\npet_train.audio / pet_quantize.rkllm",
         "AudioEvaluator / QuantizedVlmEvaluator 真正\n要跑这些。复制契约到 pet-eval 会违反 SSOT。\n导入 lazy 防 module-load 拉 SDK"),
    ],
    page=23,
)

# ---- Section D: Edge + Delivery ----

slide_section_divider("D", "端侧与发布", "pet-quantize · pet-ota", "Slides 25 – 30")

# pet-quantize
slide_repo_intro(
    "pet-quantize", "§7 · pet-quantize (1/3)", "pet-quantize — 量化 + 打包签名",
    "4 CONVERTERS + 3 DATASETS + 2 dual-mode inference runners",
    does=[
        ("vlm_rkllm_w4a16", "VLM → RKLLM W4A16 for RK3576"),
        ("audio_rknn_fp16", "audio CNN → RKNN FP16"),
        ("vision_rknn_fp16", "ViT → RKNN FP16"),
        ("noop_converter", "零 SDK CI smoke"),
        ("3 calibration DATASETS", "content-addressed cache"),
        ("RKLLMRunner / RKNNRunner", "PC sim ↔ on-device ADB dual-mode"),
        ("packaging: tarball + manifest + sign", "SHA-256 + 可选签名"),
    ],
    does_not=[
        ("不训练", "pet-train 负责"),
        ("不做 gate 决策", "pet-eval 负责"),
        ("不发布到设备", "pet-ota 负责"),
        ("不强制装 RK SDK", "PET_ALLOW_MISSING_SDK=1 逃生"),
    ],
    page=25,
)

slide_repo_modules(
    "pet-quantize", "§7 · pet-quantize (2/3)", "pet-quantize — SDK-gated cluster 图",
    "rknn / rkllm 两个 SDK 簇 + noop always-available",
    modules=[
        ("Always-available", [
            ("noop_converter", "零 SDK · CI smoke\n产确定性 fake EdgeArtifact"),
        ]),
        ("rknn cluster", [
            ("audio_rknn_fp16", "FP16 · 无需 calib"),
            ("vision_rknn_fp16", "FP16 opt_level=3\n输出 ONNX + RKNN"),
            ("audio/vision calibration_subset", "DATASETS"),
        ]),
        ("rkllm cluster", [
            ("vlm_rkllm_w4a16", "W4A16 · 需 calib batch"),
            ("vlm_calibration_subset", "DATASETS\n(num_samples, 2048) int64"),
            ("RKLLMRunner", "init/generate/release\n被 pet-eval 跨仓引用"),
        ]),
    ],
    page=26,
    notes="register_all: try/except ImportError → re-raise UNLESS PET_ALLOW_MISSING_SDK=1 → logger.warning + skip cluster",
)

slide_repo_design(
    "pet-quantize", "§7 · pet-quantize (3/3)", "pet-quantize — 关键设计决策",
    "SDK cluster · dual-mode · content-addressable cache",
    designs=[
        ("SDK-gated cluster + 逃生旗标\nPET_ALLOW_MISSING_SDK=1",
         "Rockchip vendor wheels 不在 PyPI。强制装会破\n所有非 vendor 环境；强制跳会让 mock 蔓延。\ncluster 按 SDK 分组精细降级"),
        ("RKLLMRunner 双模\n(PC simulated ↔ ADB on-device)",
         "硬件未到 CI 前，pet-eval 的 quantized_vlm_evaluator\n就能本地走通全路径。硬件接入时 flip target+device_id\n代码不变"),
        ("DATASETS cache key\nsha256(modality|source_uri|num_samples)",
         "orchestrator resume-from-cache 依赖确定性 card_id。\n带时间戳的文件名会让 stage_config_sha 每次漂。\ncache 命中 = 几分钟 vs 几小时"),
    ],
    page=27,
)

# pet-ota
slide_repo_intro(
    "pet-ota", "§8 · pet-ota (1/3)", "pet-ota — 发布 + canary rollout",
    "3 OTA backends + 5-state FSM · resume-from-state · optional signing",
    does=[
        ("local / s3 / http backends", "3 个 OTA registry plugins"),
        ("canary_rollout FSM", "5 states · 48h observation window"),
        ("resume-from-state", "deployments/<id>.json 续跑"),
        ("manifest SHA-256 verify", "每 tarball 校验"),
        ("bsdiff4 delta + tenacity retry", "大文件 IO flake 3 次重试"),
        ("monitoring + alert", "update_rate + alert hook"),
        ("optional signing", "lazy import pet_quantize.verify"),
    ],
    does_not=[
        ("不量化转换", "pet-quantize 负责"),
        ("不签名", "signing optional · 缺 pet-quantize 软降级"),
        ("不做实验 tracking", "orchestrator 负责"),
        ("不 depend on RK SDK", "pet-ota 纯 Python"),
    ],
    page=28,
)

slide_repo_modules(
    "pet-ota", "§8 · pet-ota (2/3)", "pet-ota — Canary rollout 5-state FSM",
    "两套 backend 共存: OTA registry plugin (artifact) + LocalBackend (stateful)",
    modules=[
        ("OTA Registry Plugins", [
            ("local_backend", "shutil.copy2 + manifest.json"),
            ("s3_backend", "boto3 + STORAGE registry\n(file/local/s3/http source)"),
            ("http_backend", "PUT + bearer/basic/no-auth"),
        ]),
        ("Canary FSM", [
            ("gate_check", "5 checks · eval_passed\ndpo_pairs ≥ min_* from params"),
            ("canary_deploying/observing", "canary_percentage=5%\nobserve=48h"),
            ("full_deploying / rolling_back", "rollback_timeout=5min\nfailure_rate=0.10"),
        ]),
        ("Packaging + Monitoring", [
            ("make_delta.py", "bsdiff4 + tenacity retry(3)"),
            ("upload_artifact.py", "SHA-256 verify\nlazy pet_quantize signing"),
            ("check_update_rate", "device pending timeout"),
        ]),
    ],
    page=29,
    notes="legacy backend/LocalBackend (stateful) 驱动 FSM; plugins/backends/LocalBackendPlugin 做 artifact 发布。职责不重叠",
)

slide_repo_design(
    "pet-ota", "§8 · pet-ota (3/3)", "pet-ota — 关键设计决策",
    "双 backend · resume-from-state · bsdiff4 retry",
    designs=[
        ("两套 backend surface 共存",
         "registry plugin = artifact 发布；legacy LocalBackend =\nstateful deployment orchestration。合并会把\ndeployment 生命周期拖进 OTA registry，耦合大无收益"),
        ("canary resume-from-state\ndeployments/<id>.json 续跑",
         "canary_observe_hours=48 默认。crash 后不续跑\n会把观察进度清零 + 可能双发设备。\ndurable FSM 是 rollout 安全前提"),
        ("bsdiff4 tenacity retry(3, 1s)\nreraise=True",
         "大 tarball (几百 MB) 经常 OOM/IO flaky。\n3 次重试从真实 incident 校准，不是 defensive slop。\nreraise 保留 bsdiff4 原 error stack"),
    ],
    page=30,
)

# ---- Section E: Independent Tool ----

slide_section_divider("E", "独立工具", "pet-id", "Slides 32 – 33")

# pet-id
slide_repo_intro(
    "pet-id", "§9 · pet-id (1/2)", "pet-id — 独立 CLI 工具",
    "零 pet-* 运行时依赖 (spec §5.2) · PetCard registry + petid CLI",
    does=[
        ("petid register", "photo / dir / video → PetCard"),
        ("petid identify", "query image → pet_id / name"),
        ("petid list / show / delete", "gallery CRUD"),
        ("purrai_core 算法核心", "detector / reid / pose\nnarrative / tracker 5 backends"),
        ("PetCard (Pydantic)", "独立 model · 不在 pet-schema"),
        ("content-addressable pet_id", "sha256(L2-normed f32)[:8]"),
    ],
    does_not=[
        ("不 import 任何 pet-* 包", "grep -rn 'from pet_' src/ → 0 hits"),
        ("不是 pet-infra plugin", "无 entry-point 注册"),
        ("不做硬件部署", "pet-id 纯 host-side"),
        ("不入 matrix 装序", "仅入 matrix 做版本对齐报告"),
    ],
    page=32,
)

slide_repo_design(
    "pet-id", "§9 · pet-id (2/2)", "pet-id — 关键设计决策",
    "两包分层 · 5 extras · 独立性 · content-addressable id",
    designs=[
        ("pet_id_registry + purrai_core\n两包分层 (不合成单包)",
         "purrai_core 从 pet-demo/core 引导；可独立复用给\n未来其他 CLI。合成单包会强迫消费纯算法的用户\n连带 CLI + 磁盘 gallery"),
        ("5 extras + meta `all`\n(detector/reid/pose/narrative/tracker)",
         "每 backend 百 MB 级 ML 依赖。只用 register/identify\n的用户 pip install pet-id[detector,reid] ~500MB\n装全 5 GB+"),
        ("compute_pet_id L2-normalize assert\n+ little-endian float32 canonicalize",
         "跨 host (amd64/arm64) 跨 dtype (fp16/fp32) 同一\nembedding → 同一 pet_id。否则 registry migration\n时 id 飘，调试地狱"),
    ],
    page=33,
)

# ---- Section F: Cross-cutting ----

slide_section_divider("F", "横切关注点", "依赖治理 · CI · 北极星", "Slides 35 – 37")

# Dependency governance
def slide_dep_governance():
    s = new_slide()
    add_header_bar(s, "依赖治理：3 种 pin 模式",
                   "生态优化收敛：从 6 种 ad-hoc 统一到 3 种 disciplined",
                   section_num="§ 10 · 横切 / 依赖")

    # Three columns
    start_y = 1_800_000
    col_h = 3_600_000
    col_w = 3_500_000
    gap = 300_000
    start_x = (SLIDE_W.emu - (col_w * 3 + gap * 2)) // 2

    styles = [
        {
            "name": "α 硬 pin",
            "subtitle": "pyproject.dependencies 写 git URL @vX.Y.Z",
            "color": CORAL,
            "applies": "pet-eval / pet-quantize / pet-ota\n(signing extras excepted)",
            "reasoning": [
                "适合：稳定契约型依赖",
                "如 pet-schema (consumers 当作数据类型)",
                "每 tag bump 需显式改 pyproject",
                "优势：pip 直装即可，CI 简单",
            ],
        },
        {
            "name": "β peer-dep",
            "subtitle": "不在 pyproject.dependencies；CI Step-1 explicit install",
            "color": TEAL,
            "applies": "pet-infra / pet-data / pet-annotation\npet-train / pet-eval / pet-quantize / pet-ota\n(相对 pet-infra 都是 β)",
            "reasoning": [
                "适合：频繁迭代型 peer",
                "如 pet-infra (版本常改)",
                "delayed RuntimeError guard in register_all()",
                "优势：裸 import 轻量 (IDE/静态分析)",
            ],
        },
        {
            "name": "跨仓 plugin no-pin",
            "subtitle": "pyproject 写 `pet-xxx` 不带版本",
            "color": BLUE,
            "applies": "pet-eval → pet-train, pet-quantize\npet-ota[signing] → pet-quantize",
            "reasoning": [
                "适合：跨仓 runtime plugin dep",
                "版本由 matrix row 锁定",
                "CI 显式装矩阵版本",
                "优势：plugin 发现松耦合",
            ],
        },
    ]
    for i, st in enumerate(styles):
        x = start_x + i * (col_w + gap)
        add_rect(s, x, start_y, col_w, col_h, fill=WHITE, line=GRAY_300)
        # Header
        add_rect(s, x, start_y, col_w, 90_000, fill=st["color"])
        add_text(s, x + 160_000, start_y + 180_000, col_w - 320_000, 480_000,
                 st["name"], size=20, color=st["color"], bold=True)
        add_text(s, x + 160_000, start_y + 680_000, col_w - 320_000, 480_000,
                 st["subtitle"], size=10, color=GRAY_500, italic=True, line_spacing=1.3)
        # Applies
        add_rect(s, x + 160_000, start_y + 1_280_000, col_w - 320_000, 10_000, fill=GRAY_300)
        add_text(s, x + 160_000, start_y + 1_340_000, col_w - 320_000, 300_000,
                 "适用仓库", size=10, color=GRAY_500, bold=True)
        add_text(s, x + 160_000, start_y + 1_640_000, col_w - 320_000, 800_000,
                 st["applies"], size=11, color=NAVY, line_spacing=1.4, font=FONT_MONO)
        # Reasoning
        add_bullets(s, x + 160_000, start_y + 2_550_000, col_w - 320_000, 980_000,
                    st["reasoning"], size=10.5, bullet_color=st["color"])

    add_footer(s, slide_num=35)


# CI guards matrix
def slide_ci_guards():
    s = new_slide()
    add_header_bar(s, "CI Guard 矩阵",
                   "生态优化把 5 类 workflow 一致化到 9 仓",
                   section_num="§ 10 · 横切 / CI")

    repos = ["pet-schema", "pet-infra", "pet-data", "pet-annotation",
             "pet-train", "pet-eval", "pet-quantize", "pet-ota", "pet-id"]
    workflows = [
        ("ci.yml", "lint + mypy + pytest"),
        ("peer-dep-smoke.yml", "独立装序 smoke"),
        ("no-wandb-residue.yml", "positive-list 扫 \\bwandb\\b"),
        ("schema_guard.yml", "pet-schema dispatch 全链"),
        ("cross-repo-smoke-install.yml", "matrix row 装序验证"),
    ]
    # Presence grid: cell value = True/False or special
    grid = {
        # repo, workflow idx -> "Y"/"N"/"."
        "pet-schema": ["Y", ".", ".", "Y", "."],  # schema_guard source
        "pet-infra": ["Y", "Y", "Y", ".", "Y"],
        "pet-data": ["Y", "Y", ".", ".", "."],  # 未加 no-wandb 因从未触过 W&B
        "pet-annotation": ["Y", "Y", ".", ".", "."],
        "pet-train": ["Y", "Y", "Y", ".", "."],
        "pet-eval": ["Y", "Y", "Y", ".", "."],
        "pet-quantize": ["Y", "Y", "Y", ".", "."],
        "pet-ota": ["Y", "Y", "Y", ".", "."],
        "pet-id": ["Y", ".", "Y", ".", "."],  # 独立工具无 peer-dep-smoke
    }

    # Layout
    left_label_w = 1_700_000
    cell_w = 1_720_000
    cell_h = 380_000
    header_y = 1_800_000
    grid_start_x = 660_000 + left_label_w

    # Column headers
    for i, (wf, desc) in enumerate(workflows):
        x = grid_start_x + i * cell_w
        add_rect(s, x, header_y, cell_w, cell_h + 120_000, fill=NAVY)
        add_text(s, x + 80_000, header_y + 50_000, cell_w - 160_000, 240_000,
                 wf, size=9.5, color=WHITE, bold=True, font=FONT_MONO, align=PP_ALIGN.CENTER)
        add_text(s, x + 80_000, header_y + 280_000, cell_w - 160_000, 220_000,
                 desc, size=8, color=GRAY_300, align=PP_ALIGN.CENTER, italic=True)

    # Rows
    for ri, repo in enumerate(repos):
        y = header_y + cell_h + 120_000 + ri * cell_h
        # Repo label
        color = REPO_COLORS[repo]
        add_rect(s, 660_000, y, left_label_w, cell_h,
                 fill=WHITE, line=GRAY_300, line_w=0.5)
        add_rect(s, 660_000, y, 100_000, cell_h, fill=color)
        add_text(s, 790_000, y, left_label_w - 150_000, cell_h,
                 repo, size=10, color=NAVY, bold=True, font=FONT_MONO,
                 anchor=MSO_ANCHOR.MIDDLE)
        # Cells
        for ci in range(len(workflows)):
            x = grid_start_x + ci * cell_w
            mark = grid[repo][ci]
            fill = WHITE
            line = GRAY_300
            if mark == "Y":
                fill = RGBColor(0xE7, 0xF4, 0xEE)  # light teal bg
                line = TEAL
            add_rect(s, x, y, cell_w, cell_h, fill=fill, line=line, line_w=0.5)
            if mark == "Y":
                add_text(s, x, y, cell_w, cell_h, "✓",
                         size=16, color=TEAL, bold=True,
                         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
            else:
                add_text(s, x, y, cell_w, cell_h, "—",
                         size=13, color=GRAY_300, bold=True,
                         align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    add_text(s, 660_000, SLIDE_H.emu - 820_000, SLIDE_W.emu - 1_320_000, 280_000,
             "✓ = 已接入；— = 该仓无需要（如 pet-id 独立无 peer-dep / pet-schema 无下游 peer-dep smoke）",
             size=9.5, color=GRAY_500, italic=True)
    add_footer(s, slide_num=36)


def slide_northstar():
    s = new_slide()
    add_header_bar(s, "北极星四维度",
                   "生态优化 Phase 10 retrospective · 维持或提升，无退化",
                   section_num="§ 10 · 横切 / North Star")

    dims = [
        {
            "name": "Pluggability",
            "tagline": "插件化程度",
            "score": 5,
            "evidence": [
                "7 registries 覆盖 TRAINERS / EVALUATORS /",
                "CONVERTERS / METRICS / DATASETS / STORAGE / OTA",
                "每仓插件 entry-point 注册; orchestrator 发现加载",
            ],
            "color": BLUE,
        },
        {
            "name": "Flexibility",
            "tagline": "配置灵活性",
            "score": 5,
            "evidence": [
                "所有数值从 params.yaml 读（no-hardcode 铁律）",
                "ExperimentRecipe.variations ablation sweep",
                "Hydra defaults-list + override 组合",
            ],
            "color": TEAL,
        },
        {
            "name": "Extensibility",
            "tagline": "扩展容易程度",
            "score": 5,
            "evidence": [
                "每仓 architecture.md §5 显式说明加 plugin 步骤",
                "3 种 pin 模式覆盖所有 dependency 形态",
                "cross-repo-smoke-install 保证扩展不破 matrix",
            ],
            "color": AMBER,
        },
        {
            "name": "Comparability",
            "tagline": "实验可比性",
            "score": 5,
            "evidence": [
                "ClearML 单一 tracker; W&B 物理移除",
                "ModelCard 全链贯穿，metrics 可跨 run 对比",
                "Replay 机制：ModelCard → 同一 config 重跑",
            ],
            "color": CORAL,
        },
    ]

    # 2×2 grid
    start_y = 1_800_000
    card_w = 5_400_000
    card_h = 1_800_000
    gap_x = 280_000
    gap_y = 240_000
    start_x = 660_000

    for i, dim in enumerate(dims):
        r = i // 2
        c = i % 2
        x = start_x + c * (card_w + gap_x)
        y = start_y + r * (card_h + gap_y)
        # Card
        add_rect(s, x, y, card_w, card_h, fill=WHITE, line=GRAY_300)
        # Color band
        add_rect(s, x, y, 120_000, card_h, fill=dim["color"])
        # Name
        add_text(s, x + 280_000, y + 160_000, card_w - 320_000, 400_000,
                 dim["name"], size=18, color=NAVY, bold=True)
        add_text(s, x + 280_000, y + 560_000, card_w - 320_000, 280_000,
                 dim["tagline"], size=11, color=GRAY_500, italic=True)
        # Score dots (5 filled)
        dot_y = y + 170_000
        dot_x0 = x + card_w - 1_500_000
        for di in range(5):
            filled = di < dim["score"]
            add_rect(s, dot_x0 + di * 250_000, dot_y, 200_000, 200_000,
                     fill=dim["color"] if filled else GRAY_300,
                     shape=MSO_SHAPE.OVAL)
        # Evidence bullets
        add_bullets(s, x + 280_000, y + 900_000, card_w - 500_000, card_h - 1_000_000,
                    dim["evidence"], size=10.5, bullet_color=dim["color"],
                    color=GRAY_700)

    add_footer(s, slide_num=37)


# Status + future
def slide_status_closeout():
    s = new_slide()
    add_header_bar(s, "Phase 10 生态优化收官",
                   "10 Phase · 9 repo · 单日 sprint · DoD 5/5",
                   section_num="§ 11 · 现状")

    # Horizontal phase timeline
    phases = [
        ("1", "pet-schema", "pre"),
        ("2", "pet-infra", "v2.6.0"),
        ("3", "pet-data", "v1.3.0"),
        ("4", "pet-annotation", "v2.1.1"),
        ("5", "pet-train", "v2.0.2"),
        ("6", "pet-eval", "v2.3.0"),
        ("7", "pet-quantize", "v2.1.0"),
        ("8", "pet-ota", "v2.2.0"),
        ("9", "pet-id", "v0.2.0"),
        ("10", "closeout", "matrix\n2026.10"),
    ]
    timeline_y = 2_300_000
    n = len(phases)
    box_w = 950_000
    box_h = 380_000
    gap = 100_000
    total_w = n * box_w + (n - 1) * gap
    start_x = (SLIDE_W.emu - total_w) // 2
    # Backbone line
    add_rect(s, start_x, timeline_y + box_h // 2 - 10_000, total_w, 20_000, fill=BLUE)
    for i, (num, name, ver) in enumerate(phases):
        x = start_x + i * (box_w + gap)
        color = REPO_COLORS.get(name, BLUE)
        # Phase dot
        add_rect(s, x + box_w // 2 - 80_000, timeline_y + box_h // 2 - 80_000,
                 160_000, 160_000, fill=color, shape=MSO_SHAPE.OVAL)
        # Phase number above
        add_text(s, x, timeline_y - 380_000, box_w, 280_000,
                 f"Phase {num}", size=10, color=GRAY_500, bold=True, align=PP_ALIGN.CENTER)
        # Repo name below
        add_text(s, x, timeline_y + box_h + 120_000, box_w, 280_000,
                 name, size=10.5, color=NAVY, bold=True, font=FONT_MONO, align=PP_ALIGN.CENTER)
        # Version lower
        add_text(s, x, timeline_y + box_h + 440_000, box_w, 420_000,
                 ver, size=9.5, color=color, align=PP_ALIGN.CENTER, line_spacing=1.2)

    # Stat strip at bottom
    stat_y = 4_700_000
    add_rect(s, 660_000, stat_y, SLIDE_W.emu - 1_320_000, 900_000, fill=GRAY_100)
    stats = [
        ("14+", "feature PR 合并"),
        ("9", "dev→main sync"),
        ("4", "workflow bug 修"),
        ("~533 LOC", "pet-eval 死代码删"),
        ("0", "open PR 收官"),
    ]
    stat_w = (SLIDE_W.emu - 1_320_000) / len(stats)
    for i, (num, label) in enumerate(stats):
        sx = 660_000 + int(i * stat_w)
        add_text(s, sx, stat_y + 140_000, int(stat_w), 400_000,
                 num, size=26, color=BLUE, bold=True, align=PP_ALIGN.CENTER)
        add_text(s, sx, stat_y + 580_000, int(stat_w), 250_000,
                 label, size=10, color=GRAY_500, align=PP_ALIGN.CENTER)

    add_footer(s, slide_num=38)


def slide_future():
    s = new_slide()
    add_header_bar(s, "Phase 5+ 硬件 · Follow-ups",
                   "retrospective §8 · 9 条（3 条 Phase 4 遗留 + 6 条本轮新增）",
                   section_num="§ 11 · 未来")

    # Two-column layout
    left_x = 660_000
    right_x = 660_000 + 5_800_000 + 400_000
    col_w = 5_800_000
    start_y = 1_800_000
    col_h = 4_200_000

    # Left — 硬件阻塞
    add_rect(s, left_x, start_y, col_w, 90_000, fill=CORAL)
    add_text(s, left_x + 200_000, start_y + 160_000, col_w - 400_000, 400_000,
             "硬件阻塞项 · Phase 5 gate",
             size=16, color=CORAL, bold=True)
    hw_items = [
        ("RK3576 单元 + self-hosted runner", "Phase 5 核心前提；解锁所有 --hardware 路径"),
        ("quantize_validate.yml 真跑", "Phase 7 修了死调用；硬件到位第一步"),
        ("canary rollout 真机测试", "pet-ota FSM 本地 sim 已验；真机 48h 观察窗"),
        ("RKNN/RKLLM 实测 latency P95", "当前 matrix 有 threshold 无测量值"),
    ]
    add_bullets(s, left_x + 200_000, start_y + 640_000, col_w - 400_000, col_h - 700_000,
                hw_items, size=12, bullet_color=CORAL)

    # Right — 可并行推进
    add_rect(s, right_x, start_y, col_w, 90_000, fill=AMBER)
    add_text(s, right_x + 200_000, start_y + 160_000, col_w - 400_000, 400_000,
             "可并行推进 · 不等硬件",
             size=16, color=AMBER, bold=True)
    sw_items = [
        ("pet-schema __version__ 属性", "Phase 10 修 workflow 时发现缺失；加 + 同 parity test"),
        ("SFT→DPO composed recipe", "当前只有 SFT 顶层 recipe；拼两 stage 5 分钟事"),
        ("pet-ota signing-smoke CI", "跑一次带 [signing] extras 装矩阵版 pet-quantize"),
        ("pet-id heavy-backends CI", "pose + narrative + tracker extras 独立 job"),
        ("pet-eval _FALLBACK_OUTPUT dynamic", "从 pet_schema defaults 动态生成"),
    ]
    add_bullets(s, right_x + 200_000, start_y + 640_000, col_w - 400_000, col_h - 700_000,
                sw_items, size=12, bullet_color=AMBER)

    add_footer(s, slide_num=39)


# Closing slide
def slide_close():
    s = new_slide()
    add_rect(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    add_text(s, 820_000, 2_600_000, 11_000_000, 1_000_000,
             "一切就绪。", size=44, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    add_text(s, 820_000, 3_700_000, 11_000_000, 600_000,
             "9 repos · tagged · main CI green · zero open PR",
             size=16, color=GRAY_300, align=PP_ALIGN.CENTER, italic=True)
    add_rect(s, SLIDE_W.emu // 2 - 800_000, 4_600_000, 1_600_000, 8_000, fill=BLUE)
    add_text(s, 820_000, 4_800_000, 11_000_000, 400_000,
             "pet-infra/docs/architecture/OVERVIEW.md · compatibility_matrix.yaml: 2026.10-ecosystem-cleanup",
             size=11, color=BLUE, align=PP_ALIGN.CENTER, font=FONT_MONO)


# ---- Compose everything ----
slide_dep_governance()
slide_ci_guards()
slide_northstar()
slide_status_closeout()
slide_future()
slide_close()


# Save
out = Path(__file__).parent / "Train-Pet-Pipeline-Technical-Overview.pptx"
prs.save(str(out))
print(f"Wrote {out}  ({out.stat().st_size // 1024} KB, {len(prs.slides)} slides)")
