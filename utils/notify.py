import html
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import streamlit as st

APP_URL = "https://hsc-kinder.streamlit.app"
KST = ZoneInfo("Asia/Seoul")


def _cfg():
    try:
        m = st.secrets["mail"]
        return m["sender"], m["app_password"], m["pastor_to"]
    except Exception:
        return None


def send_mail(subject: str, lines):
    """목사님께 메일 발송. 실패해도 예외를 밖으로 내보내지 않는다. (성공 여부 반환)"""
    cfg = _cfg()
    if not cfg:
        return False
    sender, pw, to = cfg
    try:
        now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
        text = "\n".join(f"{k}: {v}" for k, v in lines) + f"\n\n접수 시각: {now}\n앱 바로가기: {APP_URL}"
        rows = "".join(
            f"<tr><td style='padding:4px 10px;color:#6b7c93;white-space:nowrap;vertical-align:top'>"
            f"{html.escape(str(k))}</td><td style='padding:4px 10px;font-weight:600'>"
            f"{html.escape(str(v)).replace(chr(10), '<br>')}</td></tr>" for k, v in lines)
        body = (f"<div style='font-family:sans-serif;font-size:15px;color:#1b3a5c'>"
                f"<table style='border-collapse:collapse'>{rows}</table>"
                f"<p style='color:#8a97a8;font-size:12px'>접수 시각 {now}</p>"
                f"<p><a href='{APP_URL}'>앱 바로가기</a></p></div>")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to
        msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
            s.login(sender, pw)
            s.sendmail(sender, [to], msg.as_string())
        return True
    except Exception:
        return False


def notify(kind: str, message: str = "", **fields):
    """notify('prayer', '...', 선생님=..., 내용=...) 형태로 호출. fields가 메일 본문이 됨."""
    titles = {"prayer": "[유치부] 새 기도제목 접수", "visit": "[유치부] 새 심방 요청 접수"}
    subject = titles.get(kind, "[유치부] 새 요청 접수")
    lines = [(k, v) for k, v in fields.items() if v not in (None, "")]
    if not lines:
        lines = [("알림", message or "새 요청이 접수되었습니다.")]
    return send_mail(subject, lines)
