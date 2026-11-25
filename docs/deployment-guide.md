# SENTRY VAULT - MASTER LIVE DEMO DOCUMENT
*Every service: what it is → how to show it live → exact words. All actions pre-verified.*

## ⏰ BEFORE (30 min early)
- AWS Console region = **Mumbai (ap-south-1)**
- Tabs open: 1-App | 2-S3 bucket | 3-CloudTrail | 4-Config | 5-IAM role | 6-CloudFormation
- Phone: Telegram open on the bot chat
- Notepad with attack URLs (below)

## 🔗 Key URLs
- Site: `http://<YOUR_ALB_DNS>`
- SQLi attack: `http://<YOUR_ALB_DNS>/?id=admin%27--`
- XSS attack: `http://<YOUR_ALB_DNS>/?q=%3Cscript%3E`
- Server's real IP (for VPC demo): `http://<EC2_PUBLIC_IP>`

---

## MOMENT 0 - The Meaning (30 sec, say first)
> "Ma'am, the purpose of my project is tamper-proof storage with provable accountability - like storing court evidence. Normal storage can be deleted by hackers, ransomware, or even a rogue admin. My system removes that possibility architecturally. Let me demonstrate each layer live."

---

## 1. THE APP - EC2 + VPC + ALB
**What:** EC2 = rented virtual server. VPC = your private network. ALB = the only entrance.
**SHOW:** Open the site - it loads.
**SAY:** "My app runs on an EC2 server inside my own VPC. Its only entrance is this load balancer."

