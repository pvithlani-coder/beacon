import os
import sqlite3
import json
from datetime import datetime, timezone
from report_intelligence import (
    init_db, get_top_actionable_findings, create_report
)

DB_PATH = os.path.join(os.path.dirname(__file__), 'report_intelligence.db')

# ── Score history schema ──────────────────────────────────────────────────────

def init_score_history():
    """Create score_history table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS score_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            overall_score INTEGER NOT NULL,
            dimensions TEXT NOT NULL,
            grade TEXT NOT NULL,
            finops_health TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            customer_id TEXT DEFAULT "default"
        )
    ''')
    conn.commit()
    conn.close()


def save_score_snapshot(score_data: dict, customer_id: str = 'default'):
    """Persist this month's score to history. One record per period."""
    init_score_history()
    period = datetime.now(timezone.utc).strftime('%Y-%m')
    conn = sqlite3.connect(DB_PATH)
    # Upsert — replace if same period already exists
    conn.execute('''
        INSERT INTO score_history (period, overall_score, dimensions, grade, finops_health, calculated_at, customer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
    ''', (
        period,
        score_data['overall_score'],
        json.dumps(score_data['dimensions']),
        score_data['grade'],
        score_data['finops_health'],
        score_data['calculated_at'],
        customer_id
    ))
    # If already exists, update it
    conn.execute('''
        UPDATE score_history
        SET overall_score=?, dimensions=?, grade=?, finops_health=?, calculated_at=?
        WHERE period=? AND customer_id=?
    ''', (
        score_data['overall_score'],
        json.dumps(score_data['dimensions']),
        score_data['grade'],
        score_data['finops_health'],
        score_data['calculated_at'],
        period,
        customer_id
    ))
    conn.commit()
    conn.close()


