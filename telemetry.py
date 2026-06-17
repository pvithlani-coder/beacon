import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEMETRY_FILE = 'telemetry_data.json'
BEHAVIOR_FILE = 'customer_behavior.json'


def load_telemetry():
    if os.path.exists(TELEMETRY_FILE):
        with open(TELEMETRY_FILE, 'r') as f:
            return json.load(f)
    return []


def save_telemetry(data):
    with open(TELEMETRY_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_behavior():
    if os.path.exists(BEHAVIOR_FILE):
        with open(BEHAVIOR_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_behavior(data):
    with open(BEHAVIOR_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def record_cost_pattern(
        customer_id, service, daily_spend,
        historical_avg, is_anomaly=False):
    telemetry = load_telemetry()

    entry = {
        'timestamp': datetime.now().isoformat(),
        'customer_id': customer_id,
        'type': 'cost_pattern',
        'service': service,
        'daily_spend': round(daily_spend, 4),
        'historical_avg': round(historical_avg, 4),
        'deviation_pct': round(
            ((daily_spend - historical_avg) / historical_avg * 100)
            if historical_avg > 0 else 0, 1),
        'is_anomaly': is_anomaly
    }

    telemetry.append(entry)
    save_telemetry(telemetry)
    return entry


def record_action(
        customer_id, feature, action_type,
        recommendation, confirmed=False, outcome=None):
    behavior = load_behavior()

    if customer_id not in behavior:
        behavior[customer_id] = {
            'customer_id': customer_id,
            'actions': [],
            'auto_approve_patterns': [],
            'feature_usage': {}
        }

    action = {
        'timestamp': datetime.now().isoformat(),
        'feature': feature,
        'action_type': action_type,
        'recommendation': recommendation[:100],
        'confirmed': confirmed,
        'outcome': outcome
    }

    behavior[customer_id]['actions'].append(action)

    # Track feature usage frequency
    if feature not in behavior[customer_id]['feature_usage']:
        behavior[customer_id]['feature_usage'][feature] = 0
    behavior[customer_id]['feature_usage'][feature] += 1

    # Detect auto-approve patterns
    # If customer confirms same action type 3+ times auto flag it
    confirmed_actions = [
        a for a in behavior[customer_id]['actions']
        if a['action_type'] == action_type and a['confirmed']
    ]

    if len(confirmed_actions) >= 3:
        pattern = {
            'action_type': action_type,
            'feature': feature,
            'confidence': min(
                95, 70 + len(confirmed_actions) * 5),
            'times_confirmed': len(confirmed_actions)
        }

        existing = next(
            (p for p in behavior[customer_id]['auto_approve_patterns']
             if p['action_type'] == action_type), None)

        if existing:
            existing.update(pattern)
        else:
            behavior[customer_id]['auto_approve_patterns'].append(pattern)

    save_behavior(behavior)
    return action


def get_cross_customer_anomalies(current_customer_id, service, deviation_pct):
    telemetry = load_telemetry()

    other_customers = [
        e for e in telemetry
        if e['customer_id'] != current_customer_id
        and e['service'] == service
        and e['type'] == 'cost_pattern'
    ]

    if len(other_customers) < 2:
        return None

    other_anomalies = [
        e for e in other_customers
        if e['is_anomaly'] or abs(e['deviation_pct']) > 20
    ]

    if len(other_anomalies) >= 2:
        return {
            'signal': 'cross_customer_pattern',
            'service': service,
            'affected_customers': len(
                set(e['customer_id'] for e in other_anomalies)),
            'likely_cause': 'AWS pricing change or platform-wide issue',
            'confidence': min(
                95, 60 + len(other_anomalies) * 10),
            'message': f'{len(other_anomalies)} other customers seeing similar {service} anomalies - likely AWS-wide issue not your infrastructure'
        }

    return None


def get_behavioral_recommendations(customer_id):
    behavior = load_behavior()

    if customer_id not in behavior:
        return []

    customer = behavior[customer_id]
    recommendations = []

    for pattern in customer['auto_approve_patterns']:
        if pattern['confidence'] >= 80:
            recommendations.append({
                'action_type': pattern['action_type'],
                'feature': pattern['feature'],
                'confidence': pattern['confidence'],
                'times_confirmed': pattern['times_confirmed'],
                'suggestion': f"You always approve {pattern['action_type']} actions. Want me to do these automatically?",
                'automation_ready': pattern['confidence'] >= 90
            })

    return recommendations


def get_telemetry_summary(customer_id=None):
    telemetry = load_telemetry()
    behavior = load_behavior()

    if customer_id:
        telemetry = [
            e for e in telemetry
            if e['customer_id'] == customer_id]
        behavior = {
            customer_id: behavior.get(customer_id, {})}

    total_patterns = len(telemetry)
    anomalies = [e for e in telemetry if e.get('is_anomaly')]
    customers = set(e['customer_id'] for e in telemetry)

    auto_approve_ready = []
    for cid, data in behavior.items():
        for pattern in data.get('auto_approve_patterns', []):
            if pattern.get('automation_ready'):
                auto_approve_ready.append({
                    'customer': cid,
                    'action': pattern['action_type'],
                    'confidence': pattern['confidence']
                })

    return {
        'total_patterns_recorded': total_patterns,
        'total_anomalies': len(anomalies),
        'customers_tracked': len(customers),
        'automation_ready_actions': auto_approve_ready,
        'cross_customer_signal_threshold': 10
    }


if __name__ == "__main__":
    print("\n=== Telemetry Layer Test ===")

    # Simulate InvoiceCloud data
    record_cost_pattern('invoicecloud', 'Amazon RDS', 45.20, 38.10, True)
    record_cost_pattern('invoicecloud', 'Amazon EC2', 12.30, 11.80, False)
    record_cost_pattern('invoicecloud', 'Amazon S3', 8.40, 8.20, False)

    # Simulate Mindcan data
    record_cost_pattern('mindcan', 'Amazon RDS', 42.10, 35.90, True)
    record_cost_pattern('mindcan', 'Amazon EC2', 18.50, 17.20, False)

    # Simulate repeated confirmed actions
    for i in range(4):
        record_action(
            'invoicecloud', 'idle_resources',
            'delete_snapshot', 'Delete old snapshot',
            confirmed=True, outcome='success'
        )

    # Check cross customer signal
    signal = get_cross_customer_anomalies(
        'default', 'Amazon RDS', 18.5)
    if signal:
        print(f"\nCross-customer signal detected:")
        print(f"  {signal['message']}")
        print(f"  Confidence: {signal['confidence']}%")

    # Check behavioral recommendations
    recs = get_behavioral_recommendations('invoicecloud')
    if recs:
        print(f"\nBehavioral automation ready:")
        for r in recs:
            print(f"  {r['suggestion']}")
            print(f"  Confidence: {r['confidence']}%")
            print(f"  Ready to automate: {r['automation_ready']}")

    summary = get_telemetry_summary()
    print(f"\nTelemetry Summary:")
    print(f"  Patterns recorded: {summary['total_patterns_recorded']}")
    print(f"  Anomalies tracked: {summary['total_anomalies']}")
    print(f"  Customers tracked: {summary['customers_tracked']}")
    print(f"  Automation ready: {len(summary['automation_ready_actions'])}")