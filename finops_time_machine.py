import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_current_spend_by_service():
    client = boto3.client('ce', region_name=AWS_REGION)
    today = datetime.today()
    start = (today - timedelta(days=30)).strftime('%Y-%m-%d')
    end = today.strftime('%Y-%m-%d')

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
        if amount > 0.001:
            costs[service] = round(amount, 4)

    return costs


def scenario_dev_weekend_shutdown():
    costs = get_current_spend_by_service()

    ec2_monthly = costs.get('Amazon EC2', 0) + costs.get('EC2 - Other', 0)
    rds_monthly = costs.get('Amazon RDS', 0)

    weekend_hours = 2 * 52 * 2 * 12
    total_hours = 8760
    weekend_fraction = weekend_hours / total_hours

    ec2_savings = round(ec2_monthly * weekend_fraction * 0.7, 2)
    rds_savings = round(rds_monthly * weekend_fraction * 0.6, 2)
    total_savings_monthly = round(ec2_savings + rds_savings, 2)
    total_savings_annual = round(total_savings_monthly * 12, 2)

    risks = [
        {
            'risk': 'Cold start latency on Monday mornings',
            'severity': 'LOW',
            'mitigation': 'Schedule startup 30 minutes before team arrives'
        },
        {
            'risk': 'Scheduled jobs running on weekends will fail',
            'severity': 'MEDIUM',
            'mitigation': 'Audit cron jobs before enabling shutdown'
        },
        {
            'risk': 'On-call engineers may need dev environment',
            'severity': 'LOW',
            'mitigation': 'Add manual override to restart on demand'
        }
    ]

    implementation = [
        'Tag all dev resources with Environment=development',
        'Create EventBridge rule: stop EC2 Friday 7pm',
        'Create EventBridge rule: start EC2 Monday 7am',
        'Create RDS stop/start schedule via Lambda',
        'Test one weekend before full rollout',
        'Add Slack notification when environments stop and start'
    ]

    terraform_hint = 'Run @Beacon generate terraform to get the IaC for this scenario'

    return {
        'scenario': 'Dev Environment Weekend Shutdown',
        'description': 'Stop all dev/staging EC2 and RDS instances every Friday at 7pm, restart Monday at 7am',
        'current_monthly': round(ec2_monthly + rds_monthly, 2),
        'ec2_monthly': ec2_monthly,
        'rds_monthly': rds_monthly,
        'ec2_savings_monthly': ec2_savings,
        'rds_savings_monthly': rds_savings,
        'total_savings_monthly': total_savings_monthly,
        'total_savings_annual': total_savings_annual,
        'savings_pct': round(
            (total_savings_monthly / (ec2_monthly + rds_monthly) * 100)
            if (ec2_monthly + rds_monthly) > 0 else 0, 1),
        'confidence': 89,
        'effort': 'Medium',
        'engineering_hours': 4,
        'affected_teams': ['Engineering', 'QA', 'DevOps'],
        'risks': risks,
        'implementation': implementation,
        'terraform_hint': terraform_hint,
        'payback_period': 'Immediate — savings start first weekend',
        'option_a': {
            'label': 'Full shutdown (EC2 + RDS)',
            'savings_monthly': total_savings_monthly,
            'savings_annual': total_savings_annual,
            'risk': 'MEDIUM',
            'effort': '4 hours engineering'
        },
        'option_b': {
            'label': 'EC2 only shutdown (safer)',
            'savings_monthly': ec2_savings,
            'savings_annual': round(ec2_savings * 12, 2),
            'risk': 'LOW',
            'effort': '2 hours engineering'
        }
    }