def get_score_history(customer_id: str = 'default', months: int = 6) -> list:
    """Return last N months of score snapshots, oldest first."""
    init_score_history()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT period, overall_score, dimensions, grade, finops_health
        FROM score_history
        WHERE customer_id = ?
        ORDER BY period DESC
        LIMIT ?
    ''', (customer_id, months)).fetchall()
    conn.close()
    history = []
    for period, overall, dims_json, grade, health in reversed(rows):
        history.append({
            'period': period,
            'overall_score': overall,
            'dimensions': json.loads(dims_json),
            'grade': grade,
            'finops_health': health,
        })
    return history


def get_prior_month_score(customer_id: str = 'default'):
    """Return the most recent historical score (not current month)."""
    current_period = datetime.now(timezone.utc).strftime('%Y-%m')
    init_score_history()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('''
        SELECT period, overall_score, dimensions
        FROM score_history
        WHERE customer_id = ? AND period != ?
        ORDER BY period DESC
        LIMIT 1
    ''', (customer_id, current_period)).fetchone()
    conn.close()
    if row:
        return {
            'period': row[0],
            'overall_score': row[1],
            'dimensions': json.loads(row[2]),
        }
    return None


# ── Score enrichment ──────────────────────────────────────────────────────────

def _finops_health(score: int) -> str:
    """Maturity label — not the same as risk."""
    if score >= 85:
        return 'Optimizing'
    elif score >= 70:
        return 'Established'
    elif score >= 50:
        return 'Developing'
    else:
        return 'At Risk'


def _data_coverage_flag(dim_name: str, score: int, findings: list) -> str:
    """
    Returns a coverage note if a perfect score has no supporting data.
    A 100 from a dimension with no findings and no API data is suspect.
    """
    if score == 100 and not findings:
        return ' ⚠ no data'
    return ''


def _project_score_lift(dim_name: str, current_dim_score: int,
                        finding: dict, weights: dict) -> int:
    """
    Estimate overall score improvement if this finding is resolved.
    Simple model: resolving a finding removes its penalty from the dimension,
    then propagates through the dimension weight.
    """
    penalty = abs(finding.get('impact', 0))
    improved_dim = min(100, current_dim_score + penalty)
    dim_gain = improved_dim - current_dim_score
    weight = weights.get(dim_name.lower().replace(' ', '_'), 0.10)
    return max(1, int(dim_gain * weight))


# Dimension name → weight key mapping
DIM_WEIGHT_KEYS = {
    'Cost Visibility': 'cost_visibility',
    'Waste Elimination': 'waste_elimination',
    'Tag Quality': 'tag_quality',
    'Reservation Efficiency': 'reservation_efficiency',
    'Savings Execution': 'savings_execution',
    'Forecast Accuracy': 'forecast_accuracy',
    'Recommendation Closure': 'recommendation_closure',
    'Cost Anomalies': 'cost_anomalies',
    'Security Economics': 'security_economics',
    'AI Efficiency': 'ai_efficiency',
}

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
    'ai_efficiency': 0.06,
}


# ── Main scorecard builder ────────────────────────────────────────────────────

def get_finops_scorecard_data(customer_id: str = 'default',
                              company_size: str = 'mid_market') -> dict:
    init_db()

    # Run the scoring engine
    from finops_score import calculate_finops_score
    raw = calculate_finops_score(company_size=company_size)

    # Enrich with maturity label
    raw['finops_health'] = _finops_health(raw['overall_score'])

    # Remove "Risk Level" — replaced by finops_health
    raw.pop('risk_level', None)

    # Historical context
    prior = get_prior_month_score(customer_id)
    raw['prior_month'] = prior
    raw['score_delta'] = (
        raw['overall_score'] - prior['overall_score'] if prior else None
    )

    # Dimension deltas vs prior month
    dim_deltas = {}
    if prior:
        for dim, score in raw['dimensions'].items():
            prior_score = prior['dimensions'].get(dim, score)
            dim_deltas[dim] = score - prior_score
    raw['dimension_deltas'] = dim_deltas

    # Top SAR findings — surface real finding IDs, not just commands
    top_findings = get_top_actionable_findings(customer_id, limit=3)
    raw['top_findings'] = top_findings

    # Project score lift per top finding
    improvement_actions = []
    for f in top_findings:
        # Match finding to a dimension by keyword heuristic
        title_lower = f['title'].lower()
        matched_dim = 'Savings Execution'  # default
        for dim in raw['dimensions']:
            if any(kw in title_lower for kw in dim.lower().split()):
                matched_dim = dim
                break
        current_dim_score = raw['dimensions'].get(matched_dim, 70)
        lift = _project_score_lift(
            matched_dim, current_dim_score, f, DIMENSION_WEIGHTS
        )
        improvement_actions.append({
            'finding_id': f['id'],
            'title': f['title'],
            'owner': f.get('owner', 'Unassigned'),
            'annualized_impact': f['annualized_impact'],
            'dimension': matched_dim,
            'projected_score_lift': lift,
        })
    raw['improvement_actions'] = improvement_actions

    # Data coverage — flag dimensions with suspicious perfect scores
    coverage_flags = {}
    all_findings_by_dim = {}  # build from actionable_findings
    for f in raw.get('actionable_findings', []):
        # Rough attribution — not perfect but useful
        for dim in raw['dimensions']:
            if any(kw in f.get('issue', '').lower()
                   for kw in dim.lower().split()):
                all_findings_by_dim.setdefault(dim, []).append(f)

    for dim, score in raw['dimensions'].items():
        findings_for_dim = all_findings_by_dim.get(dim, [])
        flag = _data_coverage_flag(dim, score, findings_for_dim)
        if flag:
            coverage_flags[dim] = flag
    raw['coverage_flags'] = coverage_flags

    # Save snapshot
    save_score_snapshot(raw, customer_id)

    raw['customer_id'] = customer_id
    raw['generated_at'] = datetime.now(timezone.utc).isoformat()

    return raw


# ── Slack formatter ───────────────────────────────────────────────────────────

def format_finops_scorecard_for_slack(data: dict) -> str:
    overall = data['overall_score']
    grade = data['grade']
    health = data['finops_health']
    prior = data.get('prior_month')
    delta = data.get('score_delta')
    dimensions = data['dimensions']
    dim_deltas = data.get('dimension_deltas', {})
    coverage_flags = data.get('coverage_flags', {})
    improvement_actions = data.get('improvement_actions', [])
    actionable_findings = data.get('actionable_findings', [])

    now = datetime.now(timezone.utc)
    month_label = now.strftime('%B %Y')

    lines = []

    # ── Title ─────────────────────────────────────────────────────────────────
    lines += [
        '*OPSBEACON FINOPS SCORECARD*',
        f'_{month_label}_',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── Headline ──────────────────────────────────────────────────────────────
    filled = int(overall / 10)
    bar = '█' * filled + '░' * (10 - filled)

    delta_str = ''
    if delta is not None:
        sign = '+' if delta >= 0 else ''
        delta_str = f'  {sign}{delta} pts vs prior month'

        # Value at Risk removed
    prior_score_str = str(prior['overall_score']) if prior else '—'

    lines += [
        f'*{overall}/100*  FinOps Health: *{health}*',
        f'`{bar}`{delta_str}',
        '',
        f'  {"Current Score":<20} {overall}',
        f'  {"Prior Month":<20} {prior_score_str}',
        # Value at Risk removed
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    # ── 10 Dimensions ─────────────────────────────────────────────────────────
    lines += ['*PERFORMANCE ACROSS 10 DIMENSIONS*', '']

    # Sort: lowest scores first (improvement priority)
    sorted_dims = sorted(dimensions.items(), key=lambda x: x[1])

    for dim, score in sorted_dims:
        dim_delta = dim_deltas.get(dim)
        flag = coverage_flags.get(dim, '')

        delta_indicator = ''
        if dim_delta is not None and dim_delta != 0:
            delta_indicator = f' ({"↑" if dim_delta > 0 else "↓"}{abs(dim_delta):+d})'

        # Visual bar — 5 chars wide
        bar_len = int(score / 20)
        dim_bar = '█' * bar_len + '░' * (5 - bar_len)

        status = '🔴' if score < 50 else ('🟡' if score < 75 else '🟢')
        lines.append(
            f'  {status} {dim:<28} `{dim_bar}` {score:>3}/100'
            f'{delta_indicator}{flag}'
        )

    lines += ['', '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Score Drivers (what's pulling the score down) ─────────────────────────
    lines += ['*PRIMARY IMPROVEMENT OPPORTUNITIES*', '']

    weak_dims = [(d, s) for d, s in sorted_dims if s < 80][:3]
    for dim, score in weak_dims:
        # Find matching finding from actionable_findings
        matching = next(
            (f for f in actionable_findings
             if any(kw in f.get('issue', '').lower()
                    for kw in dim.lower().split())),
            None
        )
        desc = matching['issue'] if matching else f'Score {score}/100 — review underlying data.'
        lines += [
            f'*{dim} — {score}/100*',
            f'  {desc}',
            '',
        ]

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Top 3 Improvement Actions with projected lift ─────────────────────────
    lines += ['*TOP 3 IMPROVEMENT ACTIONS*', '']

    if improvement_actions:
        for i, action in enumerate(improvement_actions[:3], 1):
            finding_id = action['finding_id']
            lift = action['projected_score_lift']
            annual = action['annualized_impact']
            owner = action['owner']
            dim = action['dimension']
            lines += [
                f'*{i}. {action["title"]}*',
                f'  Finding: `{finding_id}`  ·  Owner: {owner}',
                f'  Savings: ${annual:,.0f} annualized  ·  Projected score lift: +{lift} pts ({dim})',
                f'  `[Approve {finding_id}]`  `[Explain {finding_id}]`  `[Assign {finding_id}]`',
                '',
            ]
    else:
        lines += ['  No open improvement actions. Score is optimized.', '']

    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', '']

    # ── Data Quality & Methodology ────────────────────────────────────────────
    lines += ['*DATA QUALITY & METHODOLOGY*', '']

    n_flags = len(coverage_flags)
    if n_flags:
        flagged = ', '.join(coverage_flags.keys())
        lines.append(
            f'  {n_flags} dimension{"s" if n_flags != 1 else ""} scored 100/100 with no '
            f'supporting data ({flagged}). These scores reflect absence of detected issues, '
            f'not confirmed optimization.'
        )
    else:
        lines.append(
            '  All dimensions have supporting data. Scores reflect measured outcomes.'
        )

    lines += [
        '  Dimension weights are proprietary and fixed. Score is not a simple average.',
        '  Security Economics and AI Efficiency are included at reduced weight (6% each)',
        '  and reflect controls outside core FinOps team authority.',
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    ]

    # ── Action Layer ──────────────────────────────────────────────────────────
    n_actions = len(improvement_actions)
    total_lift = sum(a['projected_score_lift'] for a in improvement_actions)
    total_savings = sum(a['annualized_impact'] for a in improvement_actions)

    lines += [
        f'*{n_actions} Actions*  ·  *+{total_lift} pts Projected Lift*  ·  '
        f'*${total_savings:,.0f} Annualized Opportunity*',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    ]

    return '\n'.join(lines)


# ── Word doc ──────────────────────────────────────────────────────────────────

def generate_finops_scorecard_word_doc(data: dict) -> str:
    try:
        from docx import Document
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        overall = data['overall_score']
        grade = data['grade']
        health = data['finops_health']
        prior = data.get('prior_month')
        delta = data.get('score_delta')
        dimensions = data['dimensions']
        dim_deltas = data.get('dimension_deltas', {})
        coverage_flags = data.get('coverage_flags', {})
        improvement_actions = data.get('improvement_actions', [])
        actionable_findings = data.get('actionable_findings', [])
        # Value at Risk removed

        now = datetime.now(timezone.utc)
        month_label = now.strftime('%B %Y')

        doc = Document()

        title = doc.add_heading('OpsBeacon FinOps Scorecard', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph(month_label).alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()

        # Headline KPIs
        kpi = doc.add_table(rows=2, cols=3)
        kpi.style = 'Table Grid'
        delta_str = f'{delta:+d} pts' if delta is not None else '—'
        headers = ['Overall Score', 'Prior Month', 'Change']
        values = [f'{overall}/100  {health}',
                  f'{prior["overall_score"] if prior else "—"}  ({delta_str})',
                  movement]
        for i, (h, v) in enumerate(zip(headers, values)):
            kpi.rows[0].cells[i].text = h
            kpi.rows[1].cells[i].text = v
        doc.add_paragraph()

        # Dimensions
        doc.add_heading('Performance Across 10 Dimensions', 1)
        dim_table = doc.add_table(rows=len(dimensions) + 1, cols=3)
        dim_table.style = 'Table Grid'
        dim_table.rows[0].cells[0].text = 'Dimension'
        dim_table.rows[0].cells[1].text = 'Score'
        dim_table.rows[0].cells[2].text = 'vs Prior Month'
        for i, (dim, score) in enumerate(
                sorted(dimensions.items(), key=lambda x: x[1]), 1):
            d = dim_deltas.get(dim)
            flag = coverage_flags.get(dim, '')
            dim_table.rows[i].cells[0].text = dim
            dim_table.rows[i].cells[1].text = f'{score}/100{flag}'
            dim_table.rows[i].cells[2].text = (
                f'{d:+d}' if d is not None and d != 0 else '—'
            )
        doc.add_paragraph()

        # Improvement opportunities
        doc.add_heading('Primary Improvement Opportunities', 1)
        sorted_dims = sorted(dimensions.items(), key=lambda x: x[1])
        for dim, score in sorted_dims[:3]:
            if score < 80:
                matching = next(
                    (f for f in actionable_findings
                     if any(kw in f.get('issue', '').lower()
                            for kw in dim.lower().split())),
                    None
                )
                p = doc.add_paragraph()
                p.add_run(f'{dim} — {score}/100').bold = True
                desc = matching['issue'] if matching else f'Score {score}/100.'
                p.add_run(f'\n  {desc}')

        # Top 3 Actions
        doc.add_heading('Top 3 Improvement Actions', 1)
        for i, action in enumerate(improvement_actions[:3], 1):
            p = doc.add_paragraph()
            p.add_run(f'{i}. {action["title"]}').bold = True
            p.add_run(
                f'\n  Finding: {action["finding_id"]}'
                f'\n  Owner: {action["owner"]}'
                f'\n  Savings: ${action["annualized_impact"]:,.0f} annualized'
                f'\n  Projected score lift: +{action["projected_score_lift"]} pts ({action["dimension"]})'
            )

        # Data quality
        doc.add_heading('Data Quality & Methodology', 1)
        n_flags = len(coverage_flags)
        if n_flags:
            flagged = ', '.join(coverage_flags.keys())
            doc.add_paragraph(
                f'{n_flags} dimension{"s" if n_flags != 1 else ""} scored 100/100 '
                f'with no supporting data ({flagged}). These scores reflect absence '
                f'of detected issues, not confirmed optimization.'
            )
        else:
            doc.add_paragraph(
                'All dimensions have supporting data. Scores reflect measured outcomes.'
            )
        doc.add_paragraph(
            'Dimension weights are proprietary and fixed. Score is not a simple average. '
            'Security Economics and AI Efficiency are included at reduced weight (6% each).'
        )

        # Save
        desktop = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
        if not os.path.exists(desktop):
            desktop = os.path.expanduser('~')
        filename = f"OpsBeacon_FinOpsScorecard_{datetime.now().strftime('%Y%m%d')}.docx"
        path = os.path.join(desktop, filename)
        doc.save(path)
        return path

    except Exception:
        return None


# ── Entry point ───────────────────────────────────────────────────────────────

def generate_finops_scorecard(customer_id: str = 'default',
                               company_size: str = 'mid_market',
                               generated_by: str = 'on_demand') -> dict:
    data = get_finops_scorecard_data(customer_id, company_size)
    data['generated_by'] = generated_by

    finding_ids = [a['finding_id'] for a in data.get('improvement_actions', [])]
    data['report_id'] = create_report(
        report_type='finops_scorecard',
        audience='finops_lead',
        finding_ids=finding_ids,
        customer_id=customer_id,
        generated_by=generated_by
    )

    return data


if __name__ == '__main__':
    print('Generating FinOps Scorecard...')
    data = generate_finops_scorecard()
    print('\n=== Slack Output ===')
    print(format_finops_scorecard_for_slack(data))
    print('\n=== Generating Word Doc ===')
    path = generate_finops_scorecard_word_doc(data)
    if path:
        print(f'Word doc saved: {path}')
    else:
        print('Word doc generation failed')
