BEACON_SYSTEM_PROMPT = """You are Beacon, an AI FinOps and InfraOps coworker for engineering teams.

Your personality:
- Direct and confident. You don't hedge or over-qualify.
- Technical but not jargon-heavy. Write for a senior engineer or technical lead.
- Action-oriented. Every response ends with something the team can do right now.
- Honest. If something looks fine, say so clearly. Don't manufacture urgency.
- Concise. Respect the reader's time. No filler sentences.

Your tone:
- Colleague, not consultant. You're part of the team.
- Calm under pressure. Incidents get clear analysis, not panic.
- Specific over vague. Dollar amounts, percentages, service names, not generalities.

Never say:
- "In today's cloud environment..."
- "It's important to note that..."
- "I hope this helps..."
- "Please don't hesitate to..."
- "Leveraging best practices..."
"""

BEACON_FORMAT = """
Format your response exactly like this every time:

**Summary:** One sentence. What's the situation.

**Findings:**
- Finding 1 with specific detail and dollar amount or percentage where relevant
- Finding 2
- Finding 3 (maximum 3 findings unless more are critical)

**Action:** One specific thing to do right now. One sentence. Be precise.

**Impact:** One sentence on cost savings, risk reduction, or time saved if action is taken.

Keep the entire response under 200 words unless the complexity genuinely requires more.
Do not add extra sections. Do not add closing remarks.
"""
FEATURE_CONFIDENCE = {
    'cost_analysis': 94,
    'savings_recommendations': 82,
    'security_score': 96,
    'finops_score': 94,
    'idle_resources': 91,
    'forecast': 78,
    'cost_rca': 81,
    'compliance': 93,
    'ai_economics': 89,
    'reservation_expiry': 97,
    'security_tradeoffs': 88,
    'standup': 94,
    'executive': 91,
    'team_summary': 86,
    'terraform': 84,
    'meeting_prep': 92,
    'general': 75,
}


def get_confidence(feature):
    return FEATURE_CONFIDENCE.get(feature, 80)


def format_confidence(feature):
    score = get_confidence(feature)
    if score >= 90:
        bar = '🟢'
    elif score >= 75:
        bar = '🟡'
    else:
        bar = '🔴'
    return f"{bar} Confidence: {score}%"

AWS_CONSOLE_LINKS = {
    'guardduty': 'https://console.aws.amazon.com/guardduty/home?region={region}#/',
    'cloudtrail': 'https://console.aws.amazon.com/cloudtrail/home?region={region}#/dashboard',
    'config': 'https://console.aws.amazon.com/config/home?region={region}#/dashboard',
    'security_hub': 'https://console.aws.amazon.com/securityhub/home?region={region}#/',
    'cost_explorer': 'https://console.aws.amazon.com/cost-management/home#/cost-explorer',
    'ec2': 'https://console.aws.amazon.com/ec2/v2/home?region={region}#Instances',
    'rds': 'https://console.aws.amazon.com/rds/home?region={region}#databases:',
    'ec2_snapshots': 'https://console.aws.amazon.com/ec2/v2/home?region={region}#Snapshots',
    'savings_plans': 'https://console.aws.amazon.com/savingsplans/home#/dashboard',
    'reserved_instances': 'https://console.aws.amazon.com/ec2/v2/home?region={region}#ReservedInstances',
    'iam': 'https://console.aws.amazon.com/iam/home#/users',
    's3': 'https://console.aws.amazon.com/s3/home',
    'lambda': 'https://console.aws.amazon.com/lambda/home?region={region}#/functions',
    'cloudwatch': 'https://console.aws.amazon.com/cloudwatch/home?region={region}#dashboards',
}


def get_console_link(service, region='us-east-2'):
    template = AWS_CONSOLE_LINKS.get(service.lower())
    if template:
        return template.format(region=region)
    return None


def format_console_link(service, region='us-east-2', label=None):
    url = get_console_link(service, region)
    if url:
        display = label or f"Open {service.replace('_', ' ').title()} in AWS Console"
        return f"<{url}|{display}>"
    return None