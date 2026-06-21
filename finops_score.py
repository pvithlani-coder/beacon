import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import json

load_dotenv()

AWS_REGION = 'us-east-2'

# Proprietary weights - never expose to customers
DIMENSION_WEIGHTS = {
    'cost_visibility': 0.12,
    'waste_elimination': 0.12,
    'tag_quality': 0.10,
    'reservation_efficiency': 0.10,
    'savings_execution': 0.12,
    'forecast_accuracy': 0.10,
    'recommendation_closure': 0.12,
    'cost_anomalies': 0.10,
    'security_economics': 0.06,
    'ai_efficiency': 0.06
}

INDUSTRY_BENCHMARKS = {
    'startup': 52,
    'mid_market': 63,
    'enterprise': 71
}

GRADE_THRESHOLDS = {
    90: 'A',
    80: 'B',
    70: 'C',
    60: 'D',
    0: 'F'
}


def get_grade(score):
    for threshold, grade in sorted(
            GRADE_THRESHOLDS.items(), reverse=True):
        if score >= threshold:
            return grade
    return 'F'


def calculate_cost_visibility():
    score = 100
    findings = []

    try:
        ce = boto3.client('ce', region_name=AWS_REGION)
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

        response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}]
        )

        accounts_with_spend = len(response['ResultsByTime'][0]['Groups'])
        if accounts_with_spend == 0:
            score -= 20
            findings.append({
                'issue': 'No cost data by account available',
                'impact': -20,
                'fix': 'Enable cost allocation by linked account'
            })

        try:
            org = boto3.client('organizations', region_name='us-east-1')
            accounts = org.list_accounts()['Accounts']
            untagged_accounts = 0
            for account in accounts:
                tags = org.list_tags_for_resource(
                    ResourceId=account['Id'])['Tags']
                tag_keys = [t['Key'] for t in tags]
                if 'Owner' not in tag_keys or 'CostCenter' not in tag_keys:
                    untagged_accounts += 1

            if untagged_accounts > 0:
                penalty = min(30, untagged_accounts * 15)
                score -= penalty
                findings.append({
                    'issue': f'{untagged_accounts} accounts missing cost allocation tags',
                    'impact': -penalty,
                    'fix': 'Run @Beacon fix tags to remediate'
                })
        except Exception:
            pass

    except Exception as e:
        print(f"Cost visibility error: {e}")

    return max(0, score), findings


def calculate_waste_elimination():
    score = 100
    findings = []

    try:
        from idle_resources import get_all_idle_resources
        idle = get_all_idle_resources()

        total_waste = idle['total_monthly_waste']

        if total_waste > 50:
            penalty = min(40, int(total_waste / 10))
            score -= penalty
            findings.append({
                'issue': f'${total_waste}/mo in idle resources detected',
                'impact': -penalty,
                'fix': 'Run @Beacon find idle resources to clean up'
            })
        elif total_waste > 10:
            penalty = min(20, int(total_waste / 5))
            score -= penalty
            findings.append({
                'issue': f'${total_waste}/mo in idle resources detected',
                'impact': -penalty,
                'fix': 'Run @Beacon find idle resources to clean up'
            })
        elif total_waste > 0:
            score -= 10
            findings.append({
                'issue': f'${total_waste}/mo in minor waste detected',
                'impact': -10,
                'fix': 'Run @Beacon find idle resources to clean up'
            })

    except Exception as e:
        print(f"Waste elimination error: {e}")

    return max(0, score), findings


def calculate_tag_quality():
    score = 100
    findings = []

    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)
        rds = boto3.client('rds', region_name=AWS_REGION)

        total_resources = 0
        untagged_resources = 0
        required_tags = ['Name', 'Environment', 'Owner']

        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name',
                      'Values': ['running', 'stopped']}]
        )

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                total_resources += 1
                tags = {t['Key']: t['Value']
                        for t in instance.get('Tags', [])}
                if not all(t in tags for t in required_tags):
                    untagged_resources += 1

        dbs = rds.describe_db_instances()
        for db in dbs['DBInstances']:
            total_resources += 1
            arn = db['DBInstanceArn']
            tag_response = rds.list_tags_for_resource(ResourceName=arn)
            tags = {t['Key']: t['Value']
                    for t in tag_response['TagList']}
            if not all(t in tags for t in ['Environment', 'Owner']):
                untagged_resources += 1

        if total_resources > 0:
            tag_pct = ((total_resources - untagged_resources)
                       / total_resources) * 100
            if tag_pct < 100:
                penalty = int((100 - tag_pct) * 0.5)
                score -= penalty
                findings.append({
                    'issue': f'{untagged_resources}/{total_resources} resources missing required tags ({tag_pct:.0f}% compliance)',
                    'impact': -penalty,
                    'fix': 'Run @Beacon compliance check to identify and fix'
                })
        else:
            findings.append({
                'issue': 'No resources found to evaluate',
                'impact': 0,
                'fix': 'Deploy resources with proper tagging from day one'
            })

    except Exception as e:
        print(f"Tag quality error: {e}")

    return max(0, score), findings


