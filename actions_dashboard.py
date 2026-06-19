import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

ACTIONS_FILE = 'open_actions.json'


def load_actions():
    if os.path.exists(ACTIONS_FILE):
        with open(ACTIONS_FILE, 'r') as f:
            return json.load(f)
    return []


def save_actions(actions):
    with open(ACTIONS_FILE, 'w') as f:
        json.dump(actions, f, indent=2)


def create_action(
        title, description, category,
        estimated_savings=0, due_days=7,
        owner=None, source_feature=None,
        priority='medium'):

    actions = load_actions()

    action_id = f"ACT-{len(actions) + 1:04d}"
    due_date = (datetime.now() + timedelta(days=due_days)).strftime('%Y-%m-%d')

    action = {
        'id': action_id,
        'title': title,
        'description': description,
        'category': category,
        'estimated_savings': round(estimated_savings, 2),
        'annual_savings': round(estimated_savings * 12, 2),
        'due_date': due_date,
        'due_days': due_days,
        'owner': owner,
        'source_feature': source_feature,
        'priority': priority,
        'status': 'open',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
        'completed_at': None,
        'days_open': 0,
        'notes': []
    }

    actions.append(action)
    save_actions(actions)
    print(f"Action created: {action_id} - {title}")
    return action


def update_action_status(action_id, status, note=None):
    actions = load_actions()

    for action in actions:
        if action['id'] == action_id:
            action['status'] = status
            action['updated_at'] = datetime.now().isoformat()

            if status == 'completed':
                action['completed_at'] = datetime.now().isoformat()

            if note:
                action['notes'].append({
                    'timestamp': datetime.now().isoformat(),
                    'note': note
                })

            save_actions(actions)
            print(f"Action {action_id} updated to {status}")
            return action

    return None


def assign_action(action_id, owner):
    actions = load_actions()

    for action in actions:
        if action['id'] == action_id:
            action['owner'] = owner
            action['updated_at'] = datetime.now().isoformat()
            save_actions(actions)
            return action

    return None


def get_open_actions(category=None, priority=None):
    actions = load_actions()
    today = datetime.now()

    open_actions = []
    for action in actions:
        if action['status'] not in ['open', 'in_progress']:
            continue
        if category and action['category'] != category:
            continue
        if priority and action['priority'] != priority:
            continue

        created = datetime.fromisoformat(action['created_at'])
        action['days_open'] = (today - created).days

        due = datetime.strptime(action['due_date'], '%Y-%m-%d')
        action['days_until_due'] = (due - today).days
        action['is_overdue'] = action['days_until_due'] < 0

        if action['days_open'] > 14:
            action['aging_alert'] = True
        else:
            action['aging_alert'] = False

        open_actions.append(action)

    open_actions.sort(key=lambda x: (
        x['is_overdue'],
        x['days_open'],
        -x['estimated_savings']
    ), reverse=True)

    return open_actions


def get_actions_summary():
    actions = load_actions()
    today = datetime.now()

    open_actions = [a for a in actions if a['status'] == 'open']
    in_progress = [a for a in actions if a['status'] == 'in_progress']
    completed = [a for a in actions if a['status'] == 'completed']
    dismissed = [a for a in actions if a['status'] == 'dismissed']

    overdue = []
    aging = []
    for a in open_actions + in_progress:
        due = datetime.strptime(a['due_date'], '%Y-%m-%d')
        days_until_due = (due - today).days
        created = datetime.fromisoformat(a['created_at'])
        days_open = (today - created).days

        if days_until_due < 0:
            overdue.append(a)
        if days_open > 14:
            aging.append(a)

    total_savings_at_stake = sum(
        a['estimated_savings'] for a in open_actions + in_progress)
    total_savings_realized = sum(
        a['estimated_savings'] for a in completed)

    categories = {}
    for a in open_actions + in_progress:
        cat = a['category']
        if cat not in categories:
            categories[cat] = {'count': 0, 'savings': 0}
        categories[cat]['count'] += 1
        categories[cat]['savings'] += a['estimated_savings']

    return {
        'total_open': len(open_actions),
        'total_in_progress': len(in_progress),
        'total_completed': len(completed),
        'total_dismissed': len(dismissed),
        'overdue_count': len(overdue),
        'aging_count': len(aging),
        'savings_at_stake': round(total_savings_at_stake, 2),
        'savings_realized': round(total_savings_realized, 2),
        'annual_savings_at_stake': round(total_savings_at_stake * 12, 2),
        'categories': categories,
        'overdue_actions': overdue,
        'aging_actions': aging
    }


