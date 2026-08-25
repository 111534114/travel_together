from flask import Flask, render_template, request, redirect, url_for, session, flash  # 匯入 Flask 核心功能：建立 App、渲染樣板、取得請求、導向、產生網址、session、顯示訊息
from mysql.connector import Error  # 匯入 MySQL 連線錯誤類別，用來捕捉資料庫例外
from werkzeug.security import check_password_hash, generate_password_hash  # 匯入密碼工具：驗證密碼、產生密碼雜湊值

from db import get_db_connection  # 匯入自訂的資料庫連線函式
from blueprints.attractions import attractions_bp  # 匯入景點管理的藍圖(Blueprint)
from blueprints.restaurants import restaurants_bp  # 匯入餐廳管理的藍圖
from blueprints.accommodations import accommodations_bp  # 匯入住宿管理的藍圖
from blueprints.locations import locations_bp  # 匯入國家/城市管理的藍圖
from blueprints.categories import categories_bp  # 匯入分類管理的藍圖
from blueprints.proposals import proposals_bp  # 匯入會員提案審核的藍圖
from blueprints.ai_data import ai_data_bp  # 匯入 AI 使用資料維護的藍圖
from blueprints.reports import reports_bp  # 匯入統計報表匯出的藍圖
from blueprints.logs import logs_bp  # 匯入操作紀錄查詢的藍圖
from blueprints.member import member_bp  # 匯入會員功能的藍圖

app = Flask(__name__)  # 建立 Flask 應用程式實例

# Session 加密金鑰，之後可以改成更複雜的字串
app.secret_key = "travel-together-secret-key"  # 設定 session 加密金鑰，用來簽章 cookie 防止竄改

# 上傳圖片大小限制（8MB）
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 限制單次請求上傳資料的最大位元組數為 8MB

app.register_blueprint(attractions_bp)  # 註冊景點管理路由
app.register_blueprint(restaurants_bp)  # 註冊餐廳管理路由
app.register_blueprint(accommodations_bp)  # 註冊住宿管理路由
app.register_blueprint(locations_bp)  # 註冊國家/城市管理路由
app.register_blueprint(categories_bp)  # 註冊分類管理路由
app.register_blueprint(proposals_bp)  # 註冊提案審核路由
app.register_blueprint(ai_data_bp)  # 註冊 AI 資料維護路由
app.register_blueprint(reports_bp)  # 註冊統計報表路由
app.register_blueprint(logs_bp)  # 註冊操作紀錄路由
app.register_blueprint(member_bp)  # 註冊會員功能路由


def redirect_by_role(role):  # 定義函式：依照使用者角色導向對應首頁
    if role == "member":  # 如果角色是一般會員
        return redirect(url_for("member_home"))  # 導向會員首頁路由

    if role == "content_admin":  # 如果角色是旅遊內容管理員
        return redirect(url_for("content_admin_home"))  # 導向內容管理員首頁路由

    if role == "system_admin":  # 如果角色是系統管理員
        return redirect(url_for("system_admin_home"))  # 導向系統管理員首頁路由

    session.clear()  # 角色不在預期範圍內，清空 session 避免殘留錯誤狀態
    flash("帳號角色設定錯誤。", "error")  # 顯示錯誤訊息給使用者
    return redirect(url_for("login"))  # 導回登入頁


@app.route("/")  # 設定網站根目錄路由
def index():  # 定義首頁進入點函式
    if "user_id" in session:  # 如果 session 裡已經有登入者
        return redirect_by_role(session.get("role"))  # 依角色導向對應首頁

    return redirect(url_for("visitor"))  # 尚未登入則導向訪客頁面


@app.route("/visitor")  # 設定訪客頁面路由
def visitor():  # 定義訪客頁面函式
    return render_template("visitor.html")  # 回傳訪客頁面樣板


