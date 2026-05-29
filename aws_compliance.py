import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


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
    client = boto3.client('ce', region_name='us-east-1')

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
    client = boto3.client('ce', region_name='us-east-1')

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