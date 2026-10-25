from flask import abort, g, request, session

from db import get_db_connection


CONTENT_ADMIN_MODULES = {
    "attractions": "景點管理",
    "restaurants": "餐廳管理",
    "accommodations": "住宿管理",
    "locations": "國家與城市",
    "categories": "分類管理",
    "proposals": "提案審核",
    "attraction_posts_admin": "景點相簿審核",
    "friend_groups_admin": "交友揪團管理",
    "ai_data": "AI 資料維護",
    "reports": "統計報表",
    "logs": "操作紀錄",
    "ai_chat": "AI 助理",
}

CONTENT_ADMIN_ACTIONS = {
    "attractions": ("view", "create", "edit", "delete"),
    "restaurants": ("view", "create", "edit", "delete"),
    "accommodations": ("view", "create", "edit", "delete"),
    "locations": ("view", "create", "edit", "delete"),
    "categories": ("view", "create", "edit", "delete"),
    "proposals": ("view", "edit"),
    "attraction_posts_admin": ("view", "edit"),
    "friend_groups_admin": ("view", "edit"),
    "ai_data": ("view", "edit"),
    "reports": ("view",),
    "logs": ("view",),
    "ai_chat": ("view",),
}

ACTION_LABELS = {"view": "查看", "create": "新增", "edit": "編輯", "delete": "刪除"}

_ENDPOINT_ACTIONS = {
    "attractions": {
        "create_attraction": "create", "import_attractions": "create",
        "import_from_google": "create", "edit_attraction": "edit",
        "bulk_activate_attractions": "edit", "restore_attraction": "edit",
        "backfill_descriptions": "edit", "delete_attraction": "delete",
        "bulk_delete_attractions": "delete", "permanently_delete_attraction": "delete",
    },
    "restaurants": {
        "create_restaurant": "create", "import_restaurants": "create",
        "import_from_google": "create", "edit_restaurant": "edit",
        "bulk_activate_restaurants": "edit", "restore_restaurant": "edit",
        "backfill_descriptions": "edit", "delete_restaurant": "delete",
        "bulk_delete_restaurants": "delete", "permanently_delete_restaurant": "delete",
    },
    "accommodations": {
        "create_accommodation": "create", "import_accommodations": "create",
        "import_from_google": "create", "edit_accommodation": "edit",
        "bulk_activate_accommodations": "edit", "restore_accommodation": "edit",
        "backfill_descriptions": "edit", "delete_accommodation": "delete",
        "bulk_delete_accommodations": "delete", "permanently_delete_accommodation": "delete",
    },
    "locations": {
        "create_country": "create", "create_city": "create",
        "import_preset_cities": "create", "edit_country": "edit",
        "edit_city": "edit", "delete_country": "delete", "delete_city": "delete",
    },
    "categories": {
        "create_category": "create", "edit_category": "edit", "delete_category": "delete",
    },
    "proposals": {
        "approve_proposal": "edit", "return_proposal": "edit", "update_proposal": "edit",
    },
    "attraction_posts_admin": {"approve_post": "edit", "reject_post": "edit"},
    "friend_groups_admin": {
        "approve_application": "edit", "reject_application": "edit", "toggle_setting": "edit",
        "new_event": "edit", "edit_event": "edit", "cancel_event": "edit", "check_in_participant": "edit",
        "post_event_announcement": "edit",
    },
    "ai_data": {"verify_item": "edit"},
}


def denied_modules(user_id=None):
    if user_id is None:
        user_id = session.get("user_id")
        if user_id is None:
            return set()
        if hasattr(g, "content_admin_denied"):
            return g.content_admin_denied

    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT module FROM content_admin_denials WHERE user_id = %s", (user_id,))
        denied = {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()
        connection.close()

    if user_id == session.get("user_id"):
        g.content_admin_denied = denied
    return denied


def content_admin_can(module, action="view"):
    if session.get("role") != "content_admin":
        return False
    if action not in CONTENT_ADMIN_ACTIONS.get(module, ()):
        return False
    denied = denied_modules()
    return module not in denied and f"{module}:view" not in denied and f"{module}:{action}" not in denied


def require_content_admin_module():
    module = request.blueprint
    if module in CONTENT_ADMIN_MODULES:
        endpoint = request.endpoint.rsplit(".", 1)[-1]
        actions = _ENDPOINT_ACTIONS.get(module, {})
        if request.method == "POST" and module != "ai_chat" and endpoint not in actions:
            abort(403)
        action = actions.get(endpoint, "view")
        if not content_admin_can(module, action):
            abort(403)
