import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
import anthropic
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from aws_costs import get_aws_costs, get_cost_forecast, get_cost_anomalies, get_savings_recommendations, get_daily_standup_data, get_forecast_recalculation
from aws_compliance import get_untagged_resources, get_policy_violations, get_egress_anomalies, get_shadow_ai, get_security_cost_tradeoffs
from incident_cost_impact import get_all_incident_analyses
from aws_accounts import get_unmanaged_accounts, fix_account_tags
from aws_reservations import get_expiring_reservations
from beacon_config import BEACON_SYSTEM_PROMPT, BEACON_FORMAT
from token_intelligence import get_token_intelligence, log_token_usage
from cost_rca import run_cost_rca
from idle_resources import get_all_idle_resources
from team_summaries import get_all_team_summaries
from iac_generator import get_iac_recommendations, generate_iac_for_finding
from executive_digest import generate_executive_digest

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
    cost_text = "\n".join(
        [f"{service}: ${amount}" for service, amount in costs.items()]
    )
    total = sum(costs.values())
    prompt = f"""Weekly Monday morning cost digest for the team.

AWS spend for the last 30 days by service:
{cost_text}

Total spend: ${round(total, 2)}

Write the Monday digest covering:
1. Total spend and biggest cost driver
2. One unusual or worth investigating finding
3. One specific action to take this week to save money
4. Offer to generate a fix script"""

    response = call_claude(prompt, feature='weekly_digest')
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    result = app.client.chat_postMessage(channel=channel, text=response)
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

    print("Running automatic RCA on anomalies...")
    rca_results = run_cost_rca(anomalies)
    rca_summary = "\n".join([
        f"{r['service']}: " + " | ".join([
            f"[{f['confidence']}] {f['cause']}"
            for f in r['findings']
        ])
        for r in rca_results
    ])

    prompt = f"""Urgent cost anomaly alert with root cause analysis.

These AWS services spiked unexpectedly in the last 24 hours:
{anomaly_text}

Root cause investigation findings:
{rca_summary}

Write the alert covering:
1. What spiked and by how much
2. Root cause identified from the investigation
3. Which specific resources are responsible
4. One immediate action to stop the bleeding

Start with a warning emoji and COST SPIKE RCA header.
Be specific about resource IDs and launch times where available."""

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
        message = f"{analysis}\n\nLink: {incident['url']}"
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


def send_daily_standup():
    print(f"Sending daily standup at {datetime.now()}")

    standup = get_daily_standup_data()
    anomalies = get_cost_anomalies()
    savings = get_savings_recommendations()
    security = get_security_cost_tradeoffs()
    reservations = get_expiring_reservations(days_threshold=30)

    disabled_security = len(security['disabled_services'])
    urgent_reservations = len([r for r in reservations if r['urgency'] == 'HIGH'])
    wow_sign = "+" if standup['wow_change'] > 0 else ""

    prompt = f"""Daily FinOps standup report for the team.

Date: {standup['date']}

SPEND DATA:
Yesterday spend: ${standup['yesterday_spend']} ({wow_sign}{standup['wow_change']}% vs last week)
Top service yesterday: {standup['top_service_yesterday']} at ${standup['top_service_amount']}
Month to date: ${standup['mtd_spend']} (Day {standup['days_elapsed']} of {standup['days_in_month']})
Daily burn rate: ${standup['daily_burn_rate']}/day
Projected month end: ${standup['projected_month_end']}

RISKS:
Cost anomalies detected: {len(anomalies)}
Security services disabled: {disabled_security}
Reserved instances expiring within 30 days: {urgent_reservations}

OPTIMIZATION:
Monthly savings available: ${savings['total_monthly_savings']}
Annual savings available: ${savings['total_annual_savings']}
Top opportunity: {savings['recommendations'][0]['service'] + ' - save $' + str(savings['recommendations'][0]['savings_monthly']) + '/mo' if savings['recommendations'] else 'None identified'}

You MUST format your response EXACTLY like this, no exceptions:

OpsBeacon Daily Standup - {standup['date']}

Yesterday: ${standup['yesterday_spend']} ({wow_sign}{standup['wow_change']}% vs last week) - top service: {standup['top_service_yesterday']}
Month to Date: ${standup['mtd_spend']} - Day {standup['days_elapsed']} of {standup['days_in_month']}, burning ${standup['daily_burn_rate']}/day
Forecast: ${standup['projected_month_end']} projected month end
Top Risks: [list each risk on its own line with a dash]
Top Opportunity: [biggest savings opportunity with specific dollar amount]
Open Actions: [one specific action the team should take today]

---
[One motivating sentence to close.]

Do not add any other sections. Keep risks, opportunity, and actions to one line each."""

    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    response = message.content[0].text
    log_token_usage(
        model="claude-sonnet-4-5",
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        feature='daily_standup'
    )

    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    app.client.chat_postMessage(channel=channel, text=response)
    print(f"Daily standup sent at {datetime.now()}")

