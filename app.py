import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import anthropic
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from aws_costs import get_aws_costs, get_cost_forecast, get_cost_anomalies, get_savings_recommendations
from aws_compliance import get_untagged_resources, get_policy_violations, get_egress_anomalies, get_shadow_ai, get_security_cost_tradeoffs
from incident_cost_impact import get_all_incident_analyses
from aws_accounts import get_unmanaged_accounts

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])
claude = anthropic.Anthropic()


def send_weekly_digest():
    print("Step 1: Starting digest...")
    costs = get_aws_costs()
    print(f"Step 2: Got costs: {costs}")
    cost_text = "\n".join(
        [f"{service}: ${amount}" for service, amount in costs.items()]
    )
    total = sum(costs.values())
    print(f"Step 3: Total spend: ${round(total, 2)}")
    prompt = f"""You are a FinOps analyst writing a Monday morning
weekly cost digest for a technical team in Slack.

Here is AWS spend for the last 30 days by service:
{cost_text}

Total spend: ${round(total, 2)}

Write a brief Monday digest that includes:
1. Total spend and biggest cost driver
2. One thing that looks unusual or worth investigating
3. One specific action they can take this week to save money
4. End with an offer to generate a fix script

Keep it conversational, direct, and under 200 words.
Format it nicely for Slack."""
    print("Step 4: Calling Claude...")
    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    print("Step 5: Got Claude response")
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    print(f"Step 6: Posting to channel: {channel}")
    response = app.client.chat_postMessage(
        channel=channel,
        text=message.content[0].text
    )
    print(f"Step 7: Slack response: {response['ok']}")
    print(f"Weekly digest sent at {datetime.now()}")


def check_and_alert_anomalies():
    print(f"Running anomaly check at {datetime.now()}")
    anomalies = get_cost_anomalies()
    if not anomalies:
        print("No anomalies detected")
        return
    anomaly_text = "\n".join([
        f"{a['service']}: ${a['latest']} today vs ${a['average']} average (+{a['increase_pct']}%)"
        for a in anomalies
    ])
    prompt = f"""You are a FinOps analyst writing an urgent cost alert for a technical team in Slack.

The following AWS services have spiked unexpectedly in the last 24 hours:

{anomaly_text}

Write a brief urgent alert that includes:
1. What spiked and by how much
2. Most likely cause for each spike
3. One immediate action to investigate or stop the bleeding
Keep it under 150 words, urgent but not panicky.
Start with a warning emoji and COST ALERT header."""
    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    app.client.chat_postMessage(
        channel=channel,
        text=message.content[0].text
    )
    print(f"Anomaly alert sent at {datetime.now()}")

def check_and_alert_incidents():
    print(f"Checking PagerDuty incidents at {datetime.now()}")

    analyses = get_all_incident_analyses()

    if not analyses:
        print("No active incidents found")
        return

    channel = os.environ["SLACK_DIGEST_CHANNEL"]

    for a in analyses:
        incident = a['incident']
        analysis = a['analysis']

        message = f"{analysis}\n\n🔗 <{incident['url']}|View in PagerDuty>"

        app.client.chat_postMessage(
            channel=channel,
            text=message
        )
        print(f"Incident alert posted: {incident['title']}")

