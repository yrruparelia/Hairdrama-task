"""Gmail notification helpers for task events."""

import base64
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _send_email(to_address: str, subject: str, html_body: str) -> None:
    """Send one HTML email through Gmail."""
    sender = (current_app.config["GMAIL_SENDER_ADDRESS"] or "").strip()
    refresh_token = (current_app.config["GMAIL_REFRESH_TOKEN"] or "").strip()

    if not sender or not refresh_token:
        current_app.logger.error(
            "Email delivery skipped: GMAIL_SENDER_ADDRESS and "
            "GMAIL_REFRESH_TOKEN must both be configured."
        )
        return
    if not to_address or "@" not in to_address:
        current_app.logger.error("Email delivery skipped: invalid recipient address.")
        return

    current_app.logger.info("Sending task email to %s: %s", to_address, subject)
    message = MIMEMultipart("alternative")
    message["From"] = sender
    message["To"] = to_address
    message["Subject"] = subject
    message.attach(MIMEText(html_body, "html"))
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    try:
        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=current_app.config["GMAIL_CLIENT_ID"],
            client_secret=current_app.config["GMAIL_CLIENT_SECRET"],
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
        credentials.refresh(Request())
        gmail = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        response_body = (
            gmail.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )
    except HttpError as error:
        current_app.logger.error(
            "Gmail API rejected email to %s (HTTP %s): %s",
            to_address, error.resp.status, error.content.decode("utf-8", errors="replace"),
        )
        return
    except (GoogleAuthError, OSError, ValueError) as error:
        current_app.logger.error(
            "Gmail API email delivery failed for %s: %s", to_address, error
        )
        return

    current_app.logger.info(
        "Email sent to %s via Gmail API: %s (id=%s)",
        to_address,
        subject,
        response_body.get("id", "unknown")
    )


def _task_details(task: dict) -> str:
    """Render the shared task details table used by task notifications."""
    creator = task.get("creator") or {}
    assignee = task.get("assignee") or {}
    due_date = task.get("due_date") or "Not set"
    return f"""
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <tr>
                <td style="padding: 9px; font-weight: bold; color: #374151;">Description</td>
                <td style="padding: 9px; color: #6b7280;">{escape(task.get('description') or 'No description provided.')}</td>
            </tr>
            <tr style="background: #f3f4f6;">
                <td style="padding: 9px; font-weight: bold; color: #374151;">Priority</td>
                <td style="padding: 9px; color: #6b7280;">{escape(str(task.get('priority', 'medium')).capitalize())}</td>
            </tr>
            <tr>
                <td style="padding: 9px; font-weight: bold; color: #374151;">Due date</td>
                <td style="padding: 9px; color: #6b7280;">{escape(str(due_date))}</td>
            </tr>
            <tr style="background: #f3f4f6;">
                <td style="padding: 9px; font-weight: bold; color: #374151;">Status</td>
                <td style="padding: 9px; color: #6b7280;">{escape(str(task.get('status', 'todo')).replace('_', ' ').capitalize())}</td>
            </tr>
            <tr>
                <td style="padding: 9px; font-weight: bold; color: #374151;">Assigned by</td>
                <td style="padding: 9px; color: #6b7280;">{escape(creator.get('name') or creator.get('email') or 'Workspace member')}</td>
            </tr>
            <tr style="background: #f3f4f6;">
                <td style="padding: 9px; font-weight: bold; color: #374151;">Assigned to</td>
                <td style="padding: 9px; color: #6b7280;">{escape(assignee.get('name') or assignee.get('email') or 'Unassigned')}</td>
            </tr>
        </table>
    """


def notify_task_created(task: dict, assignee_email: str) -> None:
    """Notify an assignee about a newly created task."""
    subject = f"📋 New Task Assigned: {task['title']}"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #4F46E5; padding: 24px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0;">New Task Assigned to You</h1>
        </div>
        <div style="background: #f9fafb; padding: 24px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
            <h2 style="color: #111827;">{escape(task['title'])}</h2>
            {_task_details(task)}
            <div style="margin-top: 24px; text-align: center;">
                <a href="{current_app.config['FRONTEND_URL']}/?task={task['id']}"
                   style="background: #4F46E5; color: white; padding: 12px 24px;
                          border-radius: 6px; text-decoration: none; font-weight: bold;">
                    View Task →
                </a>
            </div>
        </div>
        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 16px;">
            HairDrama Task Manager
        </p>
    </div>
    """
    _send_email(assignee_email, subject, html_body)


def notify_task_completed(task: dict, creator_email: str) -> None:
    """Notify the creator when a task is completed."""
    subject = f"✅ Task Completed: {task['title']}"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #10B981; padding: 24px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0;">Task Completed! 🎉</h1>
        </div>
        <div style="background: #f9fafb; padding: 24px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
            <p style="color: #374151;">Great news! The following task has been marked as <strong>completed</strong>:</p>
            <h2 style="color: #111827;">{escape(task['title'])}</h2>
            {_task_details(task)}
            <div style="margin-top: 24px; text-align: center;">
                <a href="{current_app.config['FRONTEND_URL']}/?task={task['id']}"
                   style="background: #10B981; color: white; padding: 12px 24px;
                          border-radius: 6px; text-decoration: none; font-weight: bold;">
                    View Task →
                </a>
            </div>
        </div>
        <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 16px;">
            HairDrama Task Manager
        </p>
    </div>
    """
    _send_email(creator_email, subject, html_body)


def notify_task_reassigned(task: dict, new_assignee_email: str) -> None:
    """Notify the new assignee when a task is reassigned."""
    subject = f"🔄 Task Reassigned to You: {task['title']}"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #F59E0B; padding: 24px; border-radius: 8px 8px 0 0;">
            <h1 style="color: white; margin: 0;">Task Reassigned to You</h1>
        </div>
        <div style="background: #f9fafb; padding: 24px; border-radius: 0 0 8px 8px; border: 1px solid #e5e7eb;">
            <p style="color: #374151;">A task has been <strong>reassigned</strong> to you:</p>
            <h2 style="color: #111827;">{task['title']}</h2>
            <p style="color: #6b7280;">{task.get('description', 'No description.')}</p>
            <div style="margin-top: 24px; text-align: center;">
                <a href="{current_app.config['FRONTEND_URL']}/?task={task['id']}"
                   style="background: #F59E0B; color: white; padding: 12px 24px;
                          border-radius: 6px; text-decoration: none; font-weight: bold;">
                    View Task →
                </a>
            </div>
        </div>
    </div>
    """
    _send_email(new_assignee_email, subject, html_body)
