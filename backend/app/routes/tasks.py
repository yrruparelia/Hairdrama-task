"""
app/routes/tasks.py — Task CRUD Routes

Endpoints:
  GET    /api/tasks/          → list all tasks (with optional filters)
  POST   /api/tasks/          → create a new task
  GET    /api/tasks/<id>      → get a single task with comments
  PATCH  /api/tasks/<id>      → update task (status, assignee, etc.)
  DELETE /api/tasks/<id>      → delete a task

Email triggers:
  - Task created + assigned_to set  → email the assignee
  - Task status changed to 'done'   → email the creator
  - Task reassigned (assigned_to changes) → email new assignee

Activity Logging:
  Every mutation (create / update / delete) writes a record to
  activity_logs so we have a full audit trail.

JWT Auth:
  Every route uses _decode_jwt() to extract the current user's ID
  from the Authorization header.
"""


import jwt
import datetime
from flask import Blueprint, jsonify, request, current_app
from app.services.supabase_client import get_supabase_client
from app.services.email_service import (
    notify_task_created,
    notify_task_completed,
    notify_task_reassigned,
)


tasks_bp = Blueprint("tasks", __name__)


# ── JWT Decode Helper ─────────────────────────────────────────────────────────
def _decode_jwt(req):
    """
    Shared JWT verification helper used across all protected routes.
    Returns the decoded payload dict, or a (response, status_code) tuple on error.
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        return payload
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401


def _log_activity(supabase, task_id: str, user_id: str, action_type: str, meta: dict = {}):
    """
    Write an entry to activity_logs.
    Fails silently — we don't want a logging error to break the main request.
    """
    try:
        supabase.table("activity_logs").insert({
            "task_id": task_id,
            "user_id": user_id,
            "action_type": action_type,
            "meta": meta,
        }).execute()
    except Exception as e:
        current_app.logger.error(f"Failed to write activity log: {e}")


def _get_task_with_relations(supabase, task_id: str):
    """Fetch a task in the same shape used by the task list endpoint."""
    result = (
        supabase.table("tasks")
        .select(
            "*, "
            "creator:created_by(id, name, email, avatar_url), "
            "assignee:assigned_to(id, name, email, avatar_url)"
        )
        .eq("id", task_id)
        .single()
        .execute()
    )
    return result.data


# ── GET /api/tasks/ ───────────────────────────────────────────────────────────
@tasks_bp.get("/")
def list_tasks():
    """
    Returns tasks with optional query param filters:
      ?status=todo|in_progress|done
      ?priority=low|medium|high
      ?assigned_to=<user_uuid>

    Joins with users table to get creator/assignee names for display.
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()

    # Build query with foreign key joins (Supabase PostgREST syntax)
    query = (
        supabase.table("tasks")
        .select(
            "*, "
            "creator:created_by(id, name, email, avatar_url), "
            "assignee:assigned_to(id, name, email, avatar_url)"
        )
        .order("created_at", desc=True)
    )

    # Apply optional filters from query params
    status = request.args.get("status")
    priority = request.args.get("priority")
    assigned_to = request.args.get("assigned_to")

    if status:
        query = query.eq("status", status)
    if priority:
        query = query.eq("priority", priority)
    if assigned_to:
        query = query.eq("assigned_to", assigned_to)

    result = query.execute()
    visible_tasks = [
        task for task in result.data
        if task.get("created_by") == payload["sub"]
        or task.get("assigned_to") == payload["sub"]
    ]
    return jsonify(visible_tasks), 200


# ── POST /api/tasks/ ──────────────────────────────────────────────────────────
@tasks_bp.post("/")
def create_task():
    """
    Creates a new task. Required fields: title.
    Optional: description, priority, due_date, assigned_to.
    Triggers: email notification to assignee if assigned_to is set.
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not data or not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    due_date = data.get("due_date")
    if due_date:
        try:
            parsed_due_date = datetime.date.fromisoformat(due_date)
        except (TypeError, ValueError):
            return jsonify({"error": "due_date must be a valid date"}), 400
        if parsed_due_date < datetime.date.today():
            return jsonify({"error": "Due date cannot be earlier than today"}), 400

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    new_task = {
        "title": data["title"],
        "description": data.get("description", ""),
        "priority": data.get("priority", "medium"),
        "due_date": due_date,                   # can be None
        "assigned_to": data.get("assigned_to"), # can be None
        "created_by": current_user_id,
        "status": "todo",
    }

    assigned_to = new_task["assigned_to"]
    if assigned_to and assigned_to != current_user_id:
        assignee_exists = (
            supabase.table("users")
            .select("id")
            .eq("id", assigned_to)
            .maybe_single()
            .execute()
        )
        if not assignee_exists.data:
            return jsonify({"error": "Assigned user not found"}), 400

    result = supabase.table("tasks").insert(new_task).execute()
    task = result.data[0]
    task = _get_task_with_relations(supabase, task["id"])

    # Log the creation action
    _log_activity(supabase, task["id"], current_user_id, "task_created")

    # If a user was assigned, fetch their email and send notification
    if task.get("assigned_to"):
        assignee = (
            supabase.table("users")
            .select("email, name")
            .eq("id", task["assigned_to"])
            .single()
            .execute()
        )
        if assignee.data:
            notify_task_created(task, assignee.data["email"])

    return jsonify(task), 201


# ── GET /api/tasks/<task_id> ──────────────────────────────────────────────────
@tasks_bp.get("/<task_id>")
def get_task(task_id: str):
    """
    Returns a single task with its comments and activity log.
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()

    task_result = (
        supabase.table("tasks")
        .select(
            "*, "
            "creator:created_by(id, name, email, avatar_url), "
            "assignee:assigned_to(id, name, email, avatar_url)"
        )
        .eq("id", task_id)
        .single()
        .execute()
    )

    if not task_result.data:
        return jsonify({"error": "Task not found"}), 404

    # Fetch comments for this task
    comments_result = (
        supabase.table("task_comments")
        .select("*, author:user_id(id, name, avatar_url)")
        .eq("task_id", task_id)
        .order("created_at")
        .execute()
    )

    # Fetch activity log for this task
    logs_result = (
        supabase.table("activity_logs")
        .select("*, actor:user_id(id, name, avatar_url)")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )

    response = {
        **task_result.data,
        "comments": comments_result.data,
        "activity_logs": logs_result.data,
    }

    return jsonify(response), 200


