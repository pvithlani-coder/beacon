import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

PROJECTS_FILE = 'ai_projects.json'


def seed_demo_projects():
    demo_projects = [
        {
            'id': 'proj_001',
            'name': 'Customer Support Bot',
            'team': 'Customer Experience',
            'model_primary': 'claude-sonnet-4-5',
            'daily_requests': 2100,
            'avg_input_tokens': 850,
            'avg_output_tokens': 420,
            'monthly_spend': 1120.00,
            'revenue_impact': 240000,
            'metric': 'conversations',
            'metric_volume': 2100000,
            'cost_per_metric': 0.00053,
            'cost_trend_pct': -3.2,
            'efficiency_score': 95,
            'status': 'healthy',
            'duplicate_prompt_pct': 8,
            'avg_prompt_length': 850,
            'peer_avg_prompt_length': 820
        },
        {
            'id': 'proj_002',
            'name': 'Sales Assistant',
            'team': 'Revenue Operations',
            'model_primary': 'claude-sonnet-4-5',
            'daily_requests': 890,
            'avg_input_tokens': 1200,
            'avg_output_tokens': 680,
            'monthly_spend': 940.00,
            'revenue_impact': 180000,
            'metric': 'deals assisted',
            'metric_volume': 4200,
            'cost_per_metric': 0.224,
            'cost_trend_pct': 2.1,
            'efficiency_score': 91,
            'status': 'healthy',
            'duplicate_prompt_pct': 12,
            'avg_prompt_length': 1200,
            'peer_avg_prompt_length': 1100
        },
        {
            'id': 'proj_003',
            'name': 'Document Search',
            'team': 'Engineering',
            'model_primary': 'claude-sonnet-4-5',
            'daily_requests': 1450,
            'avg_input_tokens': 2100,
            'avg_output_tokens': 380,
            'monthly_spend': 720.00,
            'revenue_impact': 0,
            'metric': 'searches',
            'metric_volume': 43500,
            'cost_per_metric': 0.0165,
            'cost_trend_pct': 18.0,
            'efficiency_score': 82,
            'status': 'watch',
            'duplicate_prompt_pct': 22,
            'avg_prompt_length': 2100,
            'peer_avg_prompt_length': 1400
        },
        {
            'id': 'proj_004',
            'name': 'Legal Copilot',
            'team': 'Legal Operations',
            'model_primary': 'gpt-4o',
            'daily_requests': 340,
            'avg_input_tokens': 7100,
            'avg_output_tokens': 3400,
            'monthly_spend': 1010.00,
            'revenue_impact': 0,
            'metric': 'documents processed',
            'metric_volume': 10200,
            'cost_per_metric': 0.099,
            'cost_trend_pct': 63.0,
            'efficiency_score': 62,
            'status': 'critical',
            'duplicate_prompt_pct': 31,
            'avg_prompt_length': 7100,
            'peer_avg_prompt_length': 3900,
            'potential_savings': 8200
        },
        {
            'id': 'proj_005',
            'name': 'Research Agent',
            'team': 'Product',
            'model_primary': 'claude-sonnet-4-5',
            'daily_requests': 180,
            'avg_input_tokens': 4200,
            'avg_output_tokens': 2100,
            'monthly_spend': 580.00,
            'revenue_impact': 0,
            'metric': 'research tasks',
            'metric_volume': 5400,
            'cost_per_metric': 0.107,
            'cost_trend_pct': 8.5,
            'efficiency_score': 59,
            'status': 'watch',
            'duplicate_prompt_pct': 19,
            'avg_prompt_length': 4200,
            'peer_avg_prompt_length': 2800
        }
    ]

    with open(PROJECTS_FILE, 'w') as f:
        json.dump(demo_projects, f, indent=2)

    print(f"Seeded {len(demo_projects)} demo AI projects")
    return demo_projects


def load_projects():
    if not os.path.exists(PROJECTS_FILE):
        return seed_demo_projects()
    with open(PROJECTS_FILE, 'r') as f:
        return json.load(f)