def calculate_reservation_efficiency():
    score = 100
    findings = []

    try:
        from aws_reservations import get_expiring_reservations
        reservations = get_expiring_reservations(days_threshold=90)

        urgent = [r for r in reservations if r['urgency'] == 'HIGH']
        if urgent:
            penalty = min(30, len(urgent) * 15)
            score -= penalty
            findings.append({
                'issue': f'{len(urgent)} reserved instances expiring within 30 days',
                'impact': -penalty,
                'fix': 'Run @Beacon check expiring reservations'
            })

        from aws_costs import get_savings_recommendations
        savings = get_savings_recommendations()
        if savings['total_monthly_savings'] > 20:
            penalty = min(40, int(savings['total_monthly_savings'] / 5))
            score -= penalty
            findings.append({
                'issue': f'${savings["total_monthly_savings"]}/mo in uncaptured reserved instance savings',
                'impact': -penalty,
                'fix': 'Run @Beacon savings recommendations to act'
            })
        elif savings['total_monthly_savings'] > 5:
            score -= 15
            findings.append({
                'issue': f'${savings["total_monthly_savings"]}/mo in available savings not yet captured',
                'impact': -15,
                'fix': 'Run @Beacon savings recommendations'
            })

    except Exception as e:
        print(f"Reservation efficiency error: {e}")

    return max(0, score), findings


def calculate_savings_execution():
    score = 100
    findings = []

    try:
        from actions_dashboard import get_actions_summary
        summary = get_actions_summary()

        total = summary['total_open'] + summary['total_completed']
        if total > 0:
            completion_rate = (summary['total_completed'] / total) * 100

            if completion_rate < 50:
                penalty = int((50 - completion_rate) * 0.8)
                score -= penalty
                findings.append({
                    'issue': f'Only {completion_rate:.0f}% of recommendations acted on',
                    'impact': -penalty,
                    'fix': 'Review open actions dashboard and close pending items'
                })
            elif completion_rate < 75:
                score -= 15
                findings.append({
                    'issue': f'{completion_rate:.0f}% recommendation completion rate - room to improve',
                    'impact': -15,
                    'fix': 'Assign owners to open actions to improve closure rate'
                })

        if summary['savings_at_stake'] > 0:
            realization_rate = (
                summary['savings_realized'] /
                (summary['savings_realized'] + summary['savings_at_stake'])
            ) * 100 if (summary['savings_realized'] + summary['savings_at_stake']) > 0 else 0

            if realization_rate < 30:
                score -= 20
                findings.append({
                    'issue': f'${summary["savings_at_stake"]}/mo in savings identified but not yet realized',
                    'impact': -20,
                    'fix': 'Act on savings recommendations in open actions'
                })

    except Exception as e:
        print(f"Savings execution error: {e}")

    return max(0, score), findings


def calculate_forecast_accuracy():
    score = 100
    findings = []

    try:
        from aws_costs import get_forecast_recalculation
        forecast = get_forecast_recalculation()

        if forecast:
            trend = forecast['trend_direction']
            trend_pct = abs(forecast['trend_pct'])

            if trend == 'ACCELERATING' and trend_pct > 30:
                score -= 25
                findings.append({
                    'issue': f'Spend accelerating {trend_pct}% above prior week - forecast reliability low',
                    'impact': -25,
                    'fix': 'Investigate cost drivers before month end'
                })
            elif trend == 'ACCELERATING' and trend_pct > 15:
                score -= 15
                findings.append({
                    'issue': f'Spend trending up {trend_pct}% - monitor closely',
                    'impact': -15,
                    'fix': 'Run @Beacon forecast to see month end projection'
                })
            else:
                findings.append({
                    'issue': 'Spend trend stable - forecast reliability high',
                    'impact': 0,
                    'fix': 'Maintain current discipline'
                })

    except Exception as e:
        print(f"Forecast accuracy error: {e}")

    return max(0, score), findings


