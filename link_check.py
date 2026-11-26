"""飯店官網連結檢查：網站已經關閉、網域到期的連結，詳情頁就不要顯示「前往飯店官網」按鈕。

連結是從 Google 的飯店資料來的，不是我們能控制的，所以由伺服器代為檢查(瀏覽器端直接檢查會被跨網域限制擋住)。
因為網址是外部輸入，檢查時要防止被拿來連內網(SSRF)：只允許 http/https，主機名稱解析出來的位址如果是
內網/本機/保留位址就拒絕，轉址的每一跳也都重新檢查。"""
import ipaddress
import re
import socket
import time
from urllib.parse import urljoin, urlsplit

import requests

CACHE_SECONDS = 24 * 3600
TIMEOUT = 6
MAX_REDIRECTS = 4
DEAD_STATUS = {404, 410}  # 只有明確「找不到」才算失效；403/405/429 常是擋機器人，網站其實還在
_cache = {}
# 網域到期後常被代管公司接手，回的是 HTTP 200 但內容是「404／網域到期／出售」的頁面，只看狀態碼抓不到
_TITLE_DEAD = re.compile(r"<title[^>]*>[^<]*(404|not\s*found|找不到|無法找到)", re.I)
_BODY_DEAD = ("相關服務已到期", "網域已到期", "網域到期", "domain has expired", "domain is for sale", "this domain may be for sale", "domain expired")
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; link-check)", "Accept": "text/html,*/*;q=0.8"}


def _public_host(host):
    """主機名稱解析出的位址必須全部是公開位址；解析不到回傳 None(代表網域不存在)，內網位址回傳 False。"""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            return False
    return True


def check(url):
    """回傳 True(還活著或無法判斷)／False(確定失效)。無法判斷的情況一律當作活著，寧可多顯示按鈕也不要誤藏。"""
    now = time.time()
    hit = _cache.get(url)
    if hit and hit[0] > now:
        return hit[1]
    alive = _check(url)
    _cache[url] = (now + CACHE_SECONDS, alive)
    if len(_cache) > 2000:
        for key in [k for k, v in _cache.items() if v[0] <= now]:
            _cache.pop(key, None)
    return alive


def _check(url):
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(current)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return True
        public = _public_host(parts.hostname)
        if public is None:
            return False  # 網域已經不存在
        if public is False:
            return True  # 內網位址不檢查(也不連線)，當作無法判斷
        try:
            try:
                response = requests.get(current, headers=_HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True)
            except requests.exceptions.SSLError:
                # 憑證有問題(過期、不符)的網站瀏覽器會警告但仍可進入，這裡忽略憑證再檢查一次內容是否還在
                response = requests.get(current, headers=_HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True, verify=False)
            body = ""
            if response.status_code == 200:
                try:
                    body = next(response.iter_content(40000, decode_unicode=False), b"").decode(response.encoding or "utf-8", "ignore")
                except Exception:
                    body = ""
            response.close()
        except requests.exceptions.ConnectionError:
            return False  # 連不上(拒絕連線、主機不存在)
        except requests.exceptions.RequestException:
            return True  # 逾時等狀況無法判斷
        if response.status_code in (301, 302, 303, 307, 308) and response.headers.get("Location"):
            current = urljoin(current, response.headers["Location"])
            continue
        if response.status_code in DEAD_STATUS:
            return False
        lowered = body.lower()
        return not (_TITLE_DEAD.search(body) or any(word in lowered for word in _BODY_DEAD))
    return True
