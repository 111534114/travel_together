import mysql.connector  # 匯入 MySQL 連線套件
from mysql.connector import Error  # 匯入 MySQL 錯誤類別，用來捕捉連線例外

from config import DB_CONFIG  # 匯入資料庫連線設定(主機、帳號、密碼、資料庫名稱等)


def get_db_connection():  # 定義取得資料庫連線的共用函式
    try:  # 嘗試建立連線
        connection = mysql.connector.connect(**DB_CONFIG)  # 用設定值建立 MySQL 連線

        if connection.is_connected():  # 如果連線成功
            return connection  # 回傳連線物件給呼叫端使用

    except Error as error:  # 如果連線過程發生錯誤
        print("資料庫連線失敗：", error)  # 在伺服器端印出錯誤內容方便除錯

    return None  # 連線失敗時回傳 None，呼叫端要自行檢查
