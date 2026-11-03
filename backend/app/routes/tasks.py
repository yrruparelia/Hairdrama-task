"""Task CRUD, comments, activity logging, and notifications."""


import jwt
import datetime
from typing import Any, cast
from flask import Blueprint, jsonify, request, current_app
from app.services.supabase_client import get_supabase_client
from app.services.email_service import (
    notify_task_created,
    notify_task_completed,
    notify_task_reassigned,
)


tasks_bp = Blueprint("tasks", __name__)


# Shared JWT validation.
def _decode_jwt(req: Any) -> dict[str, Any] | tuple[Any, int]:
    """Return the decoded payload or an error response."""
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


def _log_activity(
    supabase: Any,
    task_id: str,
    user_id: str,
    action_type: str,
    meta: dict[str, Any] | None = None,
):
    """Write an activity log entry without interrupting the request."""
    try:
        supabase.table("activity_logs").insert({
            "task_id": task_id,
            "user_id": user_id,
            "action_type": action_type,
            "meta": meta or {},
        }).execute()
    except Exception as e:
        current_app.logger.error(f"Failed to write activity log: {e}")


def _get_task_with_relations(supabase: Any, task_id: str) -> dict[str, Any]:
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
    return cast(dict[str, Any], result.data)


# List tasks.
@tasks_bp.get("/")
def list_tasks():
    """Return tasks visible to the authenticated user."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()

    query = (
        supabase.table("tasks")
        .select(
            "*, "
            "creator:created_by(id, name, email, avatar_url), "
            "assignee:assigned_to(id, name, email, avatar_url)"
        )
        .order("created_at", desc=True)
    )

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
    tasks = cast(list[dict[str, Any]], result.data)
    visible_tasks = [
        task for task in tasks
        if task.get("created_by") == payload["sub"]
        or task.get("assigned_to") == payload["sub"]
    ]
    return jsonify(visible_tasks), 200


# Create a task.
@tasks_bp.post("/")
def create_task():
    """Create a task and notify an assigned user."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not isinstance(data, dict) or not data.get("title"):
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
        if not assignee_exists or not assignee_exists.data:
            return jsonify({"error": "Assigned user not found"}), 400

    result = supabase.table("tasks").insert(new_task).execute()
    task = cast(dict[str, Any], result.data[0])
    task = _get_task_with_relations(supabase, task["id"])

    _log_activity(supabase, task["id"], current_user_id, "task_created")

    if task.get("assigned_to"):
        assignee = (
            supabase.table("users")
            .select("email, name")
            .eq("id", task["assigned_to"])
            .single()
            .execute()
        )
        assignee_data = cast(dict[str, Any], assignee.data)
        if assignee_data:
            notify_task_created(task, str(assignee_data["email"]))

    return jsonify(task), 201


# Get one task.
@tasks_bp.get("/<task_id>")
def get_task(task_id: str):
    """Return a task with comments and activity history."""
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

    if not isinstance(task_result.data, dict):
        return jsonify({"error": "Task not found"}), 404

    comments_result = (
        supabase.table("task_comments")
        .select("*, author:user_id(id, name, avatar_url)")
        .eq("task_id", task_id)
        .order("created_at")
        .execute()
    )

    logs_result = (
        supabase.table("activity_logs")
        .select("*, actor:user_id(id, name, avatar_url)")
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .execute()
    )

    response = {
        **cast(dict[str, Any], task_result.data),
        "comments": comments_result.data,
        "activity_logs": logs_result.data,
    }

    return jsonify(response), 200


# Update a task.
@tasks_bp.patch("/<task_id>")
def update_task(task_id: str):
    """Update allowed task fields and process notifications."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "No data provided"}), 400

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    old_task_result = (
        supabase.table("tasks").select("*").eq("id", task_id).single().execute()
    )
    if not old_task_result.data:
        return jsonify({"error": "Task not found"}), 404

    old_task = cast(dict[str, Any], old_task_result.data)

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
    updated_task = cast(dict[str, Any], result.data[0])
    updated_task = _get_task_with_relations(supabase, updated_task["id"])

    if update_data.get("status") == "done" and old_task["status"] != "done":
        _log_activity(
            supabase, task_id, current_user_id, "status_changed",
            {"old_status": old_task["status"], "new_status": "done"}
        )
        creator = (
            supabase.table("users").select("email").eq("id", old_task["created_by"]).single().execute()
        )
        creator_data = cast(dict[str, Any], creator.data)
        if creator_data:
            notify_task_completed(updated_task, str(creator_data["email"]))

    new_assignee_id = update_data.get("assigned_to")
    if new_assignee_id and new_assignee_id != old_task.get("assigned_to"):
        _log_activity(
            supabase, task_id, current_user_id, "reassigned",
            {"old_assignee": old_task.get("assigned_to"), "new_assignee": new_assignee_id}
        )
        new_assignee = (
            supabase.table("users").select("email").eq("id", new_assignee_id).single().execute()
        )
        new_assignee_data = cast(dict[str, Any], new_assignee.data)
        if new_assignee_data:
            notify_task_reassigned(updated_task, str(new_assignee_data["email"]))

    return jsonify(updated_task), 200


# Delete a task.
@tasks_bp.delete("/<task_id>")
def delete_task(task_id: str):
    """Delete a task owned by the authenticated user."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    supabase = get_supabase_client()
    current_user_id = payload["sub"]

    task_result = (
        supabase.table("tasks").select("created_by").eq("id", task_id).single().execute()
    )
    if not isinstance(task_result.data, dict):
        return jsonify({"error": "Task not found"}), 404

    task = cast(dict[str, Any], task_result.data)
    if task["created_by"] != current_user_id:
        return jsonify({"error": "Forbidden: only the task creator can delete it"}), 403

    supabase.table("tasks").delete().eq("id", task_id).execute()
    return jsonify({"message": "Task deleted successfully"}), 200


# Add a comment.
@tasks_bp.post("/<task_id>/comments")
def add_comment(task_id: str):
    """Add a comment to a task."""
    payload = _decode_jwt(request)
    if isinstance(payload, tuple):
        return payload

    data = request.get_json()
    if not isinstance(data, dict) or not data.get("content"):
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
