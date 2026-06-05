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
from aws_accounts import get_unmanaged_accounts, fix_account_tags
from aws_reservations import get_expiring_reservations
from beacon_config import BEACON_SYSTEM_PROMPT, BEACON_FORMAT
from token_intelligence import get_token_intelligence, log_token_usage

load_dotenv()

app = App(token=os.environ["SLACK_BOT_TOKEN"])
claude = anthropic.Anthropic()

pending_tag_fixes = {}


def call_claude(prompt, feature='general'):
    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        system=BEACON_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt + BEACON_FORMAT}]
    )
    log_token_usage(
        model="claude-sonnet-4-5",
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        feature=feature
    )
    return message.content[0].text


def send_weekly_digest():
    print("Step 1: Starting digest...")
    costs = get_aws_costs()
    print(f"Step 2: Got costs: {costs}")
    cost_text = "\n".join(
        [f"{service}: ${amount}" for service, amount in costs.items()]
    )
    total = sum(costs.values())
    print(f"Step 3: Total spend: ${round(total, 2)}")
    prompt = f"""Weekly Monday morning cost digest for the team.

AWS spend for the last 30 days by service:
{cost_text}

Total spend: ${round(total, 2)}

Write the Monday digest covering:
1. Total spend and biggest cost driver
2. One unusual or worth investigating finding
3. One specific action to take this week to save money
4. Offer to generate a fix script"""

    print("Step 4: Calling Claude...")
    response = call_claude(prompt, feature='weekly_digest')
    print("Step 5: Got Claude response")
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    print(f"Step 6: Posting to channel: {channel}")
    result = app.client.chat_postMessage(
        channel=channel,
        text=response
    )
    print(f"Step 7: Slack response: {result['ok']}")
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
    prompt = f"""Urgent cost anomaly alert for the team.

These AWS services spiked unexpectedly in the last 24 hours:
{anomaly_text}

Write the alert covering:
1. What spiked and by how much
2. Most likely cause
3. One immediate action to investigate or stop the bleeding

Start with a warning emoji and COST ALERT header."""

    response = call_claude(prompt, feature='anomaly_alert')
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    app.client.chat_postMessage(channel=channel, text=response)
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
        app.client.chat_postMessage(channel=channel, text=message)
        print(f"Incident alert posted: {incident['title']}")


def check_expiring_reservations():
    print(f"Checking expiring reservations at {datetime.now()}")
    reservations = get_expiring_reservations()
    if not reservations:
        print("No expiring reservations found")
        return
    urgent = [r for r in reservations if r['urgency'] == 'HIGH']
    if not urgent:
        print("No urgent expiring reservations")
        return
    res_text = "\n".join([
        f"{r['type']}: {r['instance_type']} expires "
        f"{r['end_date']} in {r['days_remaining']} days"
        for r in urgent
    ])
    prompt = f"""Urgent reservation expiry alert.

These AWS reserved instances are expiring within 30 days:
{res_text}

Write the alert covering:
1. What is expiring and the cost impact
2. Immediate action to renew

Start with a warning emoji and RESERVATION EXPIRY ALERT header."""

    response = call_claude(prompt, feature='reservation_alert')
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    app.client.chat_postMessage(channel=channel, text=response)
    print(f"Reservation expiry alert sent at {datetime.now()}")


