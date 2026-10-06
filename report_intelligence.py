import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict
from enum import Enum

DB_PATH = os.path.join(os.path.dirname(__file__), 'report_intelligence.db')


# ── Enums ────────────────────────────────────────────────────────────────────

class FindingStatus(Enum):
    IDENTIFIED = 'identified'
    ACCEPTED = 'accepted'
    IN_PROGRESS = 'in_progress'
    IMPLEMENTED = 'implemented'
    VERIFIED = 'verified'
    DISMISSED = 'dismissed'
    SNOOZED = 'snoozed'


class FindingCategory(Enum):
    COMPUTE = 'compute'
    STORAGE = 'storage'
    DATABASE = 'database'
    NETWORK = 'network'
    AI = 'ai'
    SECURITY = 'security'
    RESERVATION = 'reservation'
    SAVINGS_PLAN = 'savings_plan'
    IDLE = 'idle'
    TAG = 'tag'
    COMPLIANCE = 'compliance'


class AudienceType(Enum):
    PRACTITIONER = 'practitioner'
    VP_ENGINEERING = 'vp_engineering'
    CFO = 'cfo'
    CIO = 'cio'
    CISO = 'ciso'
    CTO = 'cto'
    BOARD = 'board'


class ActionType(Enum):
    APPROVE = 'approve'
    ASSIGN = 'assign'
    GENERATE_FIX = 'generate_fix'
    SNOOZE = 'snooze'
    EXPLAIN = 'explain'
    DISMISS = 'dismiss'


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class Finding:
    id: str
    title: str
    description: str
    category: str
    annualized_impact: float
    monthly_impact: float
    owner: Optional[str]
    team: Optional[str]
    confidence: float
    days_open: int
    status: str
    actions_available: List[str]
    evidence: Dict
    fix_command: Optional[str]
    fix_type: Optional[str]  # terraform / cli / manual
    verified_outcome: Optional[float]
    period_start: str
    period_end: str
    created_at: str
    updated_at: str
    snoozed_until: Optional[str]
    snooze_note: Optional[str]
    approved_by: Optional[str]
    approved_at: Optional[str]
    implemented_at: Optional[str]
    verified_at: Optional[str]
    resource_id: Optional[str]
    resource_type: Optional[str]
    region: Optional[str]
    console_link: Optional[str]
    report_id: Optional[str]
    source_feature: Optional[str]


