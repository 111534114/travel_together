import smtplib
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from config import SMTP_FROM_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME


def send_password_reset_email(to_email, reset_url):
    """寄送重設密碼信。SMTP 設定不完整或寄送失敗時回傳 False，由呼叫端決定如何提示使用者。"""
    if not (SMTP_HOST and SMTP_USERNAME and SMTP_PASSWORD):
        print("尚未設定 SMTP，略過寄送重設密碼信。")
        return False

    subject = "走吧揪團｜重設密碼"
    body = (
        "你好，\n\n"
        "我們收到重設你「走吧揪團」帳號密碼的請求。\n"
        f"請在 30 分鐘內點擊以下連結設定新密碼：\n{reset_url}\n\n"
        "如果這不是你本人的操作，請忽略這封信，你的密碼不會被更改。\n"
    )
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = Header(subject, "utf-8")
    message["From"] = formataddr((str(Header("走吧揪團", "utf-8")), SMTP_FROM_EMAIL))
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=SMTP_FROM_EMAIL.split("@")[-1])

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM_EMAIL, [to_email], message.as_string())
        return True
    except Exception as error:
        print("寄送重設密碼信失敗：", error)
        return False
