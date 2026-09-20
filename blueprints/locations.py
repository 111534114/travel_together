from flask import Blueprint, flash, redirect, render_template, request, url_for  # 匯入 Flask 藍圖與常用功能

from activity_log import log_action  # 匯入操作紀錄共用函式
from auth import login_required  # 匯入登入/角色檢查裝飾器
from db import get_db_connection  # 匯入取得資料庫連線的函式
from utils import get_cities, normalize_place_name  # 匯入取得城市清單、異體字正規化函式
import wikidata_places  # 匯入 Wikidata 查詢函式，給沒有內建清單的國家即時查詢行政區用

locations_bp = Blueprint("locations", __name__, url_prefix="/content-admin/locations")  # 建立國家/城市管理藍圖，網址前綴 /content-admin/locations

PRESET_CITIES = {  # 定義常見國家的完整城市/行政區清單，讓內容管理員可以一鍵匯入，不用一筆一筆手動輸入
    # 每個城市是 (名稱, 地區) 的 tuple；地區沒有適合分類的就填 None，前端會直接顯示、不分組
    "台灣": [  # 台灣 6 直轄市 + 3 市 + 13 縣，共 22 個縣市，依慣用的北中南東離島分區
        ("台北市", "北部"), ("新北市", "北部"), ("基隆市", "北部"), ("桃園市", "北部"),
        ("新竹市", "北部"), ("新竹縣", "北部"), ("宜蘭縣", "北部"),
        ("台中市", "中部"), ("苗栗縣", "中部"), ("彰化縣", "中部"), ("南投縣", "中部"), ("雲林縣", "中部"),
        ("台南市", "南部"), ("高雄市", "南部"), ("嘉義市", "南部"), ("嘉義縣", "南部"), ("屏東縣", "南部"),
        ("花蓮縣", "東部"), ("台東縣", "東部"),
        ("澎湖縣", "離島"), ("金門縣", "離島"), ("連江縣", "離島"),
    ],
    "日本": [  # 日本 47 都道府縣，依慣用的 8 地方分區(近畿地方在旅遊語境常稱「關西」，故採此名)
        ("北海道", "北海道"),
        ("青森縣", "東北地方"), ("岩手縣", "東北地方"), ("宮城縣", "東北地方"),
        ("秋田縣", "東北地方"), ("山形縣", "東北地方"), ("福島縣", "東北地方"),
        ("茨城縣", "關東"), ("栃木縣", "關東"), ("群馬縣", "關東"), ("埼玉縣", "關東"),
        ("千葉縣", "關東"), ("東京都", "關東"), ("神奈川縣", "關東"),
        ("新潟縣", "中部地方"), ("富山縣", "中部地方"), ("石川縣", "中部地方"), ("福井縣", "中部地方"),
        ("山梨縣", "中部地方"), ("長野縣", "中部地方"), ("岐阜縣", "中部地方"),
        ("靜岡縣", "中部地方"), ("愛知縣", "中部地方"),
        ("三重縣", "關西"), ("滋賀縣", "關西"), ("京都府", "關西"), ("大阪府", "關西"),
        ("兵庫縣", "關西"), ("奈良縣", "關西"), ("和歌山縣", "關西"),
        ("鳥取縣", "中國地方"), ("島根縣", "中國地方"), ("岡山縣", "中國地方"),
        ("廣島縣", "中國地方"), ("山口縣", "中國地方"),
        ("德島縣", "四國"), ("香川縣", "四國"), ("愛媛縣", "四國"), ("高知縣", "四國"),
        ("福岡縣", "九州"), ("佐賀縣", "九州"), ("長崎縣", "九州"), ("熊本縣", "九州"),
        ("大分縣", "九州"), ("宮崎縣", "九州"), ("鹿兒島縣", "九州"), ("沖繩縣", "九州"),
    ],
    "泰國": [  # 泰國 76 府 + 曼谷首都圈，共 77 個一級行政區(依維基百科「泰國行政區劃」條目整理，暫無地區分類)
        ("曼谷", None), ("安納乍倫府", None), ("紅統府", None), ("汶干府", None), ("武里南府", None),
        ("差春騷府", None), ("猜納府", None), ("猜也蓬府", None), ("莊他武里府", None), ("清邁府", None),
        ("清萊府", None), ("春武里府", None), ("春蓬府", None), ("加拉信府", None), ("甘烹碧府", None),
        ("北碧府", None), ("孔敬府", None), ("甲米府", None), ("南邦府", None), ("南奔府", None),
        ("黎府", None), ("華富里府", None), ("夜豐頌府", None), ("馬哈沙拉堪府", None), ("穆達漢府", None),
        ("那空那育府", None), ("佛統府", None), ("那空拍儂府", None), ("那空叻差是瑪府", None), ("那空沙旺府", None),
        ("那空是貪瑪叻府", None), ("難府", None), ("那拉提瓦府", None), ("農磨蘭普府", None), ("廊開府", None),
        ("暖武里府", None), ("巴吞他尼府", None), ("北大年府", None), ("攀牙府", None), ("博他侖府", None),
        ("帕堯府", None), ("碧差汶府", None), ("碧武里府", None), ("披集府", None), ("彭世洛府", None),
        ("大城府", None), ("帕府", None), ("普吉府", None), ("巴真府", None), ("巴蜀府", None),
        ("拉廊府", None), ("叻武里府", None), ("羅勇府", None), ("黎逸府", None), ("沙繳府", None),
        ("沙功那空府", None), ("沙沒巴干府", None), ("沙沒沙空府", None), ("沙沒頌堪府", None), ("沙拉武里府", None),
        ("沙敦府", None), ("信武里府", None), ("四色菊府", None), ("宋卡府", None), ("素可泰府", None),
        ("素攀府", None), ("素叻他尼府", None), ("素林府", None), ("達府", None), ("董里府", None),
        ("達叻府", None), ("烏汶府", None), ("烏隆府", None), ("烏泰他尼府", None), ("程逸府", None),
        ("也拉府", None), ("益梭通府", None),
    ],
    "韓國": [  # 韓國第一級行政區(依維基百科「韓國行政區劃」條目整理，含 2026 年光州與全羅南道合併為統合特別市，暫無地區分類)
        (name, None) for name in [
            "首爾特別市", "全南光州統合特別市", "世宗特別自治市", "釜山廣域市", "大邱廣域市",
            "仁川廣域市", "大田廣域市", "蔚山廣域市", "京畿道", "江原特別自治道",
            "忠清北道", "忠清南道", "全北特別自治道", "慶尚北道", "慶尚南道", "濟州特別自治道",
        ]
    ],
}