def scenario_gpt_model_switch(
        project_name='Legal Copilot',
        current_model='gpt-4o',
        target_model='gpt-4o-mini'):

    from ai_economics import get_project_detail

    project = get_project_detail(project_name)

    if not project:
        return {
            'scenario': f'GPT Model Switch — {project_name}',
            'error': f'Project {project_name} not found in AI Economics data'
        }

    current_monthly = project['monthly_spend']
    input_tokens = project['avg_input_tokens']
    output_tokens = project['avg_output_tokens']
    daily_requests = project['daily_requests']

    model_pricing = {
        'gpt-4o': {'input': 2.50, 'output': 10.00},
        'gpt-4o-mini': {'input': 0.15, 'output': 0.60},
        'claude-sonnet-4-6': {'input': 3.00, 'output': 15.00},
        'claude-haiku-4-5': {'input': 0.25, 'output': 1.25},
        'claude-opus-4-6': {'input': 15.00, 'output': 75.00},
    }

    current_pricing = model_pricing.get(current_model,
                                        {'input': 2.50, 'output': 10.00})
    target_pricing = model_pricing.get(target_model,
                                       {'input': 0.15, 'output': 0.60})

    monthly_requests = daily_requests * 30

    current_cost_per_request = (
        (input_tokens / 1_000_000) * current_pricing['input'] +
        (output_tokens / 1_000_000) * current_pricing['output']
    )

    target_cost_per_request = (
        (input_tokens / 1_000_000) * target_pricing['input'] +
        (output_tokens / 1_000_000) * target_pricing['output']
    )

    target_monthly = round(target_cost_per_request * monthly_requests, 2)
    savings_monthly = round(current_monthly - target_monthly, 2)
    savings_annual = round(savings_monthly * 12, 2)
    savings_pct = round((savings_monthly / current_monthly * 100)
                        if current_monthly > 0 else 0, 1)

    quality_impact = {
        'gpt-4o-mini': 'Good for summarization and simple tasks. May struggle with complex legal reasoning.',
        'claude-haiku-4-5': 'Fast and cost-effective. Strong reasoning but shorter context window.',
        'claude-sonnet-4-6': 'Near-parity with GPT-4o for most tasks. Strong reasoning and longer context.',
    }

    return {
        'scenario': f'GPT Model Switch — {project_name}',
        'description': f'Switch {project_name} from {current_model} to {target_model}',
        'project': project_name,
        'current_model': current_model,
        'target_model': target_model,
        'current_monthly': current_monthly,
        'target_monthly': target_monthly,
        'savings_monthly': savings_monthly,
        'savings_annual': savings_annual,
        'savings_pct': savings_pct,
        'current_cost_per_request': round(current_cost_per_request, 6),
        'target_cost_per_request': round(target_cost_per_request, 6),
        'confidence': 94,
        'effort': 'Low',
        'engineering_hours': 2,
        'quality_impact': quality_impact.get(target_model,
                                             'Review output quality carefully'),
        'recommendation': 'A/B test on 10% of traffic for 1 week before full switch',
        'option_a': {
            'label': f'Full switch to {target_model}',
            'savings_monthly': savings_monthly,
            'savings_annual': savings_annual,
            'risk': 'MEDIUM',
            'effort': '2 hours engineering + 1 week A/B test'
        },
        'option_b': {
            'label': f'Hybrid: {target_model} for simple tasks only',
            'savings_monthly': round(savings_monthly * 0.4, 2),
            'savings_annual': round(savings_monthly * 0.4 * 12, 2),
            'risk': 'LOW',
            'effort': '4 hours engineering to add routing logic'
        }
    }


def run_scenario(scenario_name, **kwargs):
    scenario_name = scenario_name.lower()

    if 'weekend' in scenario_name or 'dev' in scenario_name or 'shutdown' in scenario_name:
        return scenario_dev_weekend_shutdown()
    elif 'gpt' in scenario_name or 'model' in scenario_name or 'switch' in scenario_name:
        project = kwargs.get('project', 'Legal Copilot')
        target = kwargs.get('target_model', 'gpt-4o-mini')
        return scenario_gpt_model_switch(project, target_model=target)
    else:
        return {'error': f'Unknown scenario: {scenario_name}'}


def format_scenario_for_slack(result):
    if 'error' in result:
        return f"Error: {result['error']}"

    lines = [
        f"*FinOps Time Machine: {result['scenario']}*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"*What if... {result['description']}?*",
        f"",
        f"*Projected Annual Savings: ${result.get('savings_annual', result.get('total_savings_annual', 0)):,.2f}*",
        f"Confidence: {result['confidence']}%",
        f"Engineering effort: {result['engineering_hours']} hours",
        f"",
        f"*Option A — {result['option_a']['label']}*",
        f"  Savings: ${result['option_a']['savings_monthly']}/mo (${result['option_a']['savings_annual']}/yr)",
        f"  Risk: {result['option_a']['risk']}",
        f"  Effort: {result['option_a']['effort']}",
        f"",
        f"*Option B — {result['option_b']['label']}*",
        f"  Savings: ${result['option_b']['savings_monthly']}/mo (${result['option_b']['savings_annual']}/yr)",
        f"  Risk: {result['option_b']['risk']}",
        f"  Effort: {result['option_b']['effort']}",
        f"",
        f"*Recommendation: Option A*",
    ]

    if 'risks' in result:
        lines.append(f"")
        lines.append(f"*Risks:*")
        for r in result['risks']:
            lines.append(f"  [{r['severity']}] {r['risk']}")
            lines.append(f"  Fix: {r['mitigation']}")

    if 'quality_impact' in result:
        lines.append(f"")
        lines.append(f"*Quality impact:* {result['quality_impact']}")
        lines.append(f"*Recommended approach:* {result['recommendation']}")

    lines.append(f"")
    lines.append(f"_Powered by OpsBeacon FinOps Time Machine_")

    return "\n".join(lines)


if __name__ == "__main__":
    print("\n=== FinOps Time Machine Test ===")

    print("\nScenario 1: Dev Weekend Shutdown")
    result1 = scenario_dev_weekend_shutdown()
    print(f"Monthly savings: ${result1['total_savings_monthly']}")
    print(f"Annual savings: ${result1['total_savings_annual']}")
    print(f"Confidence: {result1['confidence']}%")
    print(f"Option A: {result1['option_a']['label']} — ${result1['option_a']['savings_monthly']}/mo")
    print(f"Option B: {result1['option_b']['label']} — ${result1['option_b']['savings_monthly']}/mo")

    print("\nScenario 2: GPT Model Switch")
    result2 = scenario_gpt_model_switch('Legal Copilot', 'gpt-4o', 'gpt-4o-mini')
    print(f"Current monthly: ${result2['current_monthly']}")
    print(f"Target monthly: ${result2['target_monthly']}")
    print(f"Monthly savings: ${result2['savings_monthly']}")
    print(f"Annual savings: ${result2['savings_annual']}")
    print(f"Confidence: {result2['confidence']}%")

    print("\nFormatted Slack output:")
    print(format_scenario_for_slack(result1))