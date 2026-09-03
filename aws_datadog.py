import os
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

DATADOG_API_KEY = os.environ.get('DATADOG_API_KEY', '')
DATADOG_APP_KEY = os.environ.get('DATADOG_APP_KEY', '')
DATADOG_SITE = os.environ.get('DATADOG_SITE', 'datadoghq.com')

BASE_URL = f'https://api.{DATADOG_SITE}'

HEADERS = {
    'DD-API-KEY': DATADOG_API_KEY,
    'DD-APPLICATION-KEY': DATADOG_APP_KEY,
    'Content-Type': 'application/json'
}


def check_datadog_connection():
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/validate',
            headers=HEADERS,
            timeout=10
        )
        return response.status_code == 200
    except Exception:
        return False


def get_datadog_hosts():
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/hosts',
            headers=HEADERS,
            params={'count': 100, 'start': 0},
            timeout=10
        )
        if response.status_code != 200:
            return []

        data = response.json()
        hosts = []

        for host in data.get('host_list', []):
            name = host.get('name', 'unknown')
            aliases = host.get('aliases', [])
            tags = host.get('tags_by_source', {})
            sources = host.get('sources', [])
            last_reported = host.get('last_reported_time', 0)
            is_muted = host.get('is_muted', False)

            # Estimate cost - Datadog charges per host
            # Infrastructure: ~$15-23/host/month
            estimated_cost = 18.0

            hosts.append({
                'name': name,
                'aliases': aliases[:3],
                'sources': sources,
                'tags': tags,
                'last_reported': datetime.fromtimestamp(last_reported).strftime('%Y-%m-%d %H:%M') if last_reported else 'unknown',
                'is_muted': is_muted,
                'estimated_cost': estimated_cost,
                'is_active': last_reported > (datetime.now().timestamp() - 3600)
            })

        return hosts

    except Exception as e:
        return []


def get_datadog_monitors():
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/monitor',
            headers=HEADERS,
            params={'page': 0, 'page_size': 100},
            timeout=10
        )
        if response.status_code != 200:
            return []

        monitors = []
        for m in response.json():
            state = m.get('overall_state', 'unknown')
            monitors.append({
                'id': m.get('id'),
                'name': m.get('name', 'unknown'),
                'type': m.get('type', 'unknown'),
                'state': state,
                'is_alerting': state in ['Alert', 'Warn'],
                'message': m.get('message', '')[:100],
                'tags': m.get('tags', []),
                'created': m.get('created', '')[:10],
                'modified': m.get('modified', '')[:10],
            })

        return monitors

    except Exception as e:
        return []


def get_datadog_usage():
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)

        response = requests.get(
            f'{BASE_URL}/api/v1/usage/hosts',
            headers=HEADERS,
            params={
                'start_hr': start.strftime('%Y-%m-%dT%H'),
                'end_hr': end.strftime('%Y-%m-%dT%H')
            },
            timeout=10
        )

        if response.status_code != 200:
            return {}

        data = response.json()
        usage = data.get('usage', [])

        max_hosts = 0
        max_containers = 0

        for u in usage:
            hosts = u.get('host_count', 0) or 0
            containers = u.get('container_count', 0) or 0
            max_hosts = max(max_hosts, hosts)
            max_containers = max(max_containers, containers)

        estimated_infra_cost = round(max_hosts * 18.0, 2)
        estimated_container_cost = round(max_containers * 0.002 * 730, 2)

        return {
            'max_hosts': max_hosts,
            'max_containers': max_containers,
            'estimated_infra_cost': estimated_infra_cost,
            'estimated_container_cost': estimated_container_cost,
            'estimated_total': round(estimated_infra_cost + estimated_container_cost, 2)
        }

    except Exception as e:
        return {}


def get_datadog_logs_usage():
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=30)

        response = requests.get(
            f'{BASE_URL}/api/v1/usage/logs',
            headers=HEADERS,
            params={
                'start_hr': start.strftime('%Y-%m-%dT%H'),
                'end_hr': end.strftime('%Y-%m-%dT%H')
            },
            timeout=10
        )

        if response.status_code != 200:
            return {}

        data = response.json()
        usage = data.get('usage', [])

        total_ingested = sum(u.get('ingested_events_bytes', 0) or 0 for u in usage)
        total_indexed = sum(u.get('indexed_events_count', 0) or 0 for u in usage)

        ingested_gb = round(total_ingested / (1024**3), 4)
        estimated_cost = round(ingested_gb * 0.10, 2)

        return {
            'ingested_gb': ingested_gb,
            'indexed_events': total_indexed,
            'estimated_cost': estimated_cost
        }

    except Exception as e:
        return {}


