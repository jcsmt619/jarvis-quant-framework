"""
design_system.py
================
Shared visual design system for the suite of Streamlit trading dashboards.

Usage (top of any dashboard):

    from design_system import *
    apply_theme()

Everything below -- colour constants, ``apply_theme()``, the HTML component
helpers, ``get_plotly_layout()`` and ``style_dataframe()`` -- is exported via the
star import so every dashboard shares one consistent dark-terminal aesthetic.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BG_PRIMARY = "#0a0a0f"        # main background
BG_CARD = "#12121a"           # card / panel background
BG_CARD_HOVER = "#1a1a24"     # card hover state
BORDER = "rgba(255,255,255,0.06)"  # subtle borders

ACCENT_CYAN = "#00d4ff"       # primary accent
ACCENT_GREEN = "#00e676"      # success / profit
ACCENT_RED = "#ff1744"        # danger / loss
ACCENT_AMBER = "#ffc107"      # warning
ACCENT_VIOLET = "#7c4dff"     # secondary accent

TEXT_PRIMARY = "#ffffff"
TEXT_SECONDARY = "#8a8a9a"
TEXT_MUTED = "#5a5a6a"

GRID_LINE = "rgba(255,255,255,0.04)"

# Regime -> colour. Keys are matched case-insensitively by ``regime_badge``.
REGIME_COLORS: dict[str, str] = {
    "Low Vol": ACCENT_GREEN,
    "Bull": ACCENT_GREEN,
    "Medium Vol": ACCENT_AMBER,
    "Neutral": ACCENT_AMBER,
    "High Vol": ACCENT_RED,
    "Bear": ACCENT_RED,
    "Uncertain": ACCENT_VIOLET,
}

FONT_MONO = "'JetBrains Mono', 'Consolas', monospace"
FONT_SANS = "'DM Sans', 'Segoe UI', sans-serif"

__all__ = [
    "BG_PRIMARY", "BG_CARD", "BG_CARD_HOVER", "BORDER",
    "ACCENT_CYAN", "ACCENT_GREEN", "ACCENT_RED", "ACCENT_AMBER", "ACCENT_VIOLET",
    "TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "GRID_LINE",
    "REGIME_COLORS", "FONT_MONO", "FONT_SANS",
    "apply_theme", "metric_card", "regime_badge", "section_header",
    "status_dot", "pnl_color", "get_plotly_layout", "style_dataframe",
    "regime_color",
]


# ---------------------------------------------------------------------------
# Theme injection
# ---------------------------------------------------------------------------
def apply_theme() -> None:
    """Inject the global dark trading-terminal CSS. Call once, at the top."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=DM+Sans:wght@400;500;700&display=swap');

        /* ---- app shell ---- */
        .stApp {{
            background: {BG_PRIMARY};
            color: {TEXT_PRIMARY};
        }}
        html, body, [class*="css"] {{
            font-family: {FONT_SANS};
        }}

        /* thin cyan accent line across the very top of the page */
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, {ACCENT_CYAN}, transparent);
            z-index: 9999;
        }}

        /* ---- kill Streamlit chrome ---- */
        #MainMenu {{visibility: hidden;}}
        header {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        [data-testid="stToolbar"] {{display: none;}}
        [data-testid="stDecoration"] {{display: none;}}
        [data-testid="stStatusWidget"] {{display: none;}}
        a[href^="https://streamlit.io"] {{display: none !important;}}

        /* ---- edge-to-edge: remove default padding ---- */
        .block-container {{
            padding: 1.2rem 1.5rem 1rem 1.5rem !important;
            max-width: 100% !important;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            background: {BG_CARD};
            border-right: 1px solid {BORDER};
        }}

        /* ---- st.metric: large monospace numbers ---- */
        [data-testid="stMetric"] {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 12px;
            padding: 14px 16px;
            transition: background 0.15s ease;
        }}
        [data-testid="stMetric"]:hover {{
            background: {BG_CARD_HOVER};
        }}
        [data-testid="stMetricValue"] {{
            font-family: {FONT_MONO};
            font-size: 2rem;
            font-weight: 700;
            color: {TEXT_PRIMARY};
            letter-spacing: -0.5px;
        }}
        [data-testid="stMetricLabel"] {{
            font-family: {FONT_SANS};
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: {TEXT_SECONDARY};
        }}
        [data-testid="stMetricDelta"] {{
            font-family: {FONT_MONO};
            font-size: 0.85rem;
        }}

        /* ---- generic card containers ---- */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 12px;
        }}

        /* ---- headings ---- */
        h1, h2, h3, h4 {{
            font-family: {FONT_SANS};
            color: {TEXT_PRIMARY};
            font-weight: 700;
        }}

        /* ---- dataframes ---- */
        [data-testid="stDataFrame"] {{
            background: {BG_CARD};
            border: 1px solid {BORDER};
            border-radius: 12px;
        }}

        /* ---- scrollbars ---- */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: {BG_PRIMARY}; }}
        ::-webkit-scrollbar-thumb {{ background: {BG_CARD_HOVER}; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: {ACCENT_CYAN}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# HTML component helpers  (render with st.markdown(..., unsafe_allow_html=True))
# ---------------------------------------------------------------------------
def metric_card(label: str, value: str, color: str = ACCENT_CYAN) -> str:
    """A styled metric: large coloured number over a small uppercase muted label."""
    return (
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
        f'border-radius:12px;padding:16px 18px;transition:background .15s ease;">'
        f'<div style="font-family:{FONT_MONO};font-size:2rem;font-weight:700;'
        f'color:{color};letter-spacing:-0.5px;line-height:1.1;">{value}</div>'
        f'<div style="font-family:{FONT_SANS};font-size:0.68rem;text-transform:uppercase;'
        f'letter-spacing:2px;color:{TEXT_MUTED};margin-top:6px;">{label}</div>'
        f'</div>'
    )


def regime_color(regime_name: str) -> str:
    """Resolve a regime name to its colour (case-insensitive; falls back to cyan)."""
    if not regime_name:
        return ACCENT_CYAN
    key = regime_name.strip().lower()
    for name, colour in REGIME_COLORS.items():
        if name.lower() == key:
            return colour
    return ACCENT_CYAN


def regime_badge(regime_name: str, confidence: float | None = None) -> str:
    """A pill badge: regime colour @20% background, full-colour text, glow shadow."""
    color = regime_color(regime_name)
    conf = ""
    if confidence is not None:
        conf = (
            f'<span style="font-family:{FONT_MONO};opacity:0.75;margin-left:8px;">'
            f'{confidence * 100:.0f}%</span>'
        )
    return (
        f'<span style="display:inline-flex;align-items:center;'
        f'background:{color}33;color:{color};'
        f'font-family:{FONT_SANS};font-size:0.8rem;font-weight:600;'
        f'letter-spacing:0.5px;padding:5px 14px;border-radius:999px;'
        f'border:1px solid {color}55;box-shadow:0 0 12px {color}44;">'
        f'{regime_name}{conf}</span>'
    )


def section_header(text: str) -> str:
    """A small uppercase, letter-spaced label with a line extending to the right."""
    return (
        f'<div style="display:flex;align-items:center;gap:12px;margin:18px 0 10px 0;">'
        f'<span style="font-family:{FONT_SANS};font-size:11px;text-transform:uppercase;'
        f'letter-spacing:3px;color:{TEXT_MUTED};white-space:nowrap;">{text}</span>'
        f'<span style="flex:1;height:1px;background:{BORDER};"></span>'
        f'</div>'
    )


def status_dot(status: str) -> str:
    """A small coloured status dot: green (ok), red (error), amber (warning)."""
    key = (status or "").strip().lower()
    if key in ("connected", "active", "online", "live", "ok", "healthy"):
        color = ACCENT_GREEN
    elif key in ("disconnected", "error", "offline", "down", "failed", "dead"):
        color = ACCENT_RED
    elif key in ("warning", "warn", "degraded", "watch", "pending"):
        color = ACCENT_AMBER
    else:
        color = TEXT_MUTED
    return (
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{color};box-shadow:0 0 8px {color};'
        f'vertical-align:middle;"></span>'
    )


def pnl_color(value: float) -> str:
    """Green for profit, red for loss (zero counts as non-negative -> green)."""
    return ACCENT_GREEN if value >= 0 else ACCENT_RED


# ---------------------------------------------------------------------------
# Plotly base layout
# ---------------------------------------------------------------------------
def get_plotly_layout() -> dict:
    """Base Plotly layout dict for the dark terminal look. Merge into figures."""
    axis = dict(
        gridcolor=GRID_LINE,
        zerolinecolor=GRID_LINE,
        linecolor=BORDER,
        tickfont=dict(family="JetBrains Mono", size=11, color=TEXT_MUTED),
        title_font=dict(family="JetBrains Mono", size=12, color=TEXT_SECONDARY),
    )
    return dict(
        paper_bgcolor=BG_PRIMARY,
        plot_bgcolor=BG_PRIMARY,
        font=dict(family="JetBrains Mono", color=TEXT_SECONDARY, size=12),
        colorway=[ACCENT_CYAN, ACCENT_GREEN, ACCENT_VIOLET, ACCENT_AMBER, ACCENT_RED],
        xaxis=dict(**axis),
        yaxis=dict(**axis),
        margin=dict(l=40, r=20, t=40, b=40),
        hoverlabel=dict(
            bgcolor=BG_CARD,
            bordercolor=ACCENT_CYAN,
            font=dict(family="JetBrains Mono", color=TEXT_PRIMARY, size=12),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color=TEXT_SECONDARY, size=11),
        ),
    )


# ---------------------------------------------------------------------------
# DataFrame styling
# ---------------------------------------------------------------------------
def style_dataframe(df):
    """Return a dark-styled pandas Styler (pass to st.dataframe / st.table)."""
    styles = [
        {"selector": "th",
         "props": [("background-color", BG_CARD_HOVER),
                   ("color", TEXT_SECONDARY),
                   ("font-family", "DM Sans, sans-serif"),
                   ("font-size", "11px"),
                   ("text-transform", "uppercase"),
                   ("letter-spacing", "1px"),
                   ("border", f"1px solid {BORDER}"),
                   ("padding", "8px 12px")]},
        {"selector": "td",
         "props": [("background-color", BG_CARD),
                   ("color", TEXT_PRIMARY),
                   ("font-family", "JetBrains Mono, monospace"),
                   ("font-size", "12px"),
                   ("border", f"1px solid {BORDER}"),
                   ("padding", "6px 12px")]},
        {"selector": "tr:hover td",
         "props": [("background-color", BG_CARD_HOVER)]},
        {"selector": "",
         "props": [("border-collapse", "collapse"),
                   ("border-radius", "12px"),
                   ("overflow", "hidden")]},
    ]
    return (
        df.style
        .set_table_styles(styles)
        .set_properties(**{"background-color": BG_CARD, "color": TEXT_PRIMARY})
    )
