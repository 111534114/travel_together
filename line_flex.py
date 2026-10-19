"""LINE Flex Message（卡片訊息）的小工具：組出 bubble / carousel 需要的 JSON 結構。

規格參考 LINE 官方文件 Flex Message；卡片上的按鈕連結需要公開的 https 網址（config.PUBLIC_BASE_URL），
沒有設定時會自動省略連結按鈕，卡片仍可正常顯示。
"""
from config import PUBLIC_BASE_URL  # 匯入網站公開網址

PRIMARY = "#00A9C0"  # 網站主色（青藍）
PRIMARY_DEEP = "#066275"
ACCENT = "#FFC53D"  # 網站強調色（黃）
INK = "#23373A"
MUTED = "#708284"
ALT_TEXT_LIMIT = 400  # LINE 規定 altText 最多 400 字


def public_link(path):  # 網站路徑轉成公開網址；沒有設定公開網址時回傳空字串
    return f"{PUBLIC_BASE_URL}{path}" if PUBLIC_BASE_URL.startswith("https://") else ""


def text(content, **style):
    return {"type": "text", "text": str(content) or " ", "wrap": True, **style}


def box(layout, contents, **style):
    return {"type": "box", "layout": layout, "contents": contents, **style}


def separator():
    return {"type": "separator", "margin": "lg", "color": "#E1EBEC"}


def info_row(label, value):  # 左邊灰色標籤、右邊內容的一列
    return box("baseline", [
        text(label, size="sm", color=MUTED, flex=2),
        text(value, size="sm", color=INK, flex=6),
    ], spacing="sm")


def uri_button(label, path, style="primary"):  # 打開網頁的按鈕；沒有公開網址時回傳 None
    url = public_link(path)
    if not url:
        return None
    button = {"type": "button", "style": style, "height": "sm", "action": {"type": "uri", "label": label, "uri": url}}
    if style == "primary":
        button["color"] = PRIMARY
    return button


def message_button(label, message):  # 點了會在聊天室送出文字的按鈕（交給關鍵字回覆處理）
    return {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": label, "text": message}}


def header(kicker, title, color=PRIMARY):  # 卡片上方的色塊標題
    return box("vertical", [
        text(kicker, size="sm", color="#FFFFFFCC", weight="bold"),
        text(title, size="xl", color="#FFFFFF", weight="bold", margin="sm"),
    ], backgroundColor=color, paddingAll="20px")


def bubble(header_box, body_contents, buttons=(), hero_url="", size="mega"):
    result = {
        "type": "bubble",
        "size": size,
        "header": header_box,
        "body": box("vertical", body_contents, spacing="md", paddingAll="20px"),
    }
    if hero_url:
        result["hero"] = {"type": "image", "url": hero_url, "size": "full", "aspectRatio": "20:9", "aspectMode": "cover"}
    buttons = [button for button in buttons if button]
    if buttons:
        result["footer"] = box("vertical", buttons, spacing="sm", paddingAll="16px")
    return result


def flex_message(alt_text, contents):  # 包成可以直接送出的訊息；altText 會顯示在通知和聊天列表
    return {"type": "flex", "altText": alt_text[:ALT_TEXT_LIMIT], "contents": contents}


def carousel(bubbles):  # 多張卡片左右滑動（LINE 上限 12 張）
    return {"type": "carousel", "contents": bubbles[:12]}


def image_url(path):  # 網站上傳的圖片（例如行程封面）轉成 LINE 抓得到的公開網址
    if not path:
        return ""
    if path.startswith("https://"):
        return path
    return public_link(f"/static/{path}")
