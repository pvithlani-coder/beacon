from datetime import datetime

DEMO_FINDINGS = [
    {'dimension':'compliance_health','impact':-40,'issue':'2 public S3 buckets detected','fix':'Restrict public access on S3 buckets immediately','monthly_cost':0,'severity':'critical','remediation_cost_monthly':0,'engineering_effort':'1 hour estimated','operational_tradeoff':'Applications relying on public access require policy update before restricting.','owner':'Cloud Platform'},
    {'dimension':'coverage','impact':-20,'issue':'Storage encryption not fully enabled across all buckets','fix':'Enable server-side encryption with managed keys (SSE-KMS)','monthly_cost':120,'severity':'high','remediation_cost_monthly':120,'engineering_effort':'2 hours estimated','operational_tradeoff':'Key management overhead; minor latency impact on large object reads.','owner':'Security Engineering'},
    {'dimension':'detection_quality','impact':-15,'issue':'3 high-severity GuardDuty findings unresolved','fix':'Review and resolve GuardDuty findings; validate no active compromise','monthly_cost':0,'severity':'high','remediation_cost_monthly':0,'engineering_effort':'3 hours estimated','operational_tradeoff':'Findings may indicate benign activity; each requires manual triage.','owner':'Security Operations'},
    {'dimension':'logging_economy','impact':-10,'issue':'CloudWatch logging costs exceed 22% of total cloud spend','fix':'Review log retention tiers; reduce verbose logging for non-production environments','monthly_cost':620,'severity':'optimization','remediation_cost_monthly':0,'engineering_effort':'4 hours estimated','operational_tradeoff':'Reduced retention may affect post-incident forensics; validate against compliance requirements.','owner':'CISO / Compliance'},
    {'dimension':'asset_hygiene','impact':-10,'issue':'4 EC2 instances missing required governance tags (Owner, Environment)','fix':'Apply required tags; enforce via AWS Config rule','monthly_cost':0,'severity':'watch','remediation_cost_monthly':0,'engineering_effort':'1 hour estimated','operational_tradeoff':'None.','owner':'Cloud Platform'},
]
DEMO_SECURITY_SPEND = {'guardduty':180,'security_hub':95,'cloudtrail':42,'config':67,'shield':0,'cloudwatch':820,'waf':0}
DEMO_SCORE = 71
DEMO_RISK_LEVEL = 'MODERATE'

# Default owner/effort/tradeoff by dimension
DIMENSION_DEFAULTS = {
    'coverage':          {'owner': 'Security Engineering', 'engineering_effort': '2 hours estimated', 'operational_tradeoff': 'Minimal operational impact; standard enablement procedure.'},
    'detection_quality': {'owner': 'Security Operations',  'engineering_effort': '3 hours estimated', 'operational_tradeoff': 'Findings may indicate benign activity; each requires manual triage.'},
    'compliance_health': {'owner': 'Cloud Platform',       'engineering_effort': '2 hours estimated', 'operational_tradeoff': 'Applications relying on public access require review before restricting.'},
    'asset_hygiene':     {'owner': 'Cloud Platform',       'engineering_effort': '1 hour estimated',  'operational_tradeoff': 'None.'},
    'governance':        {'owner': 'Cloud Governance',     'engineering_effort': '2 hours estimated', 'operational_tradeoff': 'None.'},
    'logging_economy':   {'owner': 'CISO / Compliance',    'engineering_effort': '4 hours estimated', 'operational_tradeoff': 'Reduced retention may affect forensics; validate against compliance requirements.'},
    'tool_efficiency':   {'owner': 'Security Engineering', 'engineering_effort': '3 hours estimated', 'operational_tradeoff': 'Enabling security services adds incremental cloud spend.'},
}

def classify_finding(f):
    if 'severity' in f:
        enriched = {**DIMENSION_DEFAULTS.get(f.get('dimension',''), {}), **f}
        return enriched
    issue = f.get('issue','').lower()
    impact = abs(f.get('impact',0))
    if any(x in issue for x in ['public s3','public bucket','exposed','guardduty finding']):
        severity = 'critical'
    elif impact >= 20 or any(x in issue for x in ['not enabled','disabled','encryption','cloudtrail']):
        severity = 'high'
    elif 'cost' in issue or 'over-log' in issue or 'retention' in issue or 'cost explorer' in issue:
        severity = 'optimization'
    else:
        severity = 'watch'
    defaults = DIMENSION_DEFAULTS.get(f.get('dimension',''), {})
    return {**defaults, **f, 'severity': severity}

