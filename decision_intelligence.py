from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def build_decision(title, context, options, recommendation_index=0,
                   confidence=85, category='cost_optimization'):
    recommendation = options[recommendation_index]

    return {
        'title': title,
        'context': context,
        'category': category,
        'options': options,
        'recommendation': recommendation,
        'recommendation_index': recommendation_index,
        'confidence': confidence,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }


def decision_reserved_instance(service, current_monthly,
                                instance_type=None, region=None):
    savings_1yr = round(current_monthly * 0.35, 2)
    savings_3yr = round(current_monthly * 0.55, 2)
    annual_1yr = round(savings_1yr * 12, 2)
    annual_3yr = round(savings_3yr * 12, 2)

    options = [
        {
            'label': '1-Year Reserved Instance',
            'description': 'Commit to 1 year at a fixed price',
            'savings_monthly': savings_1yr,
            'savings_annual': annual_1yr,
            'upfront_cost': round(current_monthly * 12 * 0.65 * 0.5, 2),
            'risk': 'LOW',
            'risk_detail': 'Can sell on AWS Marketplace if needs change',
            'effort': '30 minutes',
            'flexibility': 'MEDIUM',
            'confidence': 91
        },
        {
            'label': '3-Year Reserved Instance',
            'description': 'Commit to 3 years for maximum savings',
            'savings_monthly': savings_3yr,
            'savings_annual': annual_3yr,
            'upfront_cost': round(current_monthly * 12 * 0.45 * 0.5, 2),
            'risk': 'MEDIUM',
            'risk_detail': 'Long commitment, harder to exit if workload changes',
            'effort': '30 minutes',
            'flexibility': 'LOW',
            'confidence': 78
        },
        {
            'label': 'Savings Plan (flexible)',
            'description': 'Compute Savings Plan covers any EC2, Lambda, Fargate',
            'savings_monthly': round(current_monthly * 0.28, 2),
            'savings_annual': round(current_monthly * 0.28 * 12, 2),
            'upfront_cost': 0,
            'risk': 'LOW',
            'risk_detail': 'Most flexible option, applies across services',
            'effort': '15 minutes',
            'flexibility': 'HIGH',
            'confidence': 88
        }
    ]

    return build_decision(
        title=f"Reserved Instance Decision — {service}",
        context=f"Current monthly spend: ${current_monthly}. "
                f"On-demand pricing with no commitment discounts applied.",
        options=options,
        recommendation_index=0,
        confidence=91,
        category='cost_optimization'
    )


def decision_idle_resource(resource_type, resource_id,
                            monthly_cost, age_days=None):
    options = [
        {
            'label': f'Delete {resource_type} immediately',
            'description': f'Permanently remove {resource_id}',
            'savings_monthly': monthly_cost,
            'savings_annual': round(monthly_cost * 12, 2),
            'upfront_cost': 0,
            'risk': 'LOW' if (age_days and age_days > 90) else 'MEDIUM',
            'risk_detail': 'Verify no restore dependencies before deleting',
            'effort': '5 minutes',
            'flexibility': 'NONE',
            'confidence': 90 if (age_days and age_days > 90) else 75
        },
        {
            'label': f'Tag and defer for 30 days',
            'description': 'Add deletion-candidate tag, review in 30 days',
            'savings_monthly': 0,
            'savings_annual': 0,
            'upfront_cost': 0,
            'risk': 'LOW',
            'risk_detail': 'Gives teams time to claim if needed',
            'effort': '2 minutes',
            'flexibility': 'HIGH',
            'confidence': 99
        },
        {
            'label': 'Archive to S3 Glacier before deleting',
            'description': 'Snapshot data to Glacier for compliance, then delete',
            'savings_monthly': round(monthly_cost * 0.85, 2),
            'savings_annual': round(monthly_cost * 0.85 * 12, 2),
            'upfront_cost': round(monthly_cost * 0.02, 2),
            'risk': 'LOW',
            'risk_detail': 'Best for compliance-sensitive environments',
            'effort': '15 minutes',
            'flexibility': 'MEDIUM',
            'confidence': 85
        }
    ]

    rec_index = 0 if (age_days and age_days > 365) else 1

    return build_decision(
        title=f"Idle Resource Decision — {resource_id}",
        context=f"{resource_type} has been idle for "
                f"{age_days or 'unknown'} days "
                f"at ${monthly_cost}/month.",
        options=options,
        recommendation_index=rec_index,
        confidence=options[rec_index]['confidence'],
        category='waste_reduction'
    )


