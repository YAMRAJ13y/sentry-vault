# SENTRY VAULT - Viva Q&A Prep Sheet
*Read this 2-3 times tonight. Answers are short on purpose - say them, don't read them.*

## 🎯 THE BIG PICTURE (your opening)

**Q: Explain your project in 1 minute.**
> "My project is SENTRY VAULT - a secure document storage system on AWS. Users upload files through a web app, and the files are protected by multiple security layers, one behind another - this is called defense-in-depth. Files are encrypted with AWS KMS, made tamper-proof with S3 Object Lock, the web app is protected by a WAF firewall, access is restricted by IAM least-privilege, and every action is audited by CloudTrail, monitored by GuardDuty, and checked by AWS Config. The whole infrastructure is deployed as code using CloudFormation."

**Q: Why did you choose this project?**
> "Our labs covered individual services one by one - encryption, object lock, WAF, GuardDuty. I wanted to combine all of them into one real system where each service protects the same application, showing how real defense-in-depth works in cloud security."

**Q: What is defense-in-depth?**
> "Instead of relying on a single security control, we stack multiple independent layers - if one fails, the next one still protects the data. In my project: WAF → ALB → IAM → KMS → Object Lock → CloudTrail. An attacker must defeat every layer."

---

## 🧩 CORE SERVICES

**Q: What is S3?**
> "Simple Storage Service - AWS's object storage. My files are stored as objects inside a bucket, like files in a folder in the cloud."

**Q: What is EC2?**
> "Elastic Compute Cloud - a virtual server in the cloud. My Flask web application runs on a t3.micro EC2 instance."

**Q: What is VPC? Why did you create one?**
> "Virtual Private Cloud - my own private network inside AWS. My server runs inside a VPC so I control exactly what can reach it. The server has no direct public access - only the load balancer can reach it."

**Q: What is a subnet / route table?** (Lab 2)
> "A subnet is a section of the VPC's IP range - mine are public subnets with internet access. The route table defines where network traffic goes - mine routes 0.0.0.0/0 to the Internet Gateway for public access."

**Q: What is IAM? What is least privilege?** (Lab 8)
> "Identity and Access Management - controls who can do what in AWS. Least privilege means giving only the minimum permissions needed. My EC2 server's IAM role can access ONLY the vault bucket and ONLY encrypt/decrypt with the vault key - nothing else. If the app is compromised, the attacker gets almost nothing."

**Q: What are identity-based vs resource-based policies?** (Lab 8)
> "Identity-based policies are attached to a user/role and say what that identity can do. Resource-based policies are attached to the resource itself, like a bucket policy, and say who can access it."

**Q: What is a trust policy?** (Lab 8)
> "It defines WHO is allowed to assume a role. My EC2 role's trust policy allows only ec2.amazonaws.com to use it."

---

## 🔐 ENCRYPTION (Lab 7)

**Q: What is KMS?**
> "AWS Key Management Service - it creates and controls encryption keys. Analogy from our lab: S3 is the locker, KMS is the key system that locks and unlocks it."

**Q: What is SSE-KMS?**
> "Server-Side Encryption with KMS - when my app uploads a file, S3 automatically encrypts it at rest, and KMS controls the key. In the demo I show the object's encryption property in the S3 console saying 'aws:kms'."

**Q: What is envelope encryption?** (Lab 7)
> "KMS doesn't encrypt the whole file with the master key. Instead, KMS generates a data key, which encrypts the file; the data key itself is encrypted by the master KMS key. Two layers - that's envelope encryption."

**Q: Why KMS instead of just SSE-S3?**
> "SSE-S3 uses keys fully managed by S3. With SSE-KMS I control my own key - key rotation is enabled, every use of the key is logged in CloudTrail, and only my IAM role can use it. Better control and auditability."

---

## 🗄️ TAMPER-PROOFING (Lab 9)

**Q: What is S3 Versioning?**
> "Keeping multiple versions of the same object. If I upload report.txt twice, S3 keeps both versions instead of overwriting. Protects against accidental overwrites."

**Q: What is Object Lock? What is WORM?**
> "Object Lock is WORM protection - Write Once, Read Many. Once a file version is locked, it cannot be deleted or overwritten during the retention period - not even by the admin. That's what makes my evidence tamper-proof. My demo shows AWS refusing a delete attempt."

**Q: Why does Object Lock need Versioning?**
> "Object Lock protects individual object versions. Versioning gives each upload a unique version ID, so the lock knows exactly which copy to protect."

**Q: Governance mode vs Compliance mode?**
> "In Governance mode, special privileged users can bypass the lock with special permission. In Compliance mode, NO ONE can delete until retention expires - not even root. My project uses Governance (1-day retention) for flexibility; switching to Compliance is a one-line change for stricter evidence handling."

---

## 🛡️ NETWORK & WEB SECURITY (Labs 2, 6)

**Q: What is WAF? How did you demo it?**
> "Web Application Firewall - inspects HTTP requests and blocks malicious ones. I attached AWS's managed rule groups: SQL injection and common exploits. In the demo, I send a URL containing a SQLi payload - WAF returns 403 Forbidden before the request ever reaches my server."