def generate_security_economics_report(customer_id='default'):
    try:
        from security_score import calculate_security_cost_score
        raw = calculate_security_cost_score()
        overall_score = raw['overall_score']
        risk_level = raw['risk_level']
        raw_findings = raw['actionable_findings']
        dimensions = raw['dimensions']
        live_data = True
    except Exception:
        overall_score = DEMO_SCORE
        risk_level = DEMO_RISK_LEVEL
        raw_findings = DEMO_FINDINGS
        dimensions = {}
        live_data = False

    findings = [classify_finding(f) for f in raw_findings]
    critical = [f for f in findings if f['severity'] == 'critical']
    high     = [f for f in findings if f['severity'] == 'high']
    optimization = [f for f in findings if f['severity'] == 'optimization']
    watch    = [f for f in findings if f['severity'] == 'watch']

    high_risk_gaps = len(critical) + len(high)
    gaps_requiring_decision = len([f for f in critical + high if f.get('remediation_cost_monthly', f.get('monthly_cost',0)) > 0 or abs(f.get('impact',0)) >= 20])
    sec_spend = DEMO_SECURITY_SPEND
    security_spend_monthly = sum(sec_spend.values())
    remediation_cost_monthly = sum(f.get('remediation_cost_monthly', f.get('monthly_cost',0)) for f in critical + high if f.get('remediation_cost_monthly', f.get('monthly_cost',0)) > 0)
    optimization_potential_monthly = sum(f.get('monthly_cost',0) for f in optimization)
    priority_findings = (critical + high + optimization)[:3]

    if overall_score >= 80:
        posture_label = 'Strong posture'
    elif overall_score >= 65:
        posture_label = 'Moderate posture'
    elif overall_score >= 50:
        posture_label = 'Elevated risk'
    else:
        posture_label = 'Critical risk'

    if critical:
        worst = critical[0]
        assessment = (f"Security posture score is {overall_score}/100 ({posture_label.lower()}). "
            f"The highest-priority gap is {worst['issue'].lower()}. "
            f"Estimated incremental remediation cost for identified gaps is ${remediation_cost_monthly:,.0f}/month. "
            f"Selected security spend may be optimizable by up to ${optimization_potential_monthly:,.0f}/month pending policy validation.")
    elif high:
        worst = high[0]
        assessment = (f"Security posture score is {overall_score}/100 ({posture_label.lower()}). "
            f"No critical gaps identified. Highest-priority finding: {worst['issue'].lower()}. "
            f"Estimated incremental remediation cost: ${remediation_cost_monthly:,.0f}/month.")
    else:
        assessment = (f"Security posture score is {overall_score}/100 ({posture_label.lower()}). "
            f"No critical or high-severity gaps identified. Review optimization opportunities to reduce security spend without increasing exposure.")

    return {
        'period': datetime.now().strftime('%B %Y'),
        'overall_score': overall_score,
        'posture_label': posture_label,
        'risk_level': risk_level,
        'high_risk_gaps': high_risk_gaps,
        'gaps_requiring_decision': gaps_requiring_decision,
        'security_spend_monthly': security_spend_monthly,
        'remediation_cost_monthly': remediation_cost_monthly,
        'optimization_potential_monthly': optimization_potential_monthly,
        'critical_findings': critical,
        'high_findings': high,
        'optimization_findings': optimization,
        'watch_findings': watch,
        'priority_findings': priority_findings,
        'dimensions': dimensions,
        'beacon_assessment': assessment,
        'live_data': live_data,
    }

