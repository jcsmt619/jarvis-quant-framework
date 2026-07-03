"""
fomc_scanner.py
===============
FOMC Sentiment Scanner — FinBERT reads the latest Fed monetary-policy statement
and scores its tone, on the shared dark-terminal design system.

Pipeline: Fed press-release RSS (monetary policy feed) -> statement page ->
BeautifulSoup article extraction -> sentence split -> ProsusAI/finbert ->
Hawkish/Dovish verdict + breakdown + top-3 sentences each way.

HONEST FRAMING (built into the UI):
  * FinBERT labels financial sentiment (positive/negative/neutral). Mapping
    negative->Hawkish / positive->Dovish is a PROXY, not a policy classifier —
    a sentence can be negative-toned yet dovish in policy terms.
  * The statement is public to every machine on Earth within milliseconds.
    This tool is macro RESEARCH context, not an execution edge.

Run:  streamlit run fomc_scanner.py
First run downloads the FinBERT model (~440 MB) from Hugging Face.
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from bs4 import BeautifulSoup

from design_system import *

st.set_page_config(page_title="FOMC Scanner", layout="wide", page_icon="~")
apply_theme()

RSS_URL = "https://www.federalreserve.gov/feeds/press_monetary.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (research; jarvis-quant-framework)"}
MIN_SENT_LEN = 40          # skip boilerplate fragments


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_latest_statement() -> dict:
    """Latest monetary-policy press release: title, date, url, full text."""
    import xml.etree.ElementTree as ET

    rss = requests.get(RSS_URL, headers=HEADERS, timeout=30)
    rss.raise_for_status()
    root = ET.fromstring(rss.content)          # stdlib parser: no lxml needed
    items = [{
        "title": (i.findtext("title") or "").strip(),
        "link": (i.findtext("link") or "").strip(),
        "date": (i.findtext("pubDate") or "").strip(),
    } for i in root.iter("item")]
    if not items:
        raise RuntimeError("Fed RSS feed returned no items")
    # Prefer an actual FOMC statement over implementation-note releases.
    item = next((i for i in items if "statement" in i["title"].lower()), items[0])
    url, title, date = item["link"], item["title"], item["date"]

    page = requests.get(url, headers=HEADERS, timeout=30)
    page.raise_for_status()
    soup = BeautifulSoup(page.content, "html.parser")
    article = soup.find("div", id="article") or soup.find(
        "div", class_=re.compile(r"col-xs-12.*col-md-8")) or soup
    paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p")]
    text = "\n".join(p for p in paragraphs if p)
    if len(text) < 200:
        raise RuntimeError("Could not extract statement body (page layout changed?)")
    return {"title": title, "date": date, "url": url, "text": text,
            "first_paragraph": next((p for p in paragraphs if len(p) > 80), paragraphs[0])}


def split_sentences(text: str) -> list[str]:
    """Regex sentence split (FinBERT works best on short chunks)."""
    rough = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.replace("\n", " "))
    return [s.strip() for s in rough if len(s.strip()) >= MIN_SENT_LEN]


# ---------------------------------------------------------------------------
# NLP engine
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def load_finbert():
    from transformers import pipeline
    return pipeline("text-classification", model="ProsusAI/finbert",
                    truncation=True, max_length=512)


@st.cache_data(ttl=3600, show_spinner=False)
def score_sentences(sentences: tuple[str, ...]) -> pd.DataFrame:
    clf = load_finbert()
    out = clf(list(sentences), batch_size=8)
    df = pd.DataFrame({"sentence": sentences,
                       "label": [o["label"] for o in out],
                       "score": [float(o["score"]) for o in out]})
    # FinBERT: negative -> Hawkish (bearish), positive -> Dovish (bullish)
    df["tone"] = df["label"].map({"negative": "Hawkish", "positive": "Dovish",
                                  "neutral": "Neutral"})
    return df


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="font-family:{FONT_MONO};font-size:2.2rem;font-weight:700;'
    f'color:{TEXT_PRIMARY};">FOMC SENTIMENT SCANNER'
    f'<span style="font-size:0.85rem;color:{TEXT_MUTED};font-family:{FONT_SANS};'
    f'letter-spacing:2px;"> &nbsp;FinBERT · ProsusAI</span></div>',
    unsafe_allow_html=True)

try:
    with st.spinner("Scraping the Federal Reserve..."):
        doc = fetch_latest_statement()
except Exception as exc:
    st.error(f"Could not fetch the FOMC statement: {exc}")
    st.stop()

st.markdown(section_header("Document verification"), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:12px;'
    f'padding:14px 16px;font-family:{FONT_SANS};font-size:0.85rem;color:{TEXT_SECONDARY};">'
    f'<span style="color:{ACCENT_CYAN};font-weight:700;">{doc["title"]}</span>'
    f'<span style="color:{TEXT_MUTED};"> &middot; {doc["date"]}</span><br><br>'
    f'{doc["first_paragraph"]}<br>'
    f'<a href="{doc["url"]}" style="color:{ACCENT_CYAN};font-size:0.75rem;">source</a></div>',
    unsafe_allow_html=True)

sentences = split_sentences(doc["text"])
if not sentences:
    st.error("No scoreable sentences extracted.")
    st.stop()

with st.spinner(f"FinBERT scoring {len(sentences)} sentences (first run downloads the model)..."):
    scored = score_sentences(tuple(sentences))

counts = scored["tone"].value_counts()
n = len(scored)
hawk_pct = counts.get("Hawkish", 0) / n
dove_pct = counts.get("Dovish", 0) / n

# ---- verdict ----
if hawk_pct > dove_pct:
    verdict, v_color = "HAWKISH: EXPECT MARKET PRESSURE", ACCENT_RED
elif dove_pct > hawk_pct:
    verdict, v_color = "DOVISH: EXPECT MARKET EXPANSION", ACCENT_GREEN
else:
    verdict, v_color = "NEUTRAL: NO DOMINANT TONE", ACCENT_AMBER

c1, c2, c3 = st.columns([2, 1, 1])
c1.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {v_color}55;border-radius:12px;'
    f'padding:18px;box-shadow:0 0 16px {v_color}33;">'
    f'<div style="font-family:{FONT_MONO};font-size:1.6rem;font-weight:700;color:{v_color};">'
    f'{verdict}</div>'
    f'<div style="font-family:{FONT_SANS};font-size:0.7rem;letter-spacing:2px;'
    f'text-transform:uppercase;color:{TEXT_MUTED};margin-top:6px;">'
    f'{n} sentences scored &middot; net tone {dove_pct - hawk_pct:+.0%} dovish</div></div>',
    unsafe_allow_html=True)
c2.markdown(metric_card("Hawkish", f"{hawk_pct:.0%}", ACCENT_RED), unsafe_allow_html=True)
c3.markdown(metric_card("Dovish", f"{dove_pct:.0%}", ACCENT_GREEN), unsafe_allow_html=True)

# ---- pie ----
st.markdown(section_header("Sentence tone breakdown"), unsafe_allow_html=True)
order = ["Hawkish", "Neutral", "Dovish"]
fig = go.Figure(go.Pie(
    labels=order, values=[int(counts.get(t, 0)) for t in order], hole=0.55,
    marker=dict(colors=[ACCENT_RED, TEXT_MUTED, ACCENT_GREEN],
                line=dict(color=BG_PRIMARY, width=2)),
    textfont=dict(family="JetBrains Mono", color=TEXT_PRIMARY)))
layout = get_plotly_layout()
layout.pop("xaxis", None); layout.pop("yaxis", None)
fig.update_layout(**layout, height=340, showlegend=True)
st.plotly_chart(fig, width="stretch")

# ---- top sentences ----
st.markdown(section_header("Most Hawkish / Most Dovish sentences"), unsafe_allow_html=True)
left, right = st.columns(2)
for col, tone, color in ((left, "Hawkish", ACCENT_RED), (right, "Dovish", ACCENT_GREEN)):
    top = scored[scored["tone"] == tone].nlargest(3, "score")
    col.markdown(
        f'<div style="font-family:{FONT_SANS};font-size:0.8rem;font-weight:700;'
        f'color:{color};margin-bottom:6px;">TOP {tone.upper()}</div>', unsafe_allow_html=True)
    if top.empty:
        col.markdown(f'<span style="color:{TEXT_MUTED};font-size:0.8rem;">none detected</span>',
                     unsafe_allow_html=True)
    for _, row in top.iterrows():
        col.markdown(
            f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-left:3px solid '
            f'{color};border-radius:10px;padding:10px 12px;margin-bottom:8px;'
            f'font-family:{FONT_SANS};font-size:0.8rem;color:{TEXT_SECONDARY};">'
            f'<span style="font-family:{FONT_MONO};color:{color};">{row["score"]:.2f}</span> '
            f'&mdash; {row["sentence"]}</div>', unsafe_allow_html=True)

# ---- honesty ----
st.markdown(section_header("Read before trading"), unsafe_allow_html=True)
st.markdown(
    f'<div style="background:{BG_CARD};border:1px solid {BORDER};border-left:3px solid '
    f'{ACCENT_AMBER};border-radius:12px;padding:14px 16px;font-family:{FONT_SANS};'
    f'font-size:0.85rem;color:{TEXT_SECONDARY};line-height:1.7;">'
    f'1. negative&rarr;Hawkish / positive&rarr;Dovish is a <b>proxy mapping</b> — FinBERT '
    f'scores financial sentiment, not monetary-policy stance.<br>'
    f'2. Statements are machine-read market-wide within milliseconds of release; treat this '
    f'as macro research context, never an execution edge.<br>'
    f'3. Fed statements are mostly deliberately neutral boilerplate — a large Neutral share '
    f'is normal; the signal is in the marginal CHANGE of tone between meetings.</div>',
    unsafe_allow_html=True)
