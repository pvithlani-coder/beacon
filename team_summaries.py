import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def get_team_spend():
    client = boto3.client('ce', region_name=AWS_REGION)
    today = datetime.today()

    # Current week
    end = today.strftime('%Y-%m-%d')
    start = (today - timedelta(days=7)).strftime('%Y-%m-%d')

    # Prior week for comparison
    prior_end = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    prior_start = (today - timedelta(days=14)).strftime('%Y-%m-%d')

    try:
        # Current week by team tag
        current_response = client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'TAG', 'Key': 'Team'}]
        )

        # Prior week by team tag
        prior_response = client.get_cost_and_usage(
            TimePeriod={'Start': prior_start, 'End': prior_end},
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'TAG', 'Key': 'Team'}]
        )

        current_spend = {}
        for day in current_response['ResultsByTime']:
            for group in day['Groups']:
                team = group['Keys'][0].replace('Team$', '')
                if not team:
                    team = 'untagged'
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                if amount > 0.001:
                    current_spend[team] = round(
                        current_spend.get(team, 0) + amount, 2)

        prior_spend = {}
        for day in prior_response['ResultsByTime']:
            for group in day['Groups']:
                team = group['Keys'][0].replace('Team$', '')
                if not team:
                    team = 'untagged'
                amount = float(group['Metrics']['UnblendedCost']['Amount'])
                if amount > 0.001:
                    prior_spend[team] = round(
                        prior_spend.get(team, 0) + amount, 2)

        # Calculate week over week change per team
        team_data = []
        all_teams = set(list(current_spend.keys()) + list(prior_spend.keys()))

        for team in all_teams:
            current = current_spend.get(team, 0)
            prior = prior_spend.get(team, 0)

            if prior > 0:
                change_pct = ((current - prior) / prior) * 100
            else:
                change_pct = 100 if current > 0 else 0

            team_data.append({
                'team': team,
                'current_week': current,
                'prior_week': prior,
                'change_pct': round(change_pct, 1),
                'change_amount': round(current - prior, 2),
                'trend': 'UP' if change_pct > 5 else 'DOWN' if change_pct < -5 else 'STABLE'
            })

        team_data.sort(key=lambda x: x['current_week'], reverse=True)

        return {
            'week_start': start,
            'week_end': end,
            'teams': team_data,
            'total_current': round(sum(t['current_week'] for t in team_data), 2),
            'total_prior': round(sum(t['prior_week'] for t in team_data), 2)
        }

    except Exception as e:
        print(f"Team spend error: {e}")
        return {
            'week_start': start,
            'week_end': end,
            'teams': [],
            'total_current': 0,
            'total_prior': 0
        }


def generate_team_summary(team_name, team_data, all_teams_data):
    team = next(
        (t for t in all_teams_data['teams'] if t['team'] == team_name),
        None
    )

    if not team:
        return None

    change_direction = "increased" if team['change_pct'] > 0 else "decreased"
    change_sign = "+" if team['change_pct'] > 0 else ""

    summary = {
        'team': team_name,
        'current_week': team['current_week'],
        'prior_week': team['prior_week'],
        'change_pct': team['change_pct'],
        'change_direction': change_direction,
        'change_sign': change_sign,
        'trend': team['trend']
    }

    return summary


def get_all_team_summaries():
    data = get_team_spend()

    if not data['teams']:
        return {
            'status': 'no_team_tags',
            'message': 'No Team tags found. Add Team tags to AWS resources to enable team summaries.',
            'teams': []
        }

    summaries = []
    for team_info in data['teams']:
        summary = generate_team_summary(
            team_info['team'], team_info, data)
        if summary:
            summaries.append(summary)

    return {
        'status': 'success',
        'week_start': data['week_start'],
        'week_end': data['week_end'],
        'total_current': data['total_current'],
        'total_prior': data['total_prior'],
        'summaries': summaries
    }


if __name__ == "__main__":
    print("\n=== Engineering Team Summaries ===")
    data = get_team_spend()

    if not data['teams']:
        print("No Team tags found in AWS account.")
        print("Add Team tags to resources to enable team summaries.")
    else:
        print(f"\nWeek: {data['week_start']} to {data['week_end']}")
        print(f"Total spend: ${data['total_current']}")
        print(f"\nBy team:")
        for team in data['teams']:
            sign = "+" if team['change_pct'] > 0 else ""
            print(f"  {team['team']}: ${team['current_week']} "
                  f"({sign}{team['change_pct']}% vs last week) "
                  f"[{team['trend']}]")