def format_security_economics_report_for_slack(report):
    lines = ['*OPSBEACON SECURITY ECONOMICS*', f'_{report["period"]} · CISO / CFO_', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    score = report['overall_score']
    posture = report['posture_label']
    gaps = report['high_risk_gaps']
    decisions = report['gaps_requiring_decision']
    rem = report['remediation_cost_monthly']
    opt = report['optimization_potential_monthly']
    lines += ['*SECURITY ECONOMICS OVERVIEW*', '',
        f'  {"Security Trade-off Score":<30} {score}/100  ({posture})',
        f'  {"Open High-Risk Gaps":<30} {gaps}  ({decisions} require decisions)',
        f'  {"Remediation Cost (est.)":<30} ${rem:,.0f}/mo incremental',
        f'  {"Avoidable Security Spend (est.)":<30} ${opt:,.0f}/mo  _(pending policy validation)_',
        '', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    sec_spend = report['security_spend_monthly']
    lines += ['*SECURITY INVESTMENT & EXPOSURE*', '', f'  Current security-related cloud spend   ${sec_spend:,.0f}/mo']
    if rem > 0:
        lines.append(f'  Incremental cost to close identified gaps  +${rem:,.0f}/mo')
    if opt > 0:
        lines.append(f'  Identified security cost optimization      \u2212${opt:,.0f}/mo  _(subject to validation)_')
    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    critical = report['critical_findings']
    high = report['high_findings']
    if critical or high:
        lines += ['\u26a0\ufe0f  *PRIORITY SECURITY GAPS*', '_Critical: immediate access control or active threat exposure_', '']
        for f in critical:
            cost = f.get('remediation_cost_monthly', f.get('monthly_cost',0))
            cost_str = f'+${cost:,.0f}/mo estimated' if cost > 0 else 'No incremental cloud spend estimated'
            lines += [f'\U0001f534 *{f["issue"]}*', f'  Severity: Critical  \u00b7  Owner: {f.get("owner","TBD")}',
                f'  Remediation: {f["fix"]}', f'  Estimated incremental cost: {cost_str}',
                f'  Effort: {f.get("engineering_effort","TBD")}', f'  Trade-off: {f.get("operational_tradeoff","None identified.")}', '']
        for f in high:
            cost = f.get('remediation_cost_monthly', f.get('monthly_cost',0))
            cost_str = f'+${cost:,.0f}/mo estimated' if cost > 0 else 'No incremental cloud spend estimated'
            lines += [f'\U0001f7e0 *{f["issue"]}*', f'  Severity: High  \u00b7  Owner: {f.get("owner","TBD")}',
                f'  Remediation: {f["fix"]}', f'  Estimated incremental cost: {cost_str}',
                f'  Effort: {f.get("engineering_effort","TBD")}', f'  Trade-off: {f.get("operational_tradeoff","None identified.")}', '']
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    opt_findings = report['optimization_findings']
    watch = report['watch_findings']
    if opt_findings or watch:
        lines += ['\U0001f7e1 *OPTIMIZATION & WATCH*', '_Spending that may be reducible, or hygiene items without immediate exposure_', '']
        for f in opt_findings:
            lines += [f'  \U0001f4b0 {f["issue"]}',
                f'  Potential: up to ${f.get("monthly_cost",0):,.0f}/mo \u2014 subject to compliance policy validation',
                f'  Action: {f["fix"]}', f'  Owner: {f.get("owner","TBD")}', '']
        for f in watch:
            lines += [f'  \U0001f441  {f["issue"]}', f'  Action: {f["fix"]}', '']
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    priority = report['priority_findings']
    if priority:
        lines += ['*DECISIONS REQUIRING ACTION*', '']
        for i, f in enumerate(priority, 1):
            cost = f.get('remediation_cost_monthly', f.get('monthly_cost',0))
            sev = f.get('severity','watch').capitalize()
            if cost > 0:
                economic = f'+${cost:,.0f}/mo estimated incremental spend'
            elif f.get('severity') == 'optimization':
                economic = f'Up to ${f.get("monthly_cost",0):,.0f}/mo potential savings (pending validation)'
            else:
                economic = 'No incremental cloud charge estimated'
            lines += [f'0{i} \u2014 {f["fix"].split(";")[0].split(".")[0]}',
                f'  Owner: {f.get("owner","TBD")}  \u00b7  {economic}',
                f'  _Reply_ `review {f.get("owner","security").lower().split("/")[0].strip()}` _or_ `assign finding-{i:02d} to @owner`_', '']
        lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']
    lines += ['*BEACON ASSESSMENT*', '', f'  {report["beacon_assessment"]}', '', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━']
    data_note = '' if report['live_data'] else '  _(demo data)_  \u00b7 '
    lines.append(f'{data_note}*{report["high_risk_gaps"]} High-Risk Gaps*  \u00b7  *${report["remediation_cost_monthly"]:,.0f}/mo Remediation Cost*  \u00b7  *${report["optimization_potential_monthly"]:,.0f}/mo Optimization Potential*')
    lines.append('Ask @Beacon: `which security gaps cost under $500 to fix` \u00b7 `show security spend breakdown` \u00b7 `explain security score`')
    return '\n'.join(lines)