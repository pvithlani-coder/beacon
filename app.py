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
from iac_generator import get_iac_recommendations
from executive_digest import generate_executive_digest
from security_score import calculate_security_cost_score, format_score_for_slack
from playbook_library import capture_recommendation, get_playbook_summary, search_playbooks
from feedback_log import log_feature_request, get_feature_summary
from ai_economics import get_ai_economics_summary, get_ai_cost_rca, get_project_detail, format_ai_summary_for_slack, get_optimization_recommendation
from telemetry import record_cost_pattern, record_action, get_cross_customer_anomalies, get_behavioral_recommendations, get_telemetry_summary
from actions_dashboard import create_action, update_action_status, assign_action, get_open_actions, get_actions_summary, format_actions_for_slack, auto_create_from_beacon

load_dotenv()

AWS_REGION = 'us-east-2'

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
    print("Starting weekly digest...")
    costs = get_aws_costs()
    cost_text = "\n".join(
        [f"{service}: ${amount}" for service, amount in costs.items()])
    total = sum(costs.values())
    prompt = f"""Weekly Monday morning cost digest for the team.

AWS spend for the last 30 days by service:
{cost_text}

Total spend: ${round(total, 2)}

Write the Monday digest covering:
1. Total spend and biggest cost driver
2. One unusual finding
3. One specific action to save money this week
4. Offer to generate a fix script"""

    response = call_claude(prompt, feature='weekly_digest')
    channel = os.environ["SLACK_DIGEST_CHANNEL"]
    app.client.chat_postMessage(channel=channel, text=response)
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

    # Record anomaly patterns for cross-customer detection
    for anomaly in anomalies:
        record_cost_pattern(
            customer_id='default',
            service=anomaly['service'],
            daily_spend=anomaly['latest'],
            historical_avg=anomaly['average'],
            is_anomaly=True
        )
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

Root cause investigation:
{rca_summary}

Write the alert covering what spiked, root cause, specific resources, and one immediate action.
Start with a warning emoji and COST SPIKE RCA header."""

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
        f"{r['type']}: {r['instance_type']} expires {r['end_date']} in {r['days_remaining']} days"
        for r in urgent
    ])
    prompt = f"""Urgent reservation expiry alert.

These AWS reserved instances are expiring within 30 days:
{res_text}