def decision_security_gap(service, monthly_cost, risk_level='HIGH'):
    options = [
        {
            'label': f'Enable {service} now',
            'description': f'Enable {service} immediately at full coverage',
            'savings_monthly': 0,
            'savings_annual': 0,
            'upfront_cost': monthly_cost,
            'monthly_cost': monthly_cost,
            'risk': 'LOW',
            'risk_detail': 'Closes security gap immediately',
            'effort': '15 minutes',
            'flexibility': 'HIGH',
            'confidence': 95
        },
        {
            'label': f'Enable {service} on critical accounts only',
            'description': 'Partial coverage on production accounts first',
            'savings_monthly': 0,
            'savings_annual': 0,
            'upfront_cost': round(monthly_cost * 0.6, 2),
            'monthly_cost': round(monthly_cost * 0.6, 2),
            'risk': 'MEDIUM',
            'risk_detail': 'Dev accounts remain unprotected',
            'effort': '30 minutes',
            'flexibility': 'MEDIUM',
            'confidence': 80
        },
        {
            'label': 'Accept risk and defer',
            'description': 'Document the accepted risk, review next quarter',
            'savings_monthly': monthly_cost,
            'savings_annual': round(monthly_cost * 12, 2),
            'upfront_cost': 0,
            'monthly_cost': 0,
            'risk': 'HIGH',
            'risk_detail': f'{risk_level} security exposure accepted',
            'effort': '0 minutes',
            'flexibility': 'HIGH',
            'confidence': 99
        }
    ]

    return build_decision(
        title=f"Security Decision — {service}",
        context=f"{service} is disabled. "
                f"Monthly cost to enable: ${monthly_cost}. "
                f"Risk level: {risk_level}.",
        options=options,
        recommendation_index=0,
        confidence=95,
        category='security'
    )


def decision_ai_model_switch(project_name, current_model,
                              target_model, savings_monthly):
    annual = round(savings_monthly * 12, 2)
    partial_savings = round(savings_monthly * 0.4, 2)

    options = [
        {
            'label': f'Full switch to {target_model}',
            'description': f'Replace {current_model} entirely with {target_model}',
            'savings_monthly': savings_monthly,
            'savings_annual': annual,
            'upfront_cost': 0,
            'risk': 'MEDIUM',
            'risk_detail': 'Quality impact on complex tasks. Run A/B test first.',
            'effort': '2 hours + 1 week A/B test',
            'flexibility': 'HIGH',
            'confidence': 87
        },
        {
            'label': f'Hybrid routing',
            'description': f'Route simple tasks to {target_model}, complex to {current_model}',
            'savings_monthly': partial_savings,
            'savings_annual': round(partial_savings * 12, 2),
            'upfront_cost': 0,
            'risk': 'LOW',
            'risk_detail': 'Requires task classification logic',
            'effort': '4 hours engineering',
            'flexibility': 'HIGH',
            'confidence': 92
        },
        {
            'label': 'Optimize prompts first',
            'description': 'Trim prompt size before switching models',
            'savings_monthly': round(savings_monthly * 0.3, 2),
            'savings_annual': round(savings_monthly * 0.3 * 12, 2),
            'upfront_cost': 0,
            'risk': 'LOW',
            'risk_detail': 'No model risk, same quality',
            'effort': '3 hours engineering',
            'flexibility': 'HIGH',
            'confidence': 95
        }
    ]

    return build_decision(
        title=f"AI Model Decision — {project_name}",
        context=f"{project_name} runs on {current_model} at "
                f"${savings_monthly + partial_savings:.0f}/mo. "
                f"Switching to {target_model} saves ${savings_monthly}/mo.",
        options=options,
        recommendation_index=1,
        confidence=92,
        category='ai_optimization'
    )


def format_decision_for_slack(decision):
    risk_emoji = {
        'LOW': '🟢',
        'MEDIUM': '🟡',
        'HIGH': '🔵',
        'NONE': '⚪'
    }

    lines = [
        f"*Decision Intelligence: {decision['title']}*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"_{decision['context']}_",
        f""
    ]

    for i, opt in enumerate(decision['options']):
        is_rec = i == decision['recommendation_index']
        prefix = "★ *RECOMMENDED* " if is_rec else ""
        risk = risk_emoji.get(opt['risk'], '⚪')

        lines.append(
            f"{prefix}*Option {chr(65+i)}: {opt['label']}*")
        lines.append(f"  {opt['description']}")

        if opt.get('savings_monthly', 0) > 0:
            lines.append(
                f"  Savings: ${opt['savings_monthly']}/mo "
                f"(${opt['savings_annual']}/yr)")
        elif opt.get('monthly_cost', 0) > 0:
            lines.append(
                f"  Monthly cost: ${opt['monthly_cost']}/mo")

        lines.append(
            f"  Risk: {risk} {opt['risk']} — {opt['risk_detail']}")
        lines.append(f"  Effort: {opt['effort']}")
        lines.append(f"  Confidence: {opt['confidence']}%")
        lines.append("")

    rec = decision['recommendation']
    lines.append(
        f"*Recommendation: Option "
        f"{chr(65 + decision['recommendation_index'])}"
        f" — {rec['label']}*")
    lines.append(
        f"Overall confidence: {decision['confidence']}%")
    lines.append(
        f"_Generated: {decision['generated_at']} "
        f"| Powered by OpsBeacon Decision Intelligence_")

    return "\n".join(lines)


if __name__ == "__main__":
    print("\n=== Decision Intelligence Test ===")

    print("\n1. Reserved Instance Decision:")
    d1 = decision_reserved_instance('Amazon RDS', 0.41)
    print(format_decision_for_slack(d1))

    print("\n2. Idle Resource Decision:")
    d2 = decision_idle_resource('EBS Snapshot',
                                 'snap-00090613d62997694',
                                 0.80, age_days=1642)
    print(format_decision_for_slack(d2))

    print("\n3. AI Model Switch Decision:")
    d3 = decision_ai_model_switch(
        'Legal Copilot', 'gpt-4o', 'gpt-4o-mini', 978.33)
    print(format_decision_for_slack(d3))