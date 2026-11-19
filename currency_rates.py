"""幣別換算（以新臺幣為基準）。

AI 估價時回傳「當地幣別的金額」，由這裡換算成行程的幣別，比讓 AI 自己心算匯率可靠。
匯率來自 open.er-api.com（與網站幣別選單同一個來源），快取 6 小時；連不上時用內建的概略匯率。
"""
import time

import requests

# 1 新臺幣可換多少外幣（概略值，只在線上匯率取不到時使用）
FALLBACK_RATES = {
    "TWD": 1.0, "JPY": 4.7, "KRW": 43.0, "USD": 0.031, "EUR": 0.029, "GBP": 0.024, "HKD": 0.24,
    "CNY": 0.22, "SGD": 0.041, "THB": 1.05, "VND": 800.0, "MYR": 0.14, "AUD": 0.047, "MOP": 0.25,
    "PHP": 1.8, "IDR": 500.0, "CAD": 0.043, "CHF": 0.027, "NZD": 0.052,
}
_cache = {"expires": 0.0, "rates": dict(FALLBACK_RATES)}


def rates():
    now = time.time()
    if now >= _cache["expires"]:
        try:
            response = requests.get("https://open.er-api.com/v6/latest/TWD", timeout=8)
            response.raise_for_status()
            data = response.json()
            if data.get("result") == "success" and data.get("rates"):
                _cache.update(rates={**FALLBACK_RATES, **data["rates"]}, expires=now + 6 * 3600)
            else:
                _cache["expires"] = now + 300
        except Exception as error:  # 網路問題時沿用上一次（或內建）的匯率
            print("匯率查詢失敗，使用概略匯率：", error)
            _cache["expires"] = now + 300
    return _cache["rates"]


def convert(amount, from_code, to_code="TWD"):
    """換算金額；不認得的幣別回傳 None。"""
    from_code = (from_code or "TWD").upper().strip()
    to_code = (to_code or "TWD").upper().strip()
    if from_code == to_code:
        return float(amount)
    table = rates()
    if from_code not in table or to_code not in table or not table[from_code]:
        return None
    return float(amount) / table[from_code] * table[to_code]