def send_executive_digest():
    print(f"Sending executive digest at {datetime.now()}")
    digest = generate_executive_digest()
    channel = os.environ.get("SLACK_EXEC_CHANNEL", os.environ["SLACK_DIGEST_CHANNEL"])
    app.client.chat_postMessage(
        channel=channel,
        text=digest
    )
    print(f"Executive digest sent at {datetime.now()}")

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

    elif 'forecast' in text or 'end of month' in text or 'bill look' in text or 'quarter' in text or 'annual' in text:
        say("Calculating your month, quarter, and annual forecasts...")

        data = get_forecast_recalculation()

        if not data:
            say("Not enough data to generate forecast yet.")
            return

        trend_sign = "+" if data['trend_pct'] > 0 else ""

        prompt = f"""AWS three tier cost forecast recalculation.

As of: {data['today']}
Daily burn rate: ${data['daily_burn_rate']}/day
Trend: {data['trend_direction']} ({trend_sign}{data['trend_pct']}% vs prior week)

MONTH END FORECAST:
Spent so far: ${data['mtd_spend']}
Days remaining: {data['days_remaining_month']}
Projected month end: ${data['month_end_forecast']}

QUARTER END FORECAST:
Spent this quarter: ${data['qtd_spend']}
Days remaining in quarter: {data['days_remaining_quarter']}
Projected quarter end: ${data['quarter_forecast']}

ANNUAL FORECAST:
Spent this year: ${data['ytd_spend']}
Days remaining in year: {data['days_remaining_year']}
Projected annual spend: ${data['annual_forecast']}

Recent 7 day average: ${data['recent_7_day_avg']}/day
Prior 7 day average: ${data['prior_7_day_avg']}/day

Write the forecast summary covering:
1. All three forecast tiers with trend context
2. Whether spend is accelerating, stable, or decelerating and what it means
3. Quarter and annual projections in business terms a CFO would understand
4. One action to take based on the trend direction
Start with FORECAST RECALCULATION header."""

        say(call_claude(prompt, feature='forecast_recalculation'))

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
            message = f"{analysis}\n\nLink: {incident['url']}"
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
                    f"Owner: {proposed_tags['Owner']}\n"
                    f"Environment: {proposed_tags['Environment']}\n"
                    f"CostCenter: {proposed_tags['CostCenter']}\n\n"
                    f"Reply confirm to apply or give me different values."
                )

    elif 'confirm' in text:
        user_id = event.get('user')
        if user_id not in pending_tag_fixes:
            say("No pending tag fixes found. Run fix tags first.")
            return
        pending = pending_tag_fixes[user_id]
        say(f"Applying tags to {pending['account_name']}...")
        result = fix_account_tags(
            pending['account_id'],
            pending['email'],
            pending['account_name']
        )
        if result['success']:
            say(
                f"Tags applied successfully to {pending['account_name']}\n"
                f"Owner: {result['tags_applied']['Owner']}\n"
                f"Environment: {result['tags_applied']['Environment']}\n"
                f"CostCenter: {result['tags_applied']['CostCenter']}"
            )
            del pending_tag_fixes[user_id]
        else:
            say(f"Failed to apply tags: {result['error']}")

    elif 'expir' in text or 'reservation expir' in text or 'savings plan expir' in text:
        say("Checking for expiring reserved instances and savings plans...")
        reservations = get_expiring_reservations()
        if not reservations:
            say("No reserved instances or savings plans expiring in the next 90 days. You are all clear.")
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
Frame this in the context of the Tokenomics Foundation standards
where tokens are the new unit of enterprise technology spend."""
        say(call_claude(prompt, feature='token_intelligence'))

    elif 'rca' in text or 'root cause' in text or 'explain spike' in text or 'why did' in text:
        say("Running root cause analysis on your AWS costs...")
        rca_results = run_cost_rca()
        rca_text = "\n\n".join([
            f"Service: {r['service']}\n"
            f"Current spend: ${r['current_spend']} vs average: ${r['historical_avg']}\n"
            f"Findings:\n" + "\n".join([
                f"  [{f['confidence']}] {f['cause']}: {str(f['detail'])[:200]}"
                for f in r['findings']
            ])
            for r in rca_results
        ])
        prompt = f"""Cost spike root cause analysis for the AWS environment.

