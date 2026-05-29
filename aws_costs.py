import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def get_aws_costs():
    client = boto3.client('ce', region_name='us-east-1')

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
    client = boto3.client('ce', region_name='us-east-1')

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
    client = boto3.client('ce', region_name='us-east-1')

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


if __name__ == "__main__":
    costs = get_aws_costs()
    for service, amount in costs.items():
        print(f"{service}: ${amount}")