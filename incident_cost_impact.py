import os
from dotenv import load_dotenv
import anthropic
from aws_costs import get_aws_costs
from pagerduty_incidents import get_active_incidents

load_dotenv()

claude = anthropic.Anthropic()


def analyze_incident_cost_impact(incident):
    costs = get_aws_costs()

    cost_text = "\n".join(
        [f"{service}: ${amount}" for service, amount in costs.items()]
    )

    prompt = f"""You are a FinOps and InfraOps analyst.

An incident has fired in PagerDuty:

Incident Title: {incident['title']}
Service: {incident['service']}
Urgency: {incident['urgency']}
Status: {incident['status']}

Current AWS spend by service this month:
{cost_text}

Analyze this incident and provide:
1. Most likely root cause based on the incident title
2. Top 2 remediation options with their estimated cost impact
   - Option A: Quick fix, what it costs to implement
   - Option B: Permanent fix, what it costs to implement
3. Which AWS service is most likely affected and its current spend
4. Estimated cost impact if incident is left unresolved for 24 hours
5. Recommended immediate action in one sentence

Format clearly for an on-call engineer reading this in Slack at 2am.
Be direct, specific, and keep it under 200 words.
Start with a fire emoji and INCIDENT ALERT header."""

    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        'incident': incident,
        'analysis': message.content[0].text
    }


def get_all_incident_analyses():
    incidents = get_active_incidents()

    if not incidents:
        return []

    analyses = []
    for incident in incidents:
        analysis = analyze_incident_cost_impact(incident)
        analyses.append(analysis)

    return analyses


if __name__ == "__main__":
    print("Analyzing active incidents with cost impact...")
    analyses = get_all_incident_analyses()

    if not analyses:
        print("No active incidents found")
    else:
        for a in analyses:
            print(f"\n{'='*50}")
            print(f"Incident: {a['incident']['title']}")
            print(f"{'='*50}")
            print(a['analysis'])