Investigation results:
{rca_text}

Write the RCA summary covering:
1. Which services have unusual spend patterns
2. Root causes identified with confidence level
3. Specific resources responsible where found
4. Priority order for remediation with dollar impact
5. One immediate action per finding

Start with COST RCA header.
Be specific with resource IDs, instance types, and timestamps where available.
If no anomalies detected say the environment looks clean and what to watch for."""
        say(call_claude(prompt, feature='cost_rca'))
    
    elif 'idle' in text or 'waste' in text or 'orphan' in text or 'unused' in text:
        say("Scanning for idle and wasteful resources across your AWS environment...")

        data = get_all_idle_resources()

        summary_parts = []

        if data['idle_ec2']:
            summary_parts.append(
                f"Idle EC2 instances ({len(data['idle_ec2'])}):\n" +
                "\n".join([
                    f"  {r['name']} ({r['id']}): {r['avg_cpu']}% avg CPU, saves ${r['estimated_monthly_savings']}/mo"
                    for r in data['idle_ec2']
                ])
            )

        if data['orphan_ebs']:
            summary_parts.append(
                f"Orphan EBS volumes ({len(data['orphan_ebs'])}):\n" +
                "\n".join([
                    f"  {r['id']}: {r['size_gb']}GB, {r['age_days']} days old, ${r['monthly_cost']}/mo"
                    for r in data['orphan_ebs']
                ])
            )

        if data['unused_eips']:
            summary_parts.append(
                f"Unused Elastic IPs ({len(data['unused_eips'])}):\n" +
                "\n".join([
                    f"  {r['ip']}: ${r['monthly_cost']}/mo"
                    for r in data['unused_eips']
                ])
            )

        if data['idle_rds']:
            summary_parts.append(
                f"Idle RDS instances ({len(data['idle_rds'])}):\n" +
                "\n".join([
                    f"  {r['id']}: {r['avg_connections']} avg connections, ${r['monthly_cost']}/mo"
                    for r in data['idle_rds']
                ])
            )

        if data['old_snapshots']:
            summary_parts.append(
                f"Old snapshots 30+ days ({len(data['old_snapshots'])}):\n" +
                "\n".join([
                    f"  {r['id']}: {r['size_gb']}GB, {r['age_days']} days old, ${r['monthly_cost']}/mo"
                    for r in data['old_snapshots']
                ])
            )

        if not any([data['idle_ec2'], data['orphan_ebs'],
                    data['unused_eips'], data['idle_rds'], data['old_snapshots']]):
            summary_parts.append("No idle or wasteful resources found.")

        resources_text = "\n\n".join(summary_parts)

        prompt = f"""Idle and wasteful AWS resource detection results.