def get_datadog_dashboards():
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/dashboard',
            headers=HEADERS,
            timeout=10
        )
        if response.status_code != 200:
            return []

        dashboards = []
        for d in response.json().get('dashboards', []):
            dashboards.append({
                'id': d.get('id'),
                'title': d.get('title', 'unknown'),
                'type': d.get('layout_type', 'unknown'),
                'author': d.get('author_handle', 'unknown'),
                'modified': d.get('modified_at', '')[:10],
                'url': f"https://app.datadoghq.com/dashboard/{d.get('id')}"
            })

        return dashboards

    except Exception as e:
        return []


def get_datadog_synthetics():
    try:
        response = requests.get(
            f'{BASE_URL}/api/v1/synthetics/tests',
            headers=HEADERS,
            timeout=10
        )
        if response.status_code != 200:
            return []

        tests = []
        for t in response.json().get('tests', []):
            tests.append({
                'name': t.get('name', 'unknown'),
                'type': t.get('type', 'unknown'),
                'status': t.get('status', 'unknown'),
                'locations': t.get('locations', [])[:3]
            })

        return tests

    except Exception as e:
        return []


def format_datadog_for_slack(data):
    hosts = data.get('hosts', [])
    monitors = data.get('monitors', [])
    usage = data.get('usage', {})
    logs = data.get('logs', {})
    dashboards = data.get('dashboards', [])

    connected = data.get('connected', False)

    if not connected:
        return (
            '*OpsBeacon Datadog Intelligence*\n'
            '━━━━━━━━━━━━━━━━━━━━\n\n'
            '❌ Could not connect to Datadog API.\n'
            'Check your API key and App key in the environment variables.'
        )

    alerting_monitors = [m for m in monitors if m['is_alerting']]
    active_hosts = [h for h in hosts if h['is_active']]

    lines = [
        '*OpsBeacon Datadog Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*Infrastructure:* {len(hosts)} hosts · {len(active_hosts)} active',
        f'*Monitors:* {len(monitors)} total · {len(alerting_monitors)} alerting',
        f'*Dashboards:* {len(dashboards)}',
        '',
    ]

    if usage:
        lines.append('*Estimated Datadog Cost (30 days):*')
        lines.append(f'  Infrastructure: ${usage.get("estimated_infra_cost", 0)}/mo')
        if usage.get('estimated_container_cost', 0) > 0:
            lines.append(f'  Containers: ${usage.get("estimated_container_cost", 0)}/mo')
        if logs.get('estimated_cost', 0) > 0:
            lines.append(f'  Logs: ${logs.get("estimated_cost", 0)}/mo ({logs.get("ingested_gb", 0)} GB ingested)')
        lines.append(f'  *Total estimate: ${usage.get("estimated_total", 0)}/mo*')
        lines.append('')

    if alerting_monitors:
        lines.append(f'*🔴 Active Alerts: {len(alerting_monitors)}*')
        for m in alerting_monitors[:5]:
            lines.append(f'  ⚠️ {m["name"]} — {m["state"]}')
        lines.append('')

    if hosts:
        lines.append('*Infrastructure Hosts:*')
        for h in hosts[:5]:
            status = '🟢' if h['is_active'] else '⚪'
            lines.append(f'  {status} `{h["name"]}` — last seen {h["last_reported"]}')
        if len(hosts) > 5:
            lines.append(f'  ... and {len(hosts) - 5} more hosts')
        lines.append('')

    if dashboards:
        lines.append(f'*Dashboards:* {len(dashboards)} total')
        lines.append('  _"You don\'t need another dashboard." — OpsBeacon_')
        lines.append('')

    lines.append('<https://app.datadoghq.com|Open Datadog Console>')
    lines.append('_Powered by OpsBeacon Datadog Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== Datadog Connection ===')
    connected = check_datadog_connection()
    print(f"Connected: {connected}")

    if connected:
        print('\n=== Datadog Hosts ===')
        hosts = get_datadog_hosts()
        print(f"Total hosts: {len(hosts)}")
        for h in hosts[:5]:
            print(f"  {h['name']} active: {h['is_active']}")

        print('\n=== Datadog Monitors ===')
        monitors = get_datadog_monitors()
        print(f"Total monitors: {len(monitors)}")
        alerting = [m for m in monitors if m['is_alerting']]
        print(f"Alerting: {len(alerting)}")

        print('\n=== Datadog Usage ===')
        usage = get_datadog_usage()
        print(f"Max hosts: {usage.get('max_hosts', 0)}")
        print(f"Estimated cost: ${usage.get('estimated_total', 0)}/mo")

        print('\n=== Datadog Dashboards ===')
        dashboards = get_datadog_dashboards()
        print(f"Total dashboards: {len(dashboards)}")
        for d in dashboards[:3]:
            print(f"  {d['title']}")
    else:
        print("Could not connect - check API keys")
