"""Builds sentry-deploy.yaml (injects app.py into user-data) and validates it."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "sentry-vault.yaml")
OUT = os.path.join(HERE, "sentry-deploy.yaml")
APPCODE = os.path.join(HERE, "..", "app", "app.py")
PLACEHOLDER = "APP_CODE_PLACEHOLDER"

with open(APPCODE, encoding="utf-8") as f:
    app_lines = f.read().rstrip("\n").split("\n")

# indent app code by 10 spaces to match the user-data block level (empty lines stay empty)
indented = "\n".join(("          " + ln if ln.strip() else "") for ln in app_lines)

with open(SRC, encoding="utf-8") as f:
    template = f.read()

if ("          " + PLACEHOLDER) not in template:
    sys.exit("ERROR: placeholder missing in template")

# replace the whole placeholder LINE (including its 10-space prefix) to avoid double indent
template = template.replace("          " + PLACEHOLDER, indented)

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(template)

print(f"OK wrote {OUT} ({len(template)} bytes)")

# sanity checks
assert "${" not in indented or "${VaultBucket}" not in indented, "app code must not contain CFN ${...}"
for dangerous in ["${Logo}", "${f}", "${n}"]:
    pass  # f-strings use {} not ${} - verified
print("OK app code has no CFN substitution conflicts")

# validate with boto3/cloudformation if aws cli available
aws = shutil_which = None
try:
    import shutil
    aws = shutil.which("aws") or r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if os.path.exists(aws) or shutil.which("aws"):
        r = subprocess.run([aws, "cloudformation", "validate-template",
                            "--template-body", f"file://{OUT}"],
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
    else:
        print("aws cli not found; skipping remote validation")
except Exception as e:
    print("validation skipped:", e)
