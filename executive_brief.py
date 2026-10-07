import os
from datetime import datetime, timezone
from report_intelligence import (
    init_db, get_top_actionable_findings, get_findings,
    create_report, FindingStatus
)


def _fmt(amount: float) -> str:
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.1f}K"
    return f"${amount:.0f}"


def _fmt_pct(pct: float) -> str:
    sign = '+' if pct > 0 else ''
    return f"{sign}{pct:.1f}%"


def get_executive_brief_data(customer_id: str = 'default') -> dict:
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

    # AWS costs
    try:
        from aws_costs import get_aws_costs
        raw_costs = get_aws_costs()
        total = sum(raw_costs.values())
        data['costs'] = {
            'total_cost': total,
            'prior_month_cost': total,
            'mom_delta': 0,
            'mom_pct': 0,
        }
    except Exception:
        data['costs'] = {'total_cost': 0, 'prior_month_cost': 0, 'mom_delta': 0, 'mom_pct': 0}

    # Forecast
    try:
        from aws_costs import get_cost_forecast
        forecast = get_cost_forecast()
        data['forecast'] = forecast
    except Exception:
        data['forecast'] = {}

    # Top findings — executive view (limit 3)
    data['decisions'] = get_top_actionable_findings(customer_id, limit=3)

    # Completed actions — findings in implemented/verified status
    try:
        completed = get_findings(
            customer_id=customer_id,
            status=FindingStatus.IMPLEMENTED.value,
            limit=5
        )
        data['completed_actions'] = completed
    except Exception:
        data['completed_actions'] = []

    # FinOps score
    try:
        from finops_score import calculate_finops_score
        score_data = calculate_finops_score()
        data['finops_score'] = score_data.get('overall_score', 0)
    except Exception:
        data['finops_score'] = 0

    return data