**Q: What is an ALB?**
> "Application Load Balancer - receives traffic and forwards it to my server. It's my app's ONLY entrance. Also required to attach WAF, and provides a single stable DNS name."

**Q: What is a security group?**
> "A virtual firewall for an instance, stateful, allows rules only. My ALB's SG accepts HTTP from the internet; my server's SG accepts HTTP ONLY from the ALB's security group - nobody can bypass the load balancer, and there is no open SSH port at all."

**Q: How do you manage the server without SSH?** (Lab 6)
> "AWS Session Manager - shell access through the AWS console with IAM authentication. All sessions are logged. No port 22 open to the internet."

---

## 👁️ MONITORING & FORENSICS (Labs 5, 9b)

**Q: What is CloudTrail?**
> "It records every API call in the account - who did what, when, from which IP. It's the CCTV of the cloud. For forensics, I can prove exactly who uploaded, downloaded, or tried to delete any file."

**Q: What is AWS Config? How is it different from CloudTrail?** (Lab 9b)
> "Config records the configuration of resources and checks compliance against rules - 'what does my resource look like, is it configured correctly?' CloudTrail answers WHO did WHAT and WHEN. Config answers WHAT CHANGED and IS IT COMPLIANT. My rule checks that my bucket never becomes public."

**Q: What is GuardDuty?**
> "AWS's intelligent threat detection service - analyzes CloudTrail, VPC Flow Logs and DNS logs using machine learning to detect suspicious activity like brute force or compromised instances, and raises findings automatically. We worked with it in Lab 5."

**Q: Show me the KMS encrypt/decrypt logs in CloudTrail?**
> Be precise and honest: "CloudTrail has two event layers. Management events - like DescribeKey, GetKeyPolicy, ListAliases on my key - are visible right in Event history; I can filter by event source kms.amazonaws.com. Object/crypto-level operations - every GenerateDataKey and Decrypt call - are *data events*: AWS records them as raw log files delivered to my audit bucket. My S3 object-level audit (uploads, tamper attempts) works exactly that way - I can show you the raw log with every attempt timestamped and attributed to the exact IAM role."

**Q: Tell me about your Telegram bot - what does it do?**
> "It's a real-time security alerting bot hosted **serverless on AWS Lambda**. Two independent notification paths: when any file lands in the vault, S3 itself triggers the Lambda function which messages me - even if my web app were compromised and silenced, the storage layer still reports. And when a tamper attempt is blocked, the application pushes an alert to my phone instantly. The bot also answers commands: /status lists all active security layers, /files shows the vault contents, /events pulls recent CloudTrail audit entries, /health checks the app. The Telegram webhook is secured with a secret token so only Telegram can invoke the Lambda."

**If ma'am asks: "Is GuardDuty running in YOUR project?"**
> Be honest and confident: *"GuardDuty is part of the architecture design. My AWS account is on the Free Plan, which restricts activating GuardDuty - it needs a plan upgrade. So the live demo focuses on the enforcement controls - WAF, KMS, Object Lock, IAM, CloudTrail and Config, which are all running. Enabling GuardDuty is a one-click step on an upgraded account, and it would plug straight into this design."*
> (Do NOT claim it is running. Honesty + knowing the concept scores better than getting caught.)

**Q: What is a security baseline?** (Lab 5)
> "The documented normal state of a system before an incident. Detection only works when you know what 'normal' looks like."

---

## ⚙️ OPS & COST

**Q: What is CloudFormation? Why use it?**
> "Infrastructure as Code - my entire architecture is one YAML template. One command deploys everything; one command deletes everything. No manual clicking, repeatable, and it's the professional way to manage cloud infrastructure."

**Q: What is a presigned URL?**
> "A temporary link that grants download access for a limited time - mine expire in 5 minutes. Convenient without making files public."

**Q: What did this project cost?**
> "Almost nothing - it fits in the AWS Free Tier, and I set a $1 budget alarm that emails me at 80% usage so there can never be a surprise bill."

**Q: Limitations / future improvements?**
> "HTTPS needs a registered domain + ACM certificate; user accounts could use Cognito; auto-scaling with multiple instances behind the ALB; GuardDuty findings could auto-trigger Lambda to isolate compromised servers - automated incident response."

**Q: If the attacker compromises your web app completely, what do they get?**
> "Only the app's IAM role - which can touch one bucket, with files encrypted, locked, and every action recorded in CloudTrail. And GuardDuty flags unusual behaviour automatically. That's the whole point of defense-in-depth."

**Q: Did you face any challenges while building this?** ⭐ (very common question - this is a REAL one you solved)
> "Yes - a real WAF tuning challenge. AWS's managed firewall rules block any request body over 8 KB by default - an anti-abuse default. When I uploaded my first real evidence file, the WAF blocked it with 403. I didn't disable the protection - I tuned that single rule to *Count mode* (detect and log, but don't block), while keeping every other rule actively blocking. That's the daily reality of cloud security: security controls must be tuned to the application, not just switched on."
>
> (This is gold: it shows you understand managed rules, tuning trade-offs, and real operations.)
