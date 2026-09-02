import boto3
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from aws_regions import get_regions

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_lambda_cost_summary():
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
                    'Values': ['AWS Lambda']
                }
            },
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'}]
        )

        total_cost = 0
        usage_breakdown = []

        for result in response['ResultsByTime']:
            for group in result.get('Groups', []):
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                if cost > 0:
                    usage_breakdown.append({
                        'usage_type': group['Keys'][0],
                        'cost': round(cost, 6)
                    })
                    total_cost += cost

        usage_breakdown.sort(key=lambda x: x['cost'], reverse=True)

        return {
            'total_monthly_cost': round(total_cost, 6),
            'usage_breakdown': usage_breakdown[:10],
            'period': f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        }

    except Exception as e:
        return {'total_monthly_cost': 0, 'usage_breakdown': [], 'error': str(e)}


def get_lambda_functions():
    regions = get_regions()
    all_functions = []

    for region in regions:
        try:
            lmb = boto3.client('lambda', region_name=region)
            cw = boto3.client('cloudwatch', region_name=region)

            paginator = lmb.get_paginator('list_functions')
            for page in paginator.paginate():
                for fn in page['Functions']:
                    name = fn['FunctionName']
                    runtime = fn.get('Runtime', 'unknown')
                    memory = fn.get('MemorySize', 128)
                    timeout = fn.get('Timeout', 3)
                    last_modified = fn.get('LastModified', '')

                    # Get invocation metrics
                    end = datetime.now(timezone.utc)
                    start = end - timedelta(days=30)

                    try:
                        inv_response = cw.get_metric_statistics(
                            Namespace='AWS/Lambda',
                            MetricName='Invocations',
                            Dimensions=[{'Name': 'FunctionName', 'Value': name}],
                            StartTime=start,
                            EndTime=end,
                            Period=2592000,
                            Statistics=['Sum']
                        )
                        invocations = int(inv_response['Datapoints'][0]['Sum']) if inv_response['Datapoints'] else 0
                    except Exception:
                        invocations = 0

                    try:
                        err_response = cw.get_metric_statistics(
                            Namespace='AWS/Lambda',
                            MetricName='Errors',
                            Dimensions=[{'Name': 'FunctionName', 'Value': name}],
                            StartTime=start,
                            EndTime=end,
                            Period=2592000,
                            Statistics=['Sum']
                        )
                        errors = int(err_response['Datapoints'][0]['Sum']) if err_response['Datapoints'] else 0
                    except Exception:
                        errors = 0

                    try:
                        dur_response = cw.get_metric_statistics(
                            Namespace='AWS/Lambda',
                            MetricName='Duration',
                            Dimensions=[{'Name': 'FunctionName', 'Value': name}],
                            StartTime=start,
                            EndTime=end,
                            Period=2592000,
                            Statistics=['Average']
                        )
                        avg_duration = round(dur_response['Datapoints'][0]['Average'], 2) if dur_response['Datapoints'] else 0
                    except Exception:
                        avg_duration = 0

                    # Estimate cost
                    # $0.20 per 1M requests + $0.0000166667 per GB-second
                    gb_seconds = (memory / 1024) * (avg_duration / 1000) * invocations
                    estimated_cost = round(
                        (invocations / 1000000 * 0.20) + (gb_seconds * 0.0000166667), 6
                    )

                    error_rate = round(errors / invocations * 100, 2) if invocations > 0 else 0

                    all_functions.append({
                        'name': name,
                        'region': region,
                        'runtime': runtime,
                        'memory_mb': memory,
                        'timeout_sec': timeout,
                        'invocations_30d': invocations,
                        'errors_30d': errors,
                        'error_rate': error_rate,
                        'avg_duration_ms': avg_duration,
                        'estimated_cost': estimated_cost,
                        'last_modified': last_modified[:10] if last_modified else 'unknown',
                        'is_idle': invocations == 0,
                        'console_link': f"https://console.aws.amazon.com/lambda/home?region={region}#/functions/{name}"
                    })

        except Exception as e:
            continue

    all_functions.sort(key=lambda x: x['estimated_cost'], reverse=True)
    return all_functions


