import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

html, body, .stApp, .stMarkdown, .stMarkdown p, label, button, button p, input, textarea, select,
h1, h2, h3, h4, [data-testid="stSidebar"], [data-testid="stSidebar"] p,
[data-testid="stCaptionContainer"], [data-baseweb="tab"], [data-baseweb="tab"] p,
[data-testid="stExpander"] summary, [data-testid="stMetricValue"], [data-testid="stDialog"] {
  font-family: 'Noto Sans KR', sans-serif !important;
}
[data-testid="stIconMaterial"], span[class*="material"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}
h1, h2, h3, .calhead, .hero-title {font-weight: 700; letter-spacing: -0.01em;}
.block-container {padding-top: 4rem; padding-bottom: 3rem; max-width: 1100px;}

/* ---- 버튼 둥글게 ---- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: 999px; border: 2px solid #8ec9f5; font-weight: 700;}
.stButton > button[kind="primary"] {background: #4a9fe0; border-color: #4a9fe0; color: #fff;}
div[data-baseweb="tab-list"] {gap: .2rem;}
button[data-baseweb="tab"] {border-radius: 12px 12px 0 0; font-weight: 700;}

/* ---- 슬림 배너 ---- */
.hero {background: linear-gradient(135deg, #d6ecff 0%, #eaf6ff 55%, #fff6cf 100%);
       border: 2px solid #bfe0fa; border-radius: 18px; padding: .75rem 1rem; margin: 0 0 .9rem;
       position: relative; overflow: hidden; color: #1b3a5c;}
.hero-title {font-size: 1.4rem; line-height: 1.3; margin: 0;}
.hero-sub {font-size: .9rem; margin-top: .15rem; color: #3b5f85;}
.hero-deco {position: absolute; right: 14px; top: 8px; font-size: 1.7rem; opacity: .9;}
.hero-deco2 {display: none;}

/* ---- 모바일 공통 ---- */
@media (max-width: 640px) {
  .block-container {padding-left: 0.8rem; padding-right: 0.8rem; padding-top: 4rem !important;}
  h1 {font-size: 1.6rem !important;}
  h2, h3 {font-size: 1.2rem !important;}
  .stButton > button, .stDownloadButton > button {min-height: 2.8rem;}
  div[data-baseweb="tab-list"] {overflow-x: auto;}
  button[data-baseweb="tab"] {padding-left: 0.6rem; padding-right: 0.6rem; white-space: nowrap;}
  .hero-title {font-size: 1.25rem;}
  .hero-deco {font-size: 1.4rem;}
}

/* ---- 카드 목록 ---- */
.kcards {display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 0.7rem; margin: 0.4rem 0 1rem;}
.kcard {border: 2px solid #cfe5f8; background: rgba(120,180,240,.10);
        border-radius: 18px; padding: 0.75rem 0.95rem; line-height: 1.5;}
.kcard.past {opacity: .55;}
.kcard .ktop {font-weight: 700; font-size: 1.05rem;}
.kcard .ksub {font-size: .95rem;}
.kcard .kmuted {font-size: .88rem; opacity: .75;}
.kcard .ktag {display: inline-block; font-size: .78rem; padding: 0 .55rem; margin-left: .3rem;
              border-radius: 999px; background: rgba(74,159,224,.22); vertical-align: middle;}
.kcard a {text-decoration: none;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero():
    st.markdown(
        "<div class='hero'>"
        "<div class='hero-deco'>🕊️</div>"
        "<div class='hero-title'>한성교회 유치부</div>"
        "<div class='hero-sub'>예수님 안에서 쑥쑥 자라는 아이들 🐑</div>"
        "</div>",
        unsafe_allow_html=True,
    )