{resources_text}

Total monthly waste: ${data['total_monthly_waste']}
Total annual waste: ${data['total_annual_waste']}

Write the idle resource summary covering:
1. Total waste found with monthly and annual impact
2. Each category of waste with specific resource details
3. Priority order for cleanup based on cost and risk
4. Specific commands or steps to eliminate each waste item
5. Quick wins that can be done in under 5 minutes

Start with IDLE RESOURCE REPORT header.
Be specific with resource IDs, ages, and exact savings amounts."""

        say(call_claude(prompt, feature='idle_resources'))

    elif 'team summary' in text or 'team spend' in text or 'engineering team' in text:
        say("Generating engineering team summaries...")

        data = get_all_team_summaries()

        if data['status'] == 'no_team_tags':
            say("No Team tags found in your AWS account. Add a Team tag to your resources to enable per-team cost summaries.")
            return

        teams_text = "\n".join([
            f"{s['team']}: ${s['current_week']} this week "
            f"({s['change_sign']}{s['change_pct']}% vs last week) "
            f"[{s['trend']}]"
            for s in data['summaries']
        ])

        prompt = f"""Engineering team cloud cost summaries for the week.

Week: {data['week_start']} to {data['week_end']}
Total spend: ${data['total_current']} vs ${data['total_prior']} last week

Team breakdown:
{teams_text}

Generate two things:

1. A brief internal summary for the FinOps team showing all teams ranked by spend with trends.

2. For each team that has a significant change (more than 10% week over week), generate a ready-to-send Slack message addressed to that team like this:

---
Dear [Team Name] Team,

Your cloud spend [increased/decreased] [X]% this week to $[amount].

[One sentence explaining the likely cause based on the service and amount]

[One specific action the team should take]

Questions? Reply to this message or reach out to the FinOps team.

OpsBeacon
---

If all teams are stable write a brief all-clear summary instead.
Be specific with dollar amounts and percentages."""

        say(call_claude(prompt, feature='team_summaries'))

    elif 'terraform' in text or 'iac' in text or 'generate code' in text or 'fix script' in text:
        say("Generating IaC code for your top cost optimization opportunities...")

        recommendations = get_iac_recommendations()

        if not recommendations:
            say("No IaC recommendations right now. Your environment looks clean.")
            return

        for rec in recommendations:
            code_block = f"```hcl\n{rec['code'][:1500]}\n```"
            if len(rec['code']) > 1500:
                code_block += f"\n_(truncated - full file is {len(rec['code'])} chars)_"

            message = f"""*IaC Generated: {rec['filename']}*

*Description:* {rec['description']}
*Estimated Savings:* {rec['estimated_savings']}
*Type:* {rec['type'].upper()}

{code_block}

_Review carefully before applying. Run `terraform plan` first._"""

            say(message)

    elif 'executive' in text or 'cfo' in text or 'board' in text or 'exec digest' in text:
        say("Preparing your executive brief...")
        digest = generate_executive_digest()
        say(digest)

    elif 'standup' in text or 'daily report' in text or 'morning report' in text:
        say("Generating your daily FinOps standup...")
        send_daily_standup()

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
    scheduler.add_job(
        send_daily_standup,
        'cron',
        hour=8,
        minute=45
    )
    scheduler.add_job(
        send_executive_digest,
        'cron',
        day_of_week='mon',
        hour=7,
        minute=30
    )
    scheduler.start()
    print("Weekly digest scheduled for Mondays at 8am")
    print("Anomaly checks scheduled every 6 hours")
    print("Incident checks scheduled every 15 minutes")
    print("Reservation expiry checks scheduled for Mondays at 8:30am")
    print("Daily standup scheduled for 8:45am every day")
    print("Executive digest scheduled for Mondays at 7:30am")

    handler = SocketModeHandler(
        app, os.environ["SLACK_APP_TOKEN"]
    )
    handler.start()