@app.route("/login", methods=["GET", "POST"])  # 設定登入頁路由，允許 GET(顯示表單) 與 POST(送出表單)
def login():  # 定義登入功能函式
    if "user_id" in session:  # 如果已經登入
        return redirect_by_role(session.get("role"))  # 直接依角色導向，不用再登入一次

    if request.method == "POST":  # 如果是表單送出(POST)請求
        username = request.form.get("username", "").strip()  # 取得使用者輸入的帳號並去除頭尾空白
        password = request.form.get("password", "")  # 取得使用者輸入的密碼

        if not username or not password:  # 如果帳號或密碼有一個是空的
            flash("請輸入帳號和密碼。", "error")  # 顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        connection = get_db_connection()  # 嘗試建立資料庫連線

        if connection is None:  # 如果連線失敗
            flash("資料庫連線失敗，請稍後再試。", "error")  # 顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        cursor = connection.cursor(dictionary=True)  # 建立資料庫游標，查詢結果以字典格式回傳

        try:  # 開始執行查詢，之後不論成功失敗都要關閉連線
            cursor.execute(  # 執行 SQL 查詢
                """
                SELECT user_id, username, password_hash,
                       full_name, nickname, role, status
                FROM users
                WHERE username = %s
                LIMIT 1
                """,  # 依帳號查詢使用者資料(只取一筆)
                (username,)  # 帶入查詢參數：使用者輸入的帳號
            )

            user = cursor.fetchone()  # 取得查詢結果的第一筆(查無資料則為 None)

        finally:  # 不論上面有沒有出錯，都要執行以下清理動作
            cursor.close()  # 關閉游標
            connection.close()  # 關閉資料庫連線

        if user is None:  # 如果查無此帳號
            flash("帳號或密碼錯誤。", "error")  # 顯示錯誤提示(刻意不區分帳號或密碼錯誤，避免洩漏帳號是否存在)
            return render_template("login.html")  # 重新顯示登入頁

        if user["status"] != "active":  # 如果帳號狀態不是啟用中
            flash("此帳號目前已停用，無法登入。", "error")  # 顯示停用提示
            return render_template("login.html")  # 重新顯示登入頁

        if not check_password_hash(user["password_hash"], password):  # 驗證輸入密碼與資料庫雜湊值是否相符
            flash("帳號或密碼錯誤。", "error")  # 密碼不符，顯示錯誤提示
            return render_template("login.html")  # 重新顯示登入頁

        session.clear()  # 登入成功前先清空舊的 session 資料
        session["user_id"] = user["user_id"]  # 把使用者 ID 存入 session
        session["username"] = user["username"]  # 把帳號存入 session
        session["full_name"] = user["full_name"]  # 把姓名存入 session
        session["nickname"] = user["nickname"]  # 把暱稱存入 session
        session["role"] = user["role"]  # 把角色存入 session

        return redirect_by_role(user["role"])  # 登入成功，依角色導向對應首頁

    return render_template("login.html")  # GET 請求，直接顯示登入表單頁


