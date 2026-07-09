import os
import re
from botbuilder.core import ActivityHandler, TurnContext, MessageFactory
from botbuilder.schema import Activity, ActivityTypes
from dotenv import load_dotenv

load_dotenv()


class OpsBeaconTeamsBot(ActivityHandler):

    async def on_message_activity(self, turn_context: TurnContext):
        text = turn_context.activity.text or ''
        text = re.sub(r'<at>[^<]+</at>', '', text).strip().lower()
        print(f"Teams message received: {text}")

        response = await self.route_intent(text, turn_context)
        await turn_context.send_activity(MessageFactory.text(response))

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(MessageFactory.text(
                    "Hi I am OpsBeacon, your AI FinOps and InfraOps coworker.\n\n"
                    "Try asking me:\n"
                    "- daily standup\n"
                    "- security score\n"
                    "- finops score\n"
                    "- find idle resources\n"
                    "- prepare MBR\n\n"
                    "Your cloud. Always watched."
                ))

    async def route_intent(self, text: str, turn_context: TurnContext) -> str:
        from app import classify_intent, call_claude
        from aws_costs import get_aws_costs, get_cost_anomalies, get_savings_recommendations, get_forecast_recalculation
        from aws_compliance import get_untagged_resources, get_policy_violations, get_egress_anomalies, get_shadow_ai, get_security_cost_tradeoffs
        from idle_resources import get_all_idle_resources
        from security_score import calculate_security_cost_score, format_score_for_slack
        from finops_score import calculate_finops_score, format_finops_score_for_slack
        from actions_dashboard import get_open_actions, get_actions_summary, format_actions_for_slack
        from timeline_replay import get_full_timeline, format_timeline_for_slack
        from unit_economics import calculate_unit_economics, format_unit_economics_for_slack
        from meeting_prep import generate_meeting_prep
        from executive_digest import generate_executive_digest
        from ai_economics import get_ai_economics_summary, format_ai_summary_for_slack

        intent = classify_intent(text)
        print(f"Teams intent: {intent}")

        if intent == 'standup':
            from aws_costs import get_daily_standup_data
            from aws_compliance import get_security_cost_tradeoffs
            from aws_costs import get_cost_anomalies, get_savings_recommendations
            from aws_reservations import get_expiring_reservations

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

Write the standup report covering yesterday spend, month to date, forecast, top risks, and one action.
Start with OpsBeacon Daily Standup header."""
            return call_claude(prompt, feature='standup', show_cost=False)

        elif intent == 'security_score':
            score_data = calculate_security_cost_score()
            return format_score_for_slack(score_data)

        elif intent == 'finops_score':
            score_data = calculate_finops_score()
            return format_finops_score_for_slack(score_data)

        elif intent == 'idle_resources':
            data = get_all_idle_resources()
            summary_parts = []
            if data['old_snapshots']:
                summary_parts.append(
                    f"Old snapshots ({len(data['old_snapshots'])}):\n" +
                    "\n".join([f"  {r['id']} [{r['region']}]: {r['age_days']} days - ${r['monthly_cost']}/mo"
                               for r in data['old_snapshots']]))
            if data['idle_ec2']:
                summary_parts.append(
                    f"Idle EC2 ({len(data['idle_ec2'])}):\n" +
                    "\n".join([f"  {r['name']} ({r['id']}) [{r['region']}]: {r['avg_cpu']}% CPU"
                               for r in data['idle_ec2']]))
            if not summary_parts:
                summary_parts.append("No idle resources found across any region.")
            resources_text = "\n\n".join(summary_parts)
            prompt = f"""Idle resource report.

{resources_text}

Total monthly waste: ${data['total_monthly_waste']}
Regions scanned: {', '.join(data['regions_scanned'])}