def get_lambda_savings_opportunities(functions):
    opportunities = []

    for fn in functions:
        if fn['is_idle']:
            opportunities.append({
                'function': fn['name'],
                'region': fn['region'],
                'issue': 'Zero invocations in 30 days — possibly unused',
                'potential_savings': fn['estimated_cost'],
                'action': 'Review and delete if no longer needed',
                'console_link': fn['console_link']
            })

        if fn['memory_mb'] >= 512 and fn['avg_duration_ms'] < 100 and fn['invocations_30d'] > 0:
            opportunities.append({
                'function': fn['name'],
                'region': fn['region'],
                'issue': f'Over-provisioned memory ({fn["memory_mb"]}MB) for fast function ({fn["avg_duration_ms"]}ms avg)',
                'potential_savings': round(fn['estimated_cost'] * 0.5, 6),
                'action': f'Reduce memory to 128MB or 256MB — saves ~50%',
                'console_link': fn['console_link']
            })

        if fn['error_rate'] > 5:
            opportunities.append({
                'function': fn['name'],
                'region': fn['region'],
                'issue': f'High error rate {fn["error_rate"]}% — wasting compute on failed invocations',
                'potential_savings': round(fn['estimated_cost'] * fn['error_rate'] / 100, 6),
                'action': 'Fix errors to eliminate wasted invocation costs',
                'console_link': fn['console_link']
            })

    return opportunities


def format_lambda_for_slack(data):
    cost_summary = data.get('cost_summary', {})
    functions = data.get('functions', [])
    opportunities = data.get('opportunities', [])

    total_cost = cost_summary.get('total_monthly_cost', 0)
    idle_functions = [f for f in functions if f['is_idle']]
    total_invocations = sum(f['invocations_30d'] for f in functions)

    lines = [
        '*OpsBeacon Lambda Cost Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*Total Lambda Cost (30 days):* ${total_cost}',
        f'*Total Functions:* {len(functions)}',
        f'*Total Invocations (30d):* {total_invocations:,}',
        f'*Idle Functions:* {len(idle_functions)}',
        '',
    ]

    if functions:
        lines.append('*Top Functions by Cost:*')
        for fn in functions[:5]:
            status = '⚠️' if fn['error_rate'] > 5 else '✅' if not fn['is_idle'] else '😴'
            lines.append(
                f'  {status} `{fn["name"]}` ({fn["region"]})\n'
                f'     {fn["invocations_30d"]:,} invocations · '
                f'{fn["avg_duration_ms"]}ms avg · '
                f'{fn["memory_mb"]}MB · '
                f'${fn["estimated_cost"]}/mo'
            )
        lines.append('')

    if opportunities:
        lines.append(f'*💡 Savings Opportunities: {len(opportunities)}*')
        for opp in opportunities[:3]:
            lines.append(f'  → {opp["issue"]}')
            lines.append(f'    Function: `{opp["function"]}` · Save ~${opp["potential_savings"]}/mo')
            lines.append(f'    <{opp["console_link"]}|Open in Lambda Console>')
        lines.append('')
    else:
        lines.append('*Savings Opportunities:* None identified')
        lines.append('')

    lines.append(f'<https://console.aws.amazon.com/lambda/home?region={AWS_REGION}#/functions|View all functions in Lambda Console>')
    lines.append('_Powered by OpsBeacon Lambda Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== Lambda Cost Summary ===')
    cost = get_lambda_cost_summary()
    print(f"Total cost: ${cost['total_monthly_cost']}")

    print('\n=== Lambda Functions ===')
    functions = get_lambda_functions()
    print(f"Total functions: {len(functions)}")
    for fn in functions[:5]:
        print(f"  {fn['name']}: {fn['invocations_30d']} invocations ${fn['estimated_cost']}/mo")

    print('\n=== Savings Opportunities ===')
    opps = get_lambda_savings_opportunities(functions)
    print(f"Opportunities: {len(opps)}")
    for o in opps:
        print(f"  {o['function']}: {o['issue']}")