import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
AWS_REGION = 'us-east-2'

def get_untagged_resources():
    ec2 = boto3.client('ec2')
    rds = boto3.client('rds')

    untagged = []

    print("Checking EC2 instances for missing tags...")
    instances = ec2.describe_instances(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    )

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}

            missing = []
            for required_tag in ['Name', 'Environment', 'Owner']:
                if required_tag not in tags:
                    missing.append(required_tag)

            if missing:
                untagged.append({
                    'type': 'EC2',
                    'id': instance_id,
                    'missing_tags': missing
                })

    print("Checking RDS instances for missing tags...")
    dbs = rds.describe_db_instances()

    for db in dbs['DBInstances']:
        db_id = db['DBInstanceIdentifier']
        arn = db['DBInstanceArn']

        tag_response = rds.list_tags_for_resource(ResourceName=arn)
        tags = {t['Key']: t['Value'] for t in tag_response['TagList']}

        missing = []
        for required_tag in ['Environment', 'Owner']:
            if required_tag not in tags:
                missing.append(required_tag)

        if missing:
            untagged.append({
                'type': 'RDS',
                'id': db_id,
                'missing_tags': missing
            })

    return untagged


def get_policy_violations():
    ec2 = boto3.client('ec2')
    s3 = boto3.client('s3')

    violations = []

    print("Checking S3 buckets for public access...")
    try:
        buckets = s3.list_buckets()
        for bucket in buckets['Buckets']:
            bucket_name = bucket['Name']
            try:
                acl = s3.get_bucket_acl(Bucket=bucket_name)
                for grant in acl['Grants']:
                    grantee = grant.get('Grantee', {})
                    if grantee.get('URI') == 'http://acs.amazonaws.com/groups/global/AllUsers':
                        violations.append({
                            'type': 'S3',
                            'id': bucket_name,
                            'violation': 'Public access enabled'
                        })
            except Exception:
                pass
    except Exception as e:
        print(f"S3 check error: {e}")

    print("Checking EC2 for oversized instances...")
    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )

        oversized = ['x1', 'x1e', 'p3', 'p4', 'inf1', 'g4']

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_type = instance['InstanceType']
                tags = {t['Key']: t['Value']
                        for t in instance.get('Tags', [])}
                environment = tags.get('Environment', 'unknown').lower()

                if any(instance_type.startswith(s) for s in oversized):
                    violations.append({
                        'type': 'EC2',
                        'id': instance['InstanceId'],
                        'violation': f'Oversized instance {instance_type} in {environment}'
                    })
    except Exception as e:
        print(f"EC2 check error: {e}")

    return violations


def get_egress_anomalies():
    client = boto3.client('ce', region_name='us-east-2')

    anomalies = []

    print("Checking for data transfer cost anomalies...")
    try:
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

        response = client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        for group in response['ResultsByTime'][0]['Groups']:
            service = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])

            if 'Data Transfer' in service and amount > 5:
                anomalies.append({
                    'service': service,
                    'amount': round(amount, 2),
                    'flag': 'High data transfer cost detected'
                })
    except Exception as e:
        print(f"Egress check error: {e}")

    return anomalies


def get_shadow_ai():
    client = boto3.client('ce', region_name='us-east-2')

    ai_services = [
        'Amazon Bedrock',
        'Amazon SageMaker',
        'Amazon Rekognition',
        'Amazon Comprehend',
        'Amazon Textract',
        'Amazon Polly',
        'Amazon Transcribe',
        'Amazon Lex',
        'AWS DeepLearning',
        'Amazon Kendra'
    ]

    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )

    shadow_ai = []

    for group in response['ResultsByTime'][0]['Groups']:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])

        if any(ai in service for ai in ai_services) and amount > 0.01:
            shadow_ai.append({
                'service': service,
                'amount': round(amount, 2),
                'flag': 'Unreviewed AI service detected'
            })

    shadow_ai.sort(key=lambda x: x['amount'], reverse=True)

    return shadow_ai


if __name__ == "__main__":
    print("\n=== Untagged Resources ===")
    untagged = get_untagged_resources()
    if untagged:
        for r in untagged:
            print(f"{r['type']} {r['id']}: missing {r['missing_tags']}")
    else:
        print("All resources properly tagged")

    print("\n=== Policy Violations ===")
    violations = get_policy_violations()
    if violations:
        for v in violations:
            print(f"{v['type']} {v['id']}: {v['violation']}")
    else:
        print("No violations found")

    print("\n=== Egress Anomalies ===")
    anomalies = get_egress_anomalies()
    if anomalies:
        for a in anomalies:
            print(f"{a['service']}: ${a['amount']} - {a['flag']}")
    else:
        print("No egress anomalies detected")

    print("\n=== Shadow AI Services ===")
    shadow = get_shadow_ai()
    if shadow:
        for s in shadow:
            print(f"{s['service']}: ${s['amount']} - {s['flag']}")
    else:
        print("No shadow AI services detected")


