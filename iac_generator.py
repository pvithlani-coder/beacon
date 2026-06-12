import boto3
from datetime import datetime
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()

AWS_REGION = 'us-east-2'
claude = anthropic.Anthropic()


def generate_tagging_terraform(account_id, required_tags=None):
    if required_tags is None:
        required_tags = ['Owner', 'Environment', 'Team', 'CostCenter']

    tag_rules = "\n".join([
        f'    "{tag}" = {{' + '\n' +
        f'      enforce = true\n' +
        f'    }}'
        for tag in required_tags
    ])

    terraform = f'''# OpsBeacon Generated - Tagging Enforcement Policy
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Account: {account_id}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{AWS_REGION}"
}}

# Require tags on all EC2 instances
resource "aws_ec2_tag" "enforce_tags" {{
  resource_id = var.instance_id
  key         = "ManagedBy"
  value       = "OpsBeacon"
}}

# Tag policy for the organization
resource "aws_organizations_policy" "tagging_policy" {{
  name        = "opsbeacon-required-tags"
  description = "Enforce required cost allocation tags"
  type        = "TAG_POLICY"

  content = jsonencode({{
    tags = {{
{tag_rules}
    }}
  }})
}}

resource "aws_organizations_policy_attachment" "tagging_policy_attachment" {{
  policy_id = aws_organizations_policy.tagging_policy.id
  target_id = "{account_id}"
}}

variable "instance_id" {{
  description = "EC2 instance ID to tag"
  type        = string
  default     = ""
}}
'''
    return terraform


def generate_rds_schedule_terraform(db_instance_id, start_time="07:00", stop_time="19:00"):
    terraform = f'''# OpsBeacon Generated - RDS Auto Start/Stop Schedule
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Instance: {db_instance_id}
# Schedule: Start {start_time} / Stop {stop_time} weekdays
# Estimated savings: ~65% of current RDS spend

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{AWS_REGION}"
}}

# IAM role for Lambda
resource "aws_iam_role" "rds_scheduler_role" {{
  name = "opsbeacon-rds-scheduler-role"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {{
        Service = "lambda.amazonaws.com"
      }}
    }}]
  }})
}}

resource "aws_iam_role_policy" "rds_scheduler_policy" {{
  name = "opsbeacon-rds-scheduler-policy"
  role = aws_iam_role.rds_scheduler_role.id

  policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Action = [
          "rds:StartDBInstance",
          "rds:StopDBInstance",
          "rds:DescribeDBInstances"
        ]
        Resource = "arn:aws:rds:{AWS_REGION}:*:db:{db_instance_id}"
      }},
      {{
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }}
    ]
  }})
}}

# Lambda function to start RDS
resource "aws_lambda_function" "rds_start" {{
  filename         = "rds_scheduler.zip"
  function_name    = "opsbeacon-rds-start-{db_instance_id}"
  role             = aws_iam_role.rds_scheduler_role.arn
  handler          = "index.handler"
  runtime          = "python3.11"

  environment {{
    variables = {{
      DB_INSTANCE_ID = "{db_instance_id}"
      ACTION         = "start"
    }}
  }}
}}

# Lambda function to stop RDS
resource "aws_lambda_function" "rds_stop" {{
  filename         = "rds_scheduler.zip"
  function_name    = "opsbeacon-rds-stop-{db_instance_id}"
  role             = aws_iam_role.rds_scheduler_role.arn
  handler          = "index.handler"
  runtime          = "python3.11"

  environment {{
    variables = {{
      DB_INSTANCE_ID = "{db_instance_id}"
      ACTION         = "stop"
    }}
  }}
}}

# EventBridge rule - Start at 7am weekdays
resource "aws_cloudwatch_event_rule" "rds_start_schedule" {{
  name                = "opsbeacon-rds-start-{db_instance_id}"
  description         = "Start RDS instance on weekday mornings"
  schedule_expression = "cron(0 {start_time.split(':')[0]} ? * MON-FRI *)"
}}

# EventBridge rule - Stop at 7pm weekdays
resource "aws_cloudwatch_event_rule" "rds_stop_schedule" {{
  name                = "opsbeacon-rds-stop-{db_instance_id}"
  description         = "Stop RDS instance on weekday evenings"
  schedule_expression = "cron(0 {stop_time.split(':')[0]} ? * MON-FRI *)"
}}

resource "aws_cloudwatch_event_target" "start_target" {{
  rule      = aws_cloudwatch_event_rule.rds_start_schedule.name
  target_id = "StartRDS"
  arn       = aws_lambda_function.rds_start.arn
}}

resource "aws_cloudwatch_event_target" "stop_target" {{
  rule      = aws_cloudwatch_event_rule.rds_stop_schedule.name
  target_id = "StopRDS"
  arn       = aws_lambda_function.rds_stop.arn
}}
'''
    return terraform


def generate_s3_lifecycle_terraform(bucket_name):
    terraform = f'''# OpsBeacon Generated - S3 Lifecycle Policy
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Bucket: {bucket_name}
# Moves objects to cheaper storage tiers automatically

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{AWS_REGION}"
}}

resource "aws_s3_bucket_lifecycle_configuration" "cost_optimization" {{
  bucket = "{bucket_name}"

  rule {{
    id     = "opsbeacon-cost-optimization"
    status = "Enabled"

    transition {{
      days          = 30
      storage_class = "STANDARD_IA"
    }}

    transition {{
      days          = 90
      storage_class = "GLACIER"
    }}

    transition {{
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }}

    expiration {{
      days = 2555  # 7 years
    }}

    noncurrent_version_transition {{
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }}

    noncurrent_version_expiration {{
      noncurrent_days = 90
    }}
  }}
}}
'''
    return terraform


