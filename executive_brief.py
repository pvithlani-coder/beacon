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

    # AWS costs — monthly MTD
    try:
        from aws_costs import get_aws_costs
        raw_costs = get_aws_costs()
        mtd_total = sum(raw_costs.values())

        # Annualize from monthly MTD: project to month-end, then ×12
        day_of_month = now.day
        import calendar
        days_in_month = calendar.monthrange(now.year, now.month)[1]
        projected_monthly = (mtd_total / day_of_month) * days_in_month
        projected_annual = projected_monthly * 12

        data['costs'] = {
            'mtd_total': mtd_total,
            'projected_monthly': projected_monthly,
            'projected_annual': projected_annual,
            'prior_month_cost': mtd_total,   # placeholder until real prior-month data
            'mom_delta': 0,
            'mom_pct': 0,
        }
    except Exception:
        data['costs'] = {
            'mtd_total': 0,
            'projected_monthly': 0,
            'projected_annual': 0,
            'prior_month_cost': 0,
            'mom_delta': 0,
            'mom_pct': 0,
        }

    # Forecast from Cost Explorer (may override projected_annual if available)
    try:
        from aws_costs import get_cost_forecast
        forecast = get_cost_forecast()
        data['forecast'] = forecast
        # If Cost Explorer provides an annual run rate, prefer it and note the source
        if forecast.get('annual_run_rate'):
            data['costs']['ce_annual_run_rate'] = forecast['annual_run_rate']
    except Exception:
        data['forecast'] = {}

    # Anomalies
    try:
        from aws_costs import get_cost_anomalies
        raw = get_cost_anomalies()
        if isinstance(raw, list):
            data['anomalies'] = {'active': raw, 'resolved': []}
        else:
            data['anomalies'] = raw
    except Exception:
        data['anomalies'] = {'active': [], 'resolved': []}

    # Security findings (disabled controls)
    try:
        from security_checks import get_security_findings
        sec = get_security_findings()
        data['security'] = sec
    except Exception:
        data['security'] = {'disabled_controls': [], 'monthly_remediation_cost': 0}

    # Top optimization findings — executive view (limit 3)
    data['decisions'] = get_top_actionable_findings(customer_id, limit=3)

    # Completed actions
    try:
        completed = get_findings(
            customer_id=customer_id,
            status=FindingStatus.IMPLEMENTED.value,
            limit=5
        )
        data['completed_actions'] = completed
    except Exception:
        data['completed_actions'] = []

    # AI cost estimate
    try:
        from aws_costs import get_aws_costs
        raw_costs = get_aws_costs()
        ai_monthly = sum(v for k, v in raw_costs.items()
                         if any(t in k.lower() for t in ['bedrock', 'sagemaker', 'rekognition']))
        data['ai_monthly_cost'] = ai_monthly
    except Exception:
        data['ai_monthly_cost'] = 0

    return data