def format_actions_for_slack(actions, title="Open Actions"):
    if not actions:
        return f"*{title}*\n\nNo open actions. Your team is on top of everything."

    lines = [f"*{title}* ({len(actions)} items)\n"]

    for a in actions[:10]:
        status_icon = "🔴" if a.get('is_overdue') else \
                      "🟡" if a.get('aging_alert') else "🟢"
        owner_text = f"@{a['owner']}" if a['owner'] else "unassigned"
        savings_text = f"${a['estimated_savings']}/mo" \
            if a['estimated_savings'] > 0 else "no savings tracked"
        due_text = f"overdue {abs(a['days_until_due'])}d" \
            if a.get('is_overdue') else f"due in {a['days_until_due']}d"

        lines.append(
            f"{status_icon} *{a['id']}* {a['title']}\n"
            f"   Owner: {owner_text} | {due_text} | "
            f"{savings_text} | open {a['days_open']}d\n"
        )

    if len(actions) > 10:
        lines.append(f"_...and {len(actions) - 10} more_")

    lines.append(
        "\n_Reply: done ACT-XXXX | assign ACT-XXXX to @name | "
        "dismiss ACT-XXXX_"
    )

    return "\n".join(lines)


def auto_create_from_beacon(feature, findings):
    created = []

    priority_map = {
        'security': 'high',
        'compliance': 'high',
        'cost_optimization': 'medium',
        'waste_reduction': 'low',
        'governance': 'medium'
    }

    category_map = {
        'security_tradeoffs': 'security',
        'compliance_check': 'compliance',
        'savings_recommendations': 'cost_optimization',
        'idle_resources': 'waste_reduction',
        'unmanaged_accounts': 'governance',
        'reservation_expiry': 'cost_optimization',
        'cost_rca': 'cost_optimization'
    }

    category = category_map.get(feature, 'general')
    priority = priority_map.get(category, 'medium')

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        title = finding.get('issue', finding.get(
            'cause', finding.get('service', 'Unknown issue')))
        description = finding.get('recommendation',
                                  finding.get('fix', ''))
        savings = finding.get('monthly_cost',
                              finding.get('estimated_savings', 0))

        if title and title != 'Unknown issue':
            action = create_action(
                title=title[:80],
                description=description[:200],
                category=category,
                estimated_savings=savings,
                due_days=7 if priority == 'high' else 14,
                source_feature=feature,
                priority=priority
            )
            created.append(action)

    return created


if __name__ == "__main__":
    print("\n=== Open Actions Dashboard Test ===")

    a1 = create_action(
        title="Enable GuardDuty for threat detection",
        description="GuardDuty not enabled. Enable immediately for ML-based threat detection.",
        category="security",
        estimated_savings=0,
        due_days=3,
        priority="high",
        source_feature="security_tradeoffs"
    )

    a2 = create_action(
        title="Delete 2 old EBS snapshots",
        description="Snapshots older than 30 days accumulating waste.",
        category="waste_reduction",
        estimated_savings=2.30,
        due_days=7,
        priority="low",
        source_feature="idle_resources"
    )

    a3 = create_action(
        title="Switch RDS to reserved instance",
        description="1-year RDS reserved instance saves 35% on current spend.",
        category="cost_optimization",
        estimated_savings=9.24,
        due_days=14,
        priority="medium",
        source_feature="savings_recommendations"
    )

    # Simulate one aging action
    actions = load_actions()
    for a in actions:
        if a['id'] == a1['id']:
            a['created_at'] = (
                datetime.now() - timedelta(days=16)).isoformat()
    save_actions(actions)

    open_actions = get_open_actions()
    summary = get_actions_summary()

    print(f"\nSummary:")
    print(f"  Open: {summary['total_open']}")
    print(f"  Savings at stake: ${summary['savings_at_stake']}/mo")
    print(f"  Aging actions: {summary['aging_count']}")
    print(f"  Overdue: {summary['overdue_count']}")

    print(f"\nFormatted output:")
    print(format_actions_for_slack(open_actions))