def calculate_recommendation_closure():
    score = 100
    findings = []

    try:
        from actions_dashboard import get_actions_summary
        summary = get_actions_summary()

        if summary['overdue_count'] > 0:
            penalty = min(40, summary['overdue_count'] * 20)
            score -= penalty
            findings.append({
                'issue': f'{summary["overdue_count"]} overdue actions past due date',
                'impact': -penalty,
                'fix': 'Run @Beacon show open actions to review overdue items'
            })

        if summary['aging_count'] > 0:
            penalty = min(30, summary['aging_count'] * 10)
            score -= penalty
            findings.append({
                'issue': f'{summary["aging_count"]} actions aging past 14 days without closure',
                'impact': -penalty,
                'fix': 'Assign owners and set deadlines on aging actions'
            })

        if summary['total_open'] > 10:
            score -= 15
            findings.append({
                'issue': f'{summary["total_open"]} open actions accumulating',
                'impact': -15,
                'fix': 'Focus on closing existing actions before creating new ones'
            })

    except Exception as e:
        print(f"Recommendation closure error: {e}")

    return max(0, score), findings


def calculate_cost_anomalies():
    score = 100
    findings = []

    try:
        from aws_costs import get_cost_anomalies
        anomalies = get_cost_anomalies()

        if anomalies:
            penalty = min(40, len(anomalies) * 20)
            score -= penalty
            findings.append({
                'issue': f'{len(anomalies)} active cost anomalies detected',
                'impact': -penalty,
                'fix': 'Run @Beacon explain spike to investigate'
            })
        else:
            findings.append({
                'issue': 'No active cost anomalies detected',
                'impact': 0,
                'fix': 'Anomaly detection running every 6 hours'
            })

    except Exception as e:
        print(f"Cost anomalies error: {e}")

    return max(0, score), findings


def calculate_security_economics():
    score = 100
    findings = []

    try:
        from security_score import calculate_security_cost_score
        security = calculate_security_cost_score()
        normalized = security['overall_score']
        score = normalized

        if normalized < 60:
            findings.append({
                'issue': f'Security Cost Score {normalized}/100 - significant gaps',
                'impact': -(100 - normalized),
                'fix': 'Run @Beacon security score for detailed breakdown'
            })
        elif normalized < 80:
            findings.append({
                'issue': f'Security Cost Score {normalized}/100 - moderate gaps',
                'impact': -(100 - normalized),
                'fix': 'Run @Beacon security score to prioritize fixes'
            })

    except Exception as e:
        print(f"Security economics error: {e}")

    return max(0, score), findings


def calculate_ai_efficiency():
    score = 100
    findings = []

    try:
        from ai_economics import get_ai_economics_summary
        data = get_ai_economics_summary()

        if data['critical_projects']:
            penalty = min(30, len(data['critical_projects']) * 15)
            score -= penalty
            findings.append({
                'issue': f'{len(data["critical_projects"])} AI projects in critical efficiency state',
                'impact': -penalty,
                'fix': 'Run @Beacon show AI projects for optimization recommendations'
            })

        if data['waste_detected'] > 100:
            score -= 20
            findings.append({
                'issue': f'${data["waste_detected"]:.0f}/mo in AI token waste detected',
                'impact': -20,
                'fix': 'Enable semantic caching on high-duplicate projects'
            })
        elif data['waste_detected'] > 50:
            score -= 10
            findings.append({
                'issue': f'${data["waste_detected"]:.0f}/mo in AI token waste',
                'impact': -10,
                'fix': 'Review duplicate prompt patterns in AI projects'
            })

    except Exception as e:
        print(f"AI efficiency error: {e}")

    return max(0, score), findings