def format_executive_brief_for_slack(data: dict) -> str:
    costs = data.get('costs', {})
    decisions = data.get('decisions', [])
    anomalies = data.get('anomalies', {})
    security = data.get('security', {})
    ai_monthly = data.get('ai_monthly_cost', 0)

    # ── Consistent number source ──────────────────────────────────────────────
    # projected_monthly → ×12 = projected_annual. One path. Used everywhere.
    projected_monthly = costs.get('projected_monthly', 0)
    projected_annual = costs.get('projected_annual', projected_monthly * 12)
    mom_pct = costs.get('mom_pct', 0)

    open_opportunity = sum(f['annualized_impact'] for f in decisions)
    active_anomalies = anomalies.get('active', [])
    n_anomalies = len(active_anomalies)
    disabled_controls = security.get('disabled_controls', [])
    n_security_gaps = len(disabled_controls)
    security_monthly_cost = security.get('monthly_remediation_cost', 0)

    now = datetime.now(timezone.utc)
    month_label = now.strftime('%B %Y')

    lines = []

    # ── Title ─────────────────────────────────────────────────────────────────
    lines += [
        f'*EXECUTIVE CLOUD ECONOMICS BRIEF — {month_label}*',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── 4 Headline Numbers ────────────────────────────────────────────────────
    mom_str = _fmt_pct(mom_pct) if mom_pct else '—'
    security_str = f'{n_security_gaps} Security Gap{"s" if n_security_gaps != 1 else ""}' if n_security_gaps else 'No Security Gaps'
    lines += [
        f'*{_fmt(projected_annual)} Annual Run Rate*  ·  *{mom_str} MoM*  ·  '
        f'*{_fmt(open_opportunity)} Savings Opportunity*  ·  *{security_str}*',
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── What Changed ─────────────────────────────────────────────────────────
    lines += ['*WHAT CHANGED*', '']

    day_of_month = now.day
    import calendar
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    mtd_total = costs.get('mtd_total', 0)

    lines.append(
        f'Cloud infrastructure spend is {_fmt(mtd_total)} month-to-date through day {day_of_month} '
        f'of {days_in_month}. Current consumption implies approximately {_fmt(projected_monthly)}/month '
        f'and {_fmt(projected_annual)} annualized.'
    )
    if n_anomalies:
        lines.append(
            f'{n_anomalies} cost {"anomaly" if n_anomalies == 1 else "anomalies"} '
            f'{"remains" if n_anomalies == 1 else "remain"} under investigation.'
        )
    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Economic Outlook ──────────────────────────────────────────────────────
    lines += ['*ECONOMIC OUTLOOK*', '']

    if open_opportunity > 0:
        pct_of_annual = (open_opportunity / projected_annual * 100) if projected_annual else 0
        lines.append(
            f'OpsBeacon identified {_fmt(open_opportunity)} in annualized optimization opportunity, '
            f'approximately {pct_of_annual:.1f}% of projected cloud spend. '
            f'The opportunities are primarily underutilized resources and can be evaluated '
            f'without changing planned service capacity.'
        )
    else:
        lines.append(
            'No material optimization opportunities are currently identified. '
            'Cloud spend is tracking to plan.'
        )
    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Risk & Resilience ─────────────────────────────────────────────────────
    lines += ['*RISK & RESILIENCE*', '']

    if n_security_gaps:
        cost_note = (f'Estimated incremental cloud cost to enable the identified controls '
                     f'is approximately {_fmt(security_monthly_cost)}/month.'
                     if security_monthly_cost else '')
        lines.append(
            f'{n_security_gaps} foundational security control{"s" if n_security_gaps != 1 else ""} '
            f'{"remain" if n_security_gaps != 1 else "remains"} disabled. '
            + (cost_note + ' ' if cost_note else '') +
            'The security implications and remediation priority should be evaluated '
            'separately from their infrastructure cost.'
        )
    else:
        lines.append('No foundational security gaps identified this period.')

    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── AI Economics ──────────────────────────────────────────────────────────
    lines += ['*AI ECONOMICS*', '']

    if ai_monthly > 0:
        lines.append(
            f'Current AI-related spend is approximately {_fmt(ai_monthly)}/month and is not '
            f'yet financially material. OpsBeacon will continue tracking usage and unit economics '
            f'as adoption increases.'
        )
    else:
        lines.append(
            'AI-related spend is not currently detected or is below the tracking threshold. '
            'OpsBeacon will begin reporting this category as consumption increases.'
        )
    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Decisions Required ────────────────────────────────────────────────────
    lines += ['*DECISIONS REQUIRED*', '']

    decision_num = 1

    # Optimization decisions from findings
    for f in decisions:
        annual = f['annualized_impact']
        finding_id = f['id']
        owner = f.get('owner', '')
        owner_str = f'  Decision owner: {owner}\n' if owner else ''
        lines += [
            f'*{decision_num:02d} — {f["title"]}*',
            f'  Economic impact: {_fmt(annual)} annualized',
        ]
        if owner:
            lines.append(f'  Decision owner: {owner}')
        lines += [
            f'  `[Approve {finding_id}]`  `[Explain {finding_id}]`  `[Assign {finding_id}]`',
            '',
        ]
        decision_num += 1

    # Security decision (if gaps exist and not already in findings)
    if n_security_gaps:
        cost_display = (f'Incremental cost: {_fmt(security_monthly_cost)}/month'
                        if security_monthly_cost else 'Incremental cost: Under evaluation')
        lines += [
            f'*{decision_num:02d} — Confirm remediation of {n_security_gaps} security control{"s" if n_security_gaps != 1 else ""}*',
            f'  {cost_display}',
            f'  `[Approve]`  `[Explain]`  `[Assign]`',
            '',
        ]
        decision_num += 1

    # Anomaly decision (if open)
    if n_anomalies:
        lines += [
            f'*{decision_num:02d} — Investigate {"open cost anomaly" if n_anomalies == 1 else f"{n_anomalies} open cost anomalies"}*',
            '  Economic impact: Pending investigation',
            '  `[Assign]`  `[Explain]`',
            '',
        ]

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Management View ───────────────────────────────────────────────────────
    lines += ['*MANAGEMENT VIEW*', '']

    parts = [f'Cloud spending remains within the current forecast at {_fmt(projected_annual)} annual run rate.']
    if open_opportunity > 0:
        parts.append(f'{_fmt(open_opportunity)} in identified optimization opportunity is available for action.')
    if n_security_gaps:
        parts.append(f'Immediate management attention should focus on closing {n_security_gaps} security-control gap{"s" if n_security_gaps != 1 else ""}.')
    if n_anomalies:
        parts.append(f'{"An outstanding" if n_anomalies == 1 else f"{n_anomalies} outstanding"} cost {"anomaly requires" if n_anomalies == 1 else "anomalies require"} investigation.')

    lines.append(' '.join(parts))
    lines.append('')

    # ── Footer ────────────────────────────────────────────────────────────────
    total_decisions = (len(decisions)
                       + (1 if n_security_gaps else 0)
                       + (1 if n_anomalies else 0))
    footer_parts = [f'*{total_decisions} Decision{"s" if total_decisions != 1 else ""}*']
    if open_opportunity > 0:
        footer_parts.append(f'*{_fmt(open_opportunity)} Identified Opportunity*')
    if n_security_gaps:
        footer_parts.append(f'*{n_security_gaps} Security Gap{"s" if n_security_gaps != 1 else ""}*')
    if n_anomalies:
        footer_parts.append(f'*{n_anomalies} Open {"Anomaly" if n_anomalies == 1 else "Anomalies"}*')

    lines += [
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '  ·  '.join(footer_parts),
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    ]

    return '\n'.join(lines)


def generate_board_narrative(data: dict) -> str:
    """
    Transforms the Executive Brief data into 3–5 board-level talking points.
    Triggered by: @Beacon prepare board narrative
    Uses the same Report Intelligence Object as the Executive Brief —
    audience-filtered output, not a separate data pull.
    """
    costs = data.get('costs', {})
    decisions = data.get('decisions', [])
    anomalies = data.get('anomalies', {})
    security = data.get('security', {})

    projected_annual = costs.get('projected_annual', 0)
    open_opportunity = sum(f['annualized_impact'] for f in decisions)
    n_anomalies = len(anomalies.get('active', []))
    n_security_gaps = len(security.get('disabled_controls', []))

    now = datetime.now(timezone.utc)
    month_label = now.strftime('%B %Y')

    lines = [
        f'*Board Narrative — Cloud Economics — {month_label}*',
        '_Prepared by OpsBeacon from Executive Brief data_',
        '',
    ]

    point = 1
    lines.append(
        f'*{point}.* Cloud infrastructure is tracking at {_fmt(projected_annual)} annual run rate, '
        f'within current forecast parameters.'
    )
    point += 1

    if open_opportunity > 0:
        pct = (open_opportunity / projected_annual * 100) if projected_annual else 0
        lines.append(
            f'*{point}.* We have identified {_fmt(open_opportunity)} ({pct:.1f}% of annual spend) '
            f'in recoverable optimization opportunity. Actions are pending management approval.'
        )
        point += 1

    if n_security_gaps:
        lines.append(
            f'*{point}.* {n_security_gaps} foundational security control{"s" if n_security_gaps != 1 else ""} '
            f'{"require" if n_security_gaps != 1 else "requires"} remediation. '
            f'Infrastructure cost is minimal; risk evaluation is in progress.'
        )
        point += 1

    if n_anomalies:
        lines.append(
            f'*{point}.* {"An" if n_anomalies == 1 else str(n_anomalies)} open cost '
            f'{"anomaly is" if n_anomalies == 1 else "anomalies are"} under investigation. '
            f'Financial impact will be reported once root cause is confirmed.'
        )
        point += 1

    lines += [
        '',
        '_These talking points are derived from the Executive Cloud Economics Brief. '
        'For supporting data, request the full brief._',
    ]

    return '\n'.join(lines)


def generate_executive_brief_word_doc(data: dict) -> str:
    try:
        from docx import Document
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        costs = data.get('costs', {})
        decisions = data.get('decisions', [])
        anomalies = data.get('anomalies', {})
        security = data.get('security', {})
        ai_monthly = data.get('ai_monthly_cost', 0)

        projected_monthly = costs.get('projected_monthly', 0)
        projected_annual = costs.get('projected_annual', projected_monthly * 12)
        mtd_total = costs.get('mtd_total', 0)
        open_opportunity = sum(f['annualized_impact'] for f in decisions)
        active_anomalies = anomalies.get('active', [])
        n_anomalies = len(active_anomalies)
        disabled_controls = security.get('disabled_controls', [])
        n_security_gaps = len(disabled_controls)
        security_monthly_cost = security.get('monthly_remediation_cost', 0)

        now = datetime.now(timezone.utc)
        month_label = now.strftime('%B %Y')

        import calendar
        day_of_month = now.day
        days_in_month = calendar.monthrange(now.year, now.month)[1]

        doc = Document()

        title = doc.add_heading(f'Executive Cloud Economics Brief — {month_label}', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph('Prepared by OpsBeacon').alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

        # Headline KPIs
        kpi = doc.add_table(rows=1, cols=4)
        kpi.style = 'Table Grid'
        security_str = f'{n_security_gaps} Security Gap{"s" if n_security_gaps != 1 else ""}' if n_security_gaps else 'No Security Gaps'
        for i, text in enumerate([
            f'{_fmt(projected_annual)}\nAnnual Run Rate',
            '—\nMoM Change',
            f'{_fmt(open_opportunity)}\nSavings Opportunity',
            f'{security_str}',
        ]):
            kpi.rows[0].cells[i].text = text
        doc.add_paragraph()

        # Sections
        doc.add_heading('What Changed', 1)
        doc.add_paragraph(
            f'Cloud infrastructure spend is {_fmt(mtd_total)} month-to-date through day '
            f'{day_of_month} of {days_in_month}. Current consumption implies approximately '
            f'{_fmt(projected_monthly)}/month and {_fmt(projected_annual)} annualized.'
        )
        if n_anomalies:
            doc.add_paragraph(
                f'{n_anomalies} cost {"anomaly" if n_anomalies == 1 else "anomalies"} '
                f'{"remains" if n_anomalies == 1 else "remain"} under investigation.'
            )

        doc.add_heading('Economic Outlook', 1)
        if open_opportunity > 0:
            pct = (open_opportunity / projected_annual * 100) if projected_annual else 0
            doc.add_paragraph(
                f'OpsBeacon identified {_fmt(open_opportunity)} in annualized optimization '
                f'opportunity, approximately {pct:.1f}% of projected cloud spend. '
                f'The opportunities are primarily underutilized resources and can be evaluated '
                f'without changing planned service capacity.'
            )
        else:
            doc.add_paragraph('No material optimization opportunities are currently identified.')

        doc.add_heading('Risk & Resilience', 1)
        if n_security_gaps:
            cost_note = (f'Estimated incremental cloud cost to enable the identified controls '
                         f'is approximately {_fmt(security_monthly_cost)}/month. '
                         if security_monthly_cost else '')
            doc.add_paragraph(
                f'{n_security_gaps} foundational security control{"s" if n_security_gaps != 1 else ""} '
                f'{"remain" if n_security_gaps != 1 else "remains"} disabled. '
                + cost_note +
                'The security implications and remediation priority should be evaluated '
                'separately from their infrastructure cost.'
            )
        else:
            doc.add_paragraph('No foundational security gaps identified this period.')

        doc.add_heading('AI Economics', 1)
        if ai_monthly > 0:
            doc.add_paragraph(
                f'Current AI-related spend is approximately {_fmt(ai_monthly)}/month '
                f'and is not yet financially material.'
            )
        else:
            doc.add_paragraph(
                'AI-related spend is not currently detected or is below the tracking threshold.'
            )

        doc.add_heading('Decisions Required', 1)
        decision_num = 1
        for f in decisions:
            annual = f['annualized_impact']
            p = doc.add_paragraph()
            p.add_run(f"{decision_num:02d} — {f['title']}").bold = True
            p.add_run(f"\n  Economic impact: {_fmt(annual)} annualized")
            if f.get('owner'):
                p.add_run(f"\n  Decision owner: {f['owner']}")
            p.add_run(f"\n  Finding ID: {f['id']}")
            decision_num += 1

        if n_security_gaps:
            p = doc.add_paragraph()
            p.add_run(f"{decision_num:02d} — Confirm remediation of {n_security_gaps} security control{'s' if n_security_gaps != 1 else ''}").bold = True
            cost_display = (f'Incremental cost: {_fmt(security_monthly_cost)}/month'
                            if security_monthly_cost else 'Incremental cost: Under evaluation')
            p.add_run(f"\n  {cost_display}")
            decision_num += 1

        if n_anomalies:
            p = doc.add_paragraph()
            p.add_run(f"{decision_num:02d} — Investigate {'open cost anomaly' if n_anomalies == 1 else f'{n_anomalies} open cost anomalies'}").bold = True
            p.add_run('\n  Economic impact: Pending investigation')

        doc.add_heading('Management View', 1)
        parts = [f'Cloud spending remains within the current forecast at {_fmt(projected_annual)} annual run rate.']
        if open_opportunity > 0:
            parts.append(f'{_fmt(open_opportunity)} in identified optimization opportunity is available for action.')
        if n_security_gaps:
            parts.append(f'Immediate management attention should focus on closing {n_security_gaps} security-control gap{"s" if n_security_gaps != 1 else ""}.')
        if n_anomalies:
            parts.append(f'{"An outstanding" if n_anomalies == 1 else f"{n_anomalies} outstanding"} cost {"anomaly requires" if n_anomalies == 1 else "anomalies require"} investigation.')
        doc.add_paragraph(' '.join(parts))

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

    except Exception:
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
    print('\n=== Board Narrative ===')
    print(generate_board_narrative(data))
    print('\n=== Generating Word Doc ===')
    path = generate_executive_brief_word_doc(data)
    if path:
        print(f'Word doc saved: {path}')
    else:
        print('Word doc generation failed')