def get_ai_economics_summary():
    projects = load_projects()

    total_monthly = sum(p['monthly_spend'] for p in projects)
    total_daily = round(total_monthly / 30, 2)

    # Yesterday spend estimate
    yesterday_spend = round(total_daily * (
        1 + sum(p['cost_trend_pct'] for p in projects) /
        len(projects) / 100
    ), 2)

    # Sort by spend
    by_spend = sorted(
        projects, key=lambda x: x['monthly_spend'], reverse=True)

    # Sort by efficiency
    by_efficiency = sorted(
        projects, key=lambda x: x['efficiency_score'], reverse=True)

    # Find biggest increase
    biggest_increase = max(projects, key=lambda x: x['cost_trend_pct'])

    # Calculate total ROI where available
    roi_projects = [
        p for p in projects if p['revenue_impact'] > 0]
    total_roi = sum(p['revenue_impact'] for p in roi_projects)
    total_roi_spend = sum(p['monthly_spend'] for p in roi_projects)
    overall_roi = round(
        total_roi / (total_roi_spend * 12), 1) if total_roi_spend > 0 else 0

    # Waste detection
    waste_projects = [
        p for p in projects if p['duplicate_prompt_pct'] > 20]
    total_waste = sum(
        p['monthly_spend'] * (p['duplicate_prompt_pct'] / 100)
        for p in waste_projects
    )

    return {
        'total_monthly_spend': round(total_monthly, 2),
        'total_daily_spend': total_daily,
        'yesterday_spend': yesterday_spend,
        'project_count': len(projects),
        'projects_by_spend': by_spend,
        'projects_by_efficiency': by_efficiency,
        'biggest_increase': biggest_increase,
        'overall_roi_multiple': overall_roi,
        'waste_detected': round(total_waste, 2),
        'waste_projects': waste_projects,
        'critical_projects': [
            p for p in projects if p['status'] == 'critical'],
        'watch_projects': [
            p for p in projects if p['status'] == 'watch'],
        'healthy_projects': [
            p for p in projects if p['status'] == 'healthy']
    }


def get_project_detail(project_name):
    projects = load_projects()
    project = next(
        (p for p in projects
         if project_name.lower() in p['name'].lower()),
        None
    )
    return project


def get_ai_cost_rca():
    projects = load_projects()
    increasing = [p for p in projects if p['cost_trend_pct'] > 10]
    increasing.sort(key=lambda x: x['cost_trend_pct'], reverse=True)

    drivers = []
    for p in increasing:
        daily_increase = round(
            p['monthly_spend'] / 30 * (p['cost_trend_pct'] / 100), 2)

        causes = []
        if p['avg_prompt_length'] > p['peer_avg_prompt_length'] * 1.3:
            causes.append(
                f"Prompts {round((p['avg_prompt_length']/p['peer_avg_prompt_length']-1)*100)}% longer than peer average")
        if p['duplicate_prompt_pct'] > 20:
            causes.append(
                f"{p['duplicate_prompt_pct']}% duplicate prompts detected")
        if p['cost_trend_pct'] > 30:
            causes.append(
                f"Cost growing {p['cost_trend_pct']}% - model or traffic change likely")

        drivers.append({
            'project': p['name'],
            'team': p['team'],
            'daily_increase': daily_increase,
            'trend_pct': p['cost_trend_pct'],
            'causes': causes,
            'efficiency_score': p['efficiency_score'],
            'recommendation': get_optimization_recommendation(p)
        })

    return drivers


def get_optimization_recommendation(project):
    recs = []

    if project['avg_prompt_length'] > project['peer_avg_prompt_length'] * 1.3:
        savings_pct = round(
            (1 - project['peer_avg_prompt_length'] /
             project['avg_prompt_length']) * 100)
        recs.append(
            f"Trim system prompt to reduce unnecessary input tokens.")

    if project['duplicate_prompt_pct'] > 20:
        waste = round(
            project['monthly_spend'] * project['duplicate_prompt_pct'] / 100)
        recs.append(
            "Evaluate semantic caching to reduce repeated inference costs.")

    if project.get('model_primary') in ['gpt-4o', 'claude-opus-4-6']:
        recs.append(
            "Assess smaller models (GPT-4o-mini or Claude Haiku) for simpler tasks, subject to quality testing.")

    return recs if recs else ["Monitor for 7 days before optimizing"]


