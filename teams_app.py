import os
import re
import json as _json
import urllib
import urllib.parse
import urllib.request
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()


async def messages(req: web.Request) -> web.Response:
    try:
        app_id = os.environ.get('MICROSOFT_APP_ID', '')
        app_password = os.environ.get('MICROSOFT_APP_PASSWORD', '')
        body = await req.json()
        print(f"Received activity: {body.get('type')} - {body.get('text', '')}")
        print(f"Full activity: {_json.dumps(body, indent=2)}")
        activity_type = body.get('type', '')
        text = body.get('text', '')

        if activity_type == 'conversationUpdate':
            members = body.get('membersAdded', [])
            recipient_id = body.get('recipient', {}).get('id', '')
            for member in members:
                if member.get('id') != recipient_id:
                    reply = {
                        "type": "message",
                        "text": "Hi I am OpsBeacon, your AI FinOps and InfraOps coworker.\n\nTry: daily standup, security score, finops score, find idle resources, prepare MBR"
                    }
                    return web.json_response(reply, status=200)

        elif activity_type == 'message' and text:
            clean_text = re.sub(r'<at>[^<]+</at>', '', text).strip().lower()
            print(f"Processing: {clean_text}")

            response_text = await process_message(clean_text)

            # Build proper Teams reply
            reply = {
                "type": "message",
                "text": response_text,
                "replyToId": body.get('id', ''),
                "conversation": body.get('conversation', {}),
                "from": body.get('recipient', {}),
                "recipient": body.get('from', {}),
                "serviceUrl": body.get('serviceUrl', ''),
            }

            # Post reply back to Teams using serviceUrl
            service_url = body.get('serviceUrl', '')
            conversation_id = body.get('conversation', {}).get('id', '')

            if service_url and conversation_id:
                import aiohttp
                service_url_clean = service_url.rstrip('/')
                reply_url = f"{service_url_clean}/v3/conversations/{conversation_id}/activities"
                
                # Get access token
                import urllib.request
                import urllib.parse
                import json

                token_url = "https://login.microsoftonline.com/opsbeaconco.onmicrosoft.com/oauth2/v2.0/token"
                token_data = urllib.parse.urlencode({
                    'grant_type': 'client_credentials',
                    'client_id': app_id,
                    'client_secret': app_password,
                    'scope': 'https://api.botframework.com/.default',
                    'tenant': 'opsbeaconco.onmicrosoft.com'
                }).encode()

                token_req = urllib.request.Request(token_url, data=token_data, method='POST')
                token_req.add_header('Content-Type', 'application/x-www-form-urlencoded')
                
                with urllib.request.urlopen(token_req) as token_resp:
                    token_json = _json.loads(token_resp.read())
                    access_token = token_json.get('access_token', '')

                async with aiohttp.ClientSession() as session:
                    headers = {
                        'Authorization': f'Bearer {access_token}',
                        'Content-Type': 'application/json'
                    }
                    async with session.post(reply_url, json=reply, headers=headers) as resp:
                        response_text = await resp.text()
                        print(f"Reply sent: {resp.status}")
                        print(f"Reply response: {response_text}")

            return web.Response(status=202)

        return web.Response(status=202)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(status=500)


async def process_message(text: str) -> str:
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, handle_sync, text)
    return result


