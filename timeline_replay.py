import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import boto3

load_dotenv()

AWS_REGION = 'us-east-2'
TIMELINE_FILE = 'timeline_events.json'


def load_timeline():
    if os.path.exists(TIMELINE_FILE):
        with open(TIMELINE_FILE, 'r') as f:
            return json.load(f)
    return []


def save_timeline(events):
    with open(TIMELINE_FILE, 'w') as f:
        json.dump(events, f, indent=2)


def log_event(event_type, title, description,
              cost_impact=0, source='beacon',
              severity='info', metadata=None):
    events = load_timeline()

    entry = {
        'id': f"EVT-{len(events) + 1:04d}",
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'title': title,
        'description': description,
        'cost_impact': round(cost_impact, 2),
        'source': source,
        'severity': severity,
        'metadata': metadata or {}
    }

    events.append(entry)
    save_timeline(events)
    return entry


def get_aws_cost_timeline(days=30):
    client = boto3.client('ce', region_name=AWS_REGION)
    today = datetime.today()
    start = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')

    events = []

    try:
        response = client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        service_history = {}
        for day in response['ResultsByTime']:
            date = day['TimePeriod']['Start']
            for group in day['Groups']:
                service = group['Keys'][0]
                amount = float(
                    group['Metrics']['UnblendedCost']['Amount'])

                if service not in service_history:
                    service_history[service] = []
                service_history[service].append({
                    'date': date,
                    'amount': round(amount, 4)
                })

        for service, history in service_history.items():
            if len(history) < 3:
                continue

            amounts = [h['amount'] for h in history]
            avg = sum(amounts[:-1]) / len(amounts[:-1])
            latest = amounts[-1]

            if avg > 0.01 and latest > avg * 1.25:
                pct = round((latest - avg) / avg * 100, 1)
                events.append({
                    'id': f"COST-{len(events)+1:04d}",
                    'timestamp': history[-1]['date'] + 'T00:00:00',
                    'event_type': 'cost_spike',
                    'title': f"{service} cost spike",
                    'description': f"{service} jumped {pct}% above average",
                    'cost_impact': round(latest - avg, 4),
                    'source': 'aws_cost_explorer',
                    'severity': 'high' if pct > 50 else 'medium',
                    'metadata': {
                        'service': service,
                        'latest': latest,
                        'average': round(avg, 4),
                        'increase_pct': pct
                    }
                })

            elif avg > 0.01 and latest < avg * 0.75:
                pct = round((avg - latest) / avg * 100, 1)
                events.append({
                    'id': f"COST-{len(events)+1:04d}",
                    'timestamp': history[-1]['date'] + 'T00:00:00',
                    'event_type': 'cost_drop',
                    'title': f"{service} cost reduction",
                    'description': f"{service} dropped {pct}% below average",
                    'cost_impact': round(latest - avg, 4),
                    'source': 'aws_cost_explorer',
                    'severity': 'info',
                    'metadata': {
                        'service': service,
                        'latest': latest,
                        'average': round(avg, 4),
                        'decrease_pct': pct
                    }
                })

    except Exception as e:
        print(f"Cost timeline error: {e}")

    return events


def get_full_timeline(days=30):
    beacon_events = load_timeline()
    aws_events = get_aws_cost_timeline(days)

    all_events = beacon_events + aws_events

    cutoff = datetime.now() - timedelta(days=days)
    filtered = [
        e for e in all_events
        if datetime.fromisoformat(
            e['timestamp'].replace('Z', '')) >= cutoff
    ]

    filtered.sort(key=lambda x: x['timestamp'])

    return filtered