@locations_bp.route("/")  # 設定國家與城市管理頁路由
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def manage_locations():  # 定義國家與城市管理頁函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template("content_admin/locations.html", countries=[], cities=[])  # 回傳空清單頁面

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢資料
        cursor.execute("""
            SELECT co.country_id, co.name,
                   COUNT(DISTINCT ci.city_id) AS city_count
            FROM countries co
            LEFT JOIN cities ci ON ci.country_id = co.country_id
            GROUP BY co.country_id, co.name
            ORDER BY co.name
        """)  # 查詢所有國家，並統計每個國家底下有幾個城市
        countries = cursor.fetchall()  # 取出國家清單

        cities = get_cities(cursor)  # 查詢所有城市，已經依國家、地區慣用順序、城市名稱排序好

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    location_groups = []  # 組成方便樣板顯示的巢狀結構：每個國家底下依地區分組(沒有地區分類的城市自成一組，排在最後)
    for country in countries:  # 逐一處理每個國家
        country_cities = [city for city in cities if city["country_id"] == country["country_id"]]  # 篩選出這個國家的城市(cities 已經照地區排序過)
        regions = []  # 這個國家底下的地區分組清單
        current_region = "__unset__"  # 用一個不可能出現的值當初始標記，確保第一筆一定會開新分組
        for city in country_cities:  # 逐一處理每個城市(已經照地區排序，同地區的會連續出現)
            if city["region"] != current_region:  # 如果跟目前分組的地區不同(包含第一筆、或換到下一個地區)
                regions.append({"name": city["region"], "cities": []})  # 開一個新的地區分組
                current_region = city["region"]  # 更新目前分組的地區標記
            regions[-1]["cities"].append(city)  # 把這個城市加進目前分組
        location_groups.append({"country": country, "regions": regions})  # 加入這個國家的完整分組結果

    return render_template(  # 渲染國家與城市管理頁面
        "content_admin/locations.html",
        countries=countries,  # 國家清單
        cities=cities,  # 城市清單
        location_groups=location_groups,  # 依國家、地區分組好的城市清單(給城市區塊顯示用)
    )


