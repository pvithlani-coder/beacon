import os
from dotenv import load_dotenv
import pagerduty

load_dotenv()

PAGERDUTY_API_KEY = os.environ.get('PAGERDUTY_API_KEY')


def get_active_incidents():
    client = pagerduty.RestApiV2Client(PAGERDUTY_API_KEY)

    incidents = client.list_all(
        'incidents',
        params={
            'statuses[]': ['triggered', 'acknowledged'],
            'sort_by': 'created_at:desc',
            'limit': 10
        }
    )

    results = []

    for incident in incidents:
        results.append({
            'id': incident['id'],
            'title': incident['title'],
            'status': incident['status'],
            'urgency': incident['urgency'],
            'created_at': incident['created_at'],
            'service': incident['service']['summary'],
            'url': incident['html_url']
        })

    return results


def get_incident_details(incident_id):
    client = pagerduty.RestApiV2Client(PAGERDUTY_API_KEY)

    incident = client.get(f'incidents/{incident_id}').json()['incident']

    notes = []
    try:
        notes_response = client.list_all(
            f'incidents/{incident_id}/notes'
        )
        notes = [n['content'] for n in notes_response]
    except Exception:
        pass

    return {
        'id': incident['id'],
        'title': incident['title'],
        'status': incident['status'],
        'urgency': incident['urgency'],
        'created_at': incident['created_at'],
        'service': incident['service']['summary'],
        'url': incident['html_url'],
        'notes': notes
    }


if __name__ == "__main__":
    print("Fetching active incidents...")
    incidents = get_active_incidents()

    if not incidents:
        print("No active incidents found")
    else:
        for i in incidents:
            print(f"\nIncident: {i['title']}")
            print(f"Status: {i['status']}")
            print(f"Urgency: {i['urgency']}")
            print(f"Service: {i['service']}")
            print(f"URL: {i['url']}")