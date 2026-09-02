import boto3
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_s3_cost_summary():
    ce = boto3.client('ce', region_name=AWS_REGION)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)

    try:
        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start.strftime('%Y-%m-%d'),
                'End': (end + timedelta(days=1)).strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Simple Storage Service']
                }
            },
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}]
        )

        results = response['ResultsByTime']
        total_cost = 0
        usage_breakdown = []

        for result in results:
            for group in result.get('Groups', []):
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                if cost > 0:
                    usage_breakdown.append({
                        'usage_type': group['Keys'][0],
                        'cost': round(cost, 4)
                    })
                    total_cost += cost

        usage_breakdown.sort(key=lambda x: x['cost'], reverse=True)

        return {
            'total_monthly_cost': round(total_cost, 4),
            'usage_breakdown': usage_breakdown[:10],
            'period': f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        }

    except Exception as e:
        return {
            'total_monthly_cost': 0,
            'usage_breakdown': [],
            'period': '',
            'error': str(e)
        }


def get_s3_buckets():
    s3 = boto3.client('s3', region_name=AWS_REGION)
    cw = boto3.client('cloudwatch', region_name=AWS_REGION)

    try:
        response = s3.list_buckets()
        buckets = response.get('Buckets', [])
        bucket_details = []

        for bucket in buckets:
            name = bucket['Name']
            created = bucket['CreationDate']

            try:
                location = s3.get_bucket_location(Bucket=name)
                region = location.get('LocationConstraint') or 'us-east-1'
            except Exception:
                region = 'unknown'

            # Get bucket size from CloudWatch
            try:
                end = datetime.now(timezone.utc)
                start = end - timedelta(days=2)
                size_response = cw.get_metric_statistics(
                    Namespace='AWS/S3',
                    MetricName='BucketSizeBytes',
                    Dimensions=[
                        {'Name': 'BucketName', 'Value': name},
                        {'Name': 'StorageType', 'Value': 'StandardStorage'}
                    ],
                    StartTime=start,
                    EndTime=end,
                    Period=86400,
                    Statistics=['Average']
                )
                datapoints = size_response.get('Datapoints', [])
                size_bytes = datapoints[-1]['Average'] if datapoints else 0
                size_gb = round(size_bytes / (1024**3), 4)
            except Exception:
                size_gb = 0

            # Get object count
            try:
                count_response = cw.get_metric_statistics(
                    Namespace='AWS/S3',
                    MetricName='NumberOfObjects',
                    Dimensions=[
                        {'Name': 'BucketName', 'Value': name},
                        {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                    ],
                    StartTime=start,
                    EndTime=end,
                    Period=86400,
                    Statistics=['Average']
                )
                count_points = count_response.get('Datapoints', [])
                object_count = int(count_points[-1]['Average']) if count_points else 0
            except Exception:
                object_count = 0

            # Estimate monthly cost ($0.023 per GB standard)
            estimated_cost = round(size_gb * 0.023, 4)

            bucket_details.append({
                'name': name,
                'region': region,
                'size_gb': size_gb,
                'object_count': object_count,
                'estimated_cost': estimated_cost,
                'created': created.strftime('%Y-%m-%d'),
                'console_link': f"https://s3.console.aws.amazon.com/s3/buckets/{name}"
            })

        bucket_details.sort(key=lambda x: x['estimated_cost'], reverse=True)
        return bucket_details

    except Exception as e:
        return []


def get_s3_savings_opportunities(buckets):
    opportunities = []

    for bucket in buckets:
        if bucket['size_gb'] > 10 and bucket['estimated_cost'] > 0.5:
            opportunities.append({
                'bucket': bucket['name'],
                'issue': 'Large bucket without lifecycle policy check',
                'potential_savings': round(bucket['estimated_cost'] * 0.4, 4),
                'action': 'Enable S3 Intelligent-Tiering or lifecycle rules',
                'console_link': bucket['console_link']
            })

        if bucket['object_count'] > 10000 and bucket['size_gb'] < 0.1:
            opportunities.append({
                'bucket': bucket['name'],
                'issue': 'Many small objects — high request costs',
                'potential_savings': round(bucket['object_count'] * 0.000005, 4),
                'action': 'Consider combining small objects or using S3 batch operations',
                'console_link': bucket['console_link']
            })

    return opportunities


def format_s3_for_slack(data):
    cost_summary = data.get('cost_summary', {})
    buckets = data.get('buckets', [])
    opportunities = data.get('opportunities', [])

    total_cost = cost_summary.get('total_monthly_cost', 0)
    total_size = sum(b['size_gb'] for b in buckets)

    lines = [
        '*OpsBeacon S3 Cost Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*Total S3 Cost (30 days):* ${total_cost}',
        f'*Total Buckets:* {len(buckets)}',
        f'*Total Storage:* {round(total_size, 2)} GB',
        '',
    ]

    if buckets:
        lines.append('*Top Buckets by Cost:*')
        for b in buckets[:5]:
            lines.append(
                f'  📦 `{b["name"]}` — {b["size_gb"]} GB · '
                f'${b["estimated_cost"]}/mo · {b["region"]}'
            )
        lines.append('')

    if cost_summary.get('usage_breakdown'):
        lines.append('*S3 Cost Breakdown:*')
        for u in cost_summary['usage_breakdown'][:5]:
            lines.append(f'  {u["usage_type"]}: ${u["cost"]}')
        lines.append('')

    if opportunities:
        lines.append(f'*💡 Savings Opportunities: {len(opportunities)}*')
        for opp in opportunities[:3]:
            lines.append(f'  → {opp["issue"]}')
            lines.append(f'    Bucket: `{opp["bucket"]}` · Save ~${opp["potential_savings"]}/mo')
            lines.append(f'    <{opp["console_link"]}|Open in S3 Console>')
        lines.append('')
    else:
        lines.append('*Savings Opportunities:* None identified')
        lines.append('')

    lines.append(f'<https://s3.console.aws.amazon.com/s3/home|View all buckets in S3 Console>')
    lines.append('_Powered by OpsBeacon S3 Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== S3 Cost Summary ===')
    cost = get_s3_cost_summary()
    print(f"Total cost: ${cost['total_monthly_cost']}")
    print(f"Usage types: {len(cost['usage_breakdown'])}")

    print('\n=== S3 Buckets ===')
    buckets = get_s3_buckets()
    print(f"Total buckets: {len(buckets)}")
    for b in buckets[:5]:
        print(f"  {b['name']}: {b['size_gb']} GB ${b['estimated_cost']}/mo")

    print('\n=== Savings Opportunities ===')
    opps = get_s3_savings_opportunities(buckets)
    print(f"Opportunities: {len(opps)}")
    for o in opps:
        print(f"  {o['bucket']}: {o['issue']}")