"""Email notifications over SMTP (Gmail by default).

Settings come from environment variables (GitHub Secrets in production):
  SMTP_USER      sender address, e.g. you@gmail.com
  SMTP_PASSWORD  Gmail App Password (not your normal password)
  EMAIL_TO       recipient(s), comma separated; defaults to SMTP_USER
  SMTP_HOST      optional, default smtp.gmail.com
  SMTP_PORT      optional, default 465 (SSL)
"""
import html
import os
import smtplib
from email.message import EmailMessage


def send_matches(matches):
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    recipients = os.environ.get("EMAIL_TO") or user
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))

    message = EmailMessage()
    count = len(matches)
    message["Subject"] = f"ikman: {count} new room/annex ad{'s' if count != 1 else ''} in your range"
    message["From"] = user
    message["To"] = recipients
    message.set_content(_plain(matches))
    message.add_alternative(_html(matches), subtype="html")

    with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)


def _plain(matches):
    blocks = []
    for m in matches:
        blocks.append(
            f"{m['title']}\n{m['price']} | {m['location']} | posted {m['posted']}\n"
            f"{m['url']}\n\n{m['snippet']}"
        )
    return "\n\n----------\n\n".join(blocks)


def _html(matches):
    items = []
    for m in matches:
        items.append(
            f'<div style="margin-bottom:20px">'
            f'<a href="{html.escape(m["url"])}" style="font-size:16px;font-weight:bold">'
            f'{html.escape(m["title"])}</a><br>'
            f'<b>{html.escape(m["price"])}</b> &middot; {html.escape(m["location"])} '
            f'&middot; posted {html.escape(m["posted"])}'
            f'<p style="color:#555;white-space:pre-line">{html.escape(m["snippet"])}</p>'
            f"</div>"
        )
    return "<html><body>" + "".join(items) + "</body></html>"