def format_ai_summary_for_slack(data):
    status_emoji = {'healthy': 'green', 'watch': 'yellow', 'critical': 'red'}

    project_lines = "\n".join([
        f"  *{p['name']}* - ${p['monthly_spend']:,.0f}/mo "
        f"| Score: {p['efficiency_score']}/100 "
        f"| Trend: {'+' if p['cost_trend_pct'] > 0 else ''}{p['cost_trend_pct']}%"
        for p in data['projects_by_spend']
    ])

    critical = "\n".join([
        f"  *{p['name']}* - {p['cost_trend_pct']}% cost increase, score {p['efficiency_score']}/100"
        for p in data['critical_projects']
    ]) if data['critical_projects'] else "  None"

    message = f"""*OpsBeacon AI Economics Summary*
━━━━━━━━━━━━━━━━━━━━

*Total AI Spend*
Yesterday: ${data['yesterday_spend']:,.0f}
Month to Date: ${data['total_monthly_spend']:,.0f}
Projects tracked: {data['project_count']}

*Projects by Spend & Efficiency:*
{project_lines}

*Needs Attention:*
{critical}

*Waste Detected:* ${data['waste_detected']:,.0f}/mo in duplicate prompts
*Overall ROI:* {data['overall_roi_multiple']}x on tracked revenue-generating projects

_Ask @Beacon: why did AI costs rise? | show Legal Copilot detail | AI efficiency scores_"""

    return message


if __name__ == "__main__":
    print("\n=== AI Economics Test ===")
    data = get_ai_economics_summary()
    print(f"Total monthly AI spend: ${data['total_monthly_spend']:,.2f}")
    print(f"Projects tracked: {data['project_count']}")
    print(f"Critical projects: {len(data['critical_projects'])}")
    print(f"Waste detected: ${data['waste_detected']:,.2f}/mo")
    print(f"\nProjects by efficiency:")
    for p in data['projects_by_efficiency']:
        print(f"  {p['name']}: {p['efficiency_score']}/100 ({p['status']})")
    print(f"\nFormatted Slack output:")
    print(format_ai_summary_for_slack(data))
    print(f"\nAI Cost RCA:")
    drivers = get_ai_cost_rca()
    for d in drivers:
        print(f"  {d['project']}: +{d['trend_pct']}% (+${d['daily_increase']}/day)")
        for cause in d['causes']:
            print(f"    Cause: {cause}")
        for rec in d['recommendation']:
            print(f"    Fix: {rec}")

# ── AI Economics Report (CTO Audience) ───────────────────────────────────────



# ── AI Economics Report (CTO Audience) ───────────────────────────────────────

