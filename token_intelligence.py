import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN_LOG_FILE = 'token_usage_log.json'

PRICING = {
    'claude-sonnet-4-5': {'input': 3.00, 'output': 15.00},
    'claude-opus-4-6': {'input': 15.00, 'output': 75.00},
    'claude-haiku-4-5': {'input': 0.80, 'output': 4.00},
    'gpt-4o': {'input': 2.50, 'output': 10.00},
    'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
}

USAGE_LOG = 'token_usage_log.json'


def load_usage_log():
    if os.path.exists(USAGE_LOG):
        with open(USAGE_LOG, 'r') as f:
            return json.load(f)
    return []


def save_usage_log(log):
    with open(USAGE_LOG, 'w') as f:
        json.dump(log, f, indent=2)


def log_token_usage(model, input_tokens, output_tokens,
                    feature='general', customer_id='default'):
    log = []
    if os.path.exists(TOKEN_LOG_FILE):
        with open(TOKEN_LOG_FILE, 'r') as f:
            log = json.load(f)

    # Pricing for claude-sonnet-4-5
    input_cost = (input_tokens / 1_000_000) * 3.00
    output_cost = (output_tokens / 1_000_000) * 15.00
    total_cost = round(input_cost + output_cost, 6)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'model': model,
        'feature': feature,
        'customer_id': customer_id,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': input_tokens + output_tokens,
        'cost': total_cost
    }

    log.append(entry)

    with open(TOKEN_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)

    return entry


def get_token_intelligence():
    log = load_usage_log()

    today = datetime.today()
    month_start = today.replace(day=1)

    mtd_entries = [
        e for e in log
        if datetime.fromisoformat(e['timestamp']) >= month_start
    ]

    if not mtd_entries:
        return {
            'total_cost_mtd': 0,
            'total_tokens_mtd': 0,
            'projected_monthly_cost': 0,
            'providers': [],
            'feature_breakdown': {},
            'model_breakdown': {},
            'most_expensive_feature': 'N/A',
            'most_efficient_model': 'N/A',
            'days_elapsed': today.day,
            'days_remaining': 30 - today.day,
            'status': 'no_data'
        }

    total_cost = sum(e['cost'] for e in mtd_entries)
    total_tokens = sum(e['total_tokens'] for e in mtd_entries)

    # Provider breakdown
    provider_data = {}
    for e in mtd_entries:
        p = e.get('provider', 'anthropic')
        if p not in provider_data:
            provider_data[p] = {
                'provider': p,
                'total_tokens': 0,
                'total_cost': 0,
                'calls': 0
            }
        provider_data[p]['total_tokens'] += e['total_tokens']
        provider_data[p]['total_cost'] += e['cost']
        provider_data[p]['calls'] += 1

    # Feature breakdown
    feature_data = {}
    for e in mtd_entries:
        f = e['feature']
        if f not in feature_data:
            feature_data[f] = {'calls': 0, 'total_cost': 0, 'total_tokens': 0}
        feature_data[f]['calls'] += 1
        feature_data[f]['total_cost'] += e['cost']
        feature_data[f]['total_tokens'] += e['total_tokens']

    # Model breakdown
    model_data = {}
    for e in mtd_entries:
        m = e['model']
        if m not in model_data:
            model_data[m] = {'calls': 0, 'total_cost': 0, 'total_tokens': 0}
        model_data[m]['calls'] += 1
        model_data[m]['total_cost'] += e['cost']
        model_data[m]['total_tokens'] += e['total_tokens']

    # Round all costs
    for p in provider_data.values():
        p['total_cost'] = round(p['total_cost'], 6)
    for f in feature_data.values():
        f['total_cost'] = round(f['total_cost'], 6)
    for m in model_data.values():
        m['total_cost'] = round(m['total_cost'], 6)

    # Most expensive feature
    most_expensive = max(
        feature_data.items(),
        key=lambda x: x[1]['total_cost']
    )[0] if feature_data else 'N/A'

    # Most efficient model (lowest cost per token)
    most_efficient = min(
        model_data.items(),
        key=lambda x: x[1]['total_cost'] / x[1]['total_tokens']
        if x[1]['total_tokens'] > 0 else float('inf')
    )[0] if model_data else 'N/A'

    # Month end forecast
    days_elapsed = today.day
    if today.month == 12:
        days_in_month = 31
    else:
        days_in_month = (datetime(today.year, today.month + 1, 1) -
                         datetime(today.year, today.month, 1)).days
    daily_rate = total_cost / days_elapsed if days_elapsed > 0 else 0
    projected_monthly = daily_rate * days_in_month

    return {
        'total_cost_mtd': round(total_cost, 6),
        'total_tokens_mtd': total_tokens,
        'projected_monthly_cost': round(projected_monthly, 6),
        'providers': list(provider_data.values()),
        'feature_breakdown': feature_data,
        'model_breakdown': model_data,
        'most_expensive_feature': most_expensive,
        'most_efficient_model': most_efficient,
        'days_elapsed': days_elapsed,
        'days_remaining': days_in_month - days_elapsed,
        'status': 'live'
    }