def handle_sync(text: str) -> str:
    try:
        from app import classify_intent, call_claude
        from aws_costs import get_aws_costs

        intent = classify_intent(text)
        print(f"Intent: {intent}")

        if intent == 'standup':
            from aws_costs import get_daily_standup_data, get_cost_anomalies, get_savings_recommendations
            from aws_compliance import get_security_cost_tradeoffs
            from aws_reservations import get_expiring_reservations

            standup = get_daily_standup_data()
            anomalies = get_cost_anomalies()
            savings = get_savings_recommendations()
            security = get_security_cost_tradeoffs()
            reservations = get_expiring_reservations(days_threshold=30)
            wow_sign = "+" if standup['wow_change'] > 0 else ""

            prompt = f"""Daily FinOps standup.
Date: {standup['date']}
Yesterday: ${standup['yesterday_spend']} ({wow_sign}{standup['wow_change']}% vs last week)
MTD: ${standup['mtd_spend']} Day {standup['days_elapsed']} of {standup['days_in_month']}
Forecast: ${standup['projected_month_end']}
Anomalies: {len(anomalies)}
Security gaps: {len(security['disabled_services'])}
Savings available: ${savings['total_monthly_savings']}/mo
Write the standup. Start with OpsBeacon Daily Standup header."""
            return call_claude(prompt, feature='standup', show_cost=False)

        elif intent == 'security_score':
            from security_score import calculate_security_cost_score, format_score_for_slack
            score_data = calculate_security_cost_score()
            return format_score_for_slack(score_data)

        elif intent == 'finops_score':
            from finops_score import calculate_finops_score, format_finops_score_for_slack
            score_data = calculate_finops_score()
            return format_finops_score_for_slack(score_data)

        elif intent == 'idle_resources':
            from idle_resources import get_all_idle_resources
            data = get_all_idle_resources()
            parts = []
            if data['old_snapshots']:
                parts.append(f"Old snapshots ({len(data['old_snapshots'])}):\n" +
                    "\n".join([f"  {r['id']} [{r['region']}]: {r['age_days']} days - ${r['monthly_cost']}/mo"
                               for r in data['old_snapshots']]))
            if not parts:
                parts.append("No idle resources found.")
            prompt = f"""Idle resource report.
{chr(10).join(parts)}
Total waste: ${data['total_monthly_waste']}/mo
Write the idle resource summary. Start with IDLE RESOURCE REPORT header."""
            return call_claude(prompt, feature='idle_resources', show_cost=False)

        elif intent == 'executive':
            from executive_digest import generate_executive_digest
            return generate_executive_digest()

        elif intent == 'meeting_prep':
            from meeting_prep import generate_meeting_prep
            meeting_type = 'qbr' if 'qbr' in text else 'weekly' if 'weekly' in text else 'mbr'
            prep = generate_meeting_prep(meeting_type)
            return prep['content']

        elif intent == 'actions':
            from actions_dashboard import get_open_actions, get_actions_summary, format_actions_for_slack
            open_actions = get_open_actions()
            summary = get_actions_summary()
            header = (
                f"OpsBeacon Actions Dashboard\n\n"
                f"Open: {summary['total_open']} | Completed: {summary['total_completed']}\n"
                f"Savings at stake: ${summary['savings_at_stake']}/mo\n\n"
            )
            return header + format_actions_for_slack(open_actions)

        elif intent == 'forecast':
            from aws_costs import get_forecast_recalculation
            data = get_forecast_recalculation()
            if not data:
                return "Not enough data yet."
            prompt = f"""Three tier forecast.
Month end: ${data['month_end_forecast']} ({data['days_remaining_month']} days left)
Quarter end: ${data['quarter_forecast']} ({data['days_remaining_quarter']} days left)
Annual: ${data['annual_forecast']} ({data['days_remaining_year']} days left)
Trend: {data['trend_direction']} ({data['trend_pct']}%)
Write the forecast. Start with FORECAST header."""
            return call_claude(prompt, feature='forecast', show_cost=False)

        elif intent == 'ai_economics':
            from ai_economics import get_ai_economics_summary, format_ai_summary_for_slack
            data = get_ai_economics_summary()
            return format_ai_summary_for_slack(data)

        elif intent == 'compliance':
            from aws_compliance import get_untagged_resources, get_policy_violations, get_shadow_ai
            untagged = get_untagged_resources()
            violations = get_policy_violations()
            shadow = get_shadow_ai()
            prompt = f"""Compliance check.
Untagged: {untagged if untagged else 'None'}
Violations: {violations if violations else 'None'}
Shadow AI: {shadow if shadow else 'None'}
Write the compliance summary."""
            return call_claude(prompt, feature='compliance', show_cost=False)

        elif intent == 'security_tradeoffs':
            from aws_compliance import get_security_cost_tradeoffs
            data = get_security_cost_tradeoffs()
            findings = "\n".join([
                f"{f['service']}: {f['status']} - ${f['monthly_cost_to_enable']}/mo to fix"
                for f in data['findings']
            ])
            prompt = f"""Security tradeoffs.
{findings}
Total: ${data['total_monthly_cost_to_fix']}/mo
Write the security summary."""
            return call_claude(prompt, feature='security', show_cost=False)

        else:
            costs = get_aws_costs()
            cost_text = "\n".join([f"{s}: ${a}" for s, a in costs.items()])
            prompt = f"""You are Beacon, AI FinOps coworker.
User asked: "{text}"
AWS spend: {cost_text}
Answer directly. Mention relevant Beacon capabilities if applicable."""
            return call_claude(prompt, feature='general', show_cost=False)

    except Exception as e:
        print(f"Handle error: {e}")
        import traceback
        traceback.print_exc()
        return f"I encountered an error processing your request: {str(e)}"


async def debug(req: web.Request) -> web.Response:
    body = await req.text()
    headers = dict(req.headers)
    print(f"DEBUG - Headers: {headers}")
    print(f"DEBUG - Body: {body}")
    return web.Response(status=200, text="OK")

APP = web.Application()
APP.router.add_post('/api/messages', messages)
APP.router.add_post('/debug', debug)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3978))
    print(f"OpsBeacon Teams bot starting on port {port}")
    print(f"Endpoint: http://localhost:{port}/api/messages")
    web.run_app(APP, host='0.0.0.0', port=port)