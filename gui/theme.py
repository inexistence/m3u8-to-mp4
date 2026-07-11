"""UI 设计令牌与组件样式预设。"""
from __future__ import annotations

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
RADIUS_MD = 10
RADIUS_LG = 14

# ── 语义色（light, dark）──────────────────────────────
ACCENT = ('#0d9488', '#2dd4bf')
ACCENT_HOVER = ('#0f766e', '#14b8a6')
ACCENT_MUTED = ('#ccfbf1', '#134e4a')

SUCCESS = ('#16a34a', '#4ade80')
ERROR = ('#dc2626', '#f87171')
WARNING = ('#d97706', '#fbbf24')
MUTED = ('#6b7280', '#9ca3af')

DANGER = ('#dc2626', '#ef4444')
DANGER_HOVER = ('#b91c1c', '#dc2626')
SECONDARY = ('#e5e7eb', '#374151')
SECONDARY_HOVER = ('#d1d5db', '#4b5563')

DROP_BORDER = ('#99f6e4', '#115e59')
DROP_BG = ('#f0fdfa', '#042f2e')

LOG_BG = ('#f8fafc', '#0f172a')
LOG_FG = ('#334155', '#cbd5e1')

STATUS_COLORS = {
    'pending': MUTED,
    'running': ACCENT,
    'done': SUCCESS,
    'error': ERROR,
    'skipped': WARNING,
}


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
    fg_color = ctk.ThemeManager.theme['CTkFrame']['fg_color']
    if isinstance(fg_color, (tuple, list)):
        return fg_color[1] if ctk.get_appearance_mode() == 'Dark' else fg_color[0]
    return fg_color


# ── 字体 ──────────────────────────────────────────────
def font_title() -> ctk.CTkFont:
    return ctk.CTkFont(family='Segoe UI', size=22, weight='bold')


def font_subtitle() -> ctk.CTkFont:
    return ctk.CTkFont(family='Segoe UI', size=13)


def font_section() -> ctk.CTkFont:
    return ctk.CTkFont(family='Segoe UI', size=13, weight='bold')


def font_body() -> ctk.CTkFont:
    return ctk.CTkFont(family='Segoe UI', size=13)


def font_caption() -> ctk.CTkFont:
    return ctk.CTkFont(family='Segoe UI', size=12)


def font_mono() -> ctk.CTkFont:
    return ctk.CTkFont(family='Consolas', size=12)


def font_icon() -> ctk.CTkFont:
    return ctk.CTkFont(size=28)


# ── 组件预设 ──────────────────────────────────────────
def style_primary_button(btn: ctk.CTkButton, *, width: int = 120) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=36,
        corner_radius=RADIUS_SM,
        fg_color=ACCENT,
        hover_color=ACCENT_HOVER,
        font=font_body(),
    )
    return btn


def style_secondary_button(btn: ctk.CTkButton, *, width: int = 100) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=36,
        corner_radius=RADIUS_SM,
        fg_color=SECONDARY,
        hover_color=SECONDARY_HOVER,
        text_color=('#1f2937', '#f3f4f6'),
        font=font_body(),
    )
    return btn


def style_danger_button(btn: ctk.CTkButton, *, width: int = 100) -> ctk.CTkButton:
    btn.configure(
        width=width,
        height=36,
        corner_radius=RADIUS_SM,
        fg_color=DANGER,
        hover_color=DANGER_HOVER,
        font=font_body(),
    )
    return btn


def style_card(frame: ctk.CTkFrame) -> ctk.CTkFrame:
    frame.configure(corner_radius=RADIUS_MD, border_width=1)
    return frame


def style_section_label(label: ctk.CTkLabel, text: str) -> ctk.CTkLabel:
    label.configure(text=text, font=font_section(), anchor='w')
    return label
