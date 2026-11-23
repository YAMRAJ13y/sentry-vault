"""
SENTRY VAULT - Secure Document Storage with Defense-in-Depth on AWS
Flask web app: uploads files to S3 with SSE-KMS encryption,
protected by S3 Versioning + Object Lock (WORM), behind WAF + ALB.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from flask import Flask, redirect, render_template_string, request, url_for

REGION = os.environ.get("AWS_REGION", "ap-south-1")
BUCKET = os.environ["VAULT_BUCKET"]
KMS_KEY_ALIAS = os.environ.get("VAULT_KMS_KEY_ALIAS", "alias/sentry-vault")
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

from botocore.config import Config

# regional endpoint + SigV4 explicitly - avoids global-endpoint region mismatch on presigned URLs
s3 = boto3.client(
    "s3", region_name=REGION,
    endpoint_url=f"https://s3.{REGION}.amazonaws.com",
    config=Config(signature_version="s3v4"))


def telegram_alert(text):
    """Push a security event to the owner's Telegram (real-time SOC-style alert)."""
    if not TG_TOKEN or not TG_CHAT:
        return
    try:
        data = json.dumps({"chat_id": TG_CHAT, "text": text, "parse_mode": "HTML"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print("telegram alert failed:", e)

app = Flask(__name__)

PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SENTRY VAULT</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #e6edf3; min-height: 100vh; }
  .header { background: linear-gradient(90deg, #010409, #161b22); border-bottom: 1px solid #30363d;
            padding: 22px 40px; display: flex; align-items: center; gap: 16px; }
  .header .logo { font-size: 34px; }
  .header h1 { font-size: 24px; letter-spacing: 3px; color: #58a6ff; }
  .header .sub { color: #8b949e; font-size: 13px; margin-top: 2px; }
  .wrap { max-width: 1000px; margin: 30px auto; padding: 0 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 24px; margin-bottom: 22px; }
  .card h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 1.5px; color: #58a6ff; margin-bottom: 14px; }
  .badges { display: flex; flex-wrap: wrap; gap: 10px; }
  .badge { background: #0d2136; border: 1px solid #1f6feb; color: #58a6ff; border-radius: 20px;
           padding: 6px 14px; font-size: 12.5px; font-weight: 600; }
  .badge span { color: #3fb950; }
  form.up { display: flex; gap: 12px; align-items: center; }
  input[type=file] { color: #8b949e; flex: 1; }
  button { background: #238636; color: #fff; border: none; border-radius: 6px; padding: 10px 22px;
           font-size: 14px; font-weight: 600; cursor: pointer; }
  button:hover { background: #2ea043; }
  button.danger { background: #67262d; border: 1px solid #b62324; font-size: 12px; padding: 6px 12px; }
  button.danger:hover { background: #8b3a42; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th { text-align: left; color: #8b949e; font-size: 12px; text-transform: uppercase;
       letter-spacing: 1px; padding: 10px 12px; border-bottom: 1px solid #30363d; }
  td { padding: 12px; border-bottom: 1px solid #21262d; }
  .kms { color: #3fb950; font-weight: 600; }
  .ver { color: #d29922; font-family: monospace; font-size: 12px; }
  .msg { border-radius: 8px; padding: 14px 18px; margin-bottom: 18px; font-size: 14px; line-height: 1.5; }
  .ok { background: #0f2f1c; border: 1px solid #238636; color: #7ee787; }
  .err { background: #3d1216; border: 1px solid #b62324; color: #ffa198; }
  .footer { text-align: center; color: #484f58; font-size: 12px; padding: 30px; }
  .mono { font-family: monospace; color: #8b949e; font-size: 12px; }
</style>
</head>
<body>
<div class="header">
  <div class="logo">&#128737;</div>
  <div>
    <h1>SENTRY VAULT</h1>
    <div class="sub">Defense-in-Depth Secure Document Storage &middot; AWS &middot; ap-south-1</div>
  </div>
</div>
<div class="wrap">

  {% if msg %}<div class="msg {{ msg_type }}">{{ msg | safe }}</div>{% endif %}

  <div class="card">
    <h2>Active Security Layers</h2>
    <div class="badges">
      <div class="badge">WAF <span>&#10003; blocking SQLi / XSS</span></div>
      <div class="badge">KMS <span>&#10003; SSE-KMS encryption</span></div>
      <div class="badge">Object Lock <span>&#10003; WORM protected</span></div>
      <div class="badge">IAM <span>&#10003; least privilege</span></div>
      <div class="badge">VPC <span>&#10003; private network</span></div>
      <div class="badge">CloudTrail <span>&#10003; full audit</span></div>
      <div class="badge">Session Manager <span>&#10003; shell without SSH</span></div>
      <div class="badge">Config <span>&#10003; compliance</span></div>
    </div>
  </div>

  <div class="card">
    <h2>Upload Evidence File</h2>
    <form class="up" method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="file" required>
      <button type="submit">Encrypt &amp; Store</button>
    </form>
    <p class="mono" style="margin-top:12px">Uploads are encrypted server-side with AWS KMS (SSE-KMS) before storage.</p>
  </div>

  <div class="card">
    <h2>Stored Files ({{ files | length }})</h2>
    {% if files %}
    <table>
      <tr><th>File</th><th>Size</th><th>Uploaded</th><th>Encryption</th><th>Version</th><th>Actions</th></tr>
      {% for f in files %}
      <tr>
        <td>{{ f.name }}</td>
        <td>{{ f.size }}</td>
        <td>{{ f.uploaded }}</td>
        <td class="kms">&#128273; SSE-KMS</td>
        <td class="ver">{{ f.version }}</td>
        <td>
          <a href="{{ f.url }}"><button>Download</button></a>
          <form method="post" action="/delete/{{ f.name }}" style="display:inline"
                onsubmit="return confirm('Try to DELETE this file? Object Lock should block it.');">
            <button class="danger" type="submit">Delete</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p style="color:#8b949e">No files yet. Upload your first evidence file above.</p>
    {% endif %}
  </div>

  <div class="footer">SENTRY VAULT &middot; Cloud Security &amp; Forensic project &middot; All actions are logged in AWS CloudTrail</div>
</div>
</body>
</html>
"""

def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def list_files():
    files = []
    try:
        resp = s3.list_objects_v2(Bucket=BUCKET)
        for obj in resp.get("Contents", []):
            name = obj["Key"]
            url = s3.generate_presigned_url(
                "get_object", Params={"Bucket": BUCKET, "Key": name}, ExpiresIn=300
            )
            files.append({
                "name": name,
                "size": human_size(obj["Size"]),
                "uploaded": obj["LastModified"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "version": obj.get("VersionId", "-")[:12] + "...",
                "url": url,
            })
    except ClientError as e:
        print("list error:", e)
    return files

@app.route("/")
def index():
    return render_template_string(PAGE, files=list_files(), msg=request.args.get("msg"), msg_type=request.args.get("t", "ok"))

@app.route("/healthz")
def healthz():
    return "healthy", 200

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return redirect(url_for("index", msg="No file selected.", t="err"))
    name = os.path.basename(f.filename).replace(" ", "_")
    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=name,
            Body=f.stream,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=KMS_KEY_ALIAS,
        )
        msg = f'&#9989; <b>"{name}"</b> encrypted with KMS and stored securely. S3 Object Lock is now protecting it.'
        return redirect(url_for("index", msg=msg, t="ok"))
    except ClientError as e:
        msg = f"&#10060; Upload failed: {e.response['Error']['Code']}"
        return redirect(url_for("index", msg=msg, t="err"))

@app.route("/delete/<path:name>", methods=["POST"])
def delete(name):
    # Attempt to destroy the file - including its protected version.
    # S3 Object Lock (WORM) refuses. This failure IS the demo.
    try:
        # target the latest protected VERSION (what a real attacker would try)
        versions = s3.list_object_versions(Bucket=BUCKET, Prefix=name)
        latest = next((v for v in versions.get("Versions", []) if v["Key"] == name and v.get("IsLatest")), None)
        if latest:
            s3.delete_object(Bucket=BUCKET, Key=name, VersionId=latest["VersionId"])
        else:
            s3.delete_object(Bucket=BUCKET, Key=name)
        return redirect(url_for("index", msg=f"{name} deleted.", t="ok"))
    except ClientError as e:
        code = e.response["Error"]["Code"]
        aws_msg = e.response["Error"].get("Message", code)
        msg = (f"&#128274; <b>DELETE BLOCKED</b> &mdash; AWS returned <b>{code}</b>: "
               f"\"{aws_msg}\". "
               f"\"{name}\" is protected by <b>S3 Object Lock (WORM)</b>: the file is "
               f"tamper-proof and cannot be deleted or overwritten during the retention period &mdash; "
               f"not even by the administrator. Evidence stays intact.")
        telegram_alert(
            f"🚨 <b>TAMPER ATTEMPT BLOCKED</b>\n"
            f"File: <code>{name}</code>\n"
            f"AWS error: {code} — {aws_msg}\n"
            f"🛡 S3 Object Lock (WORM) refused the deletion. Evidence intact.\n"
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        return redirect(url_for("index", msg=msg, t="err"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, threaded=True)
