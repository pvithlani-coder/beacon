import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import boto3

load_dotenv()

AWS_REGION = 'us-east-2'
METRICS_FILE = 'business_metrics.json'


def load_metrics():
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, 'r') as f:
            return json.load(f)
    return get_default_metrics()


def get_default_metrics():
    return {
        'customers': 0,
        'transactions': 0,
        'api_calls': 0,
        'active_users': 0,
        'monthly_revenue': 0,
        'custom_metrics': {},
        'updated_at': datetime.now().isoformat()
    }


def save_metrics(metrics):
    metrics['updated_at'] = datetime.now().isoformat()
    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)


def update_metric(metric_name, value):
    metrics = load_metrics()

    standard_metrics = [
        'customers', 'transactions',
        'api_calls', 'active_users', 'monthly_revenue'
    ]

    if metric_name in standard_metrics:
        metrics[metric_name] = value
    else:
        metrics['custom_metrics'][metric_name] = value

    save_metrics(metrics)
    print(f"Updated {metric_name} to {value}")
    return metrics


def get_monthly_aws_spend():
    try:
        client = boto3.client('ce', region_name=AWS_REGION)
        today = datetime.today()
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')

        response = client.get_cost_and_usage(
            TimePeriod={'Start': month_start, 'End': today_str},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost']
        )

        spend = float(
            response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
        )
        return round(spend, 2)

    except Exception as e:
        print(f"AWS spend error: {e}")
        return 0


def get_service_breakdown():
    try:
        client = boto3.client('ce', region_name=AWS_REGION)
        today = datetime.today()
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        today_str = today.strftime('%Y-%m-%d')

        response = client.get_cost_and_usage(
            TimePeriod={'Start': month_start, 'End': today_str},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        services = {}
        for group in response['ResultsByTime'][0]['Groups']:
            service = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            if amount > 0.01:
                services[service] = round(amount, 4)

        return dict(sorted(
            services.items(), key=lambda x: x[1], reverse=True))

    except Exception as e:
        print(f"Service breakdown error: {e}")
        return {}


def calculate_unit_economics():
    metrics = load_metrics()
    monthly_spend = get_monthly_aws_spend()
    service_breakdown = get_service_breakdown()

    units = {}

    if metrics['customers'] > 0:
        units['cost_per_customer'] = round(
            monthly_spend / metrics['customers'], 4)

    if metrics['transactions'] > 0:
        units['cost_per_transaction'] = round(
            monthly_spend / metrics['transactions'], 6)

    if metrics['api_calls'] > 0:
        units['cost_per_api_call'] = round(
            monthly_spend / metrics['api_calls'], 8)

    if metrics['active_users'] > 0:
        units['cost_per_active_user'] = round(
            monthly_spend / metrics['active_users'], 4)

    if metrics['monthly_revenue'] > 0:
        units['infra_as_pct_revenue'] = round(
            (monthly_spend / metrics['monthly_revenue']) * 100, 3)
        units['cost_per_dollar_revenue'] = round(
            monthly_spend / metrics['monthly_revenue'], 5)

    # Per service unit costs
    service_units = {}
    for service, cost in service_breakdown.items():
        service_units[service] = {}
        if metrics['customers'] > 0:
            service_units[service]['per_customer'] = round(
                cost / metrics['customers'], 6)
        if metrics['transactions'] > 0:
            service_units[service]['per_transaction'] = round(
                cost / metrics['transactions'], 8)

    # Find most expensive service per unit
    most_expensive_service = None
    if metrics['transactions'] > 0 and service_breakdown:
        most_expensive_service = max(
            service_breakdown.items(),
            key=lambda x: x[1]
        )[0]

    return {
        'monthly_spend': monthly_spend,
        'metrics': metrics,
        'unit_costs': units,
        'service_breakdown': service_breakdown,
        'service_units': service_units,
        'most_expensive_service': most_expensive_service,
        'calculated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'has_metrics': any([
            metrics['customers'] > 0,
            metrics['transactions'] > 0,
            metrics['api_calls'] > 0,
            metrics['active_users'] > 0
        ])
    }


