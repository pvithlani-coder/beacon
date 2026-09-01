import boto3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aws_regions import get_regions

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_cloudtrail_status():
    regions = get_regions()
    results = {
        'enabled_regions': [],
        'disabled_regions': [],
        'total_regions': len(regions),
        'trails': [],
        'multi_region_trails': [],
        'is_logging': False,
        'monthly_cost_estimate': 0
    }

    for region in regions:
        try:
            ct = boto3.client('cloudtrail', region_name=region)
            trails = ct.describe_trails(includeShadowTrails=False)

            if not trails['trailList']:
                results['disabled_regions'].append(region)
                continue

            for trail in trails['trailList']:
                status = ct.get_trail_status(Name=trail['TrailARN'])
                trail_info = {
                    'name': trail['TrailARN'].split('/')[-1],
                    'region': region,
                    'is_logging': status.get('IsLogging', False),
                    'multi_region': trail.get('IsMultiRegionTrail', False),
                    's3_bucket': trail.get('S3BucketName', 'N/A'),
                    'log_file_validation': trail.get('LogFileValidationEnabled', False),
                    'include_global': trail.get('IncludeGlobalServiceEvents', False),
                }
                results['trails'].append(trail_info)

                if trail.get('IsMultiRegionTrail'):
                    results['multi_region_trails'].append(trail_info)

                if status.get('IsLogging'):
                    results['is_logging'] = True
                    results['enabled_regions'].append(region)

        except Exception as e:
            results['disabled_regions'].append(region)

    results['coverage_pct'] = round(
        len(results['enabled_regions']) / results['total_regions'] * 100
    ) if results['total_regions'] > 0 else 0

    # Estimate cost: $2/100k events, roughly $2-5/mo for small accounts
    results['monthly_cost_estimate'] = round(
        len(results['enabled_regions']) * 1.5, 2
    )

    return results


def get_cloudtrail_events(hours=24, event_names=None):
    try:
        ct = boto3.client('cloudtrail', region_name=AWS_REGION)
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)

        kwargs = {
            'StartTime': start,
            'EndTime': end,
            'MaxResults': 50
        }

        if event_names:
            kwargs['LookupAttributes'] = [
                {'AttributeKey': 'EventName', 'AttributeValue': name}
                for name in event_names[:1]
            ]

        response = ct.lookup_events(**kwargs)
        events = []

        for event in response.get('Events', []):
            events.append({
                'event_name': event.get('EventName'),
                'event_time': event.get('EventTime'),
                'username': event.get('Username', 'unknown'),
                'source_ip': event.get('CloudTrailEvent', '{}'),
                'resources': [r.get('ResourceName') for r in event.get('Resources', [])]
            })

        return events

    except Exception as e:
        return []


def get_suspicious_events(hours=24):
    suspicious_event_names = [
        'DeleteTrail', 'StopLogging', 'DeleteBucket',
        'PutBucketPolicy', 'CreateUser', 'AttachUserPolicy',
        'CreateAccessKey', 'DeleteSecurityGroup',
        'AuthorizeSecurityGroupIngress', 'ModifyInstanceAttribute'
    ]

    try:
        ct = boto3.client('cloudtrail', region_name=AWS_REGION)
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)

        suspicious = []
        for event_name in suspicious_event_names[:5]:
            try:
                response = ct.lookup_events(
                    StartTime=start,
                    EndTime=end,
                    MaxResults=10,
                    LookupAttributes=[
                        {'AttributeKey': 'EventName', 'AttributeValue': event_name}
                    ]
                )
                for event in response.get('Events', []):
                    suspicious.append({
                        'event_name': event.get('EventName'),
                        'event_time': event.get('EventTime').strftime('%Y-%m-%d %H:%M UTC') if event.get('EventTime') else 'unknown',
                        'username': event.get('Username', 'unknown'),
                        'risk': 'HIGH' if event_name in ['DeleteTrail', 'StopLogging', 'CreateAccessKey'] else 'MEDIUM'
                    })
            except Exception:
                continue

        return suspicious

    except Exception as e:
        return []


def get_api_activity_summary(hours=24):
    try:
        ct = boto3.client('cloudtrail', region_name=AWS_REGION)
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)

        response = ct.lookup_events(
            StartTime=start,
            EndTime=end,
            MaxResults=50
        )

        events = response.get('Events', [])
        services = {}
        users = {}

        for event in events:
            source = event.get('EventSource', 'unknown').replace('.amazonaws.com', '')
            services[source] = services.get(source, 0) + 1

            user = event.get('Username', 'unknown')
            users[user] = users.get(user, 0) + 1

        return {
            'total_events': len(events),
            'top_services': sorted(services.items(), key=lambda x: x[1], reverse=True)[:5],
            'top_users': sorted(users.items(), key=lambda x: x[1], reverse=True)[:5],
            'hours': hours
        }

    except Exception as e:
        return {'total_events': 0, 'top_services': [], 'top_users': [], 'hours': hours}


def format_cloudtrail_for_slack(data):
    status = data['status']
    events = data.get('activity', {})
    suspicious = data.get('suspicious', [])

    if status['is_logging']:
        status_emoji = '✅'
        status_text = f"Active in {len(status['enabled_regions'])} region(s)"
    else:
        status_emoji = '❌'
        status_text = 'Not configured'

    lines = [
        '*OpsBeacon CloudTrail Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*Status:* {status_emoji} {status_text}',
        f'*Coverage:* {status["coverage_pct"]}% of regions',
        f'*Multi-region trails:* {len(status["multi_region_trails"])}',
        '',
    ]

    if events.get('total_events', 0) > 0:
        lines.append(f'*API Activity (last 24h):* {events["total_events"]} events')
        if events.get('top_services'):
            lines.append('*Top services:*')
            for svc, count in events['top_services'][:3]:
                lines.append(f'  {svc}: {count} calls')
        lines.append('')

    if suspicious:
        lines.append(f'*⚠️ Suspicious Events Detected: {len(suspicious)}*')
        for ev in suspicious[:3]:
            lines.append(f'  🔵 {ev["event_name"]} by {ev["username"]} at {ev["event_time"]}')
        lines.append('')
    else:
        lines.append('*Suspicious Events:* None detected in last 24h ✅')
        lines.append('')

    if not status['is_logging']:
        lines.append('*Action Required:*')
        lines.append('  CloudTrail is not enabled. This is a critical security gap.')
        lines.append(f'  <https://console.aws.amazon.com/cloudtrail/home?region={AWS_REGION}#/dashboard|Enable CloudTrail in AWS Console>')
        lines.append('  Enabling CloudTrail will raise your Security Trade-off Score by ~30 points.')

    lines.append('_Powered by OpsBeacon CloudTrail Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== CloudTrail Status ===')
    status = get_cloudtrail_status()
    print(f"Enabled regions: {status['enabled_regions']}")
    print(f"Disabled regions: {status['disabled_regions']}")
    print(f"Coverage: {status['coverage_pct']}%")
    print(f"Trails: {len(status['trails'])}")

    print('\n=== API Activity (last 24h) ===')
    activity = get_api_activity_summary(hours=24)
    print(f"Total events: {activity['total_events']}")
    for svc, count in activity['top_services']:
        print(f"  {svc}: {count}")

    print('\n=== Suspicious Events ===')
    suspicious = get_suspicious_events()
    if suspicious:
        for ev in suspicious:
            print(f"  [{ev['risk']}] {ev['event_name']} by {ev['username']}")
    else:
        print("  None detected")