if __name__ == "__main__":
    print("\n=== Token Intelligence Report ===")

    # Seed some demo data so it works immediately
    print("Seeding demo token usage data...")
    demo_entries = [
        ('claude-sonnet-4-5', 450, 380, 'cost_analysis', 'anthropic'),
        ('claude-sonnet-4-5', 520, 420, 'compliance_check', 'anthropic'),
        ('claude-sonnet-4-5', 480, 350, 'security_tradeoffs', 'anthropic'),
        ('claude-sonnet-4-5', 390, 290, 'savings_recommendations', 'anthropic'),
        ('claude-sonnet-4-5', 410, 310, 'cost_forecast', 'anthropic'),
        ('claude-sonnet-4-5', 550, 440, 'weekly_digest', 'anthropic'),
        ('claude-sonnet-4-5', 430, 360, 'incident_analysis', 'anthropic'),
        ('claude-sonnet-4-5', 460, 380, 'cost_analysis', 'anthropic'),
        ('claude-sonnet-4-5', 500, 400, 'shadow_ai', 'anthropic'),
        ('claude-sonnet-4-5', 420, 330, 'unmanaged_accounts', 'anthropic'),
    ]

    for model, inp, out, feature, provider in demo_entries:
        log_token_usage(model, inp, out, feature, provider)

    data = get_token_intelligence()
    print(f"\nTotal Token Spend MTD: ${data['total_cost_mtd']}")
    print(f"Total Tokens Used: {data['total_tokens_mtd']:,}")
    print(f"Projected Month End: ${data['projected_monthly_cost']}")
    print(f"Most Expensive Feature: {data['most_expensive_feature']}")
    print(f"Most Efficient Model: {data['most_efficient_model']}")
    print(f"Status: {data['status']}")
    print(f"\nFeature Breakdown:")
    for feature, stats in sorted(data['feature_breakdown'].items(),
                                  key=lambda x: x[1]['total_cost'], reverse=True):
        print(f"  {feature}: {stats['calls']} calls, "
              f"{stats['total_tokens']:,} tokens, ${stats['total_cost']}")
        
def get_cost_by_customer(customer_id='default'):
    if not os.path.exists(TOKEN_LOG_FILE):
        return None

    with open(TOKEN_LOG_FILE, 'r') as f:
        log = json.load(f)

    customer_entries = [
        e for e in log
        if e.get('customer_id', 'default') == customer_id
    ]

    if not customer_entries:
        return {
            'customer_id': customer_id,
            'total_cost': 0,
            'total_tokens': 0,
            'total_calls': 0,
            'by_feature': {}
        }

    total_cost = sum(e.get('cost', 0) for e in customer_entries)
    total_tokens = sum(
        e.get('input_tokens', 0) + e.get('output_tokens', 0)
        for e in customer_entries
    )

    by_feature = {}
    for entry in customer_entries:
        feature = entry.get('feature', 'unknown')
        if feature not in by_feature:
            by_feature[feature] = {
                'calls': 0,
                'tokens': 0,
                'cost': 0
            }
        by_feature[feature]['calls'] += 1
        by_feature[feature]['tokens'] += (
            entry.get('input_tokens', 0) +
            entry.get('output_tokens', 0)
        )
        by_feature[feature]['cost'] += entry.get('cost', 0)

    for feature in by_feature:
        by_feature[feature]['cost'] = round(
            by_feature[feature]['cost'], 6)

    return {
        'customer_id': customer_id,
        'total_cost': round(total_cost, 6),
        'total_calls': len(customer_entries),
        'total_tokens': total_tokens,
        'by_feature': by_feature,
        'margin_at_499': round(499 - total_cost, 2),
        'margin_at_199': round(199 - total_cost, 2)
    }


def get_all_customer_costs():
    if not os.path.exists(TOKEN_LOG_FILE):
        return []

    with open(TOKEN_LOG_FILE, 'r') as f:
        log = json.load(f)

    customer_ids = set(
        e.get('customer_id', 'default') for e in log)

    results = []
    for customer_id in customer_ids:
        data = get_cost_by_customer(customer_id)
        if data:
            results.append(data)

    results.sort(key=lambda x: x['total_cost'], reverse=True)
    return results

    if __name__ == "__main__":
        print("\n=== Token Cost by Customer ===")
        data = get_cost_by_customer('default')
        if data:
            print(f"Customer: {data['customer_id']}")
            print(f"Total cost: ${data['total_cost']}")
            print(f"Total calls: {data['total_calls']}")
            print(f"Total tokens: {data['total_tokens']:,}")
            print(f"Margin at $499/mo: ${data['margin_at_499']}")
            print(f"Margin at $199/mo: ${data['margin_at_199']}")
            print(f"\nBy feature:")
        for feature, stats in sorted(
                data['by_feature'].items(),
                key=lambda x: x[1]['cost'], reverse=True):
            print(f"  {feature}: {stats['calls']} calls, "
                  f"{stats['tokens']:,} tokens, "
                  f"${stats['cost']:.6f}")

    print("\n=== All Customer Costs ===")
    all_customers = get_all_customer_costs()
    for c in all_customers:
        print(f"  {c['customer_id']}: ${c['total_cost']} "
              f"({c['total_calls']} calls)")