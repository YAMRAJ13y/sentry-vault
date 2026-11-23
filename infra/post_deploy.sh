#!/bin/bash
# Complete post-deploy configuration for SENTRY VAULT
# Run AFTER 'aws cloudformation deploy' completes successfully
export PATH="$PATH:/c/Program Files/Amazon/AWSCLIV2"
P="--profile zcode --region ap-south-1"
ACCOUNT=YOUR_ACCOUNT_ID
BUCKET="sentry-vault-${ACCOUNT}"
TRAILBUCKET="sentry-trail-${ACCOUNT}"
EMAIL="${1:-your-email@example.com}"

echo "===== 1. S3 Object Lock default retention (GOVERNANCE, 1 day) ====="
aws $P s3api put-object-lock-configuration --bucket "$BUCKET" \
  --object-lock-configuration '{"ObjectLockEnabled":"Enabled","Rule":{"DefaultRetention":{"Mode":"GOVERNANCE","Days":1}}}' \
  && echo "OK object lock"

echo "===== 2. Canonical trail bucket policy ====="
cat > /tmp/trail_policy.json <<EOF
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
EOF
aws $P s3api put-bucket-policy --bucket "$TRAILBUCKET" --policy "file:///tmp/trail_policy.json" && echo "OK policy"

echo "===== 3. CloudTrail trail + start logging ====="
aws $P cloudtrail create-trail \
  --name sentry-trail \
  --s3-bucket-name "$TRAILBUCKET" \
  --is-multi-region-trail \
  --include-global-service-events \
  --enable-log-file-validation \
  --no-cli-pager && echo "OK trail created"
aws $P cloudtrail start-logging --name sentry-trail && echo "OK logging started"

echo "===== 4. GuardDuty detector (may need console subscription) ====="
aws $P guardduty create-detector --enable --finding-publishing-frequency FIFTEEN_MINUTES 2>&1 && echo "OK guardduty" || echo "!! GuardDuty needs one-time console enable"

echo "===== 5. AWS Config: role + recorder + delivery + rule ====="
aws $P iam create-role --role-name sentry-config-role \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"config.amazonaws.com"},"Action":"sts:AssumeRole"}]}' 2>&1 | grep -q RoleName && echo "OK config role" || echo "role exists?"
aws $P iam attach-role-policy --role-name sentry-config-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWS_ConfigRole
aws $P iam put-role-policy --role-name sentry-config-role --policy-name sentry-delivery \
  --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"s3:PutObject\",\"s3:GetBucketAcl\"],\"Resource\":[\"arn:aws:s3:::${TRAILBUCKET}\",\"arn:aws:s3:::${TRAILBUCKET}/AWSLogs/${ACCOUNT}/Config/*\"]}]}"

aws $P configservice put-configuration-recorder --configuration-recorder "name=sentry-recorder,roleARN=arn:aws:iam::${ACCOUNT}:role/sentry-config-role" --recording-group allSupported=true,includeGlobalResourceTypes=true && echo "OK recorder"
aws $P configservice put-delivery-channel --delivery-channel "name=sentry-delivery,s3BucketName=${TRAILBUCKET},configSnapshotDeliveryProperties={deliveryFrequency=One_Hour}" && echo "OK delivery"
aws $P configservice start-configuration-recorder --configuration-recorder-name sentry-recorder && echo "OK config started"
aws $P configservice put-config-rule --config-rule '{"ConfigRuleName":"sentry-bucket-not-public","Scope":{"ComplianceResourceTypes":["AWS::S3::Bucket"]},"Source":{"Owner":"AWS","SourceIdentifier":"S3_BUCKET_PUBLIC_READ_PROHIBITED"}}' && echo "OK config rule"

echo "===== 6. Budget: \$1 monthly, email alert ====="
aws $P budgets create-budget --account-id "$ACCOUNT" \
  --budget "{\"BudgetName\":\"sentry-vault-budget\",\"BudgetLimit\":{\"Amount\":\"1\",\"Unit\":\"USD\"},\"TimeUnit\":\"MONTHLY\",\"BudgetType\":\"COST\"}" \
  --notifications-with-subscribers "[{\"Notification\":{\"NotificationType\":\"ACTUAL\",\"ComparisonOperator\":\"GREATER_THAN\",\"Threshold\":80,\"ThresholdType\":\"PERCENTAGE\"},\"Subscribers\":[{\"SubscriptionType\":\"EMAIL\",\"Address\":\"${EMAIL}\"}]}]" \
  && echo "OK budget (confirm email: ${EMAIL})" || echo "!! budget failed (maybe exists)"

echo "===== POST-DEPLOY COMPLETE ====="