@dataclass
class ReportObject:
    id: str
    report_type: str
    period_start: str
    period_end: str
    audience: str
    generated_at: str
    generated_by: str  # scheduled / on_demand / user_id
    status: str  # draft / published / archived

    # KPIs
    total_spend: float
    total_savings_identified: float
    total_savings_accepted: float
    total_savings_implemented: float
    total_savings_verified: float
    total_economic_impact: float

    # Workload summary
    decisions_required: int
    actions_due: int
    owners_count: int

    # Findings
    finding_ids: List[str]

    # Scores
    finops_score: Optional[float]
    security_score: Optional[float]
    ai_economics_score: Optional[float]

    # Period comparison
    prior_period_spend: Optional[float]
    spend_change_pct: Optional[float]

    # Metadata
    customer_id: str
    slack_message_ts: Optional[str]
    word_doc_path: Optional[str]


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            annualized_impact REAL DEFAULT 0,
            monthly_impact REAL DEFAULT 0,
            owner TEXT,
            team TEXT,
            confidence REAL DEFAULT 0.8,
            days_open INTEGER DEFAULT 0,
            status TEXT DEFAULT 'identified',
            actions_available TEXT DEFAULT '[]',
            evidence TEXT DEFAULT '{}',
            fix_command TEXT,
            fix_type TEXT,
            verified_outcome REAL,
            period_start TEXT,
            period_end TEXT,
            created_at TEXT,
            updated_at TEXT,
            snoozed_until TEXT,
            snooze_note TEXT,
            approved_by TEXT,
            approved_at TEXT,
            implemented_at TEXT,
            verified_at TEXT,
            resource_id TEXT,
            resource_type TEXT,
            region TEXT,
            console_link TEXT,
            report_id TEXT,
            source_feature TEXT,
            customer_id TEXT DEFAULT 'default'
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            report_type TEXT NOT NULL,
            period_start TEXT,
            period_end TEXT,
            audience TEXT,
            generated_at TEXT,
            generated_by TEXT,
            status TEXT DEFAULT 'draft',
            total_spend REAL DEFAULT 0,
            total_savings_identified REAL DEFAULT 0,
            total_savings_accepted REAL DEFAULT 0,
            total_savings_implemented REAL DEFAULT 0,
            total_savings_verified REAL DEFAULT 0,
            total_economic_impact REAL DEFAULT 0,
            decisions_required INTEGER DEFAULT 0,
            actions_due INTEGER DEFAULT 0,
            owners_count INTEGER DEFAULT 0,
            finding_ids TEXT DEFAULT '[]',
            finops_score REAL,
            security_score REAL,
            ai_economics_score REAL,
            prior_period_spend REAL,
            spend_change_pct REAL,
            customer_id TEXT DEFAULT 'default',
            slack_message_ts TEXT,
            word_doc_path TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS finding_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            finding_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT,
            note TEXT,
            created_at TEXT,
            customer_id TEXT DEFAULT 'default'
        )
    ''')

    conn.commit()
    conn.close()


# ── Finding CRUD ──────────────────────────────────────────────────────────────

def create_finding(
    title: str,
    description: str,
    category: str,
    monthly_impact: float,
    confidence: float = 0.8,
    owner: str = None,
    team: str = None,
    fix_command: str = None,
    fix_type: str = None,
    resource_id: str = None,
    resource_type: str = None,
    region: str = None,
    console_link: str = None,
    evidence: dict = None,
    source_feature: str = None,
    customer_id: str = 'default'
) -> str:
    import uuid
    now = datetime.now(timezone.utc).isoformat()
    finding_id = f"SAR-{datetime.now(timezone.utc).strftime('%Y%m')}-{str(uuid.uuid4())[:6].upper()}"

    annualized = round(monthly_impact * 12, 2)

    actions = [ActionType.EXPLAIN.value, ActionType.ASSIGN.value]
    if fix_command:
        actions.append(ActionType.GENERATE_FIX.value)
    actions.append(ActionType.APPROVE.value)
    actions.append(ActionType.SNOOZE.value)

    conn = get_db()
    conn.execute('''
        INSERT INTO findings (
            id, title, description, category,
            annualized_impact, monthly_impact,
            owner, team, confidence, days_open, status,
            actions_available, evidence, fix_command, fix_type,
            resource_id, resource_type, region, console_link,
            source_feature, customer_id,
            created_at, updated_at,
            period_start, period_end
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        finding_id, title, description, category,
        annualized, monthly_impact,
        owner, team, confidence, 0, FindingStatus.IDENTIFIED.value,
        json.dumps(actions), json.dumps(evidence or {}),
        fix_command, fix_type,
        resource_id, resource_type, region, console_link,
        source_feature, customer_id,
        now, now,
        datetime.now(timezone.utc).strftime('%Y-%m-01'),
        datetime.now(timezone.utc).strftime('%Y-%m-%d')
    ))
    conn.commit()
    conn.close()

    log_finding_event(finding_id, 'created', 'system', customer_id=customer_id)
    return finding_id

def upsert_finding(
    title: str,
    description: str,
    category: str,
    monthly_impact: float,
    confidence: float = 0.8,
    owner: str = None,
    team: str = None,
    fix_command: str = None,
    fix_type: str = None,
    resource_id: str = None,
    resource_type: str = None,
    region: str = None,
    console_link: str = None,
    evidence: dict = None,
    source_feature: str = None,
    customer_id: str = 'default'
) -> str:
    """Create finding if it doesn't exist; update impact/confidence if it does."""
    conn = get_db()
    row = conn.execute(
        '''SELECT id FROM findings
           WHERE title = ? AND category = ? AND customer_id = ?
           LIMIT 1''',
        (title, category, customer_id)
    ).fetchone()
    conn.close()

    if row:
        # Update the existing finding's impact and confidence, leave status alone
        now = datetime.now(timezone.utc).isoformat()
        conn = get_db()
        conn.execute(
            '''UPDATE findings
               SET monthly_impact = ?, annualized_impact = ?,
                   confidence = ?, description = ?,
                   fix_command = COALESCE(?, fix_command),
                   updated_at = ?
               WHERE id = ?''',
            (monthly_impact, round(monthly_impact * 12, 2),
             confidence, description,
             fix_command, now, row['id'])
        )
        conn.commit()
        conn.close()
        return row['id']
    else:
        return create_finding(
            title=title, description=description, category=category,
            monthly_impact=monthly_impact, confidence=confidence,
            owner=owner, team=team, fix_command=fix_command,
            fix_type=fix_type, resource_id=resource_id,
            resource_type=resource_type, region=region,
            console_link=console_link, evidence=evidence,
            source_feature=source_feature, customer_id=customer_id
        )
    
