import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic
import os

load_dotenv()

AWS_REGION = 'us-east-2'
claude = anthropic.Anthropic()


def get_executive_digest_data():
    from aws_costs import get_aws_costs, get_cost_anomalies, get_savings_recommendations, get_forecast_recalculation
    from aws_compliance import get_security_cost_tradeoffs
    from idle_resources import get_all_idle_resources
    from aws_reservations import get_expiring_reservations
    from token_intelligence import get_token_intelligence

    today = datetime.today()

    # Current week spend
    ce_client = boto3.client('ce', region_name=AWS_REGION)
    week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    week_end = today.strftime('%Y-%m-%d')

    week_response = ce_client.get_cost_and_usage(
        TimePeriod={'Start': week_start, 'End': week_end},
        Granularity='DAILY',
        Metrics=['UnblendedCost']
    )
    week_spend = sum(
        float(d['Total']['UnblendedCost']['Amount'])
        for d in week_response['ResultsByTime']
    )

    # Prior week for comparison
    prior_start = (today - timedelta(days=14)).strftime('%Y-%m-%d')
    prior_end = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    prior_response = ce_client.get_cost_and_usage(
        TimePeriod={'Start': prior_start, 'End': prior_end},
        Granularity='DAILY',
        Metrics=['UnblendedCost']
    )
    prior_week_spend = sum(
        float(d['Total']['UnblendedCost']['Amount'])
        for d in prior_response['ResultsByTime']
    )

    wow_change = ((week_spend - prior_week_spend) / prior_week_spend * 100) \
        if prior_week_spend > 0 else 0

    # Get all the data
    forecast = get_forecast_recalculation()
    security = get_security_cost_tradeoffs()
    savings = get_savings_recommendations()
    idle = get_all_idle_resources()
    reservations = get_expiring_reservations(days_threshold=90)
    anomalies = get_cost_anomalies()
    tokens = get_token_intelligence()

    return {
        'date': today.strftime('%B %d, %Y'),
        'week_start': week_start,
        'week_end': week_end,
        'week_spend': round(week_spend, 2),
        'prior_week_spend': round(prior_week_spend, 2),
        'wow_change': round(wow_change, 1),
        'mtd_spend': forecast['mtd_spend'] if forecast else 0,
        'month_end_forecast': forecast['month_end_forecast'] if forecast else 0,
        'annual_forecast': forecast['annual_forecast'] if forecast else 0,
        'trend_direction': forecast['trend_direction'] if forecast else 'STABLE',
        'security_disabled': len(security['disabled_services']),
        'security_fix_cost': security['total_monthly_cost_to_fix'],
        'savings_monthly': savings['total_monthly_savings'],
        'savings_annual': savings['total_annual_savings'],
        'idle_waste_monthly': idle['total_monthly_waste'],
        'idle_waste_annual': idle['total_annual_waste'],
        'expiring_reservations': len(reservations),
        'cost_anomalies': len(anomalies),
        'token_spend_mtd': tokens['total_cost_mtd'],
        'token_projected': tokens['projected_monthly_cost']
    }


def generate_executive_digest():
    print("Gathering executive digest data...")
    data = get_executive_digest_data()

    wow_sign = "+" if data['wow_change'] > 0 else ""
    trend_plain = {
        'ACCELERATING': 'increasing faster than normal',
        'DECELERATING': 'slowing down',
        'STABLE': 'stable'
    }.get(data['trend_direction'], 'stable')

    total_opportunity = round(
        data['savings_monthly'] + data['idle_waste_monthly'], 2)
    total_annual_opportunity = round(
        data['savings_annual'] + data['idle_waste_annual'], 2)

    prompt = f"""You are writing a weekly executive cloud cost brief for a CFO and VP of Infrastructure.

This is NOT for engineers. Write in plain business language.
No AWS service names, no instance types, no technical jargon.
Convert everything to business terms: money, risk, and decisions.

DATA FOR THIS WEEK:

SPEND:
This week: ${data['week_spend']} ({wow_sign}{data['wow_change']}% vs last week)
Prior week: ${data['prior_week_spend']}
Month to date: ${data['mtd_spend']}
Projected month end: ${data['month_end_forecast']}
Projected annual: ${data['annual_forecast']}
Spend trend: {trend_plain}

RISK:
Security gaps: {data['security_disabled']} core security services not enabled
Cost to close gaps: ${data['security_fix_cost']}/month
Active cost anomalies: {data['cost_anomalies']}
Commitments expiring soon: {data['expiring_reservations']} (price increases if not renewed)

SAVINGS OPPORTUNITIES:
Immediate savings available: ${data['savings_monthly']}/month (${data['savings_annual']}/year)
Waste identified: ${data['idle_waste_monthly']}/month (${data['idle_waste_annual']}/year)
Total opportunity: ${total_opportunity}/month (${total_annual_opportunity}/year)

AI COSTS:
AI tooling spend this month: ${data['token_spend_mtd']}
Projected AI spend: ${data['token_projected']}/month

Write the executive brief in EXACTLY this format:

*OpsBeacon Executive Brief — Week of {data['week_start']}*

*CLOUD INVESTMENT THIS WEEK*
[2-3 sentences on spend in business terms. Use words like investment, budget, run rate. Never say EC2 or RDS.]

*RISK SNAPSHOT*
[2-3 bullet points on risks in plain language. Frame security gaps as business exposure not technical gaps.]

*SAVINGS OPPORTUNITIES*
[1-2 sentences on money being left on the table. Frame as ROI not technical fixes.]

*AI COST INTELLIGENCE*
[1 sentence on AI spend in context of the Tokenomics Foundation trend where tokens are the new unit of enterprise technology spend.]

*RECOMMENDED BOARD NARRATIVE*
[One paragraph, 3-4 sentences, that a CFO could copy paste into a board update or investor brief. Professional, confident, forward looking.]

---
_Prepared by OpsBeacon | prashant@opsbeacon.co_

Keep the entire brief under 300 words. Write for a CFO who has 60 seconds to read this."""

    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text


if __name__ == "__main__":
    print("\n=== Executive Digest Test ===")
    digest = generate_executive_digest()
    print(digest)