def format_unit_economics_for_slack(data):
    spend = data['monthly_spend']
    metrics = data['metrics']
    units = data['unit_costs']

    if not data['has_metrics']:
        return (
            f"*Unit Economics Report*\n\n"
            f"Monthly AWS Spend: ${spend}\n\n"
            f"No business metrics configured yet.\n\n"
            f"Set your metrics to unlock unit economics:\n"
            f"  @Beacon set customers to 500\n"
            f"  @Beacon set transactions to 125000\n"
            f"  @Beacon set monthly revenue to 50000\n"
            f"  @Beacon set active users to 1200\n\n"
            f"_Unit economics shows what it actually costs to serve each customer, "
            f"process each transaction, and handle each API call._"
        )

    lines = [
        f"*Unit Economics Report — {data['calculated_at'][:7]}*\n",
        f"Monthly Infrastructure: ${spend}",
    ]

    if metrics['customers'] > 0:
        lines.append(f"Active Customers: {metrics['customers']:,}")
    if metrics['transactions'] > 0:
        lines.append(f"Transactions: {metrics['transactions']:,}")
    if metrics['api_calls'] > 0:
        lines.append(f"API Calls: {metrics['api_calls']:,}")
    if metrics['active_users'] > 0:
        lines.append(f"Active Users: {metrics['active_users']:,}")
    if metrics['monthly_revenue'] > 0:
        lines.append(f"Monthly Revenue: ${metrics['monthly_revenue']:,}")

    lines.append("\n*Unit Costs:*")

    if 'cost_per_customer' in units:
        lines.append(
            f"  Cost per Customer:      ${units['cost_per_customer']:.4f}/mo")
    if 'cost_per_transaction' in units:
        val = units['cost_per_transaction']
        lines.append(
            f"  Cost per Transaction:   ${val:.6f}")
    if 'cost_per_api_call' in units:
        val = units['cost_per_api_call']
        lines.append(
            f"  Cost per API Call:      ${val:.8f}")
    if 'cost_per_active_user' in units:
        lines.append(
            f"  Cost per Active User:   ${units['cost_per_active_user']:.4f}/mo")
    if 'infra_as_pct_revenue' in units:
        lines.append(
            f"  Infra % of Revenue:     {units['infra_as_pct_revenue']:.3f}%")
    if 'cost_per_dollar_revenue' in units:
        lines.append(
            f"  Cost per $1 Revenue:    ${units['cost_per_dollar_revenue']:.5f}")

    if data['most_expensive_service']:
        lines.append(
            f"\n*Most expensive service:* {data['most_expensive_service']}")

    lines.append(
        "\n_Update metrics: @Beacon set customers to [number]_")

    return "\n".join(lines)


def parse_metric_update(text):
    text = text.lower()

    metric_map = {
        'customer': 'customers',
        'customers': 'customers',
        'transaction': 'transactions',
        'transactions': 'transactions',
        'api call': 'api_calls',
        'api calls': 'api_calls',
        'active user': 'active_users',
        'active users': 'active_users',
        'revenue': 'monthly_revenue',
        'monthly revenue': 'monthly_revenue'
    }

    detected_metric = None
    for keyword, metric_name in metric_map.items():
        if keyword in text:
            detected_metric = metric_name
            break

    if not detected_metric:
        return None, None

    import re
    numbers = re.findall(r'[\d,]+(?:\.\d+)?', text)
    if not numbers:
        return None, None

    value_str = numbers[-1].replace(',', '')
    try:
        value = float(value_str)
        if value == int(value):
            value = int(value)
    except ValueError:
        return None, None

    return detected_metric, value


if __name__ == "__main__":
    print("\n=== Unit Economics Test ===")

    update_metric('customers', 450)
    update_metric('transactions', 125000)
    update_metric('api_calls', 2100000)
    update_metric('active_users', 380)
    update_metric('monthly_revenue', 52000)

    data = calculate_unit_economics()

    print(f"\nMonthly Spend: ${data['monthly_spend']}")
    print(f"\nUnit Costs:")
    for metric, cost in data['unit_costs'].items():
        print(f"  {metric}: ${cost}")

    print(f"\nFormatted output:")
    print(format_unit_economics_for_slack(data))