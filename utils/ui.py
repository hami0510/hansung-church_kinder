import html
from datetime import date
import pandas as pd
import streamlit as st

CSS = """
<style>
.block-container {padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1100px;}

/* ---- 모바일 공통 ---- */
@media (max-width: 640px) {
  .block-container {padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 1.5rem;}
  h1 {font-size: 1.6rem !important;}
  h2, h3 {font-size: 1.2rem !important;}
  .stButton > button, .stDownloadButton > button {min-height: 2.8rem;}
  div[data-baseweb="tab-list"] {overflow-x: auto;}
  button[data-baseweb="tab"] {padding-left: 0.6rem; padding-right: 0.6rem; white-space: nowrap;}
}

/* ---- 달력 이동 버튼: 모바일에서도 한 줄 ---- */
.st-key-calnav [data-testid="stHorizontalBlock"] {flex-wrap: nowrap !important; gap: 0.4rem;}
.st-key-calnav [data-testid="stColumn"], .st-key-calnav [data-testid="column"] {
  min-width: 0 !important; flex: 1 1 0 !important; width: auto !important;}
.calhead {text-align: center; font-size: 1.3rem; font-weight: 700; margin: 0.2rem 0 0.4rem;}

/* ---- 월간 달력 ---- */
.kcal {width: 100%; border-collapse: collapse; table-layout: fixed;}
.kcal th {background: #ffd966; color: #333; padding: 6px 2px; border: 1px solid #d9d9d9; font-size: 14px;}
.kcal td {vertical-align: top; height: 92px; padding: 3px; border: 1px solid rgba(128,128,128,.35); font-size: 12px;}
.kcal .d {font-weight: 700; font-size: 13px;}
.kcal .sun {color: #e03131;}
.kcal .sat {color: #1c64f2;}
.kcal td.today {background: #fff3bf; color: #222;}
.kcal .ev {background: #e7f1ff; color: #1c3d6e; border-radius: 3px; margin-top: 2px; padding: 1px 3px;
           overflow: hidden; text-overflow: ellipsis; white-space: nowrap;}
.kcal .more {color: #868e96; margin-top: 2px;}
.kcal .dots {display: none;}
.kcal .dot {display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #1c64f2; margin: 1px;}
@media (max-width: 640px) {
  .kcal th {font-size: 12px; padding: 4px 0;}
  .kcal td {height: 52px; padding: 2px; font-size: 11px;}
  .kcal .ev, .kcal .more {display: none;}
  .kcal .dots {display: block; text-align: center; line-height: 1;}
}

/* ---- 카드 목록 (일정, 아동) ---- */
.kcards {display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 0.6rem; margin: 0.4rem 0 1rem;}
.kcard {border: 1px solid rgba(128,128,128,.35); background: rgba(128,128,128,.07);
        border-radius: 10px; padding: 0.7rem 0.9rem; line-height: 1.5;}
.kcard.past {opacity: .55;}
.kcard .ktop {font-weight: 700; font-size: 1.02rem;}
.kcard .ksub {font-size: .95rem;}
.kcard .kmuted {font-size: .88rem; opacity: .75;}
.kcard .kwarn {font-size: .92rem; color: #e03131; font-weight: 600;}
.kcard .ktag {display: inline-block; font-size: .78rem; padding: 0 .5rem; margin-left: .3rem;
              border-radius: 999px; background: rgba(28,100,242,.15); vertical-align: middle;}
.kcard .ktag.new {background: rgba(240,140,0,.2);}
.kcard a {text-decoration: none;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


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


def event_cards(df):
    """df: event_date(date), time_str, title, category, location 열 필요"""
    if df is None or df.empty:
        return
    today = date.today()
    out = ["<div class='kcards'>"]
    for _, r in df.iterrows():
        d = r["event_date"]
        wd = "월화수목금토일"[d.weekday()]
        when = f"{d.month}/{d.day}({wd})"
        if _s(r.get("time_str")):
            when += f" {_s(r.get('time_str'))}"
        cat = _s(r.get("category"))
        tag = f"<span class='ktag'>{html.escape(cat)}</span>" if cat else ""
        loc = _s(r.get("location"))
        past = " past" if d < today else ""
        out.append(
            f"<div class='kcard{past}'>"
            f"<div class='kmuted'>{html.escape(when)}</div>"
            f"<div class='ktop'>{_e(r.get('title'))}{tag}</div>"
            + (f"<div class='ksub'>📍 {html.escape(loc)}</div>" if loc else "")
            + "</div>"
        )
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)


def child_cards(df, show_contact=False, show_inactive_tag=False):
    if df is None or df.empty:
        return
    out = ["<div class='kcards'>"]
    for _, r in df.iterrows():
        tags = ""
        if _s(r.get("class_name")):
            tags += f"<span class='ktag'>{_e(r.get('class_name'))}</span>"
        if _s(r.get("gender")):
            tags += f"<span class='ktag'>{_e(r.get('gender'))}</span>"
        if _s(r.get("is_new_family")).lower() == "true":
            tags += "<span class='ktag new'>새가족</span>"
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
        out.append(f"<div class='kcard'>{body}</div>")
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)
