"""UI 设计令牌与组件样式预设。"""
from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

THEME_JSON = Path(__file__).with_name('theme.json')

# ── 间距 ──────────────────────────────────────────────
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# ── 圆角 ──────────────────────────────────────────────
RADIUS_SM = 6
RADIUS_MD = 8
RADIUS_LG = 10

# ── 语义色（light, dark）──────────────────────────────
# 所有控件颜色均派生自这一组 shadcn 风格的语义令牌，避免页面、卡片和
# 交互控件各自维护一套灰阶。
SURFACE_BACKGROUND = ('#F8FAFC', '#0F172A')
SURFACE_CARD = ('#FFFFFF', '#162033')
SURFACE_MUTED = ('#F1F5F9', '#1E293B')
SURFACE_INPUT = ('#FFFFFF', '#0F172A')
SURFACE_OVERLAY = ('#FFFFFF', '#1E293B')

TEXT_PRIMARY = ('#0F172A', '#F8FAFC')
TEXT_SECONDARY = ('#475569', '#94A3B8')
TEXT_DISABLED = ('#94A3B8', '#64748B')
BORDER = ('#E2E8F0', '#334155')
BORDER_STRONG = ('#CBD5E1', '#475569')

ACCENT = ('#2563EB', '#2563EB')
ACCENT_HOVER = ('#1D4ED8', '#1D4ED8')
ACCENT_MUTED = ('#DBEAFE', '#1E3A5F')

SUCCESS = ('#15803D', '#4ADE80')
ERROR = ('#DC2626', '#F87171')
WARNING = ('#D97706', '#FBBF24')
MUTED = TEXT_SECONDARY

DANGER = ('#DC2626', '#DC2626')
DANGER_HOVER = ('#B91C1C', '#B91C1C')
SECONDARY = SURFACE_MUTED
SECONDARY_HOVER = ('#E2E8F0', '#334155')
GHOST_HOVER = SURFACE_MUTED

DROP_BORDER = BORDER_STRONG
DROP_BG = SURFACE_MUTED

LOG_BG = SURFACE_MUTED
LOG_FG = TEXT_PRIMARY

STATUS_META = {
    'pending': {'label': '待处理', 'icon': '○', 'color': MUTED, 'background': 'transparent'},
    'running': {
        'label': '转换中',
        'icon': '◌',
        'color': ('#1D4ED8', '#BFDBFE'),
        'background': ACCENT_MUTED,
    },
    'done': {'label': '完成', 'icon': '✓', 'color': SUCCESS, 'background': ('#DCFCE7', '#173A2A')},
    'error': {
        'label': '失败',
        'icon': '✕',
        'color': ('#B91C1C', '#F87171'),
        'background': ('#FEE2E2', '#3F2025'),
    },
    'skipped': {
        'label': '已跳过',
        'icon': '–',
        'color': ('#92400E', '#FBBF24'),
        'background': ('#FEF3C7', '#3D3018'),
    },
}

# 向后兼容已有任务状态配色调用。
STATUS_COLORS = {status: metadata['color'] for status, metadata in STATUS_META.items()}

# ── 字体族 ────────────────────────────────────────────
if sys.platform == 'win32':
    FONT_UI = 'Microsoft YaHei UI'
    FONT_MONO = 'Consolas'
elif sys.platform == 'darwin':
    FONT_UI = 'PingFang SC'
    FONT_MONO = 'Menlo'
else:
    FONT_UI = 'Noto Sans CJK SC'
    FONT_MONO = 'DejaVu Sans Mono'


def init_theme() -> None:
    ctk.set_appearance_mode('System')
    try:
        ctk.set_default_color_theme(str(THEME_JSON))
    except (KeyError, OSError):
        ctk.set_default_color_theme('blue')


def resolve_color(pair: tuple[str, str] | str) -> str:
    if isinstance(pair, str):
        return pair
    return pair[1] if ctk.get_appearance_mode() == 'Dark' else pair[0]


def frame_bg() -> str:
    fg_color = ctk.ThemeManager.theme['CTk']['fg_color']
    if isinstance(fg_color, (tuple, list)):
        return fg_color[1] if ctk.get_appearance_mode() == 'Dark' else fg_color[0]
    return fg_color


# ── 字体 ──────────────────────────────────────────────
def font_title() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=17, weight='bold')


def font_subtitle() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=12)


def font_section() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=12, weight='bold')


def font_body() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=13)


def font_caption() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=11)


def font_mono() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_MONO, size=12)


def font_icon() -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_UI, size=20)


# ── 组件预设 ──────────────────────────────────────────
def style_primary_button(btn: ctk.CTkButton, *, width: int = 120) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=32,
        corner_radius=RADIUS_SM,
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        text_color=('#FFFFFF', '#FFFFFF'),
        font=font_body(),
    )
    return btn


def set_primary_button_state(btn: ctk.CTkButton, enabled: bool) -> None:
    """同步主操作的可用状态与颜色，禁用时不可继续呈现为可点击蓝色。"""
    btn.configure(
        state='normal' if enabled else 'disabled',
        fg_color=ACCENT if enabled else SECONDARY,
        hover_color=ACCENT_HOVER if enabled else SECONDARY,
        text_color=('#FFFFFF', '#FFFFFF') if enabled else TEXT_DISABLED,
    )


def style_secondary_button(btn: ctk.CTkButton, *, width: int = 100) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=32,
        corner_radius=RADIUS_SM,
        fg_color=SURFACE_OVERLAY,
        hover_color=SECONDARY_HOVER,
        text_color=TEXT_PRIMARY,
        border_width=1,
        border_color=BORDER_STRONG,
        font=font_body(),
    )
    return btn


def style_ghost_button(btn: ctk.CTkButton, *, width: int = 100) -> ctk.CTkButton:
    """应用无边框的次要操作样式。"""
    btn.configure(
        width=width,
        height=32,
        corner_radius=RADIUS_SM,
        fg_color='transparent',
        hover_color=GHOST_HOVER,
        text_color=TEXT_SECONDARY,
        font=font_body(),
    )
    return btn


def style_danger_button(btn: ctk.CTkButton, *, width: int = 100) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=32,
        corner_radius=RADIUS_SM,
        fg_color=DANGER,
        hover_color=DANGER_HOVER,
        text_color=('#FFFFFF', '#FFFFFF'),
        font=font_body(),
    )
    return btn


def style_card(frame: ctk.CTkFrame) -> ctk.CTkFrame:
    frame.configure(fg_color=SURFACE_CARD, corner_radius=RADIUS_MD, border_width=0)
    return frame


def style_section_label(label: ctk.CTkLabel, text: str) -> ctk.CTkLabel:
    label.configure(text=text, font=font_section(), text_color=MUTED, anchor='w')
    return label