def get_finding(finding_id: str) -> Optional[Dict]:
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM findings WHERE id = ?', (finding_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    result = dict(row)
    result['actions_available'] = json.loads(result['actions_available'])
    result['evidence'] = json.loads(result['evidence'])
    return result


def get_findings(
    status: str = None,
    category: str = None,
    customer_id: str = 'default',
    limit: int = 50
) -> List[Dict]:
    conn = get_db()
    query = 'SELECT * FROM findings WHERE customer_id = ?'
    params = [customer_id]

    if status:
        query += ' AND status = ?'
        params.append(status)
    if category:
        query += ' AND category = ?'
        params.append(category)

    query += ' ORDER BY annualized_impact DESC LIMIT ?'
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        r['actions_available'] = json.loads(r['actions_available'])
        r['evidence'] = json.loads(r['evidence'])
        results.append(r)
    return results


def update_finding_status(
    finding_id: str,
    new_status: str,
    actor: str = 'system',
    note: str = None
) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()

    updates = {'status': new_status, 'updated_at': now}

    if new_status == FindingStatus.ACCEPTED.value:
        updates['approved_by'] = actor
        updates['approved_at'] = now
    elif new_status == FindingStatus.IMPLEMENTED.value:
        updates['implemented_at'] = now
    elif new_status == FindingStatus.VERIFIED.value:
        updates['verified_at'] = now

    set_clause = ', '.join(f'{k} = ?' for k in updates)
    conn.execute(
        f'UPDATE findings SET {set_clause} WHERE id = ?',
        list(updates.values()) + [finding_id]
    )
    conn.commit()
    conn.close()

    log_finding_event(finding_id, f'status_changed_to_{new_status}', actor, note)
    return True


def assign_finding(finding_id: str, owner: str, team: str = None, actor: str = 'system') -> bool:
    now = datetime.now(timezone.utc).isoformat()
    owner = ' '.join(w[0].upper() + w[1:] for w in owner.split()) if owner else owner   # ← fix capitalization
    conn = get_db()
    conn.execute(
        'UPDATE findings SET owner = ?, team = ?, updated_at = ? WHERE id = ?',
        (owner, team, now, finding_id)
    )
    conn.commit()
    conn.close()
    log_finding_event(finding_id, 'assigned', actor, f'Assigned to {owner}')
    return True


def snooze_finding(finding_id: str, days: int, note: str = None, actor: str = 'system') -> bool:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    snooze_until = (now + timedelta(days=days)).isoformat()
    conn = get_db()
    conn.execute(
        '''UPDATE findings SET status = ?, snoozed_until = ?,
           snooze_note = ?, updated_at = ? WHERE id = ?''',
        (FindingStatus.SNOOZED.value, snooze_until, note,
         now.isoformat(), finding_id)
    )
    conn.commit()
    conn.close()
    log_finding_event(finding_id, 'snoozed', actor, f'Snoozed for {days} days')
    return True


def verify_finding(finding_id: str, actual_savings: float, actor: str = 'system') -> bool:
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute(
        '''UPDATE findings SET status = ?, verified_outcome = ?,
           verified_at = ?, updated_at = ? WHERE id = ?''',
        (FindingStatus.VERIFIED.value, actual_savings, now, now, finding_id)
    )
    conn.commit()
    conn.close()
    log_finding_event(
        finding_id, 'verified', actor,
        f'Actual savings: ${actual_savings}/mo'
    )
    return True