def calculate_finops_score(company_size='mid_market'):
    print("Calculating OpsBeacon FinOps Score...")

    cost_visibility, cv_findings = calculate_cost_visibility()
    print(f"  Cost Visibility: {cost_visibility}")

    waste_elimination, we_findings = calculate_waste_elimination()
    print(f"  Waste Elimination: {waste_elimination}")

    tag_quality, tq_findings = calculate_tag_quality()
    print(f"  Tag Quality: {tag_quality}")

    reservation_efficiency, re_findings = calculate_reservation_efficiency()
    print(f"  Reservation Efficiency: {reservation_efficiency}")

    savings_execution, se_findings = calculate_savings_execution()
    print(f"  Savings Execution: {savings_execution}")

    forecast_accuracy, fa_findings = calculate_forecast_accuracy()
    print(f"  Forecast Accuracy: {forecast_accuracy}")

    recommendation_closure, rc_findings = calculate_recommendation_closure()
    print(f"  Recommendation Closure: {recommendation_closure}")

    cost_anomalies, ca_findings = calculate_cost_anomalies()
    print(f"  Cost Anomalies: {cost_anomalies}")

    security_economics, sec_findings = calculate_security_economics()
    print(f"  Security Economics: {security_economics}")

    ai_efficiency, ai_findings = calculate_ai_efficiency()
    print(f"  AI Efficiency: {ai_efficiency}")

    overall = int(
        cost_visibility * DIMENSION_WEIGHTS['cost_visibility'] +
        waste_elimination * DIMENSION_WEIGHTS['waste_elimination'] +
        tag_quality * DIMENSION_WEIGHTS['tag_quality'] +
        reservation_efficiency * DIMENSION_WEIGHTS['reservation_efficiency'] +
        savings_execution * DIMENSION_WEIGHTS['savings_execution'] +
        forecast_accuracy * DIMENSION_WEIGHTS['forecast_accuracy'] +
        recommendation_closure * DIMENSION_WEIGHTS['recommendation_closure'] +
        cost_anomalies * DIMENSION_WEIGHTS['cost_anomalies'] +
        security_economics * DIMENSION_WEIGHTS['security_economics'] +
        ai_efficiency * DIMENSION_WEIGHTS['ai_efficiency']
    )

    all_findings = (
        cv_findings + we_findings + tq_findings +
        re_findings + se_findings + fa_findings +
        rc_findings + ca_findings + sec_findings + ai_findings
    )

    actionable = [f for f in all_findings if f['impact'] < 0]
    actionable.sort(key=lambda x: x['impact'])

    benchmark = INDUSTRY_BENCHMARKS.get(company_size, 63)
    vs_benchmark = overall - benchmark
    grade = get_grade(overall)

    monthly_value_at_risk = 0
    try:
        from actions_dashboard import get_actions_summary
        summary = get_actions_summary()
        monthly_value_at_risk = summary['savings_at_stake']
    except Exception:
        pass

    dimensions = {
        'Cost Visibility': cost_visibility,
        'Waste Elimination': waste_elimination,
        'Tag Quality': tag_quality,
        'Reservation Efficiency': reservation_efficiency,
        'Savings Execution': savings_execution,
        'Forecast Accuracy': forecast_accuracy,
        'Recommendation Closure': recommendation_closure,
        'Cost Anomalies': cost_anomalies,
        'Security Economics': security_economics,
        'AI Efficiency': ai_efficiency
    }

    return {
        'overall_score': overall,
        'grade': grade,
        'risk_level': 'LOW' if overall >= 80 else
                      'MODERATE' if overall >= 60 else
                      'HIGH' if overall >= 40 else 'CRITICAL',
        'dimensions': dimensions,
        'actionable_findings': actionable[:5],
        'benchmark': benchmark,
        'vs_benchmark': vs_benchmark,
        'company_size': company_size,
        'monthly_value_at_risk': monthly_value_at_risk,
        'calculated_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }


def format_finops_score_for_slack(score_data):
    overall = score_data['overall_score']
    grade = score_data['grade']
    benchmark = score_data['benchmark']
    vs_benchmark = score_data['vs_benchmark']
    vs_sign = "+" if vs_benchmark >= 0 else ""

    filled = int(overall / 10)
    empty = 10 - filled
    bar = "█" * filled + "░" * empty

    dim_lines = "\n".join([
        f"  {name:<25} {score:>3}/100"
        for name, score in score_data['dimensions'].items()
    ])

    finding_lines = "\n".join([
        f"  {f['issue'][:65]} ({f['impact']} pts)"
        for f in score_data['actionable_findings'][:3]
    ])

    action_lines = "\n".join([
        f"  {i+1}. {f['fix']}"
        for i, f in enumerate(score_data['actionable_findings'][:3])
    ])

    message = f"""*OpsBeacon FinOps Score*
━━━━━━━━━━━━━━━━━━━━

*Overall: {overall}/100 — Grade {grade}*
{bar}

*Risk Level:* {score_data['risk_level']}
*vs Industry Benchmark:* {vs_sign}{vs_benchmark} pts (benchmark: {benchmark})
*Monthly Value at Risk:* ${score_data['monthly_value_at_risk']}

*10-Dimension Breakdown:*
{dim_lines}

*Top Score Drivers:*
{finding_lines}

*Recommended Actions:*
{action_lines}

_Calculated: {score_data['calculated_at']} | Powered by OpsBeacon_
_Exact weighting is proprietary. Dimensions shown for transparency._"""

    return message


if __name__ == "__main__":
    print("\n=== OpsBeacon FinOps Score ===")
    score_data = calculate_finops_score()
    print(f"\nOverall Score: {score_data['overall_score']}/100")
    print(f"Grade: {score_data['grade']}")
    print(f"Risk Level: {score_data['risk_level']}")
    print(f"vs Benchmark: {score_data['vs_benchmark']:+d} pts")
    print(f"\nDimension Scores:")
    for dim, score in score_data['dimensions'].items():
        print(f"  {dim}: {score}/100")
    print(f"\nTop Findings:")
    for f in score_data['actionable_findings'][:3]:
        print(f"  [{f['impact']} pts] {f['issue']}")
    print(f"\nFormatted Slack Output:")
    print(format_finops_score_for_slack(score_data))