# ── PATCH /api/tasks/<task_id> ────────────────────────────────────────────────
@tasks_bp.patch("/<task_id>")
def update_task(task_id: str):
    """
    Partial update of a task. Detects:
      - Status change to 'done'     → email creator
      - assigned_to change          → email new assignee
    Logs all changes to activity_logs.
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    # Fetch the current state before updating (needed to detect changes)
    old_task_result = (
        supabase.table("tasks").select("*").eq("id", task_id).single().execute()
    )
    if not old_task_result.data:
        return jsonify({"error": "Task not found"}), 404

    old_task = old_task_result.data

    # Only update allowed fields (whitelist approach for security)
    allowed_fields = {"title", "description", "status", "priority", "due_date", "assigned_to"}
    update_data = {k: v for k, v in data.items() if k in allowed_fields}

    if not update_data:
        return jsonify({"error": "No valid fields to update"}), 400

    is_delegated = (
        old_task.get("assigned_to")
        and old_task.get("assigned_to") != old_task.get("created_by")
    )
    if "status" in update_data:
        can_update_status = (
            old_task.get("assigned_to") == current_user_id
            if is_delegated
            else old_task.get("created_by") == current_user_id
        )
        if not can_update_status:
            return jsonify({
                "error": "Only the task doer can update the status of an assigned task"
            }), 403

    result = (
        supabase.table("tasks").update(update_data).eq("id", task_id).execute()
    )
    updated_task = result.data[0]
    updated_task = _get_task_with_relations(supabase, updated_task["id"])

    # ── Detect and handle status change to 'done' ──────────────────────────
    if update_data.get("status") == "done" and old_task["status"] != "done":
        _log_activity(
            supabase, task_id, current_user_id, "status_changed",
            {"old_status": old_task["status"], "new_status": "done"}
        )
        # Notify the task creator
        creator = (
            supabase.table("users").select("email").eq("id", old_task["created_by"]).single().execute()
        )
        if creator.data:
            notify_task_completed(updated_task, creator.data["email"])

    # ── Detect reassignment ────────────────────────────────────────────────
    new_assignee_id = update_data.get("assigned_to")
    if new_assignee_id and new_assignee_id != old_task.get("assigned_to"):
        _log_activity(
            supabase, task_id, current_user_id, "reassigned",
            {"old_assignee": old_task.get("assigned_to"), "new_assignee": new_assignee_id}
        )
        new_assignee = (
            supabase.table("users").select("email").eq("id", new_assignee_id).single().execute()
        )
        if new_assignee.data:
            notify_task_reassigned(updated_task, new_assignee.data["email"])

    return jsonify(updated_task), 200


# ── DELETE /api/tasks/<task_id> ───────────────────────────────────────────────
@tasks_bp.delete("/<task_id>")
def delete_task(task_id: str):
    """
    Deletes a task. Only the task creator can delete it.
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    # Authorization check: only the creator can delete
    task_result = (
        supabase.table("tasks").select("created_by").eq("id", task_id).single().execute()
    )
    if not task_result.data:
        return jsonify({"error": "Task not found"}), 404

    if task_result.data["created_by"] != current_user_id:
        return jsonify({"error": "Forbidden: only the task creator can delete it"}), 403

    supabase.table("tasks").delete().eq("id", task_id).execute()
    return jsonify({"message": "Task deleted successfully"}), 200


# ── POST /api/tasks/<task_id>/comments ────────────────────────────────────────
@tasks_bp.post("/<task_id>/comments")
def add_comment(task_id: str):
    """
    Adds a comment to a task.
    Required body field: content
    """
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not data or not data.get("content"):
        return jsonify({"error": "content is required"}), 400

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    result = supabase.table("task_comments").insert({
        "task_id": task_id,
        "user_id": current_user_id,
        "content": data["content"],
    }).execute()

    _log_activity(supabase, task_id, current_user_id, "comment_added")

    return jsonify(result.data[0]), 201
