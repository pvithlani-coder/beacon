import boto3
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from aws_regions import get_regions

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_ec2_metrics(instance_id, region, hours=24):
    cw = boto3.client('cloudwatch', region_name=region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    metrics = {}

    metric_queries = [
        ('CPUUtilization', 'AWS/EC2', 'Percent'),
        ('NetworkIn', 'AWS/EC2', 'Bytes'),
        ('NetworkOut', 'AWS/EC2', 'Bytes'),
        ('DiskReadOps', 'AWS/EC2', 'Count'),
        ('DiskWriteOps', 'AWS/EC2', 'Count'),
    ]

    for metric_name, namespace, unit in metric_queries:
        try:
            response = cw.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            datapoints = sorted(
                response['Datapoints'],
                key=lambda x: x['Timestamp']
            )
            if datapoints:
                metrics[metric_name] = {
                    'average': round(sum(d['Average'] for d in datapoints) / len(datapoints), 2),
                    'maximum': round(max(d['Maximum'] for d in datapoints), 2),
                    'unit': unit,
                    'datapoints': len(datapoints)
                }
            else:
                metrics[metric_name] = {
                    'average': 0, 'maximum': 0,
                    'unit': unit, 'datapoints': 0
                }
        except Exception as e:
            metrics[metric_name] = {
                'average': 0, 'maximum': 0,
                'unit': unit, 'datapoints': 0
            }

    return metrics


def get_rds_metrics(db_instance_id, region, hours=24):
    cw = boto3.client('cloudwatch', region_name=region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    metrics = {}
    metric_queries = [
        'CPUUtilization',
        'DatabaseConnections',
        'FreeStorageSpace',
        'ReadIOPS',
        'WriteIOPS',
    ]

    for metric_name in metric_queries:
        try:
            response = cw.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName=metric_name,
                Dimensions=[{'Name': 'DBInstanceIdentifier', 'Value': db_instance_id}],
                StartTime=start,
                EndTime=end,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            datapoints = response['Datapoints']
            if datapoints:
                metrics[metric_name] = {
                    'average': round(sum(d['Average'] for d in datapoints) / len(datapoints), 2),
                    'maximum': round(max(d['Maximum'] for d in datapoints), 2),
                    'datapoints': len(datapoints)
                }
            else:
                metrics[metric_name] = {
                    'average': 0, 'maximum': 0, 'datapoints': 0
                }
        except Exception:
            metrics[metric_name] = {
                'average': 0, 'maximum': 0, 'datapoints': 0
            }

    return metrics


def get_cost_anomaly_metrics(hours=168):
    cw = boto3.client('cloudwatch', region_name=AWS_REGION)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    try:
        response = cw.describe_alarms(
            AlarmTypes=['MetricAlarm'],
            StateValue='ALARM'
        )
        alarms = response.get('MetricAlarms', [])
        return {
            'active_alarms': len(alarms),
            'alarm_details': [
                {
                    'name': a['AlarmName'],
                    'metric': a.get('MetricName', 'unknown'),
                    'state': a['StateValue'],
                    'reason': a.get('StateReason', '')[:100]
                }
                for a in alarms[:5]
            ]
        }
    except Exception as e:
        return {'active_alarms': 0, 'alarm_details': []}


def get_all_ec2_metrics():
    regions = get_regions()
    all_metrics = []

    for region in regions:
        try:
            ec2 = boto3.client('ec2', region_name=region)
            instances = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )
            for reservation in instances['Reservations']:
                for inst in reservation['Instances']:
                    instance_id = inst['InstanceId']
                    instance_type = inst['InstanceType']
                    tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                    name = tags.get('Name', instance_id)

                    metrics = get_ec2_metrics(instance_id, region)

                    cpu_avg = metrics.get('CPUUtilization', {}).get('average', 0)
                    is_idle = cpu_avg < 5

                    all_metrics.append({
                        'instance_id': instance_id,
                        'name': name,
                        'instance_type': instance_type,
                        'region': region,
                        'cpu_avg': cpu_avg,
                        'cpu_max': metrics.get('CPUUtilization', {}).get('maximum', 0),
                        'network_in': metrics.get('NetworkIn', {}).get('average', 0),
                        'network_out': metrics.get('NetworkOut', {}).get('average', 0),
                        'is_idle': is_idle,
                        'idle_risk': 'HIGH' if cpu_avg < 1 else 'MEDIUM' if cpu_avg < 5 else 'LOW'
                    })
        except Exception as e:
            continue

    return all_metrics


def get_cloudwatch_alarms():
    try:
        cw = boto3.client('cloudwatch', region_name=AWS_REGION)
        response = cw.describe_alarms(AlarmTypes=['MetricAlarm'])
        alarms = response.get('MetricAlarms', [])

        return {
            'total': len(alarms),
            'in_alarm': len([a for a in alarms if a['StateValue'] == 'ALARM']),
            'ok': len([a for a in alarms if a['StateValue'] == 'OK']),
            'insufficient_data': len([a for a in alarms if a['StateValue'] == 'INSUFFICIENT_DATA']),
            'alarms': [
                {
                    'name': a['AlarmName'],
                    'metric': a.get('MetricName', 'unknown'),
                    'state': a['StateValue'],
                    'namespace': a.get('Namespace', 'unknown')
                }
                for a in alarms[:10]
            ]
        }
    except Exception as e:
        return {'total': 0, 'in_alarm': 0, 'ok': 0, 'insufficient_data': 0, 'alarms': []}


def format_cloudwatch_for_slack(data):
    ec2_metrics = data.get('ec2_metrics', [])
    alarms = data.get('alarms', {})

    idle_instances = [m for m in ec2_metrics if m['is_idle']]

    lines = [
        '*OpsBeacon CloudWatch Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*EC2 Instances Monitored:* {len(ec2_metrics)}',
        f'*Idle Instances (CPU < 5%):* {len(idle_instances)}',
        '',
    ]

    if ec2_metrics:
        lines.append('*Instance Health:*')
        for m in ec2_metrics[:5]:
            idle_emoji = '🔴' if m['idle_risk'] == 'HIGH' else '🟡' if m['idle_risk'] == 'MEDIUM' else '🟢'
            lines.append(
                f'  {idle_emoji} `{m["instance_id"]}` ({m["instance_type"]}) '
                f'{m["region"]} — CPU avg: {m["cpu_avg"]}% max: {m["cpu_max"]}%'
            )
        lines.append('')

    if alarms.get('total', 0) > 0:
        lines.append(f'*CloudWatch Alarms:* {alarms["total"]} total')
        lines.append(f'  🔴 In alarm: {alarms["in_alarm"]}')
        lines.append(f'  🟢 OK: {alarms["ok"]}')
        lines.append(f'  ⚪ Insufficient data: {alarms["insufficient_data"]}')
        lines.append('')

        if alarms.get('in_alarm', 0) > 0:
            lines.append('*Active Alarms:*')
            for alarm in alarms['alarms']:
                if alarm['state'] == 'ALARM':
                    lines.append(f'  ⚠️ {alarm["name"]} — {alarm["metric"]}')
    else:
        lines.append('*CloudWatch Alarms:* No alarms configured')
        lines.append(f'  <https://console.aws.amazon.com/cloudwatch/home?region={AWS_REGION}#alarmsV2:|Set up alarms in CloudWatch>')

    lines.append('')
    lines.append('_Powered by OpsBeacon CloudWatch Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== CloudWatch Alarms ===')
    alarms = get_cloudwatch_alarms()
    print(f"Total alarms: {alarms['total']}")
    print(f"In alarm: {alarms['in_alarm']}")
    print(f"OK: {alarms['ok']}")

    print('\n=== EC2 Metrics ===')
    metrics = get_all_ec2_metrics()