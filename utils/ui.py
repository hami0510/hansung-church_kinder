import html
from datetime import date
import pandas as pd
import streamlit as st
from utils.labels import class_label

CAT_ICON = {"예배": "⛪", "행사": "🎈", "교사회의": "📋", "교육": "📖", "심방": "🏠", "기타": "⭐"}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Jua&display=swap');

html, body, .stMarkdown, .stMarkdown p, label, button p, input, textarea,
[data-testid="stSidebar"] p, [data-testid="stCaptionContainer"], [data-baseweb="tab"] p {
  font-family: 'Gowun Dodum', sans-serif;
}
[data-testid="stIconMaterial"], span[class*="material"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}
h1, h2, h3, .calhead, .hero-title {font-family: 'Jua', 'Gowun Dodum', sans-serif !important; letter-spacing: 0;}
.block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1100px;}

/* ---- 버튼 둥글게 ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 999px; border: 2px solid #8ec9f5; font-weight: 700;}
.stButton > button[kind="primary"] {background: #4a9fe0; border-color: #4a9fe0; color: #fff;}
div[data-baseweb="tab-list"] {gap: .2rem;}
button[data-baseweb="tab"] {border-radius: 12px 12px 0 0; font-weight: 700;}

/* ---- 환영 배너 ---- */
.hero {background: linear-gradient(135deg, #d6ecff 0%, #eaf6ff 55%, #fff6cf 100%);
       border: 2px solid #bfe0fa; border-radius: 22px; padding: 1.1rem 1.2rem; margin: 0 0 .7rem;
       position: relative; overflow: hidden; color: #1b3a5c;}
.hero-title {font-size: 1.7rem; line-height: 1.3; margin: 0;}
.hero-sub {font-size: 1rem; margin-top: .3rem; color: #3b5f85;}
.hero-deco {position: absolute; right: 14px; top: 8px; font-size: 2.1rem; opacity: .9;}
.hero-deco2 {position: absolute; right: 64px; bottom: 6px; font-size: 1.2rem; opacity: .7;}

/* ---- 현황 한 줄 ---- */
.stats {display: flex; flex-wrap: wrap; gap: .4rem .5rem; margin: 0 0 1rem;}
.stat {font-size: .86rem; padding: .22rem .75rem; border-radius: 999px; background: #eef6ff;
       border: 1px solid #cfe5f8; color: #1b3a5c; white-space: nowrap;}
.stat b {color: #2b6cb0;}

/* ---- 모바일 공통 ---- */
@media (max-width: 640px) {
  .block-container {padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 3rem !important;}
  h1 {font-size: 1.6rem !important;}
  h2, h3 {font-size: 1.2rem !important;}
  .stButton > button, .stDownloadButton > button {min-height: 2.8rem;}
  div[data-baseweb="tab-list"] {overflow-x: auto;}
  button[data-baseweb="tab"] {padding-left: 0.6rem; padding-right: 0.6rem; white-space: nowrap;}
  .hero-title {font-size: 1.35rem;}
  .hero-deco {font-size: 1.7rem;}
  .stat {font-size: .8rem; padding: .18rem .6rem;}
}

/* ---- 달력 이동 버튼: 모바일에서도 한 줄 ---- */
.st-key-calnav [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap: 0.4rem;}
.st-key-calnav [data-testid="stColumn"], .st-key-calnav [data-testid="column"] {
  min-width: 0 !important; flex: 1 1 0 !important; width: auto !important;}
.calhead {text-align: center; font-size: 1.4rem; margin: 0.2rem 0 0.4rem;}

/* ---- 월간 달력 (표 모양) ---- */
.kcal {width: 100%; border-collapse: separate; border-spacing: 0; table-layout: fixed;
       border: 2px solid #bfe0fa; border-radius: 16px; overflow: hidden;}
.kcal th {background: #cfe9fc; color: #1b3a5c; padding: 7px 2px; border-bottom: 2px solid #bfe0fa; font-size: 14px;}
.kcal th.sun {color: #d6336c;}
.kcal th.sat {color: #1c64f2;}
.kcal td {vertical-align: top; height: 92px; padding: 3px; border-top: 1px solid rgba(128,128,128,.25);
          border-left: 1px solid rgba(128,128,128,.2); font-size: 12px;}
.kcal td:first-child {border-left: none;}
.kcal .d {font-weight: 700; font-size: 13px;}
.kcal .sun {color: #d6336c;}
.kcal .sat {color: #1c64f2;}
.kcal td.today {background: #fff3bf; color: #222; box-shadow: inset 0 0 0 2px #ffd43b;}
.kcal .ev {background: #dff0ff; color: #1b3a5c; border-radius: 8px; margin-top: 2px; padding: 1px 4px;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.kcal .more {color: #868e96; margin-top: 2px;}
.kcal .dots {display: none;}
.kcal .dot {display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #4a9fe0; margin: 1px;}
@media (max-width: 640px) {
  .kcal th {font-size: 12px; padding: 4px 0;}
  .kcal td {height: 52px; padding: 2px; font-size: 11px;}
  .kcal .ev, .kcal .more {display: none;}
  .kcal .dots {display: block; text-align: center; line-height: 1;}
}

/* ---- 카드 목록 (일정, 아동) ---- */
.kcards {display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 0.7rem; margin: 0.4rem 0 1rem;}
.kcard {border: 2px solid #cfe5f8; background: rgba(120,180,240,.10);
        border-radius: 18px; padding: 0.75rem 0.95rem; line-height: 1.5;}
.kcard.past {opacity: .55;}
.kcard .ktop {font-weight: 700; font-size: 1.05rem;}
.kcard .ksub {font-size: .95rem;}
.kcard .kmuted {font-size: .88rem; opacity: .75;}
.kcard .kwarn {font-size: .92rem; color: #e03131; font-weight: 700;}
.kcard .ktag {display: inline-block; font-size: .78rem; padding: 0 .55rem; margin-left: .3rem;
              border-radius: 999px; background: rgba(74,159,224,.22); vertical-align: middle;}
.kcard .ktag.new {background: rgba(255,200,0,.35);}
.kcard a {text-decoration: none;}
.kflex {display: flex; gap: .75rem; align-items: flex-start;}
.kbody {min-width: 0; flex: 1;}
.kphoto {width: 68px; height: 68px; border-radius: 50%; object-fit: cover;
         border: 3px solid #bfe0fa; flex-shrink: 0; background: #dff0ff;}
.kphoto.ph {display: flex; align-items: center; justify-content: center; font-size: 1.9rem;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown(
        "<div class='hero'>"
        "<div class='hero-deco'>🕊️</div><div class='hero-deco2'>⭐</div>"
        "<div class='hero-title'>한성교회 유치부</div>"
        "<div class='hero-sub'>예수님 안에서 쑥쑥 자라는 아이들 🐑✨</div>"
        "</div>",
        unsafe_allow_html=True,
    )


def stats_line(items):
    """items: [(아이콘, 라벨, 값), ...] → 현황 칩 한 줄"""
    chips = "".join(
        f"<span class='stat'>{html.escape(icon)} {html.escape(label)} <b>{html.escape(str(val))}</b></span>"
        for icon, label, val in items)
    st.markdown(f"<div class='stats'>{chips}</div>", unsafe_allow_html=True)


def _s(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v)


def _e(v):
    return html.escape(_s(v))


def event_card_html(r, past=False):
    """일정 한 장의 카드 HTML (r: event_date, time_str, title, category, location)"""
    d = r["event_date"]
    wd = "월화수목금토일"[d.weekday()]
    when = f"{d.month}/{d.day}({wd})"
    if _s(r.get("time_str")):
        when += f" {_s(r.get('time_str'))}"
    cat = _s(r.get("category"))
    icon = CAT_ICON.get(cat, "⭐")
    tag = f"<span class='ktag'>{html.escape(cat)}</span>" if cat else ""
    loc = _s(r.get("location"))
    cls = " past" if past else ""
    return (
        f"<div class='kcard{cls}'>"
        f"<div class='kmuted'>{html.escape(when)}</div>"
        f"<div class='ktop'>{icon} {_e(r.get('title'))}{tag}</div>"
        + (f"<div class='ksub'>📍 {html.escape(loc)}</div>" if loc else "")
        + "</div>"
    )


def event_cards(df):
    """df: event_date(date), time_str, title, category, location 열 필요"""
    if df is None or df.empty:
        return
    today = date.today()
    out = ["<div class='kcards'>"]
    for _, r in df.iterrows():
        out.append(event_card_html(r, past=r["event_date"] < today))
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)


def child_cards(df, show_contact=False, show_inactive_tag=False, show_photo=False):
    if df is None or df.empty:
        return
    out = ["<div class='kcards'>"]
    for _, r in df.iterrows():
        tags = ""
        lbl = class_label(r)
        if lbl != "반 미정":
            tags += f"<span class='ktag'>{html.escape(lbl)}</span>"
        if _s(r.get("gender")):
            tags += f"<span class='ktag'>{_e(r.get('gender'))}</span>"
        if _s(r.get("is_new_family")).lower() == "true":
            tags += "<span class='ktag new'>새가족 🌱</span>"
        if show_inactive_tag and _s(r.get("is_active")).lower() == "false":
            tags += "<span class='ktag'>퇴원</span>"
        body = f"<div class='ktop'>{_e(r.get('name'))}{tags}</div>"
        if _s(r.get("birth_date")):
            body += f"<div class='kmuted'>🎂 {_e(r.get('birth_date'))}</div>"
        if _s(r.get("allergy")):
            body += f"<div class='kwarn'>⚠️ 알레르기: {_e(r.get('allergy'))}</div>"
        if _s(r.get("notes")):
            body += f"<div class='ksub'>📝 {_e(r.get('notes'))}</div>"
        if show_contact and (_s(r.get("guardian_name")) or _s(r.get("guardian_phone"))):
            phone = _s(r.get("guardian_phone"))
            tel = f"<a href='tel:{html.escape(phone)}'>📞 {html.escape(phone)}</a>" if phone else ""
            body += f"<div class='ksub'>👤 {_e(r.get('guardian_name'))} {tel}</div>"

        if show_photo:
            url = _s(r.get("photo_url"))
            img = (f"<img class='kphoto' src='{html.escape(url)}' alt=''>" if url
                   else "<div class='kphoto ph'>🐑</div>")
            out.append(f"<div class='kcard kflex'>{img}<div class='kbody'>{body}</div></div>")
        else:
            out.append(f"<div class='kcard'>{body}</div>")
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)
