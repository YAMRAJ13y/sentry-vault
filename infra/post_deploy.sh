#!/usr/bin/env bash
# ============================================================
# SENTRY VAULT - post-deploy configuration (all platforms)
# Usage:
#   bash infra/post_deploy.sh <email>                    # core services
#   TELEGRAM_BOT_TOKEN=123:abc TELEGRAM_CHAT_ID=456 \
#     bash infra/post_deploy.sh <email>                  # core + Telegram bot
# Works on Windows (Git Bash), Linux and macOS.
# Requires: aws cli v2 configured (default profile or AWS_PROFILE), python 3.
# ============================================================
set -uo pipefail

EMAIL="${1:-}"
BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
BOT_CHAT="${TELEGRAM_CHAT_ID:-}"
REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo ap-south-1)}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="sentry-vault-${ACCOUNT}"
TRAILBUCKET="sentry-trail-${ACCOUNT}"
P="--profile ${AWS_PROFILE:-default}"

if [ -z "$ACCOUNT" ] || [ "$ACCOUNT" = "None" ]; then
  echo "ERROR: aws credentials not working. Run: aws configure"
  exit 1
fi

echo "== SENTRY VAULT post-deploy (account ${ACCOUNT}, region ${REGION}) =="

echo "== 1. S3 Object Lock default retention (GOVERNANCE, 1 day) =="
aws $P s3api put-object-lock-configuration --bucket "$BUCKET" \
  --object-lock-configuration '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"GOVERNANCE","Days":1}}}' \
  && echo "OK object lock"

echo "== 2. Canonical trail bucket policy =="
TMPPOLICY="$(pwd)/trail_policy.tmp.json"
cat > "$TMPPOLICY" <<POLICYEOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Sid": "AWSCloudTrailAclCheck20150319", "Effect": "Allow",
     "Principal": {"Service": "cloudtrail.amazonaws.com"},
     "Action": "s3:GetBucketAcl",
     "Resource": "arn:aws:s3:::${TRAILBUCKET}"},
    {"Sid": "AWSCloudTrailWrite20150319", "Effect": "Allow",
     "Principal": {"Service": "cloudtrail.amazonaws.com"},
     "Action": "s3:PutObject",
     "Resource": "arn:aws:s3:::${TRAILBUCKET}/AWSLogs/${ACCOUNT}/*",
     "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}}},
    {"Sid": "AWSConfigBucketPermissionsCheck", "Effect": "Allow",
     "Principal": {"Service": "config.amazonaws.com"},
     "Action": ["s3:GetBucketAcl", "s3:ListBucket"],
     "Resource": "arn:aws:s3:::${TRAILBUCKET}"},
    {"Sid": "AWSConfigBucketDelivery", "Effect": "Allow",
     "Principal": {"Service": "config.amazonaws.com"},
     "Action": "s3:PutObject",
     "Resource": "arn:aws:s3:::${TRAILBUCKET}/AWSLogs/${ACCOUNT}/Config/*",
     "Condition": {"StringEquals": {"s3:x-amz-acl": "bucket-owner-full-control"}}}
  ]
}
POLICYEOF
aws $P s3api put-bucket-policy --bucket "$TRAILBUCKET" --policy "file://$TMPPOLICY" && echo "OK policy"
rm -f "$TMPPOLICY"

echo "== 3. CloudTrail + start logging =="
aws $P cloudtrail create-trail --name sentry-trail --s3-bucket-name "$TRAILBUCKET" \
  --is-multi-region-trail --include-global-service-events --enable-log-file-validation --no-cli-pager >/dev/null \
  && echo "OK trail"
aws $P cloudtrail start-logging --name sentry-trail && echo "OK logging"

echo "== 4. AWS Config (role, recorder, delivery, rule) =="
aws $P iam create-role --role-name sentry-config-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"config.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null 2>&1
aws $P iam attach-role-policy --role-name sentry-config-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWS_ConfigRole
aws $P iam put-role-policy --role-name sentry-config-role --policy-name sentry-delivery \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:PutObject\",\"s3:GetBucketAcl\"],\"Resource\":[\"arn:aws:s3:::${TRAILBUCKET}\",\"arn:aws:s3:::${TRAILBUCKET}/AWSLogs/${ACCOUNT}/Config/*\"]}]}"
aws $P configservice put-configuration-recorder \
  --configuration-recorder "name=sentry-recorder,roleARN=arn:aws:iam::${ACCOUNT}:role/sentry-config-role" \
  --recording-group allSupported=true,includeGlobalResourceTypes=true && echo "OK recorder"
sleep 15   # role propagation
aws $P configservice put-delivery-channel \
  --delivery-channel "name=sentry-delivery,s3BucketName=${TRAILBUCKET},configSnapshotDeliveryProperties={deliveryFrequency=One_Hour}" \
  && echo "OK delivery"
aws $P configservice start-configuration-recorder --configuration-recorder-name sentry-recorder && echo "OK config started"
aws $P configservice put-config-rule --config-rule '{"ConfigRuleName":"sentry-bucket-not-public","Scope":{"ComplianceResourceTypes":["AWS::S3::Bucket"]},"Source":{"Owner":"AWS","SourceIdentifier":"S3_BUCKET_PUBLIC_READ_PROHIBITED"}}' && echo "OK config rule"