def generate_ai_economics_report(customer_id: str = 'default') -> dict:
    """Structured data for the CTO-audience AI Economics Report."""
    data = get_ai_economics_summary()
    rca = get_ai_cost_rca()
    projects = data['projects_by_spend']
    total_monthly = data['total_monthly_spend']

    # Weighted MoM trend
    avg_trend = round(
        sum(p['cost_trend_pct'] * p['monthly_spend'] for p in projects) /
        total_monthly, 1
    ) if total_monthly > 0 else 0

    # Cost per 1K requests (weighted average across portfolio)
    total_monthly_requests = sum(p['daily_requests'] * 30 for p in projects)
    cost_per_1k = round((total_monthly / total_monthly_requests * 1000), 4) if total_monthly_requests > 0 else 0

    # GPU utilization — illustrative: derive from efficiency scores weighted by spend
    gpu_projects = [p for p in projects if p['efficiency_score'] < 90]
    avg_gpu_util = round(sum(p['efficiency_score'] * 0.7 for p in projects) / len(projects), 0) if projects else 0

    # Optimization potential — computed after actions are built (placeholder; overwritten below)
    opt_annual = 0  # will be overwritten below by sum of traced action savings only

    # ROI
    roi_projects = [p for p in projects if p['revenue_impact'] > 0]
    total_revenue_impact = sum(p['revenue_impact'] for p in roi_projects)
    total_roi_spend_annual = sum(p['monthly_spend'] for p in roi_projects) * 12

    # Top 3 optimization actions (SAR-style) — deduplicated by project
    actions = []
    seen_projects = set()
    for p in sorted(projects, key=lambda x: x['efficiency_score']):
        if p['name'] in seen_projects:
            continue
        recs = get_optimization_recommendation(p)
        # Traceable savings: 40% of spend eligible for optimization x 35% reduction, capped at 50% annual
        eligible_monthly = p['monthly_spend'] * 0.40
        raw_annual = eligible_monthly * 0.35 * 12
        cap_annual = p['monthly_spend'] * 0.50 * 12
        potential = round(min(raw_annual, cap_annual))
        # Pick most impactful rec for this project
        best_rec = next((r for r in recs if r != 'Monitor for 7 days before optimizing'), None)
        if best_rec:
            # Make title project-specific
            action_title = f"{p['name']}: {best_rec.split(' - ')[0]}"
            actions.append({
                'title': action_title,
                'detail': best_rec,
                'project': p['name'],
                'team': p['team'],
                'potential_annual': potential,
                'status': 'Identified',
            })
            seen_projects.add(p['name'])
        if len(actions) >= 3:
            break

    # Beacon Assessment narrative
    trend_word = 'growing faster than' if avg_trend > 5 else ('growing in line with' if avg_trend > 0 else 'declining relative to')
    critical_names = ', '.join(p['name'] for p in data['critical_projects'])
    # Find the highest-trend critical project for the assessment narrative
    critical_list = data['critical_projects']
    if critical_list:
        worst = max(critical_list, key=lambda p: p['cost_trend_pct'])
        assessment = (
            f"AI portfolio spending increased {avg_trend:.1f}% month over month. "
            f"{worst['name']} shows the largest reported project-level increase "
            f"(+{worst['cost_trend_pct']:.0f}%) with a relatively low efficiency score "
            f"({worst['efficiency_score']}/100). "
            f"Prioritize validating prompt optimization and caching opportunities for "
            f"{worst['name']}, while monitoring quality and performance before implementing changes."
        )
    else:
        assessment = (
            f"AI portfolio spending increased {avg_trend:.1f}% month over month. "
            f"No projects are in a critical state. "
            f"Monitor watch-list projects to prevent efficiency decay."
        )

    # Reconcile optimization potential with actual action savings
    opt_annual = sum(a['potential_annual'] for a in actions)

    return {
        'period': datetime.now().strftime('%B %Y'),
        'total_monthly_spend': total_monthly,
        'total_annual_spend': round(total_monthly * 12, 0),
        'avg_trend_pct': avg_trend,
        'cost_per_1k_requests': cost_per_1k,
        'gpu_utilization_pct': avg_gpu_util,
        'optimization_potential_annual': opt_annual,
        'project_count': len(projects),
        'overall_roi_multiple': data['overall_roi_multiple'],
        'total_revenue_impact': total_revenue_impact,
        'total_roi_spend_annual': total_roi_spend_annual,
        'waste_monthly': data['waste_detected'],
        'waste_annual': round(data['waste_detected'] * 12, 0),
        'projects': projects,
        'critical_projects': data['critical_projects'],
        'watch_projects': data['watch_projects'],
        'healthy_projects': data['healthy_projects'],
        'top_actions': actions,
        'rca_drivers': rca,
        'beacon_assessment': assessment,
    }


