import io  # 匯入 io，用來在記憶體中組出 CSV 檔案內容
import os  # 匯入作業系統相關功能，用來處理檔案路徑與資料夾
import uuid  # 匯入 uuid，用來產生不重複的檔名
import csv  # 匯入 csv，用來寫出 CSV 格式的內容

from flask import Response, current_app  # 匯入 Response(組成檔案下載回應)、current_app(取得目前執行中的 Flask 應用程式)
from werkzeug.utils import secure_filename  # 匯入 secure_filename，把檔名轉成安全、不含危險字元的格式

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}  # 定義允許上傳的圖片副檔名集合


def _extension(filename):  # 定義內部函式：取出檔名的副檔名(小寫)
    if "." not in filename:  # 如果檔名裡沒有點(代表沒有副檔名)
        return ""  # 回傳空字串

    return filename.rsplit(".", 1)[1].lower()  # 從最後一個點切開，取後半段並轉小寫作為副檔名


def save_uploaded_image(file_storage, subfolder):  # 定義儲存上傳圖片的函式，subfolder 是要存到哪個子資料夾(例如 attractions)
    if file_storage is None or file_storage.filename == "":  # 如果沒有選擇檔案(欄位是空的)
        return None  # 回傳 None，代表沒有新圖片要處理

    extension = _extension(file_storage.filename)  # 取得上傳檔案的副檔名

    if extension not in ALLOWED_IMAGE_EXTENSIONS:  # 如果副檔名不在允許清單內
        raise ValueError("不支援的圖片格式，請上傳 png、jpg、jpeg、gif 或 webp")  # 拋出例外，讓呼叫端顯示錯誤訊息

    stored_name = f"{uuid.uuid4().hex}.{extension}"  # 用亂數產生的 uuid 當檔名，避免不同使用者上傳同名檔案互相覆蓋
    safe_name = secure_filename(stored_name)  # 再用 secure_filename 過濾一次，確保檔名安全

    upload_dir = os.path.join(current_app.static_folder, "uploads", subfolder)  # 組成實際要存放的資料夾路徑(static/uploads/子資料夾)
    os.makedirs(upload_dir, exist_ok=True)  # 建立資料夾，如果已存在就不報錯

    file_storage.save(os.path.join(upload_dir, safe_name))  # 把上傳的檔案實際寫入硬碟

    return f"uploads/{subfolder}/{safe_name}"  # 回傳相對路徑，方便存進資料庫的 image_path 欄位


def delete_uploaded_image(relative_path):  # 定義刪除已上傳圖片的函式，relative_path 是資料庫裡存的相對路徑
    if not relative_path:  # 如果路徑是空值(代表原本就沒有圖片)
        return  # 直接結束，不用做任何事

    full_path = os.path.join(current_app.static_folder, relative_path)  # 組成圖片在硬碟上的完整路徑

    if os.path.isfile(full_path):  # 如果該檔案確實存在
        try:  # 嘗試刪除檔案
            os.remove(full_path)  # 從硬碟刪除圖片檔案
        except OSError:  # 如果刪除過程發生系統錯誤(例如檔案被占用)
            pass  # 不中斷程式，直接略過(圖片頂多變成孤兒檔案，不影響資料庫資料)


def get_countries(cursor):  # 定義取得所有國家清單的共用函式，cursor 是已開啟的資料庫游標
    cursor.execute("SELECT country_id, name FROM countries ORDER BY name")  # 查詢所有國家，依名稱排序
    return cursor.fetchall()  # 回傳查詢結果(國家清單)


def get_cities(cursor, country_id=None):  # 定義取得城市清單的共用函式，可選擇只取某個國家底下的城市
    if country_id:  # 如果有指定國家 ID
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            WHERE country_id = %s
            ORDER BY name
            """,  # 只查詢屬於該國家的城市，依名稱排序
            (country_id,)  # 帶入國家 ID 參數
        )
    else:  # 如果沒有指定國家 ID
        cursor.execute(
            """
            SELECT city_id, country_id, name
            FROM cities
            ORDER BY name
            """  # 查詢所有城市，依名稱排序
        )

    return cursor.fetchall()  # 回傳查詢結果(城市清單)


def get_categories(cursor, category_type):  # 定義取得指定類型分類清單的共用函式(例如景點/餐廳/住宿分類)
    cursor.execute(
        """
        SELECT category_id, category_name
        FROM categories
        WHERE category_type = %s
        ORDER BY category_name
        """,  # 依分類類型查詢，並依分類名稱排序
        (category_type,)  # 帶入分類類型參數
    )
    return cursor.fetchall()  # 回傳查詢結果(分類清單)


def get_or_create_country(cursor, name):  # 定義函式：依名稱找國家，找不到就自動新增(給 CSV 匯入用)，cursor 需為非字典格式
    cursor.execute("SELECT country_id FROM countries WHERE name = %s", (name,))  # 查詢是否已有同名國家
    row = cursor.fetchone()  # 取得查詢結果(一筆 tuple 或 None)

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該國家的 ID

    cursor.execute("INSERT INTO countries(name) VALUES (%s)", (name,))  # 不存在就新增這個國家
    return cursor.lastrowid  # 回傳新增後產生的國家 ID


def get_or_create_city(cursor, country_id, name):  # 定義函式：依國家 ID 與城市名稱找城市，找不到就自動新增
    cursor.execute(  # 查詢該國家底下是否已有同名城市
        "SELECT city_id FROM cities WHERE country_id = %s AND name = %s",
        (country_id, name)
    )
    row = cursor.fetchone()  # 取得查詢結果

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該城市的 ID

    cursor.execute(  # 不存在就新增這個城市
        "INSERT INTO cities(country_id, name) VALUES (%s, %s)",
        (country_id, name)
    )
    return cursor.lastrowid  # 回傳新增後產生的城市 ID


def get_or_create_category(cursor, category_type, name):  # 定義函式：依類型與名稱找分類，找不到就自動新增
    if not name:  # 如果沒有提供分類名稱
        return None  # 直接回傳 None，代表不設定分類

    cursor.execute(  # 查詢該類型底下是否已有同名分類
        "SELECT category_id FROM categories WHERE category_type = %s AND category_name = %s",
        (category_type, name)
    )
    row = cursor.fetchone()  # 取得查詢結果

    if row:  # 如果已經存在
        return row[0]  # 直接回傳該分類的 ID

    cursor.execute(  # 不存在就新增這個分類
        "INSERT INTO categories(category_type, category_name) VALUES (%s, %s)",
        (category_type, name)
    )
    return cursor.lastrowid  # 回傳新增後產生的分類 ID


def csv_response(filename, header, rows):  # 定義共用函式：把表頭與資料列組成可下載的 CSV 回應(給匯出統計、匯入範本共用)
    buffer = io.StringIO()  # 建立一個記憶體中的文字緩衝區
    buffer.write("﻿")  # 寫入 UTF-8 BOM，讓 Excel 開啟 CSV 時能正確辨識中文編碼
    writer = csv.writer(buffer)  # 建立 CSV 寫入器，綁定到這個緩衝區
    writer.writerow(header)  # 寫入表頭那一列
    writer.writerows(rows)  # 寫入所有資料列

    return Response(  # 組成 Flask 回應物件
        buffer.getvalue(),  # 回應內容為緩衝區裡累積的所有文字
        mimetype="text/csv",  # 設定回應的內容類型為 CSV
        headers={"Content-Disposition": f"attachment; filename={filename}"}  # 設定為附件下載，並指定檔名
    )