@app.event("app_mention")
def handle_mention(event, say):
    text = event.get('text', '').lower()
    print(f"Received text: {text}")
    print(f"Shadow check: {'shadow' in text}")
    print(f"Compliance check: {'compliance' in text}")

    if 'compliance' in text or 'untagged' in text or 'violations' in text or 'shadow' in text:
        say("Running compliance and shadow AI checks across your AWS environment...")
        untagged = get_untagged_resources()
        violations = get_policy_violations()
        anomalies = get_egress_anomalies()
        shadow_ai = get_shadow_ai()
        prompt = f"""You are a FinOps analyst.
Here are the compliance check results:

Untagged Resources: {untagged if untagged else 'None found'}
Policy Violations: {violations if violations else 'None found'}
Egress Anomalies: {anomalies if anomalies else 'None found'}
Shadow AI Services: {shadow_ai if shadow_ai else 'None found'}

Write a brief compliance summary for a technical lead.
If everything is clean say so clearly and suggest
proactive steps to maintain it.
If there are issues prioritize them by business impact.
Be direct and specific."""
        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        say(message.content[0].text)

    elif 'forecast' in text or 'end of month' in text or 'bill look' in text:
        say("Calculating your month end forecast, one second...")
        forecast = get_cost_forecast()
        prompt = f"""You are a FinOps analyst.
Here is the AWS cost forecast for this month:

Actual spend so far: ${forecast['actual_spend']}
Days elapsed: {forecast['days_elapsed']} of {forecast['days_in_month']}
Days remaining: {forecast['days_remaining']}
Forecasted remaining spend: ${forecast['forecasted_remaining']}
Total projected month end: ${forecast['total_projected']}
Low estimate: ${forecast['lower_bound']}
High estimate: ${forecast['upper_bound']}

Write a brief forecast summary for a technical lead that includes:
1. Projected month end total with confidence range
2. Whether spend is trending normal or high
3. One action they can take in the next 3 days to reduce the bill
Keep it under 150 words, direct and specific."""
        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        say(message.content[0].text)

    elif 'savings' in text or 'reserved' in text or 'save money' in text:
        say("Analyzing your savings opportunities, one second...")

        data = get_savings_recommendations()
        recs = data['recommendations']
        total_monthly = data['total_monthly_savings']
        total_annual = data['total_annual_savings']

        rec_text = "\n".join([
            f"{r['service']}: ${r['current_monthly']}/mo current, "
            f"save ${r['savings_monthly']}/mo ({r['savings_pct']}%) "
            f"with {r['recommendation']}"
            for r in recs
        ])

        prompt = f"""You are a FinOps analyst.
Here are the AWS savings plan and reserved instance recommendations:

{rec_text}

Total potential monthly savings: ${total_monthly}
Total potential annual savings: ${total_annual}

Write a brief savings recommendation summary for a technical lead that includes:
1. Total savings opportunity with annual impact
2. Each recommendation with clear business case
3. Which one to act on first and why
4. A simple next step to get started
Keep it under 200 words, direct and specific."""

        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        say(message.content[0].text)


    elif 'security' in text or 'guardduty' in text or 'cloudtrail' in text or 'tradeoff' in text:
        say("Analyzing your security posture and cost tradeoffs...")

        data = get_security_cost_tradeoffs()
        disabled = data['disabled_services']
        enabled = data['enabled_services']
        total_cost = data['total_monthly_cost_to_fix']

        findings_text = "\n".join([
            f"{f['service']}: {f['status']} - Risk: {f['risk']} - Cost to fix: ${f['monthly_cost_to_enable']}/mo"
            for f in data['findings']
        ])

        prompt = f"""You are a FinOps and security analyst.
Here are the AWS security service findings:

{findings_text}

Total monthly cost to enable all disabled services: ${total_cost}
Disabled services: {len(disabled)}
Enabled services: {len(enabled)}

Write a brief security cost tradeoff summary for a technical lead that includes:
1. What is disabled and the real risk it creates
2. The total cost to fix everything
3. Priority order for which to enable first and why
4. One sentence on the cost vs risk calculation
Keep it under 200 words, direct and specific.
Be honest about the risks, don't sugarcoat."""

        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        say(message.content[0].text)

    elif 'incident' in text or 'pagerduty' in text or 'alert' in text:
        say("Pulling active incidents and analyzing cost impact...")

        analyses = get_all_incident_analyses()

        if not analyses:
            say("No active incidents in PagerDuty right now.")
            return

        for a in analyses:
            incident = a['incident']
            analysis = a['analysis']
            message = f"{analysis}\n\n🔗 <{incident['url']}|View in PagerDuty>"
            say(message)

    elif 'unmanaged' in text or 'accounts' in text or 'organization' in text:
        say("Scanning your AWS organization for unmanaged accounts...")

        accounts = get_unmanaged_accounts()

        if not accounts:
            say("All AWS accounts are properly managed and tagged.")
            return

        accounts_text = "\n".join([
            f"Account: {a['account_name']} ({a['account_id']})\n"
            f"Email: {a['email']}\n"
            f"Monthly Spend: ${a['monthly_spend']}\n"
            f"Issues: {', '.join(a['issues'])}"
            for a in accounts
        ])

        prompt = f"""You are a FinOps analyst.
Here are the AWS organization account findings:

{accounts_text}

Write a brief unmanaged accounts summary for a technical lead that includes:
1. How many accounts have governance issues
2. The specific issues found per account
3. Risk of leaving accounts untagged and unmanaged
4. Priority actions to fix each issue
5. One sentence on the business impact
Keep it under 200 words, direct and specific."""

        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        say(message.content[0].text)

    else:
        say("Pulling your AWS cost data, give me a second...")
        costs = get_aws_costs()
        cost_text = "\n".join(
            [f"{service}: ${amount}" for service, amount in costs.items()]
        )
        prompt = f"""You are a FinOps analyst.
Here is AWS spend for the last 30 days by service:

{cost_text}

Identify the top 3 cost drivers, flag anything unusual,
and suggest one specific action for each.
Be direct and specific. Write for a technical lead."""
        message = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        say(message.content[0].text)


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        send_weekly_digest,
        'cron',
        day_of_week='mon',
        hour=8,
        minute=0
    )
    scheduler.add_job(
        check_and_alert_anomalies,
        'interval',
        hours=6
    )
    scheduler.start()
    print("Weekly digest scheduled for Mondays at 8am")
    print("Anomaly checks scheduled every 6 hours")

    handler = SocketModeHandler(
        app, os.environ["SLACK_APP_TOKEN"]
    )
    
    scheduler.add_job(
        check_and_alert_anomalies,
        'interval',
        hours=6
    )

    scheduler.add_job(
        check_and_alert_incidents,
        'interval',
        minutes=15
    )
    handler.start()