import json
import os
from datetime import datetime

PLAYBOOK_FILE = 'playbook_library.json'


def load_playbooks():
    if os.path.exists(PLAYBOOK_FILE):
        with open(PLAYBOOK_FILE, 'r') as f:
            return json.load(f)
    return []


def save_playbooks(playbooks):
    with open(PLAYBOOK_FILE, 'w') as f:
        json.dump(playbooks, f, indent=2)


def capture_recommendation(
        category, issue, recommendation,
        fix_command=None, estimated_savings=0,
        customer_id='default'):

    playbooks = load_playbooks()

    entry = {
        'id': f"pb_{len(playbooks) + 1:04d}",
        'timestamp': datetime.now().isoformat(),
        'customer_id': customer_id,
        'category': category,
        'issue': issue,
        'recommendation': recommendation,
        'fix_command': fix_command,
        'estimated_savings': estimated_savings,
        'status': 'recommended',
        'validated': False,
        'validation_timestamp': None,
        'times_used': 1
    }

    playbooks.append(entry)
    save_playbooks(playbooks)
    print(f"Playbook captured: {entry['id']} - {issue[:50]}")
    return entry['id']


def validate_playbook(playbook_id, outcome='success'):
    playbooks = load_playbooks()

    for p in playbooks:
        if p['id'] == playbook_id:
            p['status'] = 'validated'
            p['validated'] = True
            p['validation_timestamp'] = datetime.now().isoformat()
            p['outcome'] = outcome
            save_playbooks(playbooks)
            print(f"Playbook validated: {playbook_id}")
            return True

    return False


def search_playbooks(query, category=None, validated_only=True):
    playbooks = load_playbooks()

    results = []
    query_lower = query.lower()

    for p in playbooks:
        if validated_only and not p['validated']:
            continue

        if category and p['category'] != category:
            continue

        if (query_lower in p['issue'].lower() or
                query_lower in p['recommendation'].lower() or
                query_lower in p['category'].lower()):
            results.append(p)

    results.sort(key=lambda x: x['times_used'], reverse=True)
    return results


def increment_usage(playbook_id):
    playbooks = load_playbooks()
    for p in playbooks:
        if p['id'] == playbook_id:
            p['times_used'] += 1
            save_playbooks(playbooks)
            return True
    return False


def get_playbook_summary():
    playbooks = load_playbooks()

    if not playbooks:
        return {
            'total': 0,
            'validated': 0,
            'pending': 0,
            'categories': {},
            'top_playbooks': [],
            'total_savings_captured': 0
        }

    validated = [p for p in playbooks if p['validated']]
    pending = [p for p in playbooks if not p['validated']]

    categories = {}
    for p in playbooks:
        cat = p['category']
        if cat not in categories:
            categories[cat] = {'total': 0, 'validated': 0}
        categories[cat]['total'] += 1
        if p['validated']:
            categories[cat]['validated'] += 1

    top_playbooks = sorted(
        validated, key=lambda x: x['times_used'], reverse=True)[:5]

    total_savings = sum(
        p['estimated_savings'] for p in validated
        if p['estimated_savings'] > 0
    )

    return {
        'total': len(playbooks),
        'validated': len(validated),
        'pending': len(pending),
        'categories': categories,
        'top_playbooks': top_playbooks,
        'total_savings_captured': round(total_savings, 2)
    }


def auto_capture_from_beacon(feature, findings):
    captured_ids = []

    category_map = {
        'cost_analysis': 'cost_optimization',
        'compliance_check': 'compliance',
        'security_tradeoffs': 'security',
        'savings_recommendations': 'cost_optimization',
        'idle_resources': 'waste_reduction',
        'cost_rca': 'incident_response',
        'iac_generation': 'automation',
        'security_score': 'security'
    }

    category = category_map.get(feature, 'general')

    for finding in findings:
        if isinstance(finding, dict) and finding.get('recommendation'):
            pb_id = capture_recommendation(
                category=category,
                issue=finding.get('issue', finding.get('cause', 'Unknown')),
                recommendation=finding.get(
                    'recommendation', finding.get('fix', '')),
                fix_command=finding.get('fix_command'),
                estimated_savings=finding.get(
                    'monthly_cost', finding.get('estimated_savings', 0))
            )
            captured_ids.append(pb_id)

    return captured_ids


if __name__ == "__main__":
    print("\n=== Playbook Library Test ===")

    # Seed some demo playbooks
    id1 = capture_recommendation(
        category='waste_reduction',
        issue='2 snapshots older than 30 days detected',
        recommendation='Delete old snapshots using AWS CLI',
        fix_command='aws ec2 delete-snapshot --snapshot-id snap-xxx',
        estimated_savings=2.30
    )

    id2 = capture_recommendation(
        category='security',
        issue='GuardDuty not enabled',
        recommendation='Enable GuardDuty for threat detection',
        fix_command='aws guardduty create-detector --enable',
        estimated_savings=0
    )

    id3 = capture_recommendation(
        category='cost_optimization',
        issue='RDS running 24/7 in dev environment',
        recommendation='Implement RDS auto start/stop schedule',
        fix_command='terraform apply rds_auto_schedule.tf',
        estimated_savings=18.50
    )

    # Validate one
    validate_playbook(id1, outcome='success')
    validate_playbook(id3, outcome='success')

    # Get summary
    summary = get_playbook_summary()
    print(f"\nPlaybook Library Summary:")
    print(f"Total: {summary['total']}")
    print(f"Validated: {summary['validated']}")
    print(f"Pending: {summary['pending']}")
    print(f"Total savings captured: ${summary['total_savings_captured']}")

    print(f"\nCategories:")
    for cat, counts in summary['categories'].items():
        print(f"  {cat}: {counts['validated']}/{counts['total']} validated")

    # Search test
    print(f"\nSearch test - 'snapshot':")
    results = search_playbooks('snapshot', validated_only=False)
    for r in results:
        print(f"  [{r['id']}] {r['issue'][:50]} - validated: {r['validated']}")