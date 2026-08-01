import sqlite3
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_FILE = 'knowledge_graph.db'


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            customer_id TEXT DEFAULT 'default',
            feature TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'open',
            confidence TEXT DEFAULT 'MEDIUM',
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            time_to_resolve_minutes INTEGER
        );

        CREATE TABLE IF NOT EXISTS root_causes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            cause TEXT NOT NULL,
            service TEXT,
            confidence TEXT DEFAULT 'MEDIUM',
            evidence TEXT,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );

        CREATE TABLE IF NOT EXISTS owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            owner TEXT NOT NULL,
            team TEXT,
            assigned_at TEXT,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );

        CREATE TABLE IF NOT EXISTS resolutions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            resolution TEXT NOT NULL,
            fix_command TEXT,
            fix_type TEXT,
            savings_monthly REAL DEFAULT 0,
            verified INTEGER DEFAULT 0,
            verified_at TEXT,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        );

        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_type TEXT NOT NULL,
            pattern_key TEXT NOT NULL UNIQUE,
            description TEXT,
            occurrences INTEGER DEFAULT 1,
            avg_time_to_resolve REAL,
            avg_savings REAL DEFAULT 0,
            confidence_score REAL DEFAULT 0.5,
            last_seen TEXT,
            example_investigation_id INTEGER,
            FOREIGN KEY (example_investigation_id) REFERENCES investigations(id)
        );

        CREATE TABLE IF NOT EXISTS pattern_matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            pattern_id INTEGER NOT NULL,
            match_score REAL DEFAULT 0,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id),
            FOREIGN KEY (pattern_id) REFERENCES patterns(id)
        );

        CREATE INDEX IF NOT EXISTS idx_investigations_feature
            ON investigations(feature);
        CREATE INDEX IF NOT EXISTS idx_investigations_customer
            ON investigations(customer_id);
        CREATE INDEX IF NOT EXISTS idx_root_causes_cause
            ON root_causes(cause);
        CREATE INDEX IF NOT EXISTS idx_patterns_key
            ON patterns(pattern_key);
    ''')

    conn.commit()
    conn.close()
    print("Knowledge Graph database initialized")


def create_investigation(feature, title, description=None,
                         customer_id='default', confidence='MEDIUM'):
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO investigations
        (timestamp, customer_id, feature, title, description,
         status, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
    ''', (datetime.now().isoformat(), customer_id, feature,
          title, description, confidence, datetime.now().isoformat()))

    investigation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"Investigation created: INV-{investigation_id:04d} - {title}")
    return investigation_id


