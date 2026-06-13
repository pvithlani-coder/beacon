import json
import os
from datetime import datetime

FEEDBACK_LOG = 'feature_requests.json'


def log_feature_request(text, user_id, response_type='unrecognized'):
    log = []
    if os.path.exists(FEEDBACK_LOG):
        with open(FEEDBACK_LOG, 'r') as f:
            log = json.load(f)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'query': text,
        'response_type': response_type,
        'status': 'new'
    }

    log.append(entry)

    with open(FEEDBACK_LOG, 'w') as f:
        json.dump(log, f, indent=2)

    print(f"Feature request logged: {text[:50]}")
    return entry


def get_feature_requests(status=None):
    if not os.path.exists(FEEDBACK_LOG):
        return []

    with open(FEEDBACK_LOG, 'r') as f:
        log = json.load(f)

    if status:
        return [e for e in log if e['status'] == status]

    return log


def get_feature_summary():
    requests = get_feature_requests()

    if not requests:
        return {
            'total': 0,
            'new': 0,
            'reviewed': 0,
            'top_queries': []
        }

    new_count = len([r for r in requests if r['status'] == 'new'])
    reviewed_count = len([r for r in requests if r['status'] == 'reviewed'])

    # Find most common query patterns
    from collections import Counter
    query_words = []
    for r in requests:
        words = r['query'].lower().split()
        query_words.extend([
            w for w in words
            if len(w) > 3 and w not in
            ['what', 'how', 'does', 'this', 'that', 'with', 'your', 'have']
        ])

    top_words = Counter(query_words).most_common(5)

    return {
        'total': len(requests),
        'new': new_count,
        'reviewed': reviewed_count,
        'top_queries': [{'word': w, 'count': c} for w, c in top_words],
        'recent': requests[-5:]
    }


if __name__ == "__main__":
    print("\n=== Feature Request Log ===")
    summary = get_feature_summary()
    print(f"Total requests: {summary['total']}")
    print(f"New: {summary['new']}")
    print(f"Reviewed: {summary['reviewed']}")
    if summary['top_queries']:
        print(f"Top query themes: {summary['top_queries']}")
    if summary['recent']:
        print(f"\nRecent requests:")
        for r in summary['recent']:
            print(f"  {r['timestamp'][:10]}: {r['query'][:60]}")