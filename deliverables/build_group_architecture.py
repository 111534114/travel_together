"""Generate the detailed group-travel functional architecture diagram."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "走吧揪團_揪團功能子架構圖.png"
FONT = Path(r"C:\Windows\Fonts\msjh.ttc")

W, H = 3600, 2880
NAVY = "#10374c"
TEAL = "#087f95"
LINE = "#8bc8d2"
PALE = "#eaf7f9"
WHITE = "#ffffff"
TEXT = "#163b4d"
MUTED = "#53727e"

image = Image.new("RGB", (W, H), "#f7fbfc")
draw = ImageDraw.Draw(image)
title_font = ImageFont.truetype(str(FONT), 88)
section_font = ImageFont.truetype(str(FONT), 62)
label_font = ImageFont.truetype(str(FONT), 47)
small_font = ImageFont.truetype(str(FONT), 42)


def centered(text, box, font, fill=TEXT):
    x0, y0, x1, y1 = box
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(((x0 + x1 - width) / 2, (y0 + y1 - height) / 2 - bounds[1]), text, font=font, fill=fill)


draw.rounded_rectangle((280, 55, W - 280, 210), radius=28, fill=NAVY)
centered("走吧揪團  揪團功能子架構圖", (280, 55, W - 280, 210), title_font, WHITE)

draw.line((W // 2, 210, W // 2, 265), fill=LINE, width=6)
draw.rounded_rectangle((300, 265, W - 300, 410), radius=24, fill=PALE, outline=LINE, width=4)
centered("LINE 綁定 → 資格申請與審核 → 官方活動出席 → 開放加入與發起揪團", (300, 265, W - 300, 410), section_font)

columns = [
    ("會員  找團與參加", [
        "搜尋篩選與查看揪團詳情", "加入前查看公開團員與簡介", "申請加入與撤回申請", "查看審核結果與團內行程",
        "依權限使用聊天室與相簿", "退出揪團與名單顯示設定", "查看成團結果與通知", "旅後心得  雙向評價與檢舉",
    ]),
    ("主揪  發起與管理", [
        "新手引導與團長等級", "新建或沿用私人行程開團", "設定日期  名額與報名截止", "審核申請  核准與婉拒",
        "設定查看者與共同編輯權限", "編輯行程  集合資訊與通知", "截止後確認成團或未成團", "標記出席  暫停取消與恢復揪團",
    ]),
    ("旅遊內容管理員", [
        "審核交友揪團資格申請", "建立與編輯官方活動", "設定活動報名截止時間", "核對活動報到與未到紀錄",
        "處理揪團與照片檢舉", "審查國際揪團資格", "管理團內聊天敏感詞",
    ]),
    ("系統管理員", [
        "開關交友揪團功能", "管理會員角色與狀態", "審核公開行程內容", "活動當日提早解鎖揪團",
        "查看全站統計報表", "查核管理操作紀錄",
    ]),
]

margin, gap = 70, 36
cw = (W - margin * 2 - gap * 3) // 4
top, bottom = 505, 2750
for index, (heading, items) in enumerate(columns):
    left = margin + index * (cw + gap)
    right = left + cw
    draw.rounded_rectangle((left, top, right, bottom), radius=28, fill=PALE, outline=LINE, width=4)
    draw.rounded_rectangle((left, top, right, top + 160), radius=28, fill=TEAL if index < 2 else NAVY)
    draw.rectangle((left, top + 125, right, top + 160), fill=TEAL if index < 2 else NAVY)
    centered(heading, (left + 12, top + 10, right - 12, top + 150), section_font, WHITE)
    row_top = top + 210
    row_height = 214
    row_gap = 28
    for item in items:
        row = (left + 28, row_top, right - 28, row_top + row_height)
        draw.rounded_rectangle(row, radius=18, fill=WHITE, outline="#b9dce2", width=3)
        font = label_font if len(item) <= 14 else small_font
        centered(item, row, font)
        row_top += row_height + row_gap

centered("依目前系統功能整理  ·  會員須完成資格審核及官方活動出席後才可加入或開團", (100, 2770, W - 100, 2850), small_font, MUTED)
image.save(OUTPUT, optimize=True)
print(OUTPUT)