def format_executive_brief_for_slack(data: dict) -> str:
    costs = data.get('costs', {})
    forecast = data.get('forecast', {})
    decisions = data.get('decisions', [])
    completed = data.get('completed_actions', [])
    finops_score = data.get('finops_score', 0)

    current_spend = costs.get('total_cost', 0)
    prior_spend = costs.get('prior_month_cost', current_spend)
    mom_delta = current_spend - prior_spend
    mom_pct = (mom_delta / prior_spend * 100) if prior_spend else 0

    month_end_forecast = forecast.get('projected_month_end', current_spend * 1.1)
    fy_budget = forecast.get('annual_budget', 0)
    fy_runrate = forecast.get('annual_run_rate', month_end_forecast * 12)
    fy_variance = fy_runrate - fy_budget if fy_budget else 0
    forecast_vs_plan = forecast.get('forecast_vs_plan', 0)
    forecast_vs_plan_pct = forecast.get('forecast_vs_plan_pct', 0)
    forecast_confidence = int(forecast.get('confidence', 0.92) * 100)

    open_opportunity = sum(f['annualized_impact'] for f in decisions)
    savings_realized = sum(f.get('annualized_impact', 0) for f in completed)

    now = datetime.now(timezone.utc)
    month_label = now.strftime('%B %Y')

    lines = []

    # Title
    lines += [
        '*OpsBeacon Executive Cloud Economics Brief*',
        f'_{month_label} | Prepared by OpsBeacon_',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # Headline KPIs — 4 numbers, one line
    mom_str = _fmt_pct(mom_pct)
    plan_str = f"+{_fmt(forecast_vs_plan)}" if forecast_vs_plan >= 0 else f"-{_fmt(abs(forecast_vs_plan))}"
    plan_pct_str = _fmt_pct(forecast_vs_plan_pct)
    n_open = len(decisions)

    lines += [
        f'*{_fmt(current_spend)}*  ·  *{plan_str} vs Plan*  ·  '
        f'*{_fmt(savings_realized)} Savings Realized*  ·  *{_fmt(open_opportunity)} Open Opportunity*',
        f'_{mom_str} MoM_   _{plan_pct_str}_   _This month_   _{n_open} open actions_',
        '',
    ]

    if fy_budget:
        lines += [
            f'_FY Forecast: {_fmt(fy_runrate)} · Budget: {_fmt(fy_budget)} · '
            f'Projected variance: {_fmt_pct((fy_variance/fy_budget*100) if fy_budget else 0)}_',
            '',
        ]

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Section 1: What Changed
    lines += ['*1 · What Changed*', '']

    top_drivers = []
    try:
        from aws_costs import get_aws_costs
        raw = get_aws_costs()
        top_drivers = sorted(raw.items(), key=lambda x: x[1], reverse=True)[:2]
    except Exception:
        pass

    if top_drivers:
        driver_text = ' and '.join([f'{name.split()[0]} workloads' for name, _ in top_drivers[:2]])
        lines.append(
            f'Cloud spend {"increased" if mom_delta >= 0 else "decreased"} '
            f'{_fmt(abs(mom_delta))} ({mom_str}) this month, primarily driven by {driver_text}.'
        )
    else:
        lines.append(
            f'Cloud spend is {_fmt(current_spend)} month-to-date, '
            f'tracking {_fmt_pct(mom_pct)} versus prior month.'
        )

    if savings_realized > 0:
        lines.append(
            f'The movement was partially offset by {_fmt(savings_realized)} in verified '
            f'optimization savings from completed actions.'
        )

    if fy_budget and fy_variance > 0:
        lines.append(
            f'At the current run rate, cloud spend is projected to finish the year '
            f'{_fmt(fy_variance)} above plan.'
        )

    lines.append('')

    # Section 2: Business Outlook (compact table)
    lines += ['*2 · Business Outlook*', '']

    fy_variance_str = f"↑ {_fmt(fy_variance)} vs plan" if fy_variance > 0 else (
        f"↓ {_fmt(abs(fy_variance))} under plan" if fy_variance < 0 else "On plan"
    )

    lines += [
        f'  {"Metric":<28} {"Current":<14} Outlook',
        f'  {"─"*28} {"─"*14} {"─"*20}',
        f'  {"FY Cloud Forecast":<28} {_fmt(fy_runrate):<14} {fy_variance_str}' if fy_budget else
        f'  {"FY Run-Rate":<28} {_fmt(fy_runrate):<14} —',
        f'  {"Verified Savings YTD":<28} {_fmt(savings_realized):<14} ↑ {_fmt(savings_realized)} this month',
        f'  {"Open Opportunity":<28} {_fmt(open_opportunity):<14} {n_open} actions',
        f'  {"Forecast Confidence":<28} {forecast_confidence}%{"":10} Stable',
    ]
    if finops_score:
        lines.append(f'  {"FinOps Score":<28} {finops_score} / 100{"":6} —')
    lines.append('')

    # Beacon interpretation
    if fy_budget and fy_variance > 0:
        lines += [
            f'_Outlook: Without additional action, approximately {_fmt(fy_variance)} of budget '
            f'pressure remains. Current optimization opportunities could offset approximately '
            f'{_fmt(open_opportunity)} of that exposure._',
            '',
        ]

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Section 3: Decisions Required — centerpiece
    lines += ['*3 · Decisions Required*', '']

    if decisions:
        for i, f in enumerate(decisions, 1):
            annual = f['annualized_impact']
            monthly_cost_of_inaction = annual / 12
            confidence_pct = int(f['confidence'] * 100)
            owner = f.get('owner', 'Unassigned')
            finding_id = f['id']

            lines += [
                f'*{i:02d} — {f["title"]}*',
                f'  Economic impact: {_fmt(annual)} annualized',
                f'  Decision owner: {owner}',
                f'  Confidence: {confidence_pct}%',
                f'  If approved: Action proceeds immediately.',
                f'  If deferred: Approximately {_fmt(monthly_cost_of_inaction)}/month of avoidable spend continues.',
                # Executive actions only — no Generate Fix, no Snooze
                f'  `[Approve {finding_id}]`  `[Explain {finding_id}]`  `[Assign {finding_id}]`',
                '',
            ]
    else:
        lines += ['  No open decisions. All findings are actioned.', '']

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Section 4: Actions Since Last Brief
    lines += ['*4 · Actions Since Last Brief*', '']

    n_completed = len(completed)
    overdue = [f for f in decisions if f.get('days_open', 0) > 14]
    n_overdue = len(overdue)

    lines.append(
        f'{n_completed} actions completed · {_fmt(savings_realized)} savings verified · '
        f'{n_overdue} actions overdue'
    )
    lines.append('')

    if completed:
        for f in completed[:3]:
            lines.append(f'  ✓ {f["title"]} — {_fmt(f["annualized_impact"] / 12)} verified/mo')
    if overdue:
        for f in overdue[:2]:
            lines.append(
                f'  ⚠ {f["title"]} — {f["days_open"]} days overdue · '
                f'{_fmt(f["annualized_impact"] / 12)}/month at stake'
            )
    lines.append('')
    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # Section 5: Management Attention
    lines += ['*5 · Management Attention*', '']

    if fy_budget and fy_variance > 0:
        primary_exposure = decisions[0]['title'] if decisions else 'cloud consumption growth'
        lines += [
            f'Overall: Cloud economics remain manageable, but current consumption trends '
            f'put FY spend approximately {_fmt(fy_variance)} above plan.',
            f'Primary exposure: {primary_exposure}.',
            f'Immediate priority: {n_open} decisions representing {_fmt(open_opportunity)} in '
            f'annualized economic impact require executive action this month.',
            '',
        ]
    else:
        lines += [
            f'Overall: Cloud spend is tracking to plan. {n_open} optimization opportunities '
            f'representing {_fmt(open_opportunity)} in annualized savings are open for action.',
            '',
        ]

    # Action Layer
    n_decisions = len(decisions)
    owners = len(set(f.get('owner', '') for f in decisions if f.get('owner')))
    lines += [
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'*{n_decisions} Decisions Required*  ·  *{n_open} Actions Open*  ·  '
        f'*{owners} Owners*  ·  *{_fmt(open_opportunity)} Economic Impact*',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    ]

    return '\n'.join(lines)


def generate_executive_brief_word_doc(data: dict) -> str:
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        costs = data.get('costs', {})
        forecast = data.get('forecast', {})
        decisions = data.get('decisions', [])
        completed = data.get('completed_actions', [])
        finops_score = data.get('finops_score', 0)

        current_spend = costs.get('total_cost', 0)
        prior_spend = costs.get('prior_month_cost', current_spend)
        mom_delta = current_spend - prior_spend
        mom_pct = (mom_delta / prior_spend * 100) if prior_spend else 0
        month_end_forecast = forecast.get('projected_month_end', current_spend * 1.1)
        fy_budget = forecast.get('annual_budget', 0)
        fy_runrate = forecast.get('annual_run_rate', month_end_forecast * 12)
        fy_variance = fy_runrate - fy_budget if fy_budget else 0
        forecast_vs_plan = forecast.get('forecast_vs_plan', 0)
        forecast_confidence = int(forecast.get('confidence', 0.92) * 100)
        open_opportunity = sum(f['annualized_impact'] for f in decisions)
        savings_realized = sum(f.get('annualized_impact', 0) for f in completed)

        now = datetime.now(timezone.utc)
        month_label = now.strftime('%B %Y')

        doc = Document()

        # Title
        title = doc.add_heading('OpsBeacon Executive Cloud Economics Brief', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(
            f"{month_label} | Prepared by OpsBeacon"
        ).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

        # Headline KPIs
        kpi_table = doc.add_table(rows=2, cols=4)
        kpi_table.style = 'Table Grid'
        headers = ['Cloud Spend', 'vs Plan', 'Savings Realized', 'Open Opportunity']
        values = [
            _fmt(current_spend),
            f"+{_fmt(forecast_vs_plan)}" if forecast_vs_plan >= 0 else f"-{_fmt(abs(forecast_vs_plan))}",
            _fmt(savings_realized),
            _fmt(open_opportunity),
        ]
        for i, (h, v) in enumerate(zip(headers, values)):
            kpi_table.rows[0].cells[i].text = h
            kpi_table.rows[1].cells[i].text = v
        doc.add_paragraph()

        if fy_budget:
            doc.add_paragraph(
                f"FY Forecast: {_fmt(fy_runrate)}  ·  Budget: {_fmt(fy_budget)}  ·  "
                f"Projected variance: +{_fmt(fy_variance)}"
            ).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

        # Section 1
        doc.add_heading('1. What Changed', 1)
        doc.add_paragraph(
            f"Cloud spend is {_fmt(current_spend)} month-to-date, "
            f"tracking {_fmt_pct(mom_pct)} versus prior month."
        )
        if savings_realized > 0:
            doc.add_paragraph(
                f"The movement was partially offset by {_fmt(savings_realized)} in verified "
                f"optimization savings from completed actions."
            )
        if fy_budget and fy_variance > 0:
            doc.add_paragraph(
                f"At the current run rate, cloud spend is projected to finish the year "
                f"{_fmt(fy_variance)} above plan."
            )

        # Section 2
        doc.add_heading('2. Business Outlook', 1)
        outlook_table = doc.add_table(rows=6, cols=3)
        outlook_table.style = 'Table Grid'
        outlook_headers = ['Metric', 'Current', 'Outlook']
        outlook_rows = [
            ('FY Cloud Forecast', _fmt(fy_runrate), f"↑ {_fmt(fy_variance)} vs plan" if fy_budget and fy_variance > 0 else "On plan"),
            ('Verified Savings YTD', _fmt(savings_realized), f"↑ {_fmt(savings_realized)} this month"),
            ('Open Opportunity', _fmt(open_opportunity), f"{len(decisions)} actions"),
            ('Forecast Confidence', f"{forecast_confidence}%", "Stable"),
            ('FinOps Score', f"{finops_score} / 100" if finops_score else "—", "—"),
        ]
        for i, h in enumerate(outlook_headers):
            outlook_table.rows[0].cells[i].text = h
        for j, (metric, current, outlook) in enumerate(outlook_rows, 1):
            outlook_table.rows[j].cells[0].text = metric
            outlook_table.rows[j].cells[1].text = current
            outlook_table.rows[j].cells[2].text = outlook
        doc.add_paragraph()

        if fy_budget and fy_variance > 0:
            p = doc.add_paragraph()
            p.add_run('Outlook: ').bold = True
            p.add_run(
                f"Without additional action, approximately {_fmt(fy_variance)} of budget "
                f"pressure remains. Current optimization opportunities could offset approximately "
                f"{_fmt(open_opportunity)} of that exposure."
            )

        # Section 3 — Decisions Required
        doc.add_heading('3. Decisions Required', 1)
        for i, f in enumerate(decisions, 1):
            annual = f['annualized_impact']
            monthly_cost = annual / 12
            p = doc.add_paragraph()
            p.add_run(f"{i:02d} — {f['title']}").bold = True
            p.add_run(
                f"\n  Economic impact: {_fmt(annual)} annualized"
                f"\n  Decision owner: {f.get('owner', 'Unassigned')}"
                f"\n  Confidence: {int(f['confidence']*100)}%"
                f"\n  If approved: Action proceeds immediately."
                f"\n  If deferred: Approximately {_fmt(monthly_cost)}/month of avoidable spend continues."
                f"\n  Finding ID: {f['id']}"
            )
        doc.add_paragraph()

        # Section 4
        doc.add_heading('4. Actions Since Last Brief', 1)
        overdue = [f for f in decisions if f.get('days_open', 0) > 14]
        doc.add_paragraph(
            f"{len(completed)} actions completed · {_fmt(savings_realized)} savings verified · "
            f"{len(overdue)} actions overdue"
        )
        for f in completed[:3]:
            doc.add_paragraph(f"✓ {f['title']} — {_fmt(f['annualized_impact']/12)} verified/mo", style='List Bullet')
        for f in overdue[:2]:
            doc.add_paragraph(
                f"⚠ {f['title']} — {f['days_open']} days overdue · {_fmt(f['annualized_impact']/12)}/month at stake",
                style='List Bullet'
            )

        # Section 5
        doc.add_heading('5. Management Attention', 1)
        if fy_budget and fy_variance > 0:
            primary = decisions[0]['title'] if decisions else 'cloud consumption growth'
            doc.add_paragraph(
                f"Overall: Cloud economics remain manageable, but current consumption trends "
                f"put FY spend approximately {_fmt(fy_variance)} above plan. "
                f"Primary exposure: {primary}. "
                f"Immediate priority: {len(decisions)} decisions representing {_fmt(open_opportunity)} "
                f"in annualized economic impact require executive action this month."
            )
        else:
            doc.add_paragraph(
                f"Overall: Cloud spend is tracking to plan. {len(decisions)} optimization opportunities "
                f"representing {_fmt(open_opportunity)} in annualized savings are open for action."
            )

        # Footer
        doc.add_paragraph()
        footer = doc.add_paragraph(
            f"{len(decisions)} Decisions Required  ·  {len(decisions)} Actions Open  ·  "
            f"{_fmt(open_opportunity)} Economic Impact"
        )
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Save
        desktop = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.expanduser('~')
        filename = f"OpsBeacon_ExecutiveBrief_{datetime.now().strftime('%Y%m%d')}.docx"
        path = os.path.join(desktop, filename)
        doc.save(path)
        return path

    except Exception as e:
        return None


def generate_executive_brief(
    customer_id: str = 'default',
    generated_by: str = 'on_demand'
) -> dict:
    data = get_executive_brief_data(customer_id)
    data['generated_by'] = generated_by

    finding_ids = [f['id'] for f in data.get('decisions', [])]
    data['report_id'] = create_report(
        report_type='executive_brief',
        audience='executive',
        finding_ids=finding_ids,
        customer_id=customer_id,
        generated_by=generated_by
    )

    return data


if __name__ == '__main__':
    print('Generating Executive Cloud Economics Brief...')
    data = generate_executive_brief()
    print('\n=== Slack Output ===')
    print(format_executive_brief_for_slack(data))
    print('\n=== Generating Word Doc ===')
    path = generate_executive_brief_word_doc(data)
    if path:
        print(f'Word doc saved: {path}')
    else:
        print('Word doc generation failed')
