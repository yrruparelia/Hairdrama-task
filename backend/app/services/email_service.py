"""
app/services/email_service.py — Gmail Email Notifications

Why Gmail SMTP with App Password?
  The Gmail API (OAuth-based) is more secure but requires setting up a
  service account or an extra OAuth flow just for the backend to send mail.
  For this project we use Gmail SMTP with an App Password — simpler,
  well-understood, and works great for low-volume transactional email.

How to get a Gmail App Password:
  1. Go to myaccount.google.com → Security
  2. Enable 2-Step Verification
  3. Search "App Passwords" → Generate one for "Mail"
  4. Paste the 16-char password in GMAIL_APP_PASSWORD env var

When are emails sent?
  - task_created  → notify the assignee with the full task details
  - task_done     → notify the original assigner with the full task details
  - task_assigned → notify the new assignee when a task is reassigned
"""

import smtplib
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import current_app


def _send_email(to_address: str, subject: str, html_body: str) -> None:
    """
    Internal helper. Opens a secure TLS connection to Gmail SMTP
    and sends a single email.

    Args:
        to_address: Recipient's email address
        subject:    Email subject line
        html_body:  HTML content of the email body
    """
    sender = (current_app.config["GMAIL_SENDER_ADDRESS"] or "").strip()
    password = (current_app.config["GMAIL_APP_PASSWORD"] or "").replace(" ", "").strip()

    if not sender or not password:
        current_app.logger.error(
            "Email delivery skipped: GMAIL_SENDER_ADDRESS and "
            "GMAIL_APP_PASSWORD must both be configured."
        )
        return
    if not to_address or "@" not in to_address:
        current_app.logger.error("Email delivery skipped: invalid recipient address.")
        return

    # MIMEMultipart lets us send both plain-text and HTML versions.
    # Email clients will show the HTML version if supported, plain-text otherwise.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_address

    # Attach HTML part
    msg.attach(MIMEText(html_body, "html"))

    current_app.logger.info("Sending task email to %s: %s", to_address, subject)

    # Try implicit TLS first, then STARTTLS for networks that block port 465.
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, to_address, msg.as_string())
    except (OSError, smtplib.SMTPException) as ssl_error:
        current_app.logger.warning(
            "Gmail SSL delivery failed; retrying with STARTTLS: %s", ssl_error
        )
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(sender, password)
                smtp.sendmail(sender, to_address, msg.as_string())
        except (OSError, smtplib.SMTPException) as starttls_error:
            current_app.logger.error(
                "Email delivery failed for %s. SSL error: %s; STARTTLS error: %s",
                to_address,
                ssl_error,
                starttls_error,
            )
            return

    current_app.logger.info("Email sent to %s: %s", to_address, subject)


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
    """
    Sends an email to the assignee when a new task is created and assigned to them.

    Args:
        task:           The newly created task dict (from Supabase)
        assignee_email: Email address of the person being assigned the task
    """
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
                <a href="{current_app.config['FRONTEND_URL']}/tasks/{task['id']}"
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
    """
    Sends an email to the task creator when a task is marked as done.

    Args:
        task:          The completed task dict
        creator_email: Email of the person who originally created the task
    """
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
                <a href="{current_app.config['FRONTEND_URL']}/tasks/{task['id']}"
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
    """
    Sends an email when a task is reassigned to a new user.

    Args:
        task:               The updated task dict
        new_assignee_email: Email of the new assignee
    """
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
                <a href="{current_app.config['FRONTEND_URL']}/tasks/{task['id']}"
                   style="background: #F59E0B; color: white; padding: 12px 24px;
                          border-radius: 6px; text-decoration: none; font-weight: bold;">
                    View Task →
                </a>
            </div>
        </div>
    </div>
    """
    _send_email(new_assignee_email, subject, html_body)