def format_ai_economics_report_for_slack(report: dict) -> str:
    trend = report['avg_trend_pct']
    trend_str = f'+{trend}%' if trend > 0 else f'{trend}%'
    trend_icon = '🔴' if trend > 10 else ('🟡' if trend > 0 else '🟢')
    status_icon = {'healthy': '🟢', 'watch': '🟡', 'critical': '🔴'}

    lines = [
        '*OPSBEACON AI ECONOMICS REPORT*',
        f'_{report["period"]} · CTO / AI Platform_',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
        '*AI INVESTMENT OVERVIEW*',
        '',
        f'  {"Monthly Spend":<28} ${report["total_monthly_spend"]:,.0f}',
        f'  {"Annual Run Rate":<28} ${report["total_annual_spend"]:,.0f}',
        f'  {"Portfolio Trend (MoM)":<28} {trend_icon} {trend_str}',
        f'  {"Cost per 1K Requests":<28} ${report["cost_per_1k_requests"]:.2f}',
        
        f'  {"Optimization Potential":<28} ${report["optimization_potential_annual"]:,.0f} annualized',
        f'  {"Active AI Projects":<28} {report["project_count"]}',
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
        '*PROJECT PORTFOLIO*',
        '',
    ]

    for p in sorted(report['projects'], key=lambda x: x['monthly_spend'], reverse=True):
        icon = status_icon.get(p['status'], '⚪')
        t = p['cost_trend_pct']
        t_str = f'+{t}%' if t > 0 else f'{t}%'
        lines += [
            f"  {icon} *{p['name']}*  ({p['team']})",
            f"     ${p['monthly_spend']:,.0f}/mo  ·  Score: {p['efficiency_score']}/100  ·  Trend: {t_str}  ·  {p['model_primary']}",
            '',
        ]

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Critical alerts
    if report['critical_projects']:
        lines += ['*⚠️  CRITICAL — ACTION REQUIRED*', '']
        for p in report['critical_projects']:
            recs = get_optimization_recommendation(p)
            waste = round(p['monthly_spend'] * p['duplicate_prompt_pct'] / 100)
            lines += [
                f"*{p['name']}* — {p['team']}",
                f"  Score: {p['efficiency_score']}/100  ·  Trend: +{p['cost_trend_pct']}%  ·  ${p['monthly_spend']:,.0f}/mo",
                f"  Duplicate-prompt cost exposure: Up to ${waste:,.0f}/month estimated; achievable savings require validation.",
            ]
            for rec in recs:
                lines.append(f'  → {rec}')
            lines.append('')
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Watch list
    if report['watch_projects']:
        lines += ['*🟡 WATCH LIST*', '']
        for p in report['watch_projects']:
            recs = get_optimization_recommendation(p)
            lines += [
                f"*{p['name']}* — {p['team']}",
                f"  Score: {p['efficiency_score']}/100  ·  Trend: +{p['cost_trend_pct']}%  ·  ${p['monthly_spend']:,.0f}/mo",
            ]
            if recs:
                lines.append(f'  → {recs[0]}')
            lines.append('')
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Top actions
    if report['top_actions']:
        lines += ['*DECISIONS REQUIRING ACTION*', '']
        for i, a in enumerate(report['top_actions'], 1):
            lines += [
                f"*{i:02d} — {a['title']}*",
                f"  Owner: {a['team']}  ·  Potential: ${a['potential_annual']:,.0f}/year",
                f"  _Reply_ `review {a['project'].lower()}` _or_ `assign {a['project'].lower()} to @owner`_",
                '',
            ]
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ROI
    lines += ['*AI RETURN ON INVESTMENT*', '_Tracked-project value / cost. Attribution requires validation._', '']
    if report['total_revenue_impact'] > 0:
        lines += [
            f"  Annual AI spend (ROI projects):  ${report['total_roi_spend_annual']:,.0f}",
            f"  Revenue impact attributed:       ${report['total_revenue_impact']:,.0f}",
            f"  ROI multiple:                    *{report['overall_roi_multiple']}x*",
            '',
            '  _Research Agent, Document Search, Legal Copilot have no tracked outcome data._',
            '  _Add business metric tracking to unlock full ROI visibility._',
        ]
    else:
        lines.append('  No revenue-linked projects tracked yet.')
    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Beacon Assessment
    lines += [
        '*BEACON ASSESSMENT*',
        '',
        f'  {report["beacon_assessment"]}',
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'*{len(report["critical_projects"])} Critical*  ·  '        f'*{len(report["watch_projects"])} Watch*  ·  '        f'*${report["optimization_potential_annual"]:,.0f} Optimization Potential*  ·  '        f'*{report["overall_roi_multiple"]}x Attributed Value / AI Spend*',
        '_Ask @Beacon: show Legal Copilot detail · why did AI costs rise · AI efficiency scores_',
    ]

    return '\n'.join(lines)