def format_timeline_for_slack(events, title="Timeline Replay"):
    if not events:
        return f"*{title}*\n\nNo events recorded in this period."

    severity_icon = {
        'critical': 'RED',
        'high': 'ORANGE',
        'medium': 'YELLOW',
        'info': 'GREEN',
        'success': 'GREEN'
    }

    type_icon = {
        'cost_spike': '📈',
        'cost_drop': '📉',
        'action_completed': '✅',
        'action_created': '📋',
        'security_finding': '🛡️',
        'incident': '🚨',
        'recommendation': '💡',
        'savings_realized': '💰',
        'compliance': '✓',
        'general': '📌'
    }

    lines = [f"*{title}* ({len(events)} events)\n"]

    current_date = None
    for e in events:
        event_date = e['timestamp'][:10]

        if event_date != current_date:
            current_date = event_date
            try:
                dt = datetime.strptime(event_date, '%Y-%m-%d')
                lines.append(
                    f"\n*{dt.strftime('%B %d, %Y')}*\n" + "─" * 30)
            except Exception:
                lines.append(f"\n*{event_date}*\n" + "─" * 30)

        icon = type_icon.get(e['event_type'], '📌')
        cost_text = ""
        if e.get('cost_impact') and e['cost_impact'] != 0:
            sign = "+" if e['cost_impact'] > 0 else ""
            cost_text = f" | {sign}${abs(e['cost_impact']):.2f}"

        lines.append(
            f"{icon} *{e['title']}*{cost_text}\n"
            f"   {e['description']}\n"
        )

    return "\n".join(lines)


def seed_demo_timeline():
    today = datetime.now()

    demo_events = [
        {
            'days_ago': 28,
            'type': 'action_created',
            'title': 'Beacon flagged idle snapshots',
            'desc': '2 snapshots older than 30 days detected costing $2.30/mo',
            'impact': -2.30,
            'severity': 'medium'
        },
        {
            'days_ago': 21,
            'type': 'security_finding',
            'title': 'Security Cost Score: 70/100',
            'desc': '4 security services disabled. GuardDuty and CloudTrail not configured.',
            'impact': -15.30,
            'severity': 'high'
        },
        {
            'days_ago': 14,
            'type': 'recommendation',
            'title': 'RDS reserved instance opportunity identified',
            'desc': 'Switch to 1-year reserved instance saves $9.24/mo (35% reduction)',
            'impact': 9.24,
            'severity': 'info'
        },
        {
            'days_ago': 10,
            'type': 'action_completed',
            'title': 'Snapshot cleanup completed',
            'desc': 'Deleted 2 old snapshots. Savings realized: $2.30/mo',
            'impact': 2.30,
            'severity': 'success'
        },
        {
            'days_ago': 7,
            'type': 'savings_realized',
            'title': 'Weekly savings summary',
            'desc': 'Total savings realized this week: $2.30/mo. $9.24/mo pending action.',
            'impact': 2.30,
            'severity': 'info'
        },
        {
            'days_ago': 3,
            'type': 'incident',
            'title': 'PagerDuty: High CPU on prod database',
            'desc': 'RDS CPU spike detected. Root cause: missing index on query. Resolved in 45 mins.',
            'impact': -0.50,
            'severity': 'high'
        },
        {
            'days_ago': 1,
            'type': 'compliance',
            'title': 'Compliance check: All clear',
            'desc': 'No untagged resources, policy violations, or egress anomalies detected.',
            'impact': 0,
            'severity': 'info'
        }
    ]

    for e in demo_events:
        timestamp = (today - timedelta(days=e['days_ago'])).isoformat()
        events = load_timeline()
        events.append({
            'id': f"EVT-{len(events)+1:04d}",
            'timestamp': timestamp,
            'event_type': e['type'],
            'title': e['title'],
            'description': e['desc'],
            'cost_impact': e['impact'],
            'source': 'beacon',
            'severity': e['severity'],
            'metadata': {}
        })
        save_timeline(events)

    print(f"Seeded {len(demo_events)} demo timeline events")


if __name__ == "__main__":
    print("\n=== Timeline Replay Test ===")

    seed_demo_timeline()

    events = get_full_timeline(days=30)
    print(f"\nTotal events: {len(events)}")
    print(f"\nFormatted output:")
    print(format_timeline_for_slack(events))