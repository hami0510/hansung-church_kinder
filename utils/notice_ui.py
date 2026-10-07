import html
import pandas as pd
import streamlit as st


def notice_cards(df):
    if df is None or df.empty:
        return
    out = ["<div class='kcards' style='grid-template-columns:1fr'>"]
    for _, r in df.iterrows():
        pinned = str(r.get("pinned")).lower() == "true"
        try:
            when = pd.to_datetime(r["created_at"], utc=True).tz_convert("Asia/Seoul")
            when = f"{when:%Y.%m.%d}"
        except Exception:
            when = ""
        content = r.get("content")
        content = html.escape(content).replace("\n", "<br>") if isinstance(content, str) else ""
        out.append(
            "<div class='kcard'>"
            f"<div class='ktop'>{'📌 ' if pinned else '📢 '}{html.escape(str(r['title']))}</div>"
            f"<div class='kmuted'>{when}</div>"
            + (f"<div class='ksub' style='margin-top:.3rem'>{content}</div>" if content else "")
            + "</div>"
        )
    out.append("</div>")
    st.markdown("".join(out), unsafe_allow_html=True)