@app.event("app_mention")
def handle_mention(event, say):
    text = event.get('text', '').lower()
    print(f"Received text: {text}")

    if 'compliance' in text or 'untagged' in text or 'violations' in text or 'shadow' in text:
        say("Running compliance and shadow AI checks...")
        untagged = get_untagged_resources()
        violations = get_policy_violations()
        anomalies = get_egress_anomalies()
        shadow_ai = get_shadow_ai()
        prompt = f"""Compliance check results for the AWS environment.

Untagged Resources: {untagged if untagged else 'None found'}
Policy Violations: {violations if violations else 'None found'}
Egress Anomalies: {anomalies if anomalies else 'None found'}
Shadow AI Services: {shadow_ai if shadow_ai else 'None found'}

Write the compliance summary covering findings and priority actions.
If everything is clean say so clearly and suggest proactive steps."""
        say(call_claude(prompt, feature='compliance_check'))

    elif 'forecast' in text or 'end of month' in text or 'bill look' in text:
        say("Calculating your month end forecast...")
        forecast = get_cost_forecast()
        prompt = f"""AWS cost forecast for this month.

Actual spend so far: ${forecast['actual_spend']}
Days elapsed: {forecast['days_elapsed']} of {forecast['days_in_month']}
Days remaining: {forecast['days_remaining']}
Forecasted remaining spend: ${forecast['forecasted_remaining']}
Total projected month end: ${forecast['total_projected']}
Low estimate: ${forecast['lower_bound']}
High estimate: ${forecast['upper_bound']}

Write the forecast summary covering projected total, trend, and one action to reduce the bill."""
        say(call_claude(prompt, feature='cost_forecast'))

    elif 'savings' in text or 'save money' in text:
        say("Analyzing your savings opportunities...")
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
        prompt = f"""AWS savings recommendations.

{rec_text}

Total potential monthly savings: ${total_monthly}
Total potential annual savings: ${total_annual}

Write the savings summary covering total opportunity, each recommendation, which to act on first, and next step."""
        say(call_claude(prompt, feature='savings_recommendations'))

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
        prompt = f"""AWS security cost tradeoff analysis.

{findings_text}

Total monthly cost to enable all disabled services: ${total_cost}
Disabled services: {len(disabled)}
Enabled services: {len(enabled)}

Write the security summary covering what is disabled, the real risk, total cost to fix, priority order, and cost vs risk calculation.
Be honest about the risks."""
        say(call_claude(prompt, feature='security_tradeoffs'))

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
        prompt = f"""AWS organization account governance findings.

{accounts_text}

Write the unmanaged accounts summary covering governance issues, risks, and priority actions."""
        say(call_claude(prompt, feature='unmanaged_accounts'))

    elif 'fix tags' in text or 'apply tags' in text:
        say("Analyzing your AWS accounts and preparing tag fixes...")
        accounts = get_unmanaged_accounts()
        if not accounts:
            say("All accounts are properly tagged. Nothing to fix.")
            return
        for account in accounts:
            has_tag_issues = any(
                'Missing' in issue for issue in account['issues']
            )
            if has_tag_issues:
                environment = 'production'
                if any(word in account['account_name'].lower()
                       for word in ['dev', 'test', 'staging', 'sandbox']):
                    environment = 'development'
                proposed_tags = {
                    'Owner': account['email'],
                    'Environment': environment,
                    'CostCenter': 'engineering'
                }
                user_id = event.get('user')
                pending_tag_fixes[user_id] = {
                    'account_id': account['account_id'],
                    'account_name': account['account_name'],
                    'email': account['email'],
                    'tags': proposed_tags
                }
                say(
                    f"I can apply these tags to "
                    f"*{account['account_name']}* "
                    f"({account['account_id']}):\n"
                    f"• Owner: `{proposed_tags['Owner']}`\n"
                    f"• Environment: `{proposed_tags['Environment']}`\n"
                    f"• CostCenter: `{proposed_tags['CostCenter']}`\n\n"
                    f"Reply *confirm* to apply or give me different values."
                )

    elif 'confirm' in text:
        user_id = event.get('user')
        if user_id not in pending_tag_fixes:
            say("No pending tag fixes found. Run `fix tags` first.")
            return
        pending = pending_tag_fixes[user_id]
        say(f"Applying tags to *{pending['account_name']}*...")
        result = fix_account_tags(
            pending['account_id'],
            pending['email'],
            pending['account_name']
        )
        if result['success']:
            say(
                f"✅ Tags applied successfully to "
                f"*{pending['account_name']}*\n"
                f"• Owner: `{result['tags_applied']['Owner']}`\n"
                f"• Environment: `{result['tags_applied']['Environment']}`\n"
                f"• CostCenter: `{result['tags_applied']['CostCenter']}`"
            )
            del pending_tag_fixes[user_id]
        else:
            say(f"❌ Failed to apply tags: {result['error']}")

    elif 'expir' in text or 'reservation expir' in text or 'savings plan expir' in text:
        say("Checking for expiring reserved instances and savings plans...")
        reservations = get_expiring_reservations()
        if not reservations:
            say("No reserved instances or savings plans expiring in the next 90 days. You're all clear.")
            return
        res_text = "\n".join([
            f"{r['type']}: {r['instance_type']} x{r['count']} "
            f"expires {r['end_date']} ({r['days_remaining']} days) "
            f"Urgency: {r['urgency']} Monthly cost: ${r['monthly_cost']}"
            for r in reservations
        ])
        prompt = f"""AWS reserved instance and savings plan expiry analysis.

{res_text}

Write the expiry summary covering what is expiring, cost impact of reverting to on-demand, priority renewal order, and next steps.
Flag anything expiring within 30 days as urgent."""
        say(call_claude(prompt, feature='reservation_expiry'))

    elif 'token' in text or 'ai cost' in text or 'tokenomics' in text:
        say("Analyzing your AI token usage and costs...")

        data = get_token_intelligence()

        feature_text = "\n".join([
            f"{feature}: {stats['calls']} calls, "
            f"{stats['total_tokens']:,} tokens, ${stats['total_cost']}"
            for feature, stats in sorted(
                data['feature_breakdown'].items(),
                key=lambda x: x[1]['total_cost'],
                reverse=True
            )
        ])

        provider_text = "\n".join([
            f"{p['provider']}: {p['total_tokens']:,} tokens, "
            f"${p['total_cost']}, {p['calls']} calls"
            for p in data['providers']
        ]) if data['providers'] else "No provider data yet"

        prompt = f"""AI token usage and cost intelligence report.

Month to date token spend: ${data['total_cost_mtd']}
Total tokens used: {data['total_tokens_mtd']:,}
Projected month end cost: ${data['projected_monthly_cost']}
Days elapsed: {data['days_elapsed']} of {data['days_elapsed'] + data['days_remaining']}
Most expensive feature: {data['most_expensive_feature']}
Most efficient model: {data['most_efficient_model']}

Provider breakdown:
{provider_text}

Feature breakdown by cost:
{feature_text}

Write the token intelligence summary covering:
1. Total AI spend this month and projection
2. Which features cost the most and why
3. Most efficient model recommendation
4. One action to optimize token costs
Frame this in the context of the new Tokenomics Foundation standards
where tokens are the new unit of enterprise technology spend."""

        say(call_claude(prompt, feature='token_intelligence'))

    else:
        say("Pulling your AWS cost data, give me a second...")
        costs = get_aws_costs()
        cost_text = "\n".join(
            [f"{service}: ${amount}" for service, amount in costs.items()]
        )
        prompt = f"""AWS cost analysis for the last 30 days.

Spend by service:
{cost_text}

Write the cost analysis covering top 3 cost drivers, anything unusual, and one specific action for each."""
        say(call_claude(prompt, feature='cost_analysis'))


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
    scheduler.add_job(
        check_and_alert_incidents,
        'interval',
        minutes=15
    )
    scheduler.add_job(
        check_expiring_reservations,
        'cron',
        day_of_week='mon',
        hour=8,
        minute=30
    )
    scheduler.start()
    print("Weekly digest scheduled for Mondays at 8am")
    print("Anomaly checks scheduled every 6 hours")
    print("Incident checks scheduled every 15 minutes")
    print("Reservation expiry checks scheduled for Mondays at 8:30am")

    handler = SocketModeHandler(
        app, os.environ["SLACK_APP_TOKEN"]
    )
    handler.start()