def get_security_cost_tradeoffs():
    findings = []

    try:
        # Check GuardDuty
        print("Checking GuardDuty status...")
        gd_client = boto3.client('guardduty', region_name=AWS_REGION)
        detectors = gd_client.list_detectors()

        if not detectors['DetectorIds']:
            findings.append({
                'service': 'GuardDuty',
                'status': 'DISABLED',
                'monthly_cost_to_enable': 2.00,
                'risk': 'No threat detection, malware, or unauthorized access alerts',
                'recommendation': 'Enable GuardDuty immediately'
            })
        else:
            detector_id = detectors['DetectorIds'][0]
            detector = gd_client.get_detector(DetectorId=detector_id)
            if detector['Status'] == 'DISABLED':
                findings.append({
                    'service': 'GuardDuty',
                    'status': 'DISABLED',
                    'monthly_cost_to_enable': 2.00,
                    'risk': 'No threat detection, malware, or unauthorized access alerts',
                    'recommendation': 'Re-enable GuardDuty immediately'
                })
            else:
                findings.append({
                    'service': 'GuardDuty',
                    'status': 'ENABLED',
                    'monthly_cost_to_enable': 0,
                    'risk': 'None',
                    'recommendation': 'No action needed'
                })
    except Exception as e:
        print(f"GuardDuty check error: {e}")

    try:
        # Check CloudTrail
        print("Checking CloudTrail status...")
        ct_client = boto3.client('cloudtrail', region_name=AWS_REGION)
        trails = ct_client.describe_trails()

        active_trails = [
            t for t in trails['trailList']
            if t.get('IsMultiRegionTrail') or t.get('HomeRegion') == AWS_REGION
        ]

        if not active_trails:
            findings.append({
                'service': 'CloudTrail',
                'status': 'DISABLED',
                'monthly_cost_to_enable': 2.00,
                'risk': 'No API activity logs, blind to unauthorized actions',
                'recommendation': 'Enable CloudTrail logging to S3 immediately'
            })
        else:
            trail_status = ct_client.get_trail_status(
                Name=active_trails[0]['TrailARN']
            )
            if not trail_status.get('IsLogging'):
                findings.append({
                    'service': 'CloudTrail',
                    'status': 'NOT LOGGING',
                    'monthly_cost_to_enable': 2.00,
                    'risk': 'Trail exists but logging is paused',
                    'recommendation': 'Resume CloudTrail logging immediately'
                })
            else:
                findings.append({
                    'service': 'CloudTrail',
                    'status': 'ENABLED',
                    'monthly_cost_to_enable': 0,
                    'risk': 'None',
                    'recommendation': 'No action needed'
                })
    except Exception as e:
        print(f"CloudTrail check error: {e}")

    try:
        # Check AWS Config
        print("Checking AWS Config status...")
        config_client = boto3.client('config', region_name=AWS_REGION)
        recorders = config_client.describe_configuration_recorders()

        if not recorders['ConfigurationRecorders']:
            findings.append({
                'service': 'AWS Config',
                'status': 'DISABLED',
                'monthly_cost_to_enable': 3.00,
                'risk': 'No compliance history or resource change tracking',
                'recommendation': 'Enable AWS Config for compliance auditing'
            })
        else:
            recorder_status = config_client.describe_configuration_recorder_status()
            is_recording = recorder_status['ConfigurationRecordersStatus'][0].get('recording', False)
            if not is_recording:
                findings.append({
                    'service': 'AWS Config',
                    'status': 'NOT RECORDING',
                    'monthly_cost_to_enable': 3.00,
                    'risk': 'Config exists but not recording changes',
                    'recommendation': 'Start AWS Config recording immediately'
                })
            else:
                findings.append({
                    'service': 'AWS Config',
                    'status': 'ENABLED',
                    'monthly_cost_to_enable': 0,
                    'risk': 'None',
                    'recommendation': 'No action needed'
                })
    except Exception as e:
        print(f"AWS Config check error: {e}")

    try:
        # Check Security Hub
        print("Checking Security Hub status...")
        sh_client = boto3.client('securityhub', region_name=AWS_REGION)
        sh_client.describe_hub()
        findings.append({
            'service': 'Security Hub',
            'status': 'ENABLED',
            'monthly_cost_to_enable': 0,
            'risk': 'None',
            'recommendation': 'No action needed'
        })
    except sh_client.exceptions.InvalidAccessException:
        findings.append({
            'service': 'Security Hub',
            'status': 'DISABLED',
            'monthly_cost_to_enable': 4.00,
            'risk': 'No centralized security findings or compliance checks',
            'recommendation': 'Enable Security Hub for unified security view'
        })
    except Exception as e:
        print(f"Security Hub check error: {e}")

    disabled = [f for f in findings if f['status'] != 'ENABLED']
    enabled = [f for f in findings if f['status'] == 'ENABLED']
    total_risk_cost = sum(f['monthly_cost_to_enable'] for f in disabled)

    return {
        'findings': findings,
        'disabled_services': disabled,
        'enabled_services': enabled,
        'total_monthly_cost_to_fix': round(total_risk_cost, 2)
    }