def add_root_cause(investigation_id, cause, service=None,
                   confidence='MEDIUM', evidence=None):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO root_causes
        (investigation_id, cause, service, confidence, evidence)
        VALUES (?, ?, ?, ?, ?)
    ''', (investigation_id, cause, service, confidence, evidence))

    conn.commit()
    conn.close()

    # Update pattern
    _update_pattern(cause, service, investigation_id)
    return cursor.lastrowid


def add_owner(investigation_id, owner, team=None):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO owners
        (investigation_id, owner, team, assigned_at)
        VALUES (?, ?, ?, ?)
    ''', (investigation_id, owner, team, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return cursor.lastrowid


def add_resolution(investigation_id, resolution, fix_command=None,
                   fix_type=None, savings_monthly=0):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO resolutions
        (investigation_id, resolution, fix_command,
         fix_type, savings_monthly)
        VALUES (?, ?, ?, ?, ?)
    ''', (investigation_id, resolution, fix_command,
          fix_type, savings_monthly))

    conn.commit()
    conn.close()
    return cursor.lastrowid


def resolve_investigation(investigation_id, savings_monthly=0):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT created_at FROM investigations WHERE id = ?
    ''', (investigation_id,))
    row = cursor.fetchone()

    time_to_resolve = None
    if row:
        created = datetime.fromisoformat(row['created_at'])
        resolved = datetime.now()
        time_to_resolve = int(
            (resolved - created).total_seconds() / 60)

    cursor.execute('''
        UPDATE investigations
        SET status = 'resolved',
            resolved_at = ?,
            time_to_resolve_minutes = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), time_to_resolve, investigation_id))

    if savings_monthly > 0:
        cursor.execute('''
            UPDATE resolutions
            SET verified = 1, verified_at = ?
            WHERE investigation_id = ?
        ''', (datetime.now().isoformat(), investigation_id))

    conn.commit()
    conn.close()

    _update_pattern_stats(investigation_id, time_to_resolve, savings_monthly)
    print(f"Investigation INV-{investigation_id:04d} resolved in "
          f"{time_to_resolve} minutes")
    return time_to_resolve


def _update_pattern(cause, service, investigation_id):
    pattern_key = f"{cause}:{service or 'unknown'}".lower().replace(' ', '_')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, occurrences FROM patterns WHERE pattern_key = ?
    ''', (pattern_key,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('''
            UPDATE patterns
            SET occurrences = occurrences + 1,
                last_seen = ?,
                confidence_score = MIN(0.95, confidence_score + 0.05)
            WHERE pattern_key = ?
        ''', (datetime.now().isoformat(), pattern_key))

        cursor.execute('''
            INSERT INTO pattern_matches
            (investigation_id, pattern_id, match_score)
            VALUES (?, ?, ?)
        ''', (investigation_id, existing['id'], existing['occurrences'] * 0.1))
    else:
        cursor.execute('''
            INSERT INTO patterns
            (pattern_type, pattern_key, description,
             occurrences, confidence_score, last_seen,
             example_investigation_id)
            VALUES (?, ?, ?, 1, 0.5, ?, ?)
        ''', ('root_cause', pattern_key,
              f"{cause} affecting {service or 'unknown service'}",
              datetime.now().isoformat(), investigation_id))

    conn.commit()
    conn.close()


def _update_pattern_stats(investigation_id, time_to_resolve, savings):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT p.id, p.avg_time_to_resolve, p.avg_savings, p.occurrences
        FROM patterns p
        JOIN pattern_matches pm ON p.id = pm.pattern_id
        WHERE pm.investigation_id = ?
    ''', (investigation_id,))

    patterns = cursor.fetchall()
    for pattern in patterns:
        new_avg_time = None
        if time_to_resolve and pattern['avg_time_to_resolve']:
            new_avg_time = (
                pattern['avg_time_to_resolve'] *
                (pattern['occurrences'] - 1) + time_to_resolve
            ) / pattern['occurrences']
        elif time_to_resolve:
            new_avg_time = time_to_resolve

        new_avg_savings = None
        if savings and pattern['avg_savings']:
            new_avg_savings = (
                pattern['avg_savings'] *
                (pattern['occurrences'] - 1) + savings
            ) / pattern['occurrences']
        elif savings:
            new_avg_savings = savings

        cursor.execute('''
            UPDATE patterns
            SET avg_time_to_resolve = COALESCE(?, avg_time_to_resolve),
                avg_savings = COALESCE(?, avg_savings)
            WHERE id = ?
        ''', (new_avg_time, new_avg_savings, pattern['id']))

    conn.commit()
    conn.close()


def find_similar_patterns(cause, service=None, limit=3):
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    search_key = f"{cause}:{service or 'unknown'}".lower().replace(' ', '_')

    cursor.execute('''
        SELECT p.*,
               COUNT(pm.id) as match_count
        FROM patterns p
        LEFT JOIN pattern_matches pm ON p.id = pm.pattern_id
        WHERE p.pattern_key LIKE ?
           OR p.description LIKE ?
        GROUP BY p.id
        ORDER BY p.confidence_score DESC, p.occurrences DESC
        LIMIT ?
    ''', (f'%{cause.lower().replace(" ", "_")}%',
          f'%{cause.lower()}%', limit))

    patterns = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return patterns


def get_knowledge_graph_summary(customer_id=None):
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    where = "WHERE customer_id = ?" if customer_id else ""
    params = (customer_id,) if customer_id else ()

    cursor.execute(f'''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved,
            SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
            AVG(time_to_resolve_minutes) as avg_resolve_minutes
        FROM investigations {where}
    ''', params)
    inv_stats = dict(cursor.fetchone())

    cursor.execute('''
        SELECT COUNT(*) as total,
               AVG(confidence_score) as avg_confidence,
               MAX(occurrences) as max_occurrences
        FROM patterns
    ''')
    pattern_stats = dict(cursor.fetchone())

    cursor.execute('''
        SELECT SUM(savings_monthly) as total_savings
        FROM resolutions
        WHERE verified = 1
    ''')
    savings = cursor.fetchone()['total_savings'] or 0

    cursor.execute('''
        SELECT p.description, p.occurrences, p.confidence_score,
               p.avg_time_to_resolve, p.avg_savings
        FROM patterns p
        ORDER BY p.occurrences DESC, p.confidence_score DESC
        LIMIT 5
    ''')
    top_patterns = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        'total_investigations': inv_stats['total'],
        'resolved_investigations': inv_stats['resolved'],
        'open_investigations': inv_stats['open'],
        'avg_resolve_minutes': round(
            inv_stats['avg_resolve_minutes'] or 0, 1),
        'total_patterns': pattern_stats['total'],
        'avg_pattern_confidence': round(
            pattern_stats['avg_confidence'] or 0, 2),
        'most_common_pattern_occurrences': pattern_stats['max_occurrences'],
        'verified_savings_monthly': round(savings, 2),
        'top_patterns': top_patterns
    }


def get_investigation_history(limit=10, customer_id=None):
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    where = "WHERE i.customer_id = ?" if customer_id else ""
    params = (customer_id,) if customer_id else ()

    cursor.execute(f'''
        SELECT i.*,
               GROUP_CONCAT(DISTINCT rc.cause) as causes,
               GROUP_CONCAT(DISTINCT o.owner) as owners,
               GROUP_CONCAT(DISTINCT r.resolution) as resolutions,
               MAX(r.savings_monthly) as max_savings
        FROM investigations i
        LEFT JOIN root_causes rc ON i.id = rc.investigation_id
        LEFT JOIN owners o ON i.id = o.investigation_id
        LEFT JOIN resolutions r ON i.id = r.investigation_id
        {where}
        GROUP BY i.id
        ORDER BY i.created_at DESC
        LIMIT ?
    ''', params + (limit,))

    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


def auto_capture_from_rca(rca_results, customer_id='default'):
    captured = []
    for result in rca_results:
        inv_id = create_investigation(
            feature='cost_rca',
            title=f"Cost spike in {result['service']}",
            description=f"Spend ${result['current_spend']} vs avg ${result['historical_avg']}",
            customer_id=customer_id,
            confidence='HIGH' if result['findings'] else 'LOW'
        )

        for finding in result['findings']:
            add_root_cause(
                inv_id,
                cause=finding['cause'],
                service=result['service'],
                confidence=finding['confidence'],
                evidence=f"Spend deviation: {result.get('deviation_pct', 0):.1f}%"
            )

        captured.append(inv_id)

    return captured


if __name__ == "__main__":
    print("\n=== Knowledge Graph Test ===")

    init_db()

    # Simulate 3 investigations
    inv1 = create_investigation(
        'cost_rca', 'EC2 cost spike - dev instances left running',
        'EC2 spend jumped 340% overnight',
        customer_id='default', confidence='HIGH'
    )
    add_root_cause(inv1, 'Dev instances not stopped after testing',
                   'Amazon EC2', 'HIGH', 'CPU 0.1% for 18 hours')
    add_owner(inv1, 'engineering-team', 'Engineering')
    add_resolution(inv1, 'Stop dev EC2 instances and add auto-shutdown',
                   'aws ec2 stop-instances --instance-ids i-xxx',
                   'manual', savings_monthly=45.00)
    resolve_investigation(inv1, savings_monthly=45.00)

    inv2 = create_investigation(
        'idle_resources', 'Orphan EBS snapshots accumulating',
        '2 snapshots older than 30 days',
        customer_id='default', confidence='HIGH'
    )
    add_root_cause(inv2, 'Snapshots not deleted after instance termination',
                   'Amazon EBS', 'HIGH', 'Snapshots 1642 days old')
    add_resolution(inv2, 'Delete old snapshots',
                   'aws ec2 delete-snapshot --snapshot-id snap-xxx',
                   'terraform', savings_monthly=2.30)
    resolve_investigation(inv2, savings_monthly=2.30)

    inv3 = create_investigation(
        'ai_economics', 'Legal Copilot token costs spiking 63%',
        'Prompts 82% longer than peer average',
        customer_id='mindcan', confidence='HIGH'
    )
    add_root_cause(inv3, 'System prompt bloat - unnecessary context loaded',
                   'OpenAI GPT-4o', 'HIGH',
                   'Avg prompt 7100 tokens vs peer avg 3900')
    add_owner(inv3, 'legal-team', 'Legal Operations')
    add_resolution(inv3, 'Trim system prompt and enable semantic caching',
                   None, 'optimization', savings_monthly=313.00)

    # Find similar patterns
    print("\nSearching for similar patterns to 'Dev instances not stopped'...")
    patterns = find_similar_patterns('Dev instances not stopped', 'Amazon EC2')
    for p in patterns:
        print(f"  Pattern: {p['description']}")
        print(f"  Occurrences: {p['occurrences']}")
        print(f"  Confidence: {p['confidence_score']:.0%}")
        if p['avg_time_to_resolve']:
            print(f"  Avg time to resolve: {p['avg_time_to_resolve']:.0f} mins")

    # Summary
    summary = get_knowledge_graph_summary()
    print(f"\nKnowledge Graph Summary:")
    print(f"  Total investigations: {summary['total_investigations']}")
    print(f"  Resolved: {summary['resolved_investigations']}")
    print(f"  Total patterns: {summary['total_patterns']}")
    print(f"  Avg resolve time: {summary['avg_resolve_minutes']} mins")
    print(f"  Verified savings: ${summary['verified_savings_monthly']}/mo")
    print(f"\nTop patterns:")
    for p in summary['top_patterns']:
        print(f"  {p['description']} "
              f"({p['occurrences']}x, "
              f"{p['confidence_score']:.0%} confidence)")