@app.route("/register", methods=["GET", "POST"])  # 設定註冊頁路由
def register():  # 定義註冊功能函式
    if request.method == "POST":  # 如果是表單送出請求
        username = request.form.get("username", "").strip()  # 取得帳號輸入值
        full_name = request.form.get("full_name", "").strip()  # 取得姓名輸入值
        nickname = request.form.get("nickname", "").strip()  # 取得暱稱輸入值
        email = request.form.get("email", "").strip()  # 取得 Email 輸入值
        password = request.form.get("password", "")  # 取得密碼輸入值
        confirm_password = request.form.get("confirm_password", "")  # 取得確認密碼輸入值

        if not username or not full_name or not email or not password:  # 檢查必填欄位是否都有填
            flash("請填寫所有必填欄位。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if len(username) < 4:  # 檢查帳號長度是否至少 4 字元
            flash("帳號至少需要4個字元。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if len(password) < 6:  # 檢查密碼長度是否至少 6 字元
            flash("密碼至少需要6個字元。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        if password != confirm_password:  # 檢查兩次輸入的密碼是否一致
            flash("兩次輸入的密碼不一致。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        connection = get_db_connection()  # 嘗試建立資料庫連線

        if connection is None:  # 如果連線失敗
            flash("資料庫連線失敗，請稍後再試。", "error")  # 顯示錯誤提示
            return render_template("register.html")  # 重新顯示註冊頁

        cursor = connection.cursor(dictionary=True)  # 建立字典格式的資料庫游標

        try:  # 開始執行資料庫操作
            cursor.execute(  # 查詢帳號或 Email 是否已被使用
                """
                SELECT user_id
                FROM users
                WHERE username = %s OR email = %s
                LIMIT 1
                """,  # 只要帳號或 Email 其中一個重複就算已存在
                (username, email)  # 帶入查詢參數
            )

            existing_user = cursor.fetchone()  # 取得查詢結果

            if existing_user:  # 如果已經有相同帳號或 Email 的使用者
                flash("帳號或電子郵件已被使用。", "error")  # 顯示錯誤提示
                return render_template("register.html")  # 重新顯示註冊頁

            password_hash = generate_password_hash(password)  # 把明文密碼轉換成雜湊值，不儲存明文密碼

            cursor.execute(  # 執行新增使用者的 SQL
                """
                INSERT INTO users
                (username, password_hash, full_name, nickname,
                 email, role, status)
                VALUES (%s, %s, %s, %s, %s, 'member', 'active')
                """,  # 新帳號預設角色為一般會員(member)、狀態為啟用(active)
                (
                    username,  # 帳號
                    password_hash,  # 密碼雜湊值
                    full_name,  # 姓名
                    nickname or None,  # 暱稱，若空字串則存 NULL
                    email  # Email
                )
            )

            connection.commit()  # 提交交易，正式寫入資料庫

        except Error as error:  # 如果資料庫操作發生錯誤
            connection.rollback()  # 回復交易，避免留下不完整的資料
            print("註冊失敗：", error)  # 在伺服器端印出錯誤內容方便除錯
            flash("註冊失敗，請稍後再試。", "error")  # 顯示錯誤提示給使用者
            return render_template("register.html")  # 重新顯示註冊頁

        finally:  # 不論成功或失敗都要執行
            cursor.close()  # 關閉游標
            connection.close()  # 關閉資料庫連線

        flash("註冊成功，請使用新帳號登入。", "success")  # 顯示註冊成功訊息
        return redirect(url_for("login"))  # 導向登入頁

    return render_template("register.html")  # GET 請求，顯示註冊表單頁


@app.route("/member")  # 設定會員首頁路由
def member_home():  # 定義會員首頁導向函式
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "member":  # 如果登入者角色不是一般會員
        return redirect_by_role(session.get("role"))  # 依實際角色導向對應首頁

    return redirect(url_for("member.dashboard"))  # 轉導到會員藍圖裡的會員儀表板路由


@app.route("/content-admin")  # 設定內容管理員首頁路由
def content_admin_home():  # 定義內容管理員儀表板函式
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "content_admin":  # 如果角色不是內容管理員
        return redirect_by_role(session.get("role"))  # 依實際角色導向對應首頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳儀表板頁面，所有統計數字都給預設值 0 或空陣列
            "content_admin_home.html",
            attraction_count=0, restaurant_count=0, accommodation_count=0,
            pending_proposal_count=0, top_attractions=[], top_restaurants=[],
            top_accommodations=[]
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢各項統計資料
        cursor.execute("SELECT COUNT(*) AS total FROM attractions")  # 查詢景點總數
        attraction_count = cursor.fetchone()["total"]  # 取出景點總數

        cursor.execute("SELECT COUNT(*) AS total FROM restaurants")  # 查詢餐廳總數
        restaurant_count = cursor.fetchone()["total"]  # 取出餐廳總數

        cursor.execute("SELECT COUNT(*) AS total FROM accommodations")  # 查詢住宿總數
        accommodation_count = cursor.fetchone()["total"]  # 取出住宿總數

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM proposals
            WHERE content_review_status = 'pending'
        """)  # 查詢待審核提案數量
        pending_proposal_count = cursor.fetchone()["total"]  # 取出待審核提案數

        cursor.execute("""
            SELECT name, country, city, favorite_count, itinerary_count
            FROM vw_popular_attractions
            ORDER BY (favorite_count + itinerary_count) DESC, name
            LIMIT 5
        """)  # 從熱門景點檢視表查詢，依收藏數+行程使用數排序，取前5筆
        top_attractions = cursor.fetchall()  # 取出熱門景點清單

        cursor.execute("""
            SELECT r.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM restaurants r
            JOIN countries co ON co.country_id = r.country_id
            JOIN cities ci ON ci.city_id = r.city_id
            LEFT JOIN itineraries i ON i.restaurant_id = r.restaurant_id
            GROUP BY r.restaurant_id, r.name, co.name, ci.name
            ORDER BY itinerary_count DESC, r.name
            LIMIT 5
        """)  # 查詢餐廳被排入行程的次數，取使用次數最多的前5筆
        top_restaurants = cursor.fetchall()  # 取出熱門餐廳清單

        cursor.execute("""
            SELECT ac.name, co.name AS country, ci.name AS city,
                   COUNT(i.itinerary_id) AS itinerary_count
            FROM accommodations ac
            JOIN countries co ON co.country_id = ac.country_id
            JOIN cities ci ON ci.city_id = ac.city_id
            LEFT JOIN itineraries i ON i.accommodation_id = ac.accommodation_id
            GROUP BY ac.accommodation_id, ac.name, co.name, ci.name
            ORDER BY itinerary_count DESC, ac.name
            LIMIT 5
        """)  # 查詢住宿被排入行程的次數，取使用次數最多的前5筆
        top_accommodations = cursor.fetchall()  # 取出熱門住宿清單

    except Error as error:  # 如果查詢過程中資料庫報錯(例如資料表結構還沒更新)
        print("內容管理資料庫結構尚未更新：", error)  # 在伺服器端印出錯誤內容
        flash("資料庫結構尚未更新，請先執行 database/migrate_0812_content_admin.sql。", "error")  # 提示使用者要先執行遷移腳本
        attraction_count = 0  # 景點總數退回預設值
        restaurant_count = 0  # 餐廳總數退回預設值
        accommodation_count = 0  # 住宿總數退回預設值
        pending_proposal_count = 0  # 待審核提案數退回預設值
        top_attractions = []  # 熱門景點清單退回空陣列
        top_restaurants = []  # 熱門餐廳清單退回空陣列
        top_accommodations = []  # 熱門住宿清單退回空陣列

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染內容管理員儀表板頁面，帶入所有統計資料
        "content_admin_home.html",
        attraction_count=attraction_count,  # 景點總數
        restaurant_count=restaurant_count,  # 餐廳總數
        accommodation_count=accommodation_count,  # 住宿總數
        pending_proposal_count=pending_proposal_count,  # 待審核提案數
        top_attractions=top_attractions,  # 熱門景點清單
        top_restaurants=top_restaurants,  # 熱門餐廳清單
        top_accommodations=top_accommodations,  # 熱門住宿清單
    )


@app.route("/system-admin")  # 設定系統管理員首頁路由
def system_admin_home():  # 定義系統管理員儀表板函式

    # 檢查是否登入
    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    # 只有 system_admin 可以進入
    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳儀表板頁面，統計數字給預設值 0
            "system_admin_home.html",
            member_count=0,
            trip_count=0,
            public_trip_count=0,
            report_count=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢各項統計資料

        # 一般會員數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
        """)  # 統計角色為會員且未被刪除的人數

        member_count = cursor.fetchone()["total"]  # 取出會員總數

        # 所有行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
        """)  # 統計所有行程數量

        trip_count = cursor.fetchone()["total"]  # 取出行程總數

        # 公開行程數量
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM trips
            WHERE visibility = 'public'
        """)  # 統計可見度為公開的行程數量

        public_trip_count = cursor.fetchone()["total"]  # 取出公開行程總數

        # 待處理檢舉
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM reports
            WHERE status = 'pending'
        """)  # 統計狀態為待處理的檢舉數量

        report_count = cursor.fetchone()["total"]  # 取出待處理檢舉數

        # 最近加入會員
        cursor.execute("""
            SELECT user_id,
                   username,
                   full_name,
                   email,
                   status,
                   created_at
            FROM users
            WHERE role = 'member'
            AND status != 'deleted'
            ORDER BY created_at DESC
            LIMIT 5
        """)  # 查詢最近註冊的 5 位會員資料

        recent_users = cursor.fetchall()  # 取出最近加入會員清單

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染系統管理員儀表板頁面
        "system_admin_home.html",
        member_count=member_count,  # 會員總數
        trip_count=trip_count,  # 行程總數
        public_trip_count=public_trip_count,  # 公開行程總數
        report_count=report_count,  # 待處理檢舉數
        recent_users=recent_users  # 最近加入會員清單
    )
@app.route("/system-admin/users")  # 設定會員管理列表頁路由
def admin_users():  # 定義會員管理列表函式

    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    keyword = request.args.get("keyword", "").strip()  # 取得網址上的搜尋關鍵字參數

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template("admin_users.html", users=[])  # 回傳空的會員清單頁面

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標

    try:  # 開始查詢會員資料

        if keyword:  # 如果有輸入搜尋關鍵字

            search = "%" + keyword + "%"  # 組成 SQL LIKE 模糊搜尋用的字串

            cursor.execute("""
                SELECT user_id,
                       username,
                       full_name,
                       nickname,
                       email,
                       role,
                       status,
                       created_at
                FROM users
                WHERE role = 'member'
                AND status != 'deleted'
                AND (
                    username LIKE %s
                    OR full_name LIKE %s
                    OR email LIKE %s
                )
                ORDER BY user_id DESC
            """, (search, search, search))  # 依帳號、姓名、Email 模糊搜尋會員資料

        else:  # 如果沒有輸入搜尋關鍵字

            cursor.execute("""
                SELECT user_id,
                       username,
                       full_name,
                       nickname,
                       email,
                       role,
                       status,
                       created_at
                FROM users
                WHERE role = 'member'
                AND status != 'deleted'
                ORDER BY user_id DESC
            """)  # 查詢全部未刪除的會員資料

        users = cursor.fetchall()  # 取出查詢結果

    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染會員管理列表頁面
        "admin_users.html",
        users=users,  # 會員清單
        keyword=keyword  # 搜尋關鍵字(用來顯示在搜尋框裡)
    )


@app.route("/system-admin/public-trips")  # 設定公開行程管理頁路由
def admin_public_trips():  # 定義公開行程管理列表函式
    if "user_id" not in session or session.get("role") != "system_admin":  # 如果尚未登入或角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    keyword = request.args.get("keyword", "").strip()  # 取得搜尋關鍵字參數
    trip_status = request.args.get("status", "").strip()  # 取得行程狀態篩選參數
    allowed_statuses = {"planning", "upcoming", "completed", "cancelled"}  # 定義允許的行程狀態集合
    if trip_status not in allowed_statuses:  # 如果傳入的狀態不在允許範圍內
        trip_status = ""  # 視為沒有篩選狀態

    connection = get_db_connection()  # 建立資料庫連線
    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return render_template(  # 回傳空清單頁面
            "admin_public_trips.html",
            trips=[], keyword=keyword, trip_status=trip_status,
            public_count=0, pending_report_count=0
        )

    cursor = connection.cursor(dictionary=True)  # 建立字典格式游標
    try:  # 開始查詢公開行程資料
        conditions = ["t.visibility = 'public'"]  # 查詢條件清單，固定只找公開行程
        params = []  # 對應條件的參數清單

        if keyword:  # 如果有輸入搜尋關鍵字
            search = f"%{keyword}%"  # 組成模糊搜尋字串
            conditions.append("""
                (t.trip_name LIKE %s OR t.country LIKE %s OR t.city LIKE %s
                 OR u.username LIKE %s OR u.full_name LIKE %s)
            """)  # 加入依行程名稱、國家、城市、擁有者帳號、姓名搜尋的條件
            params.extend([search] * 5)  # 5 個搜尋欄位都用同一個關鍵字

        if trip_status:  # 如果有指定行程狀態
            conditions.append("t.status = %s")  # 加入狀態篩選條件
            params.append(trip_status)  # 加入對應參數

        where_clause = " AND ".join(conditions)  # 把所有條件用 AND 串起來
        cursor.execute(f"""
            SELECT t.trip_id, t.trip_name, t.country, t.city,
                   t.start_date, t.end_date, t.status, t.created_at,
                   u.username AS owner_username, u.full_name AS owner_name,
                   COUNT(DISTINCT CASE WHEN tm.join_status = 'accepted'
                                      THEN tm.trip_member_id END) AS member_count,
                   COUNT(DISTINCT i.itinerary_id) AS itinerary_count,
                   COUNT(DISTINCT CASE WHEN r.status IN ('pending', 'processing')
                                      THEN r.report_id END) AS report_count
            FROM trips t
            JOIN users u ON u.user_id = t.owner_id
            LEFT JOIN trip_members tm ON tm.trip_id = t.trip_id
            LEFT JOIN itineraries i ON i.trip_id = t.trip_id
            LEFT JOIN reports r ON r.target_type = 'trip' AND r.target_id = t.trip_id
            WHERE {where_clause}
            GROUP BY t.trip_id, t.trip_name, t.country, t.city,
                     t.start_date, t.end_date, t.status, t.created_at,
                     u.username, u.full_name
            ORDER BY t.created_at DESC
        """, tuple(params))  # 查詢公開行程清單，附帶成員數、行程項目數、待處理檢舉數
        trips = cursor.fetchall()  # 取出公開行程清單

        cursor.execute("SELECT COUNT(*) AS total FROM trips WHERE visibility = 'public'")  # 查詢公開行程總數
        public_count = cursor.fetchone()["total"]  # 取出公開行程總數

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM reports r
            JOIN trips t ON t.trip_id = r.target_id
            WHERE r.target_type = 'trip'
              AND r.status IN ('pending', 'processing')
              AND t.visibility = 'public'
        """)  # 查詢公開行程中待處理的檢舉總數
        pending_report_count = cursor.fetchone()["total"]  # 取出待處理檢舉總數
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return render_template(  # 渲染公開行程管理頁面
        "admin_public_trips.html",
        trips=trips,  # 公開行程清單
        keyword=keyword,  # 搜尋關鍵字
        trip_status=trip_status,  # 狀態篩選值
        public_count=public_count,  # 公開行程總數
        pending_report_count=pending_report_count,  # 待處理檢舉總數
    )


@app.route("/system-admin/public-trips/<int:trip_id>/unpublish", methods=["POST"])  # 設定取消公開行程的路由，網址帶入行程 ID
def unpublish_public_trip(trip_id):  # 定義取消公開行程函式
    if "user_id" not in session or session.get("role") != "system_admin":  # 如果尚未登入或角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    connection = get_db_connection()  # 建立資料庫連線
    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("admin_public_trips"))  # 導回公開行程管理頁

    cursor = connection.cursor()  # 建立一般游標(不需要字典格式)
    try:  # 開始執行更新
        cursor.execute("""
            UPDATE trips
            SET visibility = 'private'
            WHERE trip_id = %s AND visibility = 'public'
        """, (trip_id,))  # 把指定的公開行程改為私人，避免誤改已經是私人的行程
        connection.commit()  # 提交交易
        if cursor.rowcount:  # 如果有實際更新到資料列
            flash("行程已取消公開，原有行程資料不受影響。", "success")  # 顯示成功訊息
        else:  # 如果沒有更新到任何資料列(可能行程已被改動)
            flash("找不到該公開行程，可能已被更新。", "error")  # 顯示找不到資料的提示
    except Exception as error:  # 如果執行過程發生例外
        connection.rollback()  # 回復交易
        print("取消公開行程失敗：", error)  # 在伺服器端印出錯誤內容
        flash("取消公開行程失敗", "error")  # 顯示錯誤提示
    finally:  # 不論成功或失敗都要執行
        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("admin_public_trips"))  # 導回公開行程管理頁