Write the alert covering what is expiring, cost impact, and immediate action to renew.
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

    prompt = f"""Daily FinOps standup report.

Date: {standup['date']}
Yesterday: ${standup['yesterday_spend']} ({wow_sign}{standup['wow_change']}% vs last week)
Top service: {standup['top_service_yesterday']} at ${standup['top_service_amount']}
Month to date: ${standup['mtd_spend']} (Day {standup['days_elapsed']} of {standup['days_in_month']})
Burn rate: ${standup['daily_burn_rate']}/day
Forecast: ${standup['projected_month_end']}
Anomalies: {len(anomalies)}
Security gaps: {disabled_security}
Expiring reservations: {urgent_reservations}
Savings available: ${savings['total_monthly_savings']}/mo

Format EXACTLY like this:

OpsBeacon Daily Standup - {standup['date']}

Yesterday: ${standup['yesterday_spend']} ({wow_sign}{standup['wow_change']}% vs last week) - top: {standup['top_service_yesterday']}
Month to Date: ${standup['mtd_spend']} - Day {standup['days_elapsed']} of {standup['days_in_month']}, burning ${standup['daily_burn_rate']}/day
Forecast: ${standup['projected_month_end']} projected month end
Top Risks: [list each risk with a dash]
Top Opportunity: [biggest savings with dollar amount]
Open Actions: [one specific action today]

---
[One motivating closing sentence.]"""

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
    channel = os.environ.get(
        "SLACK_EXEC_CHANNEL", os.environ["SLACK_DIGEST_CHANNEL"])
    app.client.chat_postMessage(channel=channel, text=digest)
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
        prompt = f"""Compliance check results.

Untagged Resources: {untagged if untagged else 'None found'}
Policy Violations: {violations if violations else 'None found'}
Egress Anomalies: {anomalies if anomalies else 'None found'}
Shadow AI Services: {shadow_ai if shadow_ai else 'None found'}

Write the compliance summary covering findings and priority actions."""
        say(call_claude(prompt, feature='compliance_check'))

    elif 'forecast' in text or 'end of month' in text or 'bill look' in text or 'quarter' in text or 'annual' in text:
        say("Calculating your forecasts...")
        data = get_forecast_recalculation()
        if not data:
            say("Not enough data to generate forecast yet.")
            return
        trend_sign = "+" if data['trend_pct'] > 0 else ""
        prompt = f"""AWS three tier cost forecast.

Daily burn rate: ${data['daily_burn_rate']}/day
Trend: {data['trend_direction']} ({trend_sign}{data['trend_pct']}% vs prior week)
Month end forecast: ${data['month_end_forecast']} (spent ${data['mtd_spend']}, {data['days_remaining_month']} days left)
Quarter end forecast: ${data['quarter_forecast']} (spent ${data['qtd_spend']}, {data['days_remaining_quarter']} days left)
Annual forecast: ${data['annual_forecast']} (spent ${data['ytd_spend']}, {data['days_remaining_year']} days left)

Write the forecast covering all three tiers, trend context, and one action.
Start with FORECAST RECALCULATION header."""
        say(call_claude(prompt, feature='forecast_recalculation'))

    elif 'savings' in text or 'save money' in text or 'reserved' in text:
        say("Analyzing your savings opportunities...")
        data = get_savings_recommendations()
        rec_text = "\n".join([
            f"{r['service']}: ${r['current_monthly']}/mo, save ${r['savings_monthly']}/mo with {r['recommendation']}"
            for r in data['recommendations']
        ])
        prompt = f"""AWS savings recommendations.

{rec_text}
Total monthly savings: ${data['total_monthly_savings']}
Total annual savings: ${data['total_annual_savings']}

Write the savings summary covering total opportunity, each recommendation, which to act on first."""
        say(call_claude(prompt, feature='savings_recommendations'))

    elif 'security score' in text or 'opsbeacon score' in text or 'my score' in text:
        say("Calculating your OpsBeacon Security Cost Score...")
        score_data = calculate_security_cost_score()
        say(format_score_for_slack(score_data))

    elif 'security' in text or 'guardduty' in text or 'cloudtrail' in text or 'tradeoff' in text:
        say("Analyzing your security posture and cost tradeoffs...")
        data = get_security_cost_tradeoffs()
        findings_text = "\n".join([
            f"{f['service']}: {f['status']} - Risk: {f['risk']} - Cost to fix: ${f['monthly_cost_to_enable']}/mo"
            for f in data['findings']
        ])
        prompt = f"""AWS security cost tradeoff analysis.

{findings_text}
Total to fix: ${data['total_monthly_cost_to_fix']}/mo
Disabled: {len(data['disabled_services'])}

Write the security summary covering risks, total cost to fix, priority order."""
        for finding in data['disabled_services']:
            create_action(
                title=f"Enable {finding['service']}",
                description=finding['recommendation'],
                category='security',
                estimated_savings=finding['monthly_cost_to_enable'],
                due_days=7,
                priority='high',
                source_feature='security_tradeoffs'
            )
        say(call_claude(prompt, feature='security_tradeoffs'))

    elif 'incident' in text or 'pagerduty' in text or 'active alert' in text or 'show alert' in text:
        say("Pulling active incidents and analyzing cost impact...")
        analyses = get_all_incident_analyses()
        if not analyses:
            say("No active incidents in PagerDuty right now.")
            return
        for a in analyses:
            incident = a['incident']
            say(f"{a['analysis']}\n\nLink: {incident['url']}")

    elif 'unmanaged' in text or 'accounts' in text or 'organization' in text:
        say("Scanning your AWS organization for unmanaged accounts...")
        accounts = get_unmanaged_accounts()
        if not accounts:
            say("All AWS accounts are properly managed and tagged.")
            return
        accounts_text = "\n".join([
            f"Account: {a['account_name']} ({a['account_id']})\nEmail: {a['email']}\nSpend: ${a['monthly_spend']}\nIssues: {', '.join(a['issues'])}"
            for a in accounts
        ])
        prompt = f"""AWS organization account governance findings.

{accounts_text}

Write the summary covering governance issues, risks, and priority actions."""
        say(call_claude(prompt, feature='unmanaged_accounts'))

    elif 'fix tags' in text or 'apply tags' in text:
        say("Analyzing your AWS accounts and preparing tag fixes...")
        accounts = get_unmanaged_accounts()
        if not accounts:
            say("All accounts are properly tagged.")
            return
        for account in accounts:
            has_tag_issues = any('Missing' in i for i in account['issues'])
            if has_tag_issues:
                environment = 'production'
                if any(w in account['account_name'].lower()
                       for w in ['dev', 'test', 'staging', 'sandbox']):
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
                    f"I can apply these tags to *{account['account_name']}* ({account['account_id']}):\n"
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
            pending['account_id'], pending['email'], pending['account_name'])
        if result['success']:
            say(
                f"Tags applied successfully to {pending['account_name']}\n"
                f"Owner: {result['tags_applied']['Owner']}\n"
                f"Environment: {result['tags_applied']['Environment']}\n"
                f"CostCenter: {result['tags_applied']['CostCenter']}"
            )
            del pending_tag_fixes[user_id]
            # Record confirmed action for behavioral learning
            record_action(
                customer_id='default',
                feature='tag_fixing',
                action_type='apply_tags',
                recommendation=f"Apply tags to {pending['account_name']}",
                confirmed=True,
                outcome='success'
            )

            # Check if behavioral automation is ready
            recs = get_behavioral_recommendations('default')
            auto_ready = [r for r in recs if r['automation_ready']]
            if auto_ready:
                say(
                    f"I notice you always approve tag fixes. "
                    f"Want me to apply tags automatically next time without asking? "
                    f"Reply *automate tags* to enable."
                )
        else:
            say(f"Failed to apply tags: {result['error']}")

    elif 'expir' in text or 'reservation expir' in text:
        say("Checking for expiring reserved instances and savings plans...")
        reservations = get_expiring_reservations()
        if not reservations:
            say("No reserved instances or savings plans expiring in the next 90 days.")
            return
        res_text = "\n".join([
            f"{r['type']}: {r['instance_type']} x{r['count']} expires {r['end_date']} ({r['days_remaining']} days) Urgency: {r['urgency']}"
            for r in reservations
        ])
        prompt = f"""AWS reserved instance expiry analysis.

{res_text}

Write the expiry summary covering what expires, cost impact, renewal priority, and next steps."""
        say(call_claude(prompt, feature='reservation_expiry'))

    elif 'ai economics' in text or 'ai spend' in text or 'ai projects' in text or 'ai efficiency' in text or 'ai cost' in text or 'legal copilot' in text or 'support bot' in text or 'sales assistant' in text or 'research agent' in text or 'document search' in text or ('ai' in text and 'rise' in text) or ('ai' in text and 'why' in text) or ('ai' in text and 'detail' in text):
        if 'why' in text or 'rise' in text or 'increase' in text:
            say("Analyzing why AI costs are rising...")
            drivers = get_ai_cost_rca()
            if not drivers:
                say("No significant AI cost increases detected.")
                return
            driver_text = "\n\n".join([
                f"*{d['project']}* ({d['team']})\n"
                f"Increase: +{d['trend_pct']}% (+${d['daily_increase']}/day)\n"
                f"Causes: {', '.join(d['causes'])}\n"
                f"Fixes: {', '.join(d['recommendation'])}"
                for d in drivers
            ])
            prompt = f"""AI cost increase root cause analysis.

{driver_text}

Write the AI RCA covering which projects are driving increases, root causes, and priority fixes.
Frame in Tokenomics Foundation context. Start with AI COST RCA header."""
            say(call_claude(prompt, feature='ai_economics_rca'))

        elif 'detail' in text or 'legal' in text or 'support bot' in text or 'research agent' in text or 'document search' in text or 'sales assistant' in text:
            project_keywords = ['legal', 'support', 'sales', 'research', 'document']
            project_name = next((kw for kw in project_keywords if kw in text), None)
            if project_name:
                project = get_project_detail(project_name)
                if project:
                    recs = "\n".join([f"  {i+1}. {r}" for i, r in enumerate(get_optimization_recommendation(project))])
                    say(
                        f"*AI Project Detail: {project['name']}*\n\n"
                        f"Team: {project['team']}\n"
                        f"Monthly Spend: ${project['monthly_spend']:,.0f}\n"
                        f"Efficiency Score: {project['efficiency_score']}/100\n"
                        f"Status: {project['status'].upper()}\n"
                        f"Model: {project['model_primary']}\n"
                        f"Cost Trend: {'+' if project['cost_trend_pct'] > 0 else ''}{project['cost_trend_pct']}%\n"
                        f"Duplicate Prompts: {project['duplicate_prompt_pct']}%\n\n"
                        f"*Recommendations:*\n{recs}"
                    )
                else:
                    say("Project not found. Try: show AI projects")
            else:
                say("Which project? Try: show Legal Copilot detail")

        else:
            say("Analyzing your AI project economics...")
            data = get_ai_economics_summary()
            prompt = f"""AI Economics report.

Total monthly AI spend: ${data['total_monthly_spend']:,.2f}
Projects: {data['project_count']}
Critical: {len(data['critical_projects'])}
Waste: ${data['waste_detected']:,.2f}/mo
ROI: {data['overall_roi_multiple']}x

Projects: {', '.join([f"{p['name']} ${p['monthly_spend']:,.0f} score {p['efficiency_score']}" for p in data['projects_by_spend']])}

Write the AI economics summary covering investment, ROI, efficiency gaps, and top optimization.
Frame in Tokenomics Foundation context. Start with AI ECONOMICS SUMMARY header."""
            say(call_claude(prompt, feature='ai_economics'))
            say(format_ai_summary_for_slack(data))

    elif 'token spend' in text or 'token usage' in text or 'tokenomics' in text or 'token intelligence' in text:
        say("Analyzing your AI token usage and costs...")
        data = get_token_intelligence()
        feature_text = "\n".join([
            f"{feature}: {stats['calls']} calls, {stats['total_tokens']:,} tokens, ${stats['total_cost']}"
            for feature, stats in sorted(
                data['feature_breakdown'].items(),
                key=lambda x: x[1]['total_cost'], reverse=True)
        ])
        prompt = f"""AI token usage intelligence.

Month to date spend: ${data['total_cost_mtd']}
Total tokens: {data['total_tokens_mtd']:,}
Projected monthly: ${data['projected_monthly_cost']}
Most expensive feature: {data['most_expensive_feature']}

Feature breakdown:
{feature_text}

Write the token summary covering spend, projection, most expensive features, and optimization action.
Frame in Tokenomics Foundation context."""
        say(call_claude(prompt, feature='token_intelligence'))

    elif 'rca' in text or 'root cause' in text or 'explain spike' in text:
        say("Running root cause analysis on your AWS costs...")
        rca_results = run_cost_rca()
        rca_text = "\n\n".join([
            f"Service: {r['service']}\nSpend: ${r['current_spend']} vs avg ${r['historical_avg']}\n"
            f"Findings: " + " | ".join([f"[{f['confidence']}] {f['cause']}" for f in r['findings']])
            for r in rca_results
        ])
        prompt = f"""Cost spike root cause analysis.

{rca_text}

Write the RCA covering which services have unusual patterns, root causes, responsible resources, and immediate actions.
Start with COST RCA header."""
        say(call_claude(prompt, feature='cost_rca'))

    elif 'idle' in text or 'waste' in text or 'orphan' in text or 'unused' in text:
        say("Scanning for idle and wasteful resources...")
        data = get_all_idle_resources()

        for snap in data['old_snapshots']:
            capture_recommendation(
                category='waste_reduction',
                issue=f"Snapshot {snap['id']} is {snap['age_days']} days old",
                recommendation=f"Delete snapshot to save ${snap['monthly_cost']}/mo",
                fix_command=f"aws ec2 delete-snapshot --snapshot-id {snap['id']} --region {AWS_REGION}",
                estimated_savings=snap['monthly_cost']
            )

        summary_parts = []
        if data['idle_ec2']:
            summary_parts.append(f"Idle EC2 ({len(data['idle_ec2'])}):\n" +
                "\n".join([f"  {r['name']} ({r['id']}): {r['avg_cpu']}% CPU - saves ${r['estimated_monthly_savings']}/mo" for r in data['idle_ec2']]))
        if data['orphan_ebs']:
            summary_parts.append(f"Orphan EBS ({len(data['orphan_ebs'])}):\n" +
                "\n".join([f"  {r['id']}: {r['size_gb']}GB, {r['age_days']} days - ${r['monthly_cost']}/mo" for r in data['orphan_ebs']]))
        if data['unused_eips']:
            summary_parts.append(f"Unused EIPs ({len(data['unused_eips'])}):\n" +
                "\n".join([f"  {r['ip']}: ${r['monthly_cost']}/mo" for r in data['unused_eips']]))
        if data['idle_rds']:
            summary_parts.append(f"Idle RDS ({len(data['idle_rds'])}):\n" +
                "\n".join([f"  {r['id']}: {r['avg_connections']} connections - ${r['monthly_cost']}/mo" for r in data['idle_rds']]))
        if data['old_snapshots']:
            summary_parts.append(f"Old snapshots ({len(data['old_snapshots'])}):\n" +
                "\n".join([f"  {r['id']}: {r['size_gb']}GB, {r['age_days']} days - ${r['monthly_cost']}/mo" for r in data['old_snapshots']]))
        if not any([data['idle_ec2'], data['orphan_ebs'], data['unused_eips'], data['idle_rds'], data['old_snapshots']]):
            summary_parts.append("No idle or wasteful resources found.")

        resources_text = "\n\n".join(summary_parts)
        prompt = f"""Idle and wasteful AWS resource report.

{resources_text}

Total monthly waste: ${data['total_monthly_waste']}
Annual waste: ${data['total_annual_waste']}

Write the idle resource summary covering total waste, each category, cleanup priority, and specific commands.
Start with IDLE RESOURCE REPORT header."""
        say(call_claude(prompt, feature='idle_resources'))

    elif 'standup' in text or 'daily report' in text or 'morning report' in text:
        say("Generating your daily FinOps standup...")
        send_daily_standup()

    elif 'executive' in text or 'cfo' in text or 'board' in text or 'exec digest' in text:
        say("Preparing your executive brief...")
        digest = generate_executive_digest()
        say(digest)

    elif 'team summary' in text or 'team spend' in text or 'engineering team' in text:
        say("Generating engineering team summaries...")
        data = get_all_team_summaries()
        if data['status'] == 'no_team_tags':
            say("No Team tags found. Add a Team tag to your resources to enable per-team cost summaries.")
            return
        teams_text = "\n".join([
            f"{s['team']}: ${s['current_week']} ({s['change_sign']}{s['change_pct']}% vs last week) [{s['trend']}]"
            for s in data['summaries']
        ])
        prompt = f"""Engineering team cost summaries.

Week: {data['week_start']} to {data['week_end']}
Total: ${data['total_current']} vs ${data['total_prior']} last week

{teams_text}

Generate internal summary and ready-to-send team messages for any team with >10% change."""
        say(call_claude(prompt, feature='team_summaries'))

    elif 'terraform' in text or 'iac' in text or 'generate code' in text or 'fix script' in text:
        say("Generating IaC for your top cost optimization opportunities...")
        recommendations = get_iac_recommendations()
        if not recommendations:
            say("No IaC recommendations right now. Your environment looks clean.")
            return
        for rec in recommendations:
            code_block = f"```hcl\n{rec['code'][:1500]}\n```"
            if len(rec['code']) > 1500:
                code_block += f"\n_(truncated - full file is {len(rec['code'])} chars)_"
            say(f"*IaC Generated: {rec['filename']}*\n\n*Description:* {rec['description']}\n*Savings:* {rec['estimated_savings']}\n\n{code_block}\n\n_Review carefully. Run terraform plan first._")

    elif 'playbook' in text or 'library' in text:
        if 'search' in text:
            query = text.replace('search playbook', '').replace('search library', '').strip()
            results = search_playbooks(query, validated_only=False)
            if not results:
                say(f"No playbooks found for that query. Library grows as Beacon validates fixes.")
                return
            results_text = "\n".join([
                f"*{r['id']}* [{r['category']}] {r['issue'][:60]}\n  Fix: {r['recommendation'][:80]}\n  Validated: {'Yes' if r['validated'] else 'Pending'}"
                for r in results[:5]
            ])
            say(f"*Playbook Search Results*\n\n{results_text}")
        else:
            summary = get_playbook_summary()
            if summary['total'] == 0:
                say("Playbook library is empty. It builds automatically as Beacon makes and validates recommendations.")
                return
            top_text = "\n".join([
                f"  *{p['id']}* {p['issue'][:50]} - used {p['times_used']}x - saves ${p['estimated_savings']}/mo"
                for p in summary['top_playbooks']
            ]) if summary['top_playbooks'] else "None yet"
            cat_text = "\n".join([
                f"  {cat}: {counts['validated']}/{counts['total']} validated"
                for cat, counts in summary['categories'].items()
            ])
            say(
                f"*OpsBeacon Playbook Library*\n\n"
                f"Total: {summary['total']} | Validated: {summary['validated']} | Pending: {summary['pending']}\n"
                f"Savings documented: ${summary['total_savings_captured']}/mo\n\n"
                f"*By category:*\n{cat_text}\n\n"
                f"*Most used:*\n{top_text}"
            )

    elif 'feature requests' in text or 'feedback log' in text or 'what are people asking' in text:
        summary = get_feature_summary()
        if summary['total'] == 0:
            say("No feature requests logged yet.")
            return
        recent_text = "\n".join([
            f"- {r['timestamp'][:10]}: {r['query'][:80]}"
            for r in summary['recent']
        ])
        top_themes = ", ".join([
            f"{t['word']} ({t['count']}x)" for t in summary['top_queries']
        ]) if summary['top_queries'] else "None yet"
        say(
            f"*Feature Request Summary*\n\n"
            f"Total: {summary['total']} | New: {summary['new']} | Reviewed: {summary['reviewed']}\n\n"
            f"*Top themes:* {top_themes}\n\n"
            f"*Recent:*\n{recent_text}"
        )

    elif 'open actions' in text or 'action dashboard' in text or 'show actions' in text or 'my actions' in text:
        say("Pulling your open actions dashboard...")
        open_actions = get_open_actions()
        summary = get_actions_summary()

        header = (
            f"*OpsBeacon Actions Dashboard*\n\n"
            f"Open: {summary['total_open']} | "
            f"In Progress: {summary['total_in_progress']} | "
            f"Completed: {summary['total_completed']}\n"
            f"Savings at stake: ${summary['savings_at_stake']}/mo "
            f"(${summary['annual_savings_at_stake']}/yr)\n"
            f"Savings realized: ${summary['savings_realized']}/mo\n"
        )

        if summary['overdue_count'] > 0:
            header += f"*{summary['overdue_count']} OVERDUE actions need attention*\n"
        if summary['aging_count'] > 0:
            header += f"*{summary['aging_count']} actions aging past 14 days*\n"

        say(header)
        say(format_actions_for_slack(open_actions))

    elif 'done act' in text or 'mark done' in text or 'completed act' in text:
        words = text.upper().split()
        action_id = next(
            (w for w in words if w.startswith('ACT-')), None)

        if not action_id:
            say("Please specify an action ID. Example: done ACT-0001")
            return

        action = update_action_status(action_id, 'completed', note='Marked done via Slack')

        if action:
            from telemetry import record_action
            record_action(
                customer_id='default',
                feature=action.get('source_feature', 'general'),
                action_type=action['category'],
                recommendation=action['title'],
                confirmed=True,
                outcome='success'
            )
            say(
                f"ACT-{action_id.replace('ACT-', '')} marked complete.\n"
                f"Savings realized: ${action['estimated_savings']}/mo\n"
                f"Well done. Run `show open actions` to see remaining items."
            )
        else:
            say(f"Action {action_id} not found. Run `show open actions` to see valid IDs.")

    elif 'assign act' in text or 'assign action' in text:
        words = text.split()
        action_id = next(
            (w.upper() for w in words if w.upper().startswith('ACT-')), None)
        owner = next(
            (w.replace('@', '') for w in words
             if w.startswith('@') and not w.startswith('@beacon')), None)

        if not action_id or not owner:
            say("Please specify action and owner. Example: assign ACT-0001 to @john")
            return

        action = assign_action(action_id, owner)
        if action:
            say(f"{action_id} assigned to @{owner}. They will be responsible for completing this by {action['due_date']}.")
        else:
            say(f"Action {action_id} not found.")

    elif 'dismiss act' in text or 'dismiss action' in text:
        words = text.upper().split()
        action_id = next(
            (w for w in words if w.startswith('ACT-')), None)

        if not action_id:
            say("Please specify an action ID. Example: dismiss ACT-0001")
            return

        action = update_action_status(
            action_id, 'dismissed', note='Dismissed via Slack')
        if action:
            say(f"{action_id} dismissed. Run `show open actions` to see remaining items.")
        else:
            say(f"Action {action_id} not found.")

    elif 'telemetry' in text or 'network effect' in text or 'cross customer' in text or 'automate' in text:
        user_id = event.get('user', 'default')
        summary = get_telemetry_summary()
        recs = get_behavioral_recommendations('default')

        auto_text = "\n".join([
            f"  - {r['suggestion']} (confidence: {r['confidence']}%)"
            for r in recs
        ]) if recs else "  None yet. Keep using Beacon to build patterns."

        say(
            f"*OpsBeacon Intelligence Summary*\n\n"
            f"*Network Effect Data:*\n"
            f"  Patterns recorded: {summary['total_patterns_recorded']}\n"
            f"  Anomalies tracked: {summary['total_anomalies']}\n"
            f"  Customers contributing: {summary['customers_tracked']}\n"
            f"  Cross-customer signal threshold: {summary['cross_customer_signal_threshold']} customers\n\n"
            f"*Behavioral Automation Ready:*\n"
            f"{auto_text}\n\n"
            f"_As more customers join OpsBeacon the network effect strengthens. "
            f"At 10 customers cross-customer anomaly detection activates automatically._"
        )

    else:
        say("Let me look into that...")
        user_id = event.get('user', 'unknown')
        log_feature_request(text, user_id, response_type='general_query')

        costs = get_aws_costs()
        cost_text = "\n".join(
            [f"{service}: ${amount}" for service, amount in costs.items()])

        prompt = f"""You are Beacon, an AI FinOps and InfraOps coworker.

The user asked: "{text}"

Current AWS spend context:
{cost_text}

Beacon's capabilities:
- Cost analysis, anomaly detection, RCA
- Compliance, tagging, shadow AI detection
- Security cost tradeoffs and Security Cost Score
- Month, quarter, and annual forecasting
- Savings recommendations and reservation management
- PagerDuty incident analysis with cost impact
- Unmanaged account detection and tag fixing
- AI Economics intelligence and token tracking
- Idle resource detection
- IaC and Terraform generation
- Engineering team summaries
- Executive digest
- Remediation playbook library
- Daily standup and weekly digest

Answer directly. If their question maps to a capability tell them exactly what to ask.
If it is a general FinOps question answer it. If unrelated say so politely."""

        say(call_claude(prompt, feature='general_query'))


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_weekly_digest, 'cron', day_of_week='mon', hour=8, minute=0)
    scheduler.add_job(check_and_alert_anomalies, 'interval', hours=6)
    scheduler.add_job(check_and_alert_incidents, 'interval', minutes=15)
    scheduler.add_job(check_expiring_reservations, 'cron', day_of_week='mon', hour=8, minute=30)
    scheduler.add_job(send_daily_standup, 'cron', hour=8, minute=45)
    scheduler.add_job(send_executive_digest, 'cron', day_of_week='mon', hour=7, minute=30)
    scheduler.start()
    print("Executive digest scheduled for Mondays at 7:30am")
    print("Weekly digest scheduled for Mondays at 8am")
    print("Anomaly checks scheduled every 6 hours")
    print("Incident checks scheduled every 15 minutes")
    print("Reservation expiry checks scheduled for Mondays at 8:30am")
    print("Daily standup scheduled for 8:45am every day")

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()