## 2. VPC HIDING - "the server is invisible" ⭐
**What:** VPC isolates your network; Security Groups filter every packet.
**SHOW:** Open new tab → `http://<EC2_PUBLIC_IP>` (the server's REAL IP) → **it never loads / connection fails**.
**SAY:** "This is my server's actual IP address - try to open it directly: nothing. It's invisible. The security group only allows traffic that came through the load balancer. No SSH port, no direct web access. The only door is the ALB."
**Console backup:** VPC console → Resource map (visual diagram); EC2 → instance → Security tab → rules show "source: ALB security group".

## 3. UPLOAD → KMS ENCRYPTION (S3 + KMS)
**What:** S3 stores objects; KMS holds your personal encryption key (auto-rotation on).
**SHOW:** Upload a file → green success → Tab 2 → click the file → **Server-side encryption: SSE-KMS**.
**SAY:** "The file is encrypted with MY KMS key before it touches storage. Even AWS employees can't read it. Every key use is logged in CloudTrail. Key rotation is on."
**If asked - envelope encryption:** "KMS gives a data key; the data key encrypts the file; the data key itself is encrypted by the master key. Two layers of key protection."

## 4. DELETE → BLOCKED ⭐⭐ THE HIGHLIGHT (Object Lock + Versioning + Telegram)
**What:** Versioning keeps every version; Object Lock = WORM: Write Once Read Many. Even root can't delete during retention.
**SHOW:** Tab 1 → click **Delete** → red **DELETE BLOCKED** → 📱 phone buzzes: "TAMPER ATTEMPT BLOCKED".
**SAY:** "AWS itself refused. The storage layer says NO - even to me, the admin. This is WORM - Write Once, Read Many. It's not a rule in my app; it's enforced by AWS's storage internals. And my Lambda-powered bot alerted my phone in real time."
**If asked - governance vs compliance:** "Governance allows special bypass permission; Compliance mode is absolute - I use Governance 1-day; real evidence would use Compliance with legal retention periods - one-line change."

## 5. WAF - LIVE ATTACK DEMO ⭐⭐
**What:** WAF reads HTTP content (Layer 7) and blocks attack signatures before the server sees them.
**SHOW:** Paste SQLi URL → **403 Forbidden** → paste XSS URL → **403** again.
**SAY (SQLi explained):** "That payload - quote + comment dashes - is a classic SQL injection: it tries to trick the database into skipping the password check. The WAF recognized the signature and blocked it in under 50 ms, at the edge - my server never saw it. These are AWS-managed rule groups, updated automatically by AWS security researchers."
**If asked - WAF vs Security Group:** "Security group filters by port and IP (layer 3-4). WAF reads the actual web content (layer 7). Both together = layered defense."
**Console backup:** WAF console → Web ACLs → sentry-webacl → two managed rule groups visible.

## 6. IAM LEAST PRIVILEGE - live proof ⭐ (Session Manager + AccessDenied)
**What:** The server's role allows ONLY the vault bucket and ONE KMS key. Nothing else.
**SHOW (2 min):** EC2 console → select instance → **Connect** → Session Manager tab → Connect → a browser terminal opens. Type:
- `aws s3 ls s3://sentry-vault-<ACCOUNT_ID>` → **works** (lists files)
- `aws s3api list-buckets` → **AccessDenied** error appears!
**SAY:** "See - the server CAN read its own vault, but when I ask it to list all buckets in the account: Access Denied. The role grants the minimum. If the app were hacked, the attacker inherits these tiny permissions - the blast radius is contained."
**Console backup:** Tab 5 → IAM role → show JSON.
**Bonus line:** "And note - I'm inside the server with NO SSH key. This is Session Manager: IAM-authenticated, fully logged."

## 7. CLOUDTRAIL - the witness (CloudForensics)
**What:** Records every API call: who, what, when, from which IP. Two layers:
- **Event history (console):** management events - key operations, bucket operations, IAM changes. Filter: dropdown "Event source" → `kms.amazonaws.com` or `s3.amazonaws.com`.
- **Raw forensic logs:** object-level events (every upload/delete/tamper attempt) are delivered as log files to the `sentry-trail-<ACCOUNT_ID>` bucket.
**SHOW (easy version):** Open the vault → file `AUDIT_LOG_EXTRACT.txt` → Download → show in Notepad:
> Lines like `DeleteObject | worm.txt | AccessDenied: object protected by object lock` - the tamper attempts, timestamped, attributed to the exact IAM role identity.
**SAY:** "Every action is recorded - uploads, tamper attempts, even the identity that attempted them. In forensics this is the difference between 'I think someone tampered' and 'here is machine-generated proof of who did what and when'."
**If asked why Event history doesn't show PutObject:** "Object-level operations are data events - AWS records them as raw log files delivered to my audit bucket rather than in the console view. The evidence is the same, the format is forensic-grade."
**If asked - CloudTrail vs Config:** "CloudTrail: WHO did WHAT and WHEN (API calls). Config: IS the configuration compliant (resource state)."

## 8. AWS CONFIG - compliance
**What:** Continuously checks resources against rules.
**SHOW:** Tab 4 → Rules → `sentry-bucket-not-public` → **Compliant** ✅.
**SAY:** "If my bucket ever became public - accidentally or maliciously - this flips to Non-compliant automatically. Continuous auditing, not point-in-time."

## 9. CLOUDFORMATION - Infrastructure as Code
**What:** One YAML template built all ~26 resources automatically.
**SHOW:** Tab 6 → Events tab (creation log) → Template tab (the code).
**SAY:** "Everything you've seen was deployed from one template - repeatable, versioned, deletable in one command. No manual clicking, no configuration drift."
**Meaning line:** "This is how real companies manage infrastructure - code, not clicks."

## 10. TELEGRAM BOT - serverless monitoring (Lambda)
**What:** AWS Lambda runs code without any server - pay per request. My bot: S3 events → Lambda → phone alert; commands /status /files /events /health.
**SHOW:** Phone: type `/status` → bot lists all 9 layers. Type `/files` → vault contents.
**SAY:** "Two independent alert paths - the app alerts, AND the storage layer itself triggers a serverless function. Even if the app were compromised and silenced, the vault still reports. Defense-in-depth applies to monitoring too."

## 11. BUDGETS - cost governance
**SHOW:** Billing → Budgets → $1 budget → "an email alerts me at 80% - I have the confirmation email."

---

## CLOSING LINE
> "So ma'am - the attack was blocked at the edge, the evidence cannot be destroyed even by the administrator, every action is witnessed, the configuration is continuously audited, the infrastructure is code, and alerts reach my phone in real time. That is defense-in-depth: every layer assumes the previous one failed."

## 🆘 FAIL-SAFES
| Problem | Fix |
|---|---|
| Any page hangs | Refresh once - say "AWS is processing" |
| Delete shows no red banner | S3 console → file → Object Lock section says GOVERNANCE |
| SQLi URL loads normally | Use XSS URL; or WAF console static view |
| WiFi dead | Phone screenshots of upload ✓ delete-block ✓ 403 ✓ |
| Session Manager won't open | Just show the IAM role JSON instead |

## 🧘 RULES
Slow speech. Narrate every click. Failures = smile bigger. Never touch Terminate/Delete/Empty in console. Have your phone charged + Telegram open.