echo "== 5. Budget: \$1 monthly + email alert (${EMAIL}) =="
if [ -z "$EMAIL" ]; then
  echo "-- skipped (no email given)"
else
  aws $P budgets delete-budget --account-id "$ACCOUNT" --budget-name sentry-vault-budget >/dev/null 2>&1
  aws $P budgets create-budget --account-id "$ACCOUNT" \
    --budget '{"BudgetName":"sentry-vault-budget","BudgetLimit":{"Amount":"1","Unit":"USD"},"TimeUnit":"MONTHLY","BudgetType":"COST"}' \
    --notifications-with-subscribers "[{\"Notification\":{\"NotificationType\":\"ACTUAL\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":80,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"${EMAIL}\"}]}]" \
    && echo "OK budget (confirm the AWS verification email in your inbox!)"
fi

echo "== 6. GuardDuty (optional - skipped automatically if the plan restricts it) =="
aws $P guardduty create-detector --enable --finding-publishing-frequency FIFTEEN_MINUTES >/dev/null 2>&1 \
  && echo "OK guardduty" || echo "-- guardduty unavailable on this account plan (not required)"

if [ -n "$BOT_TOKEN" ] && [ -n "$BOT_CHAT" ]; then
  echo "== 7. Telegram bot: Lambda + webhook + S3 alerts =="
  (cd bot && python -m zipfile -c sentry-bot.zip lambda_function.py)
  aws $P iam create-role --role-name sentry-telegram-lambda-role \
    --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' >/dev/null 2>&1
  aws $P iam attach-role-policy --role-name sentry-telegram-lambda-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  aws $P iam put-role-policy --role-name sentry-telegram-lambda-role --policy-name sentry-bot-access \
    --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:ListBucket\",\"s3:GetObject\"],\"Resource\":[\"arn:aws:s3:::${BUCKET}\",\"arn:aws:s3:::${BUCKET}/*\"]},{\"Effect\":\"Allow\",\"Action\":\"cloudtrail:LookupEvents\",\"Resource\":\"*\"}]}"
  sleep 12
  aws $P lambda create-function --function-name sentry-telegram-bot --runtime python3.12 \
    --handler lambda_function.handler --role "arn:aws:iam::${ACCOUNT}:role/sentry-telegram-lambda-role" \
    --zip-file "fileb://bot/sentry-bot.zip" --timeout 15 --memory-size 128 \
    --environment "Variables={TELEGRAM_TOKEN=${BOT_TOKEN},TELEGRAM_CHAT_ID=${BOT_CHAT},VAULT_BUCKET=${BUCKET},WEBHOOK_SECRET=sentry-vault-hook-${ACCOUNT},APP_URL=PENDING}" >/dev/null \
    && echo "OK lambda"
  FURL=$(aws $P lambda create-function-url-config --function-name sentry-telegram-bot --auth-type NONE --query FunctionUrl --output text)
  aws $P lambda add-permission --function-name sentry-telegram-bot --statement-id url-invocation --action lambda:InvokeFunctionUrl --principal "*" --function-url-auth-type NONE >/dev/null
  aws $P lambda add-permission --function-name sentry-telegram-bot --statement-id url-invoke --action lambda:InvokeFunction --principal "*" >/dev/null
  sleep 10
  aws $P lambda add-permission --function-name sentry-telegram-bot --statement-id s3-invoke --action lambda:InvokeFunction --principal s3.amazonaws.com --source-arn "arn:aws:s3:::${BUCKET}" >/dev/null
  aws $P s3api put-bucket-notification-configuration --bucket "$BUCKET" \
    --notification-configuration "{\"LambdaFunctionConfigurations\":[{\"LambdaFunctionArn\":\"arn:aws:lambda:${REGION}:${ACCOUNT}:function:sentry-telegram-bot\",\"Events\":[\"s3:ObjectCreated:*\"]}]}" \
    && echo "OK s3 -> lambda alerts"
  curl -s "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" -d "url=${FURL}" -d "secret_token=sentry-vault-hook-${ACCOUNT}" -d 'allowed_updates=["message"]' >/dev/null \
    && echo "OK telegram webhook: ${FURL}"
  # point the lambda at the live app URL (from the stack output)
  APP=$(aws $P cloudformation describe-stacks --stack-name sentry-vault \
        --query "Stacks[0].Outputs[?OutputKey=='WebsiteURL'].OutputValue" --output text 2>/dev/null)
  if [ -n "$APP" ]; then
    aws $P lambda update-function-configuration --function-name sentry-telegram-bot \
      --environment "Variables={TELEGRAM_TOKEN=${BOT_TOKEN},TELEGRAM_CHAT_ID=${BOT_CHAT},VAULT_BUCKET=${BUCKET},WEBHOOK_SECRET=sentry-vault-hook-${ACCOUNT},APP_URL=${APP}}" >/dev/null \
      && echo "OK bot APP_URL wired to ${APP}"
  fi
  rm -f bot/sentry-bot.zip
else
  echo "-- skipping Telegram bot (set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable)"
fi

echo "== POST-DEPLOY COMPLETE =="
