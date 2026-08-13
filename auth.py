from functools import wraps

from flask import redirect, session, url_for


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            if role and session.get("role") != role:
                return redirect(url_for("login"))

            return view(*args, **kwargs)

        return wrapped

    return decorator
