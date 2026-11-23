"""住客評價的 AI 整理：把 Google 的各面向統計(好評/待改善次數)與最新幾則住客留言交給 AI，
整理成「住客覺得很棒的地方」和「需要加強的地方」。只根據提供的資料整理，不憑空發揮。
結果快取一小時，同一間飯店不重複呼叫 AI。AI 沒設定或失敗時丟出 ai_client.AIUnavailable。"""
import time

from ai_client import AIUnavailable, ask_json

CACHE_TTL_SECONDS = 60 * 60
_cache = {}  # {飯店 token: (過期時間, 結果)}
MAX_REVIEWS = 12
MAX_REVIEW_CHARS = 320


def _clean_list(value, limit=6):
    items = []
    for item in value if isinstance(value, list) else []:
        text = str(item or "").strip()
        if text and text not in items:
            items.append(text[:80])
    return items[:limit]


def summarize(token, hotel_name, rating, review_count, overview, reviews):
    """回傳 {"summary": str, "strengths": [str], "improvements": [str]}。"""
    cached = _cache.get(token)
    if cached and cached[0] > time.time():
        return cached[1]

    topics = (overview or {}).get("topics") or []
    topic_lines = [
        f"- {t['name']}：提及 {t['total']} 次，好評 {t['positive']}、待改善 {t['negative']}、中立 {t['neutral']}"
        for t in topics[:15]
    ]
    review_lines = []
    for review in (reviews or [])[:MAX_REVIEWS]:
        text = " ".join(str(review.get("text") or "").split())[:MAX_REVIEW_CHARS]
        if text:
            review_lines.append(f"- ({review.get('rating') or '?'} 星) {text}")
    if not topic_lines and not review_lines:
        raise AIUnavailable("這間飯店目前沒有足夠的住客評價可以整理。")

    prompt = (
        "你是旅遊住宿評價整理助手。請根據下面「Google 住客評價」資料，整理住客覺得很棒的地方與需要加強的地方。"
        "所有內容用繁體中文，只回傳 JSON 物件，不要 Markdown。"
        '格式：{"summary":"一句話總結(40 字內)","strengths":["..."],"improvements":["..."]}。'
        "規則：strengths 列 3 到 5 點、improvements 列 2 到 5 點，每點 30 字內、簡潔具體；"
        "只能根據提供的資料，不可編造；各面向統計裡「待改善」次數明顯偏多的才放進 improvements，"
        "沒有明顯缺點時 improvements 可以少列或留空陣列，不要硬湊；"
        "引用數字時用統計裡真實的數字(例如「清潔：52 則提及中 38 則好評」)；"
        "留言是飯店評價的樣本(最新幾則)，不代表全部，不要說成「所有住客」。"
        f"\n飯店：{hotel_name}；Google 評分 {rating}（{review_count} 則評論）。"
        "\n各面向統計：\n" + ("\n".join(topic_lines) or "(沒有)")
        + "\n最新住客留言樣本：\n" + ("\n".join(review_lines) or "(沒有)")
    )
    payload = ask_json(prompt, timeout=40)
    result = {
        "summary": str(payload.get("summary") or "").strip()[:120],
        "strengths": _clean_list(payload.get("strengths")),
        "improvements": _clean_list(payload.get("improvements")),
    }
    if not result["strengths"] and not result["improvements"]:
        raise AIUnavailable("AI 沒有整理出內容，請再試一次。")
    _cache[token] = (time.time() + CACHE_TTL_SECONDS, result)
    return result
