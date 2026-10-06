import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from report_intelligence import (
    init_db, get_top_actionable_findings, format_interactive_footer,
    create_report, FindingStatus
)

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


# ── Data Collection ───────────────────────────────────────────────────────────

def get_cemr_data(customer_id: str = 'default') -> dict:
    """Collect all data needed for the Cloud Economics Monthly Report."""
    init_db()

    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1).strftime('%Y-%m-%d')
    period_end = now.strftime('%Y-%m-%d')

    data = {
        'period_start': period_start,
        'period_end': period_end,
        'generated_at': now.isoformat(),
        'customer_id': customer_id,
    }

    # 1. AWS Costs
    try:
        from aws_costs import get_aws_costs
        costs = get_aws_costs()
        data['costs'] = costs
    except Exception:
        data['costs'] = {}

    # 2. Forecast
    try:
        from aws_costs import get_cost_forecast
        forecast = get_cost_forecast()
        data['forecast'] = forecast
    except Exception:
        data['forecast'] = {}

    # 3. Anomalies
    try:
        from aws_costs import get_cost_anomalies
        anomalies = get_cost_anomalies()
        data['anomalies'] = anomalies
    except Exception:
        data['anomalies'] = {}

    # 4. Team summaries
    try:
        from team_summaries import get_all_team_summaries
        teams = get_all_team_summaries()
        data['teams'] = teams
    except Exception:
        data['teams'] = {}

    # 5. Top findings from Report Intelligence
    data['top_findings'] = get_top_actionable_findings(customer_id, limit=3)

    return data


def _fmt(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.1f}K"
    return f"${amount:.0f}"


def _fmt_pct(pct: float, show_sign: bool = True) -> str:
    sign = '+' if pct > 0 else ''
    return f"{sign}{pct:.1f}%"


def _trend_emoji(pct: float) -> str:
    if pct > 10:
        return '🔴'
    elif pct > 3:
        return '🟡'
    elif pct < -3:
        return '🟢'
    return '⚪'


# ── Slack Formatter ───────────────────────────────────────────────────────────