@locations_bp.route("/countries/new", methods=["POST"])  # 設定新增國家的路由，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_country():  # 定義新增國家函式
    name = request.form.get("name", "").strip()  # 取得表單輸入的國家名稱

    if not name:  # 如果名稱是空的
        flash("請輸入國家名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試新增資料
        cursor.execute("INSERT INTO countries(name) VALUES (%s)", (name,))  # 執行新增國家的 SQL
        log_action(cursor, "create_country", "country", cursor.lastrowid, f"新增國家：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家新增成功", "success")  # 顯示成功訊息
    except Exception as error:  # 如果新增過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("新增國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("新增國家失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/countries/<int:country_id>/edit", methods=["POST"])  # 設定編輯國家名稱的路由，網址帶入國家 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_country(country_id):  # 定義編輯國家函式
    name = request.form.get("name", "").strip()  # 取得表單輸入的新國家名稱

    if not name:  # 如果名稱是空的
        flash("請輸入國家名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        cursor.execute(  # 執行更新國家名稱的 SQL
            "UPDATE countries SET name = %s WHERE country_id = %s",
            (name, country_id)
        )
        log_action(cursor, "update_country", "country", country_id, f"更新國家名稱為：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家名稱已更新", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("更新國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("更新國家失敗，名稱可能已存在", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/countries/<int:country_id>/delete", methods=["POST"])  # 設定刪除國家的路由，網址帶入國家 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_country(country_id):  # 定義刪除國家函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試刪除資料
        cursor.execute("SELECT name FROM countries WHERE country_id = %s", (country_id,))  # 先查出國家名稱，等下寫操作紀錄要用
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute("DELETE FROM countries WHERE country_id = %s", (country_id,))  # 執行刪除國家的 SQL

        if existing:  # 如果原本有查到這個國家(代表確實刪除了)
            log_action(cursor, "delete_country", "country", country_id, f"刪除國家：{existing[0]}")  # 寫入操作紀錄

        connection.commit()  # 提交交易(國家資料與操作紀錄一起寫入)
        flash("國家已刪除", "success")  # 顯示成功訊息
    except Exception as error:  # 如果刪除過程發生例外(例如底下還有城市，外鍵擋住)
        connection.rollback()  # 回復交易
        print("刪除國家失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除失敗，此國家底下仍有城市，請先刪除相關城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/countries/<int:country_id>/import-cities", methods=["POST"])  # 設定一鍵匯入該國家所有城市的路由，網址帶入國家 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def import_preset_cities(country_id):  # 定義一鍵匯入城市函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始執行匯入
        cursor.execute("SELECT name FROM countries WHERE country_id = %s", (country_id,))  # 查出這個國家的名稱，才能對照預設清單
        country = cursor.fetchone()  # 取得查詢結果

        if not country:  # 如果找不到這個國家
            flash("找不到這個國家", "error")  # 顯示錯誤提示
        else:
            country_name = country["name"]  # 取出國家名稱，方便後面重複使用
            source_note = ""  # 預設不附加來源說明(內建清單不需要特別註明)
            preset_items = None  # 預設還沒有取得任何清單，每一筆是 (城市名稱, 地區或 None) 的 tuple

            if country_name in PRESET_CITIES:  # 如果這個國家有內建、已經查證過的城市清單
                preset_items = [  # 直接使用內建清單(正規化異體字，地區維持原樣)
                    (normalize_place_name(name), region) for name, region in PRESET_CITIES[country_name]
                ]
            else:  # 如果沒有內建清單，改即時向 Wikidata 查詢
                try:  # 嘗試查詢
                    raw_names = wikidata_places.get_admin_divisions(country_name)  # 即時查詢這個國家的第一級行政區中文名稱
                except wikidata_places.WikidataError as error:  # 如果查詢過程發生錯誤(連線失敗、服務異常等)
                    flash(f"查詢「{country_name}」的城市清單失敗，請稍後再試或手動新增：{error}", "error")  # 顯示錯誤提示
                    raw_names = []  # 視為查無資料，往下不會執行匯入

                if raw_names:  # 如果有查到行政區名稱
                    preset_items = [(normalize_place_name(name), None) for name in raw_names]  # 正規化異體字(Wikidata 查詢結果沒有地區分類)
                    source_note = "（來源：維基百科，建議確認名稱正確性）"  # 附加來源說明，提醒可能需要人工確認
                else:  # 如果查無資料(國家對不到、或沒有中文名稱資料)
                    flash(f"在維基百科查不到「{country_name}」的行政區資料，請手動新增城市", "error")  # 顯示錯誤提示

            if preset_items:  # 如果最後有取得可用的城市清單(不論是內建還是 Wikidata 查詢到的)
                cursor.execute("SELECT name FROM cities WHERE country_id = %s", (country_id,))  # 查出這個國家目前已有的城市名稱
                existing_names = {normalize_place_name(row["name"]) for row in cursor.fetchall()}  # 整理成集合，方便比對避免重複

                new_items = [(name, region) for name, region in preset_items if name not in existing_names]  # 篩選出還沒有的城市

                for name, region in new_items:  # 逐一新增缺少的城市(附帶地區分類)
                    cursor.execute("INSERT INTO cities(country_id, name, region) VALUES (%s, %s, %s)", (country_id, name, region))

                log_action(  # 把這次一鍵匯入寫入操作紀錄
                    cursor, "import_preset_cities", "country", country_id,
                    f"一鍵匯入 {country_name} 城市 {len(new_items)} 筆"
                )
                connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)

                if new_items:  # 如果有新增到城市
                    flash(f"已匯入 {len(new_items)} 個城市{source_note}", "success")  # 顯示成功訊息
                else:  # 如果全部城市原本就都已經有了
                    flash("這個國家的城市清單已經是最新的，沒有新增任何城市", "success")  # 顯示提示訊息
    except Exception as error:  # 如果匯入過程發生例外
        connection.rollback()  # 回復交易
        print("一鍵匯入城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("匯入失敗，請再試一次", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/new", methods=["POST"])  # 設定新增城市的路由，只允許 POST
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def create_city():  # 定義新增城市函式
    country_id = request.form.get("country_id", "").strip()  # 取得表單選擇的國家 ID
    name = request.form.get("name", "").strip()  # 取得表單輸入的城市名稱
    region = request.form.get("region", "").strip() or None  # 取得表單輸入的地區分類(選填，空字串轉成 None)

    if not country_id or not name:  # 如果國家沒選或名稱是空的
        flash("請選擇國家並輸入城市名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試新增資料
        cursor.execute(  # 執行新增城市的 SQL
            "INSERT INTO cities(country_id, name, region) VALUES (%s, %s, %s)",
            (country_id, name, region)
        )
        log_action(cursor, "create_city", "city", cursor.lastrowid, f"新增城市：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市新增成功", "success")  # 顯示成功訊息
    except Exception as error:  # 如果新增過程發生例外(例如同一國家下城市名稱重複)
        connection.rollback()  # 回復交易
        print("新增城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("新增城市失敗，此國家下可能已有相同名稱的城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/<int:city_id>/edit", methods=["POST"])  # 設定編輯城市的路由，網址帶入城市 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def edit_city(city_id):  # 定義編輯城市函式
    country_id = request.form.get("country_id", "").strip()  # 取得表單選擇的所屬國家 ID
    name = request.form.get("name", "").strip()  # 取得表單輸入的城市名稱

    if not country_id or not name:  # 如果國家沒選或名稱是空的
        flash("請選擇國家並輸入城市名稱", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試更新資料
        region = request.form.get("region", "").strip() or None  # 取得表單輸入的地區分類(選填，空字串轉成 None)
        cursor.execute(  # 執行更新城市資料的 SQL(可同時更換所屬國家、地區分類)
            "UPDATE cities SET country_id = %s, name = %s, region = %s WHERE city_id = %s",
            (country_id, name, region, city_id)
        )
        log_action(cursor, "update_city", "city", city_id, f"更新城市資料為：{name}")  # 寫入操作紀錄
        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市資料已更新", "success")  # 顯示成功訊息
    except Exception as error:  # 如果更新過程發生例外(例如名稱重複)
        connection.rollback()  # 回復交易
        print("更新城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("更新城市失敗，此國家下可能已有相同名稱的城市", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁


@locations_bp.route("/cities/<int:city_id>/delete", methods=["POST"])  # 設定刪除城市的路由，網址帶入城市 ID
@login_required("content_admin")  # 限制只有內容管理員登入後才能存取
def delete_city(city_id):  # 定義刪除城市函式
    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 嘗試刪除資料
        cursor.execute("SELECT name FROM cities WHERE city_id = %s", (city_id,))  # 先查出城市名稱，等下寫操作紀錄要用
        existing = cursor.fetchone()  # 取得查詢結果(可能為 None)

        cursor.execute("DELETE FROM cities WHERE city_id = %s", (city_id,))  # 執行刪除城市的 SQL

        if existing:  # 如果原本有查到這個城市(代表確實刪除了)
            log_action(cursor, "delete_city", "city", city_id, f"刪除城市：{existing[0]}")  # 寫入操作紀錄

        connection.commit()  # 提交交易(城市資料與操作紀錄一起寫入)
        flash("城市已刪除", "success")  # 顯示成功訊息
    except Exception as error:  # 如果刪除過程發生例外(例如仍有景點/餐廳/住宿使用這個城市，外鍵擋住)
        connection.rollback()  # 回復交易
        print("刪除城市失敗：", error)  # 在伺服器端印出錯誤內容
        flash("刪除失敗，此城市仍有景點、餐廳或住宿使用中", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("locations.manage_locations"))  # 導回國家與城市管理頁
