#!/bin/sh
set -eu

if ! awslocal s3api head-bucket --bucket enter-resume-quarantine 2>/dev/null; then
  awslocal s3api create-bucket \
    --bucket enter-resume-quarantine \
    --region ap-south-1 \
    --create-bucket-configuration LocationConstraint=ap-south-1
fi
awslocal s3api put-bucket-cors \
  --bucket enter-resume-quarantine \
  --cors-configuration '{"CORSRules":[{"AllowedHeaders":["content-type","x-amz-meta-sha256"],"AllowedMethods":["PUT"],"AllowedOrigins":["http://localhost:8000"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":300}]}'
