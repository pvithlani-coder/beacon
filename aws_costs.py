import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def get_aws_costs():
    client = boto3.client('ce', region_name=AWS_REGION)

    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )

    costs = {}
    for group in response['ResultsByTime'][0]['Groups']:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])
        if amount > 0.01:
            costs[service] = round(amount, 2)

    sorted_costs = dict(
        sorted(costs.items(), key=lambda x: x[1], reverse=True)
    )

    return sorted_costs


def get_cost_forecast():
    client = boto3.client('ce', region_name=AWS_REGION)

    today = datetime.today()

    start = (today + timedelta(days=1)).strftime('%Y-%m-%d')

    if today.month == 12:
        end = datetime(today.year + 1, 1, 1).strftime('%Y-%m-%d')
    else:
        end = datetime(today.year, today.month + 1, 1).strftime('%Y-%m-%d')

    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    actual = client.get_cost_and_usage(
        TimePeriod={'Start': month_start, 'End': today_str},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost']
    )

    actual_spend = float(
        actual['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']
    )

    forecast = client.get_cost_forecast(
        TimePeriod={'Start': start, 'End': end},
        Metric='UNBLENDED_COST',
        Granularity='MONTHLY'
    )

    forecasted_spend = float(forecast['Total']['Amount'])

    forecast_result = forecast['ForecastResultsByTime'][0]
    lower_bound = float(forecast_result.get(
        'PredictionIntervalLowerBound', forecasted_spend * 0.9))
    upper_bound = float(forecast_result.get(
        'PredictionIntervalUpperBound', forecasted_spend * 1.1))

    total_projected = actual_spend + forecasted_spend

    if today.month == 12:
        next_month = datetime(today.year + 1, 1, 1)
    else:
        next_month = datetime(today.year, today.month + 1, 1)

    days_in_month = (
        next_month - datetime(today.year, today.month, 1)).days
    days_elapsed = today.day
    days_remaining = days_in_month - days_elapsed

    return {
        'actual_spend': round(actual_spend, 2),
        'forecasted_remaining': round(forecasted_spend, 2),
        'total_projected': round(total_projected, 2),
        'lower_bound': round(lower_bound + actual_spend, 2),
        'upper_bound': round(upper_bound + actual_spend, 2),
        'days_elapsed': days_elapsed,
        'days_remaining': days_remaining,
        'days_in_month': days_in_month
    }


def get_cost_anomalies():
    client = boto3.client('ce', region_name=AWS_REGION)

    today = datetime.today()

    end = today.strftime('%Y-%m-%d')
    start = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    recent = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )

    service_daily = {}
    for day in recent['ResultsByTime']:
        for group in day['Groups']:
            service = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            if service not in service_daily:
                service_daily[service] = []
            service_daily[service].append(amount)

    anomalies = []

    for service, daily_amounts in service_daily.items():
        if len(daily_amounts) < 3:
            continue

        historical_avg = sum(daily_amounts[:-1]) / len(daily_amounts[:-1])
        latest = daily_amounts[-1]

        if historical_avg < 0.10:
            continue

        if latest > historical_avg * 1.20:
            pct_increase = ((latest - historical_avg) / historical_avg) * 100
            anomalies.append({
                'service': service,
                'latest': round(latest, 2),
                'average': round(historical_avg, 2),
                'increase_pct': round(pct_increase, 1)
            })

    anomalies.sort(key=lambda x: x['increase_pct'], reverse=True)

    return anomalies


def get_savings_recommendations():
    ce_client = boto3.client('ce', region_name=AWS_REGION)

    recommendations = []

    end = datetime.today().strftime('%Y-%m-%d')
    start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

    response = ce_client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='MONTHLY',
        Metrics=['UnblendedCost'],
        GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
    )

    costs = {}
    for group in response['ResultsByTime'][0]['Groups']:
        service = group['Keys'][0]
        amount = float(group['Metrics']['UnblendedCost']['Amount'])
        if amount > 0.01:
            costs[service] = round(amount, 2)

    ec2_cost = costs.get(
        'Amazon Elastic Compute Cloud - Compute', 0)
    if ec2_cost > 5:
        recommendations.append({
            'service': 'EC2',
            'current_monthly': ec2_cost,
            'savings_monthly': round(ec2_cost * 0.40, 2),
            'savings_pct': 40,
            'recommendation': '1-year Compute Savings Plan',
            'commitment': '1 year'
        })

    rds_cost = costs.get(
        'Amazon Relational Database Service', 0)
    if rds_cost > 5:
        recommendations.append({
            'service': 'RDS',
            'current_monthly': rds_cost,
            'savings_monthly': round(rds_cost * 0.35, 2),
            'savings_pct': 35,
            'recommendation': '1-year RDS Reserved Instance',
            'commitment': '1 year'
        })

    elasticache_cost = costs.get('Amazon ElastiCache', 0)
    if elasticache_cost > 1:
        recommendations.append({
            'service': 'ElastiCache',
            'current_monthly': elasticache_cost,
            'savings_monthly': round(elasticache_cost * 0.30, 2),
            'savings_pct': 30,
            'recommendation': '1-year ElastiCache Reserved Node',
            'commitment': '1 year'
        })

    sagemaker_cost = costs.get('Amazon SageMaker', 0)
    if sagemaker_cost > 5:
        recommendations.append({
            'service': 'SageMaker',
            'current_monthly': sagemaker_cost,
            'savings_monthly': round(sagemaker_cost * 0.30, 2),
            'savings_pct': 30,
            'recommendation': '1-year SageMaker Savings Plan',
            'commitment': '1 year'
        })

    recommendations.sort(
        key=lambda x: x['savings_monthly'], reverse=True)

    total_monthly_savings = sum(
        r['savings_monthly'] for r in recommendations)
    total_annual_savings = round(total_monthly_savings * 12, 2)

    return {
        'recommendations': recommendations,
        'total_monthly_savings': round(total_monthly_savings, 2),
        'total_annual_savings': total_annual_savings
    }


if __name__ == "__main__":
    costs = get_aws_costs()
    for service, amount in costs.items():
        print(f"{service}: ${amount}")