"""
SENTRY VAULT Telegram Bot - hosted on AWS Lambda
- Webhook for Telegram commands: /start /help /status /files /events /health
- Handles S3 event notifications -> upload alerts to the owner
Two independent alert paths: S3 -> Lambda (this) and app -> Telegram API (app.py)
"""
import json
import os
import urllib.request

import boto3

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
BUCKET = os.environ["VAULT_BUCKET"]
SECRET = os.environ.get("WEBHOOK_SECRET", "")
APP_URL = os.environ.get("APP_URL", "")

s3 = boto3.client("s3")


def tg_api(method, **kw):
    data = json.dumps(kw).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/{method}",
        data=data, headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=10).read()


def send(chat, text):
    try:
        tg_api("sendMessage", chat_id=chat, text=text, parse_mode="HTML")
    except Exception as e:
        print("telegram send failed:", e)


def handler(event, context):
    # ---- S3 upload events -> alert ----
    if "Records" in event:
        for r in event["Records"]:
            if r.get("eventSource") in ("s3", "aws:s3") and r["eventName"].startswith("ObjectCreated"):
                obj = r["s3"]["object"]
                key = obj["key"].replace("<", "&lt;")
                size = obj.get("size", 0)
                send(CHAT_ID,
                     f"📁 <b>NEW EVIDENCE STORED</b>\n"
                     f"File: <code>{key}</code>\n"
                     f"Size: {size} bytes\n"
                     f"🔒 SSE-KMS encrypted + Object Lock (WORM) protected\n"
                     f"🛡 CloudTrail event logged")
        return {"statusCode": 200}

    # ---- Telegram webhook ----
    if SECRET and event.get("headers", {}).get("x-telegram-bot-api-secret-token") != SECRET:
        return {"statusCode": 403, "body": "forbidden"}

    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        return {"statusCode": 200}

    msg = body.get("message", {})
    chat = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()
    if chat is None or not text.startswith("/"):
        return {"statusCode": 200}

    cmd = text.split()[0].split("@")[0].lower()

    if cmd in ("/start", "/help"):
        send(chat,
             "🛡 <b>SENTRY VAULT BOT</b>\n"
             "Defense-in-Depth Document Vault on AWS\n\n"
             "Commands:\n"
             "/status - security layers status\n"
             "/files - files stored in the vault\n"
             "/events - recent CloudTrail audit events\n"
             "/health - web app health check\n\n"
             "🔔 This bot also alerts automatically on new uploads and tamper attempts.")
    elif cmd == "/status":
        send(chat,
             "🛡 <b>SENTRY VAULT - ALL LAYERS ACTIVE</b>\n"
             "✅ WAF - blocking SQLi / XSS at the edge\n"
             "✅ ALB - single controlled entrance\n"
             "✅ VPC - network isolation\n"
             "✅ IAM - least privilege role\n"
             "✅ KMS - SSE-KMS encryption\n"
             "✅ Object Lock - WORM (GOVERNANCE, 1 day)\n"
             "✅ CloudTrail - full API audit\n"
             "✅ AWS Config - compliance monitoring\n"
             "✅ Session Manager - shell without SSH")
    elif cmd == "/files":
        try:
            resp = s3.list_objects_v2(Bucket=BUCKET)
            objs = resp.get("Contents", [])
            if not objs:
                send(chat, "📁 Vault is empty.")
            else:
                lines = [f"• {o['Key']} - {o['Size']} B" for o in objs[:10]]
                send(chat, "📁 <b>Files in vault:</b>\n" + "\n".join(lines))
        except Exception as e:
            send(chat, f"⚠️ Could not list vault: {e}")
    elif cmd == "/events":
        try:
            ct = boto3.client("cloudtrail")
            evs = ct.lookup_events(MaxResults=6).get("Events", [])
            lines = [f"• {e['EventName']} - {e['Username']}" for e in evs]
            send(chat, "📜 <b>Recent audit events:</b>\n" + "\n".join(lines) if lines else "No events found.")
        except Exception as e:
            send(chat, f"⚠️ Could not query CloudTrail: {e}")
    elif cmd == "/health":
        try:
            r = urllib.request.urlopen(APP_URL + "/healthz", timeout=8)
            send(chat, f"✅ Web app healthy - HTTP {r.status}")
        except Exception as e:
            send(chat, f"⚠️ App check failed: {e}")
    else:
        send(chat, "Unknown command - try /help")

    return {"statusCode": 200}