def generate_snapshot_cleanup_terraform(snapshot_ids):
    snap_list = "\n".join([f'    "{snap}",' for snap in snapshot_ids])

    terraform = f'''# OpsBeacon Generated - Snapshot Cleanup
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}
# Snapshots to delete: {len(snapshot_ids)}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }}
  }}
}}

provider "aws" {{
  region = "{AWS_REGION}"
}}

# WARNING: This will permanently delete the following snapshots.
# Review carefully before applying.
# Snapshots to delete:
{chr(10).join([f"# - {snap}" for snap in snapshot_ids])}

locals {{
  snapshot_ids = [
{snap_list}
  ]
}}

# Note: Terraform cannot directly delete snapshots via resource blocks.
# Use the AWS CLI commands below instead:
{chr(10).join([f"# aws ec2 delete-snapshot --snapshot-id {snap} --region {AWS_REGION}" for snap in snapshot_ids])}

# Or use this null_resource to run cleanup automatically:
resource "null_resource" "delete_snapshots" {{
  provisioner "local-exec" {{
    command = <<-EOT
{chr(10).join([f"      aws ec2 delete-snapshot --snapshot-id {snap} --region {AWS_REGION}" for snap in snapshot_ids])}
    EOT
  }}
}}
'''
    return terraform


def generate_iac_for_finding(finding_type, context=None):
    if context is None:
        context = {}

    if finding_type == 'tagging':
        account_id = context.get('account_id', 'YOUR_ACCOUNT_ID')
        return {
            'type': 'terraform',
            'filename': 'tagging_enforcement.tf',
            'description': 'Enforce required cost allocation tags across all resources',
            'estimated_savings': 'Enables cost attribution and prevents future untagged resource waste',
            'code': generate_tagging_terraform(account_id)
        }

    elif finding_type == 'rds_schedule':
        db_id = context.get('db_id', 'your-db-instance')
        monthly_cost = context.get('monthly_cost', 0)
        savings = round(monthly_cost * 0.65, 2)
        return {
            'type': 'terraform',
            'filename': 'rds_auto_schedule.tf',
            'description': f'Auto start/stop RDS instance {db_id} on weekday schedule',
            'estimated_savings': f'${savings}/month (65% reduction)',
            'code': generate_rds_schedule_terraform(db_id)
        }

    elif finding_type == 's3_lifecycle':
        bucket = context.get('bucket_name', 'your-bucket-name')
        return {
            'type': 'terraform',
            'filename': 's3_lifecycle_policy.tf',
            'description': f'S3 lifecycle policy to move objects to cheaper storage tiers',
            'estimated_savings': 'Up to 80% reduction on S3 storage costs over time',
            'code': generate_s3_lifecycle_terraform(bucket)
        }

    elif finding_type == 'snapshot_cleanup':
        snapshot_ids = context.get('snapshot_ids', [])
        monthly_waste = context.get('monthly_waste', 0)
        return {
            'type': 'terraform',
            'filename': 'snapshot_cleanup.tf',
            'description': f'Delete {len(snapshot_ids)} old snapshots',
            'estimated_savings': f'${monthly_waste}/month',
            'code': generate_snapshot_cleanup_terraform(snapshot_ids)
        }

    return None


def get_iac_recommendations():
    from idle_resources import get_all_idle_resources
    from aws_accounts import get_unmanaged_accounts

    recommendations = []

    # Check for old snapshots
    idle_data = get_all_idle_resources()
    if idle_data['old_snapshots']:
        snapshot_ids = [s['id'] for s in idle_data['old_snapshots']]
        monthly_waste = sum(s['monthly_cost'] for s in idle_data['old_snapshots'])
        iac = generate_iac_for_finding('snapshot_cleanup', {
            'snapshot_ids': snapshot_ids,
            'monthly_waste': round(monthly_waste, 2)
        })
        if iac:
            recommendations.append(iac)

    # Check for untagged accounts
    accounts = get_unmanaged_accounts()
    for account in accounts:
        if any('Missing' in issue for issue in account['issues']):
            iac = generate_iac_for_finding('tagging', {
                'account_id': account['account_id']
            })
            if iac:
                recommendations.append(iac)
            break

    # Always include RDS schedule recommendation if RDS exists
    try:
        rds = boto3.client('rds', region_name=AWS_REGION)
        dbs = rds.describe_db_instances()
        for db in dbs['DBInstances']:
            if db['DBInstanceStatus'] == 'available':
                iac = generate_iac_for_finding('rds_schedule', {
                    'db_id': db['DBInstanceIdentifier'],
                    'monthly_cost': 40
                })
                if iac:
                    recommendations.append(iac)
                break
    except Exception as e:
        print(f"RDS check error: {e}")

    return recommendations


if __name__ == "__main__":
    print("\n=== IaC Generation Test ===")
    recs = get_iac_recommendations()
    print(f"\nGenerated {len(recs)} IaC recommendations:")
    for rec in recs:
        print(f"\nType: {rec['type']}")
        print(f"File: {rec['filename']}")
        print(f"Description: {rec['description']}")
        print(f"Savings: {rec['estimated_savings']}")
        print(f"Code preview (first 200 chars):")
        print(rec['code'][:200])