Write the idle resource summary covering total waste, findings, and cleanup commands.
Start with IDLE RESOURCE REPORT header."""
            return call_claude(prompt, feature='idle_resources', show_cost=False)

        elif intent == 'executive':
            return generate_executive_digest()

        elif intent == 'meeting_prep':
            if 'qbr' in text:
                meeting_type = 'qbr'
            elif 'weekly' in text:
                meeting_type = 'weekly'
            else:
                meeting_type = 'mbr'
            prep = generate_meeting_prep(meeting_type)
            return prep['content']

        elif intent == 'actions':
            open_actions = get_open_actions()
            summary = get_actions_summary()
            header = (
                f"OpsBeacon Actions Dashboard\n\n"
                f"Open: {summary['total_open']} | Completed: {summary['total_completed']}\n"
                f"Savings at stake: ${summary['savings_at_stake']}/mo\n"
                f"Savings realized: ${summary['savings_realized']}/mo\n\n"
            )
            return header + format_actions_for_slack(open_actions)

        elif intent == 'forecast':
            data = get_forecast_recalculation()
            if not data:
                return "Not enough data to generate forecast yet."
            trend_sign = "+" if data['trend_pct'] > 0 else ""
            prompt = f"""AWS three tier cost forecast.

Month end: ${data['month_end_forecast']} (spent ${data['mtd_spend']}, {data['days_remaining_month']} days left)
Quarter end: ${data['quarter_forecast']} (spent ${data['qtd_spend']}, {data['days_remaining_quarter']} days left)
Annual: ${data['annual_forecast']} (spent ${data['ytd_spend']}, {data['days_remaining_year']} days left)
Trend: {data['trend_direction']} ({trend_sign}{data['trend_pct']}% vs prior week)

Write the forecast covering all three tiers and one action. Start with FORECAST header."""
            return call_claude(prompt, feature='forecast', show_cost=False)

        elif intent == 'savings':
            data = get_savings_recommendations()
            rec_text = "\n".join([
                f"{r['service']}: save ${r['savings_monthly']}/mo with {r['recommendation']}"
                for r in data['recommendations']
            ])
            prompt = f"""Savings recommendations.

{rec_text}
Total: ${data['total_monthly_savings']}/mo (${data['total_annual_savings']}/yr)

Write the savings summary covering each opportunity and which to act on first."""
            return call_claude(prompt, feature='savings', show_cost=False)

        elif intent == 'ai_economics':
            data = get_ai_economics_summary()
            return format_ai_summary_for_slack(data)

        elif intent == 'unit_economics':
            data = calculate_unit_economics()
            return format_unit_economics_for_slack(data)

        elif intent == 'timeline':
            days = 7 if 'week' in text else 90 if 'quarter' in text else 30
            events = get_full_timeline(days=days)
            if not events:
                return "No events recorded in that period."
            return format_timeline_for_slack(events, title=f"Timeline - last {days} days")

        elif intent == 'compliance':
            untagged = get_untagged_resources()
            violations = get_policy_violations()
            shadow_ai = get_shadow_ai()
            prompt = f"""Compliance check.

Untagged: {untagged if untagged else 'None'}
Violations: {violations if violations else 'None'}
Shadow AI: {shadow_ai if shadow_ai else 'None'}

Write the compliance summary."""
            return call_claude(prompt, feature='compliance', show_cost=False)

        elif intent == 'security_tradeoffs':
            data = get_security_cost_tradeoffs()
            findings_text = "\n".join([
                f"{f['service']}: {f['status']} - ${f['monthly_cost_to_enable']}/mo to fix"
                for f in data['findings']
            ])
            prompt = f"""Security cost tradeoffs.

{findings_text}
Total to fix: ${data['total_monthly_cost_to_fix']}/mo

Write the security summary covering risks and priority order."""
            return call_claude(prompt, feature='security_tradeoffs', show_cost=False)

        else:
            costs = get_aws_costs()
            cost_text = "\n".join([f"{s}: ${a}" for s, a in costs.items()])
            prompt = f"""You are Beacon, AI FinOps and InfraOps coworker.

User asked: "{text}"

AWS spend context:
{cost_text}

Answer directly. If the question maps to a Beacon capability tell them what to ask.
Beacon covers: cost analysis, security scoring, FinOps scoring, forecasting, savings, idle resources, IaC generation, AI economics, meeting prep, executive digest, timeline replay, unit economics, open actions."""
            return call_claude(prompt, feature='general', show_cost=False)