def format_cemr_for_slack(data: dict) -> str:
    costs = data.get('costs', {})
    forecast = data.get('forecast', {})
    anomalies = data.get('anomalies', {})
    teams = data.get('teams', {})
    top_findings = data.get('top_findings', [])

    period = f"{data['period_start']} to {data['period_end']}"

    # ── Extract key numbers ──
    current_spend = costs.get('total_cost', 0)
    prior_spend = costs.get('prior_month_cost', current_spend)
    mom_delta = current_spend - prior_spend
    mom_pct = (mom_delta / prior_spend * 100) if prior_spend else 0

    month_end_forecast = forecast.get('projected_month_end', current_spend * 1.1)
    fy_budget = forecast.get('annual_budget', 0)
    fy_runrate = forecast.get('annual_run_rate', month_end_forecast * 12)
    forecast_vs_plan = forecast.get('forecast_vs_plan', 0)
    forecast_vs_plan_pct = forecast.get('forecast_vs_plan_pct', 0)
    forecast_confidence = forecast.get('confidence', 0.85)

    # Open opportunity = sum of top findings annualized / 12 for monthly view
    open_opportunity = sum(f['annualized_impact'] for f in top_findings)

    lines = []

    # ── Title ──
    lines += [
        '*OpsBeacon Cloud Economics Monthly Report*',
        f'_{period}_',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── Headline KPIs ──
    mom_str = _fmt_pct(mom_pct)
    plan_str = f"+{_fmt(forecast_vs_plan)}" if forecast_vs_plan >= 0 else f"-{_fmt(abs(forecast_vs_plan))}"
    plan_pct_str = _fmt_pct(forecast_vs_plan_pct)
    opp_str = _fmt(open_opportunity)

    lines += [
        f'*{_fmt(current_spend)}* Spend   *{mom_str} MoM*   '
        f'*{plan_str} / {plan_pct_str} vs Plan*   *{opp_str} Open Opportunity*',
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── Section 1: Spend Summary ──
    lines += [
        '*1 · Spend Summary*',
        '',
        f'  MTD Spend:          {_fmt(current_spend)}',
        f'  Prior Month:        {_fmt(prior_spend)}',
        f'  MoM Change:         {_fmt(mom_delta)} ({_fmt_pct(mom_pct)}) {_trend_emoji(mom_pct)}',
        f'  Month-End Forecast: {_fmt(month_end_forecast)}',
        '',
    ]

    # ── Section 2: Top Cost Drivers ──
    services = costs.get('by_service', [])
    total_mom_change = sum(
        s.get('mom_delta', 0) for s in services if s.get('mom_delta', 0) > 0
    ) or 1  # avoid division by zero

    if services:
        lines += ['*2 · Top Cost Drivers*', '']
        for svc in services[:5]:
            name = svc.get('service', 'Unknown')
            spend = svc.get('cost', 0)
            wow_pct = svc.get('wow_pct', 0)
            mom_d = svc.get('mom_delta', 0)
            contribution = abs(mom_d) / abs(total_mom_change) * 100 if total_mom_change else 0

            wow_str = _fmt_pct(wow_pct)
            mom_d_str = f"+{_fmt(mom_d)}" if mom_d >= 0 else f"-{_fmt(abs(mom_d))}"
            contrib_str = f"{contribution:.0f}% of change" if abs(mom_d) > 0 else "stable"
            emoji = _trend_emoji(wow_pct)

            lines.append(
                f'  {emoji} *{name}*   {_fmt(spend)}   '
                f'WoW {wow_str}   {mom_d_str} MoM   _{contrib_str}_'
            )
        lines.append('')
    else:
        lines += ['*2 · Top Cost Drivers*', '  No service breakdown available.', '']

    # ── Section 3: Team Breakdown ──
    team_list = teams.get('teams', []) if isinstance(teams, dict) else []
    if team_list:
        lines += ['*3 · Team Breakdown*', '']
        total_team_spend = sum(t.get('total_spend', 0) for t in team_list) or 1
        for team in sorted(team_list, key=lambda t: t.get('total_spend', 0), reverse=True)[:6]:
            name = team.get('team_name', 'Unknown')
            spend = team.get('total_spend', 0)
            mom_t = team.get('mom_change_pct', 0)
            pct_total = spend / total_team_spend * 100
            top_svc = team.get('top_service', '')
            top_svc_str = f" · top: {top_svc}" if top_svc else ''
            emoji = _trend_emoji(mom_t)
            lines.append(
                f'  {emoji} *{name}*   {_fmt(spend)}   '
                f'{pct_total:.0f}% of total   {_fmt_pct(mom_t)} MoM{top_svc_str}'
            )
        lines.append('')
    else:
        lines += ['*3 · Team Breakdown*', '  No team data available.', '']

    # ── Section 4: Forecast & Budget ──
    ninety_day = forecast.get('ninety_day_forecast', month_end_forecast * 3)
    fy_variance = fy_runrate - fy_budget if fy_budget else 0
    fy_variance_str = f"+{_fmt(fy_variance)}" if fy_variance >= 0 else f"-{_fmt(abs(fy_variance))}"
    confidence_pct = int(forecast_confidence * 100)

    lines += [
        '*4 · Forecast & Budget*',
        '',
        f'  Month-End Forecast:  {_fmt(month_end_forecast)}',
        f'  Forecast vs Plan:    {plan_str} / {plan_pct_str}',
        f'  90-Day Forecast:     {_fmt(ninety_day)}',
        f'  FY Run-Rate:         {_fmt(fy_runrate)}',
    ]
    if fy_budget:
        lines.append(f'  FY Budget:           {_fmt(fy_budget)}')
        lines.append(f'  Projected Variance:  {fy_variance_str}')
    lines += [
        f'  Forecast Confidence: {confidence_pct}%',
        '',
    ]

    # ── Section 5: Anomalies & Exceptions ──
    active_anomalies = anomalies.get('active', [])
    resolved_anomalies = anomalies.get('resolved', [])
    all_anomalies = (
        [(a, 'ACTIVE') for a in active_anomalies] +
        [(a, 'RESOLVED') for a in resolved_anomalies]
    )

    lines += ['*5 · Anomalies & Exceptions*', '']
    if all_anomalies:
        for anomaly, status in all_anomalies[:5]:
            service = anomaly.get('service', 'Unknown')
            impact = anomaly.get('impact', 0)
            pct_change = anomaly.get('pct_change', 0)
            root_cause = anomaly.get('root_cause', '')
            owner = anomaly.get('owner', '')
            resolved_date = anomaly.get('resolved_date', '')

            status_emoji = '🔴' if status == 'ACTIVE' else '✅'
            header = f"  {status_emoji} *{service}* +{pct_change:.0f}% · {_fmt(impact)} impact · *{status}*"
            lines.append(header)
            if root_cause:
                lines.append(f"    _{root_cause}_")
            meta = []
            if owner:
                meta.append(f"Owner: {owner}")
            if status == 'RESOLVED' and resolved_date:
                meta.append(f"Resolved: {resolved_date[:10]}")
            if meta:
                lines.append(f"    {' · '.join(meta)}")
            lines.append('')
    else:
        lines += ['  ✅ No active anomalies this period.', '']

    # ── Section 6: Top Actions (from SAR) ──
    lines += ['*6 · Top Actions*', '']
    if top_findings:
        for i, f in enumerate(top_findings, 1):
            annual = f['annualized_impact']
            confidence_pct_f = int(f['confidence'] * 100)
            days = f['days_open']
            owner_str = f['owner'] if f.get('owner') else 'Unassigned'
            days_str = f'{days}d open' if days > 0 else 'new'
            status_str = f['status'].replace('_', ' ').title()

            lines.append(f"  *{i}. {f['title']}* — {_fmt(annual)} annualized")
            lines.append(f"    {owner_str} · {days_str} · {confidence_pct_f}% confidence")

            # Buttons — same Finding IDs as SAR
            actions = f['actions_available']
            btns = []
            if 'approve' in actions:
                btns.append(f"`[Approve {f['id']}]`")
            if 'assign' in actions:
                btns.append(f"`[Assign {f['id']}]`")
            if 'generate_fix' in actions:
                btns.append(f"`[Generate Fix {f['id']}]`")
            if 'explain' in actions:
                btns.append(f"`[Explain {f['id']}]`")
            if 'snooze' in actions:
                btns.append(f"`[Snooze {f['id']}]`")
            if btns:
                lines.append('    ' + '  '.join(btns))
            lines.append('')
    else:
        lines += ['  No open findings. Run `@Beacon savings action report` to sync.', '']

    # ── Action Layer ──
    lines.append(format_interactive_footer(data['customer_id']))

    return '\n'.join(lines)


# ── Word Doc ──────────────────────────────────────────────────────────────────

def generate_cemr_word_doc(data: dict) -> str:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()
        costs = data.get('costs', {})
        forecast = data.get('forecast', {})
        anomalies = data.get('anomalies', {})
        teams = data.get('teams', {})
        top_findings = data.get('top_findings', [])

        current_spend = costs.get('total_cost', 0)
        prior_spend = costs.get('prior_month_cost', current_spend)
        mom_delta = current_spend - prior_spend
        mom_pct = (mom_delta / prior_spend * 100) if prior_spend else 0
        month_end_forecast = forecast.get('projected_month_end', current_spend * 1.1)
        fy_budget = forecast.get('annual_budget', 0)
        fy_runrate = forecast.get('annual_run_rate', month_end_forecast * 12)
        forecast_vs_plan = forecast.get('forecast_vs_plan', 0)
        forecast_vs_plan_pct = forecast.get('forecast_vs_plan_pct', 0)
        forecast_confidence = forecast.get('confidence', 0.85)
        open_opportunity = sum(f['annualized_impact'] for f in top_findings)

        # Title
        title = doc.add_heading('OpsBeacon Cloud Economics Monthly Report', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(
            f"Period: {data['period_start']} to {data['period_end']}"
        ).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(
            f"Generated: {data['generated_at'][:19]} UTC"
        ).alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Headline KPIs table
        doc.add_heading('Headline KPIs', 1)
        kpi_table = doc.add_table(rows=2, cols=4)
        kpi_table.style = 'Table Grid'
        headers = ['MTD Spend', 'MoM Change', 'vs Plan', 'Open Opportunity']
        values = [
            _fmt(current_spend),
            f"{_fmt_pct(mom_pct)}",
            f"{'+' if forecast_vs_plan >= 0 else ''}{_fmt(forecast_vs_plan)} / {_fmt_pct(forecast_vs_plan_pct)}",
            _fmt(open_opportunity)
        ]
        for i, (h, v) in enumerate(zip(headers, values)):
            kpi_table.rows[0].cells[i].text = h
            kpi_table.rows[1].cells[i].text = v
        doc.add_paragraph()

        # Spend Summary
        doc.add_heading('1. Spend Summary', 1)
        doc.add_paragraph(
            f"MTD spend of {_fmt(current_spend)} represents a {_fmt_pct(mom_pct)} change "
            f"({_fmt(abs(mom_delta))} {'increase' if mom_delta >= 0 else 'decrease'}) "
            f"versus prior month ({_fmt(prior_spend)}). "
            f"Month-end forecast: {_fmt(month_end_forecast)}."
        )

        # Top Cost Drivers
        doc.add_heading('2. Top Cost Drivers', 1)
        services = costs.get('by_service', [])
        total_mom_change = sum(s.get('mom_delta', 0) for s in services if s.get('mom_delta', 0) > 0) or 1
        if services:
            svc_table = doc.add_table(rows=len(services[:5]) + 1, cols=5)
            svc_table.style = 'Table Grid'
            for i, h in enumerate(['Service', 'Spend', 'WoW %', 'MoM Δ', 'Contribution']):
                svc_table.rows[0].cells[i].text = h
            for j, svc in enumerate(services[:5], 1):
                mom_d = svc.get('mom_delta', 0)
                contribution = abs(mom_d) / abs(total_mom_change) * 100
                svc_table.rows[j].cells[0].text = svc.get('service', '')
                svc_table.rows[j].cells[1].text = _fmt(svc.get('cost', 0))
                svc_table.rows[j].cells[2].text = _fmt_pct(svc.get('wow_pct', 0))
                svc_table.rows[j].cells[3].text = f"+{_fmt(mom_d)}" if mom_d >= 0 else f"-{_fmt(abs(mom_d))}"
                svc_table.rows[j].cells[4].text = f"{contribution:.0f}% of change"
        doc.add_paragraph()

        # Team Breakdown
        doc.add_heading('3. Team Breakdown', 1)
        team_list = teams.get('teams', []) if isinstance(teams, dict) else []
        if team_list:
            total_team_spend = sum(t.get('total_spend', 0) for t in team_list) or 1
            t_table = doc.add_table(rows=len(team_list[:6]) + 1, cols=4)
            t_table.style = 'Table Grid'
            for i, h in enumerate(['Team', 'Spend', '% Total', 'MoM']):
                t_table.rows[0].cells[i].text = h
            for j, team in enumerate(
                sorted(team_list, key=lambda t: t.get('total_spend', 0), reverse=True)[:6], 1
            ):
                spend = team.get('total_spend', 0)
                t_table.rows[j].cells[0].text = team.get('team_name', '')
                t_table.rows[j].cells[1].text = _fmt(spend)
                t_table.rows[j].cells[2].text = f"{spend/total_team_spend*100:.0f}%"
                t_table.rows[j].cells[3].text = _fmt_pct(team.get('mom_change_pct', 0))
        doc.add_paragraph()

        # Forecast & Budget
        doc.add_heading('4. Forecast & Budget', 1)
        ninety_day = forecast.get('ninety_day_forecast', month_end_forecast * 3)
        fy_variance = fy_runrate - fy_budget if fy_budget else 0
        forecast_lines = [
            f"Month-End Forecast: {_fmt(month_end_forecast)}",
            f"Forecast vs Plan: {'+' if forecast_vs_plan >= 0 else ''}{_fmt(forecast_vs_plan)} / {_fmt_pct(forecast_vs_plan_pct)}",
            f"90-Day Forecast: {_fmt(ninety_day)}",
            f"FY Run-Rate: {_fmt(fy_runrate)}",
        ]
        if fy_budget:
            forecast_lines += [
                f"FY Budget: {_fmt(fy_budget)}",
                f"Projected Variance: {'+' if fy_variance >= 0 else ''}{_fmt(fy_variance)}",
            ]
        forecast_lines.append(f"Forecast Confidence: {int(forecast_confidence * 100)}%")
        for line in forecast_lines:
            doc.add_paragraph(line, style='List Bullet')
        doc.add_paragraph()

        # Anomalies
        doc.add_heading('5. Anomalies & Exceptions', 1)
        active = anomalies.get('active', [])
        resolved = anomalies.get('resolved', [])
        if active or resolved:
            for a in active[:3]:
                p = doc.add_paragraph()
                p.add_run(f"[ACTIVE] {a.get('service', '')} +{a.get('pct_change', 0):.0f}% · {_fmt(a.get('impact', 0))} impact").bold = True
                if a.get('root_cause'):
                    p.add_run(f"\n  {a['root_cause']}")
            for a in resolved[:3]:
                p = doc.add_paragraph()
                p.add_run(f"[RESOLVED] {a.get('service', '')} · {_fmt(a.get('impact', 0))} impact").bold = True
                if a.get('root_cause'):
                    p.add_run(f"\n  {a['root_cause']}")
        else:
            doc.add_paragraph('No active anomalies this period.')
        doc.add_paragraph()

        # Top Actions
        doc.add_heading('6. Top Actions', 1)
        if top_findings:
            for i, f in enumerate(top_findings, 1):
                p = doc.add_paragraph()
                p.add_run(f"{i}. {f['title']}").bold = True
                p.add_run(
                    f"\n   Annualized impact: {_fmt(f['annualized_impact'])}"
                    f"\n   Owner: {f.get('owner', 'Unassigned')}"
                    f"\n   Days open: {f['days_open']}"
                    f"\n   Confidence: {int(f['confidence']*100)}%"
                    f"\n   Finding ID: {f['id']}"
                )
        else:
            doc.add_paragraph('No open findings.')

        # Footer
        doc.add_paragraph()
        footer = doc.add_paragraph(
            f"OpsBeacon · Cloud Economics Monthly Report · "
            f"{data['period_start']}"
        )
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Save
        desktop = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.expanduser('~')
        filename = f"OpsBeacon_CEMR_{datetime.now().strftime('%Y%m%d')}.docx"
        path = os.path.join(desktop, filename)
        doc.save(path)
        return path

    except Exception as e:
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_cloud_economics_report(
    customer_id: str = 'default',
    generated_by: str = 'on_demand'
) -> dict:
    data = get_cemr_data(customer_id)
    data['generated_by'] = generated_by

    # Register in Report Intelligence
    finding_ids = [f['id'] for f in data.get('top_findings', [])]
    data['report_id'] = create_report(
        report_type='cloud_economics_monthly',
        audience='practitioner',
        finding_ids=finding_ids,
        customer_id=customer_id,
        generated_by=generated_by
    )

    return data


if __name__ == '__main__':
    print('Generating Cloud Economics Monthly Report...')
    data = generate_cloud_economics_report()

    print('\n=== Slack Output ===')
    print(format_cemr_for_slack(data))

    print('\n=== Generating Word Doc ===')
    path = generate_cemr_word_doc(data)
    if path:
        print(f'Word doc saved: {path}')
    else:
        print('Word doc generation failed')
