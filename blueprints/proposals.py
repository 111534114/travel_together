from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from auth import login_required
from db import get_db_connection

proposals_bp = Blueprint("proposals", __name__, url_prefix="/content-admin/proposals")

STATUS_CHOICES = ("pending", "approved", "returned", "not_required")

STATUS_LABELS = {
    "pending": "待審核",
    "approved": "已核准",
    "returned": "已退回",
    "not_required": "無需審核",
}


@proposals_bp.route("/")
@login_required("content_admin")
def list_proposals():
    status = request.args.get("status", "pending").strip()

    if status not in STATUS_CHOICES and status != "all":
        status = "pending"

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return render_template(
            "content_admin/proposals/list.html",
            proposals=[], status=status, status_labels=STATUS_LABELS
        )

    cursor = connection.cursor(dictionary=True)

    try:
        params = []
        where_clause = ""

        if status != "all":
            where_clause = "WHERE p.content_review_status = %s"
            params.append(status)

        cursor.execute(
            f"""
            SELECT p.proposal_id, p.proposal_type, p.title, p.location,
                   p.estimated_cost, p.proposed_date, p.content_review_status,
                   p.created_at, t.trip_name, u.full_name AS proposer_name
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            JOIN users u ON u.user_id = p.proposer_id
            {where_clause}
            ORDER BY p.created_at DESC
            """,
            params
        )
        proposals = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "content_admin/proposals/list.html",
        proposals=proposals,
        status=status,
        status_labels=STATUS_LABELS
    )


@proposals_bp.route("/<int:proposal_id>")
@login_required("content_admin")
def view_proposal(proposal_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.list_proposals"))

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT p.*, t.trip_name, u.full_name AS proposer_name,
                   u.email AS proposer_email, r.full_name AS reviewer_name
            FROM proposals p
            JOIN trips t ON t.trip_id = p.trip_id
            JOIN users u ON u.user_id = p.proposer_id
            LEFT JOIN users r ON r.user_id = p.reviewed_by
            WHERE p.proposal_id = %s
            """,
            (proposal_id,)
        )
        proposal = cursor.fetchone()

    finally:
        cursor.close()
        connection.close()

    if proposal is None:
        flash("找不到這筆提案", "error")
        return redirect(url_for("proposals.list_proposals"))

    return render_template(
        "content_admin/proposals/detail.html",
        proposal=proposal,
        status_labels=STATUS_LABELS
    )


@proposals_bp.route("/<int:proposal_id>/approve", methods=["POST"])
@login_required("content_admin")
def approve_proposal(proposal_id):
    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE proposals
            SET content_review_status = 'approved',
                reviewed_by = %s, reviewed_at = NOW(), review_note = NULL
            WHERE proposal_id = %s
            """,
            (session["user_id"], proposal_id)
        )
        connection.commit()
        flash("提案已核准", "success")
    except Exception as error:
        connection.rollback()
        print("核准提案失敗：", error)
        flash("核准提案失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))


@proposals_bp.route("/<int:proposal_id>/return", methods=["POST"])
@login_required("content_admin")
def return_proposal(proposal_id):
    review_note = request.form.get("review_note", "").strip()

    if not review_note:
        flash("退回提案時請填寫退回原因", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE proposals
            SET content_review_status = 'returned',
                reviewed_by = %s, reviewed_at = NOW(), review_note = %s
            WHERE proposal_id = %s
            """,
            (session["user_id"], review_note, proposal_id)
        )
        connection.commit()
        flash("提案已退回", "success")
    except Exception as error:
        connection.rollback()
        print("退回提案失敗：", error)
        flash("退回提案失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))


@proposals_bp.route("/<int:proposal_id>/update", methods=["POST"])
@login_required("content_admin")
def update_proposal(proposal_id):
    title = request.form.get("title", "").strip()
    location = request.form.get("location", "").strip() or None
    description = request.form.get("description", "").strip() or None
    website_url = request.form.get("website_url", "").strip() or None
    estimated_cost = request.form.get("estimated_cost", "").strip()
    proposed_date = request.form.get("proposed_date", "").strip() or None

    if not title:
        flash("請輸入提案標題", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    try:
        estimated_cost = float(estimated_cost) if estimated_cost else 0
        if estimated_cost < 0:
            raise ValueError
    except ValueError:
        flash("預估花費必須是不小於 0 的數字", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    connection = get_db_connection()

    if connection is None:
        flash("資料庫連線失敗", "error")
        return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE proposals
            SET title = %s, location = %s, description = %s,
                website_url = %s, estimated_cost = %s, proposed_date = %s
            WHERE proposal_id = %s
            """,
            (title, location, description, website_url, estimated_cost,
             proposed_date, proposal_id)
        )
        connection.commit()
        flash("提案內容已修正", "success")
    except Exception as error:
        connection.rollback()
        print("修正提案失敗：", error)
        flash("修正提案失敗", "error")
    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("proposals.view_proposal", proposal_id=proposal_id))