def log_finding_event(
    finding_id: str,
    event_type: str,
    actor: str = 'system',
    note: str = None,
    customer_id: str = 'default'
):
    conn = get_db()
    conn.execute(
        '''INSERT INTO finding_events
           (finding_id, event_type, actor, note, created_at, customer_id)
           VALUES (?,?,?,?,?,?)''',
        (finding_id, event_type, actor, note,
         datetime.now(timezone.utc).isoformat(), customer_id)
    )
    conn.commit()
    conn.close()


def get_finding_events(finding_id: str) -> List[Dict]:
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM finding_events WHERE finding_id = ? ORDER BY created_at',
        (finding_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Pipeline Summary ──────────────────────────────────────────────────────────

def get_pipeline_summary(customer_id: str = 'default') -> Dict:
    conn = get_db()

    stages = [s.value for s in FindingStatus]
    summary = {}

    for stage in stages:
        rows = conn.execute(
            '''SELECT COUNT(*) as count, SUM(annualized_impact) as total
               FROM findings WHERE status = ? AND customer_id = ?''',
            (stage, customer_id)
        ).fetchone()
        summary[stage] = {
            'count': rows['count'] or 0,
            'total': round(rows['total'] or 0, 2)
        }

    # Decisions required = identified with high confidence and impact
    decisions = conn.execute(
        '''SELECT COUNT(*) as count FROM findings
           WHERE status = ? AND customer_id = ?
           AND confidence >= 0.8 AND annualized_impact >= 10000''',
        (FindingStatus.IDENTIFIED.value, customer_id)
    ).fetchone()

    # Actions due = accepted or in_progress
    actions = conn.execute(
        '''SELECT COUNT(*) as count FROM findings
           WHERE status IN (?,?) AND customer_id = ?''',
        (FindingStatus.ACCEPTED.value,
         FindingStatus.IN_PROGRESS.value, customer_id)
    ).fetchone()

    # Unique owners
    owners = conn.execute(
        '''SELECT COUNT(DISTINCT owner) as count FROM findings
           WHERE owner IS NOT NULL AND customer_id = ?
           AND status NOT IN (?,?)''',
        (customer_id, FindingStatus.VERIFIED.value,
         FindingStatus.DISMISSED.value)
    ).fetchone()

    # Total economic impact
    impact = conn.execute(
        '''SELECT SUM(annualized_impact) as total FROM findings
           WHERE customer_id = ? AND status NOT IN (?,?)''',
        (customer_id, FindingStatus.DISMISSED.value,
         FindingStatus.SNOOZED.value)
    ).fetchone()

    conn.close()

    return {
        'pipeline': summary,
        'decisions_required': decisions['count'] or 0,
        'actions_due': actions['count'] or 0,
        'owners_count': owners['count'] or 0,
        'economic_impact': round(impact['total'] or 0, 2),
        'realization_rate': round(
            summary.get('verified', {}).get('total', 0) /
            max(summary.get('identified', {}).get('total', 1), 1) * 100, 1
        )
    }


# ── Top Findings for Interactive Footer ──────────────────────────────────────

def get_top_actionable_findings(
    customer_id: str = 'default',
    limit: int = 3
) -> List[Dict]:
    conn = get_db()
    rows = conn.execute(
        '''SELECT * FROM findings
           WHERE customer_id = ?
           AND status IN (?,?,?)
           ORDER BY annualized_impact DESC
           LIMIT ?''',
        (customer_id,
         FindingStatus.IDENTIFIED.value,
         FindingStatus.ACCEPTED.value,
         FindingStatus.IN_PROGRESS.value,
         limit)
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        r = dict(row)
        r['actions_available'] = json.loads(r['actions_available'])
        r['evidence'] = json.loads(r['evidence'])
        results.append(r)
    return results


# ── Report CRUD ───────────────────────────────────────────────────────────────

def create_report(
    report_type: str,
    audience: str,
    finding_ids: List[str],
    customer_id: str = 'default',
    generated_by: str = 'on_demand'
) -> str:
    import uuid
    now = datetime.now(timezone.utc)
    report_id = f"RPT-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"

    pipeline = get_pipeline_summary(customer_id)

    conn = get_db()
    conn.execute('''
        INSERT INTO reports (
            id, report_type, period_start, period_end,
            audience, generated_at, generated_by, status,
            total_savings_identified, total_savings_accepted,
            total_savings_implemented, total_savings_verified,
            total_economic_impact,
            decisions_required, actions_due, owners_count,
            finding_ids, customer_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        report_id, report_type,
        now.strftime('%Y-%m-01'), now.strftime('%Y-%m-%d'),
        audience, now.isoformat(), generated_by, 'published',
        pipeline['pipeline'].get('identified', {}).get('total', 0),
        pipeline['pipeline'].get('accepted', {}).get('total', 0),
        pipeline['pipeline'].get('implemented', {}).get('total', 0),
        pipeline['pipeline'].get('verified', {}).get('total', 0),
        pipeline['economic_impact'],
        pipeline['decisions_required'],
        pipeline['actions_due'],
        pipeline['owners_count'],
        json.dumps(finding_ids),
        customer_id
    ))
    conn.commit()
    conn.close()
    return report_id


# ── Interactive Footer Formatter ──────────────────────────────────────────────

def format_interactive_footer(
    customer_id: str = 'default',
    report_id: str = None
) -> str:
    pipeline = get_pipeline_summary(customer_id)
    top_findings = get_top_actionable_findings(customer_id)

    impact = pipeline['economic_impact']
    if impact >= 1000000:
        impact_str = f"${impact/1000000:.1f}M"
    elif impact >= 1000:
        impact_str = f"${impact/1000:.0f}K"
    else:
        impact_str = f"${impact:.0f}"

    lines = [
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'*Decisions Required* `{pipeline["decisions_required"]}`  '
        f'*Actions Due* `{pipeline["actions_due"]}`  '
        f'*Owners* `{pipeline["owners_count"]}`  '
        f'*Economic Impact* `{impact_str}`',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        ''
    ]

    for i, finding in enumerate(top_findings, 1):
        annual = finding['annualized_impact']
        if annual >= 1000:
            annual_str = f"${annual/1000:.0f}K"
        else:
            annual_str = f"${annual:.0f}"

        confidence_pct = int(finding['confidence'] * 100)
        days = finding['days_open']

        lines.append(
            f"*{i} · {finding['title']}* — {annual_str} annualized"
        )

        meta_parts = [f"Confidence: {confidence_pct}%", f"{days} days open"]
        if finding.get('owner'):
            meta_parts.insert(0, f"Owner: {finding['owner']}")
        lines.append(f"  {' · '.join(meta_parts)}")

        # Finding-specific action buttons
        actions = finding['actions_available']
        button_parts = []
        if 'approve' in actions:
            button_parts.append(f"`[Approve {finding['id']}]`")
        if 'assign' in actions:
            button_parts.append(f"`[Assign {finding['id']}]`")
        if 'generate_fix' in actions:
            button_parts.append(f"`[Generate Fix {finding['id']}]`")
        if 'explain' in actions:
            button_parts.append(f"`[Explain {finding['id']}]`")
        if 'snooze' in actions:
            button_parts.append(f"`[Snooze {finding['id']}]`")

        if button_parts:
            lines.append('  ' + '  '.join(button_parts))
        lines.append('')

    return '\n'.join(lines)


# ── Auto-capture from existing features ──────────────────────────────────────

def capture_from_savings_recommendations(recommendations: List[Dict], customer_id: str = 'default'):
    for rec in recommendations:
        create_finding(
            title=rec.get('description', 'Savings opportunity'),
            description=rec.get('details', ''),
            category=FindingCategory.COMPUTE.value,
            monthly_impact=rec.get('estimated_savings', 0),
            confidence=0.82,
            fix_type='cli',
            source_feature='savings_recommendations',
            customer_id=customer_id
        )


def capture_from_idle_resources(resources: List[Dict], customer_id: str = 'default'):
    for resource in resources:
        if resource.get('monthly_cost', 0) > 0:
            create_finding(
                title=f"Idle resource: {resource.get('resource_id', 'unknown')}",
                description=f"{resource.get('resource_type', 'Resource')} idle for {resource.get('age_days', 0)} days",
                category=FindingCategory.IDLE.value,
                monthly_impact=resource.get('monthly_cost', 0),
                confidence=0.88,
                resource_id=resource.get('resource_id'),
                resource_type=resource.get('resource_type'),
                region=resource.get('region'),
                fix_command=resource.get('cli_command'),
                fix_type='cli',
                console_link=resource.get('console_link'),
                source_feature='idle_resources',
                customer_id=customer_id
            )


def capture_from_security_gaps(gaps: List[Dict], customer_id: str = 'default'):
    for gap in gaps:
        create_finding(
            title=f"Security gap: {gap.get('service', 'Unknown service')} not enabled",
            description=gap.get('description', ''),
            category=FindingCategory.SECURITY.value,
            monthly_impact=gap.get('monthly_cost_to_enable', 0),
            confidence=0.95,
            fix_type='manual',
            console_link=gap.get('console_link'),
            source_feature='security_score',
            customer_id=customer_id
        )


# ── Init and test ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('Initializing Report Intelligence database...')
    init_db()
    print('✓ Database created')

    # Seed test findings
    print('\nSeeding test findings...')

    f1 = create_finding(
        title='GPU cluster optimization',
        description='ML training cluster running 24/7 with 12% average utilization. Shutdown schedule would reduce costs by 85% during off-hours.',
        category=FindingCategory.COMPUTE.value,
        monthly_impact=15333,
        confidence=0.94,
        owner='AI Platform',
        team='ML Infrastructure',
        fix_command='aws ec2 stop-instances --instance-ids i-0abc123 --region us-east-2',
        fix_type='cli',
        resource_id='i-0abc123',
        resource_type='EC2',
        region='us-east-2',
        source_feature='idle_resources'
    )
    print(f'✓ Created finding: {f1}')

    f2 = create_finding(
        title='Savings Plan commitment opportunity',
        description='Current on-demand EC2 spend of $10,500/month qualifies for 1-year Compute Savings Plan at $3,200/month.',
        category=FindingCategory.SAVINGS_PLAN.value,
        monthly_impact=7300,
        confidence=0.91,
        owner='VP Infrastructure',
        source_feature='savings_recommendations'
    )
    print(f'✓ Created finding: {f2}')

    f3 = create_finding(
        title='Unused storage volumes',
        description='4 EBS volumes unattached for 31+ days across us-east-2 and us-east-1.',
        category=FindingCategory.STORAGE.value,
        monthly_impact=3500,
        confidence=0.96,
        owner='Data Platform',
        team='Data Engineering',
        fix_command='aws ec2 delete-volume --volume-id vol-0abc123 --region us-east-2',
        fix_type='cli',
        source_feature='idle_resources'
    )
    print(f'✓ Created finding: {f3}')

    print('\n=== Pipeline Summary ===')
    pipeline = get_pipeline_summary()
    print(f"Decisions required: {pipeline['decisions_required']}")
    print(f"Actions due: {pipeline['actions_due']}")
    print(f"Owners: {pipeline['owners_count']}")
    print(f"Economic impact: ${pipeline['economic_impact']:,.2f}")
    print(f"Realization rate: {pipeline['realization_rate']}%")

    print('\n=== Interactive Footer ===')
    footer = format_interactive_footer()
    print(footer)

    print('\n=== Test: Approve finding 1 ===')
    update_finding_status(f1, FindingStatus.ACCEPTED.value, actor='prashant')
    finding = get_finding(f1)
    print(f"Status: {finding['status']}")
    print(f"Approved by: {finding['approved_by']}")

    print('\n=== Test: Assign finding 2 ===')
    assign_finding(f2, owner='Sarah Chen', team='Infrastructure', actor='prashant')
    finding = get_finding(f2)
    print(f"Owner: {finding['owner']}")

    print('\n=== Finding Events ===')
    events = get_finding_events(f1)
    for e in events:
        print(f"  {e['event_type']} by {e['actor']} at {e['created_at'][:19]}")