@app.route("/system-admin/users/<int:user_id>/disable", methods=["POST"])  # 設定停用會員的路由，網址帶入會員 ID
def disable_user():  # 定義停用會員函式(注意：這裡函式簽名少了 user_id 參數，是既有的程式錯誤，執行到下面用到 user_id 時會噴錯)

    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("admin_users"))  # 導回會員管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 開始執行更新

        cursor.execute("""
            UPDATE users
            SET status = 'disabled'
            WHERE user_id = %s
            AND role = 'member'
        """, (user_id,))  # 把指定會員狀態改為停用(僅限角色為會員的帳號)

        connection.commit()  # 提交交易

        flash("會員已停用", "success")  # 顯示成功訊息

    except Exception as error:  # 如果執行過程發生例外

        connection.rollback()  # 回復交易

        print("停用會員失敗：", error)  # 在伺服器端印出錯誤內容

        flash("停用會員失敗", "error")  # 顯示錯誤提示

    finally:  # 不論成功或失敗都要執行

        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("admin_users"))  # 導回會員管理頁
@app.route("/system-admin/users/<int:user_id>/enable", methods=["POST"])  # 設定恢復會員的路由，網址帶入會員 ID
def enable_user():  # 定義恢復會員函式(同樣缺少 user_id 參數，是既有的程式錯誤)

    if "user_id" not in session:  # 如果尚未登入
        return redirect(url_for("login"))  # 導向登入頁

    if session.get("role") != "system_admin":  # 如果角色不是系統管理員
        return redirect(url_for("login"))  # 導向登入頁

    connection = get_db_connection()  # 建立資料庫連線

    if connection is None:  # 如果連線失敗
        flash("資料庫連線失敗", "error")  # 顯示錯誤提示
        return redirect(url_for("admin_users"))  # 導回會員管理頁

    cursor = connection.cursor()  # 建立一般游標

    try:  # 開始執行更新

        cursor.execute("""
            UPDATE users
            SET status = 'active'
            WHERE user_id = %s
            AND role = 'member'
        """, (user_id,))  # 把指定會員狀態改回啟用(僅限角色為會員的帳號)

        connection.commit()  # 提交交易

        flash("會員已恢復", "success")  # 顯示成功訊息

    except Exception as error:  # 如果執行過程發生例外

        connection.rollback()  # 回復交易

        print("恢復會員失敗：", error)  # 在伺服器端印出錯誤內容

        flash("恢復會員失敗", "error")  # 顯示錯誤提示

    finally:  # 不論成功或失敗都要執行

        cursor.close()  # 關閉游標
        connection.close()  # 關閉資料庫連線

    return redirect(url_for("admin_users"))  # 導回會員管理頁
@app.route("/logout")  # 設定登出路由
def logout():  # 定義登出函式
    session.clear()  # 清空 session，移除登入狀態
    flash("你已成功登出。", "success")  # 顯示登出成功訊息
    return redirect(url_for("login"))  # 導向登入頁


if __name__ == "__main__":  # 如果這個檔案是直接被執行(而不是被匯入)
    app.run(debug=True)  # 啟動 Flask 開發伺服器，開啟除錯模式
