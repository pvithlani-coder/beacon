import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def get_unmanaged_accounts():
    results = []

    try:
        org_client = boto3.client('organizations', region_name='us-east-1')
        ce_client = boto3.client('ce', region_name=AWS_REGION)

        print("Fetching all AWS organization accounts...")
        accounts = org_client.list_accounts()['Accounts']

        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

        print("Fetching cost data per account...")
        cost_response = ce_client.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'LINKED_ACCOUNT'}]
        )

        accounts_with_spend = {}
        for group in cost_response['ResultsByTime'][0]['Groups']:
            account_id = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            accounts_with_spend[account_id] = round(amount, 2)

        for account in accounts:
            account_id = account['Id']
            account_name = account['Name']
            account_status = account['Status']
            account_email = account['Email']

            issues = []

            # Check for missing name
            if not account_name or account_name == account_id:
                issues.append('No friendly name assigned')

            # Check for no cost tracking
            spend = accounts_with_spend.get(account_id, 0)
            if spend == 0:
                issues.append('No recorded spend in last 30 days')

            # Check tags
            try:
                tag_response = org_client.list_tags_for_resource(
                    ResourceId=account_id
                )
                tags = {t['Key']: t['Value']
                        for t in tag_response['Tags']}

                if 'Owner' not in tags:
                    issues.append('Missing Owner tag')
                if 'Environment' not in tags:
                    issues.append('Missing Environment tag')
                if 'CostCenter' not in tags:
                    issues.append('Missing CostCenter tag')

            except Exception as e:
                issues.append(f'Could not fetch tags: {str(e)[:50]}')

            if issues:
                results.append({
                    'account_id': account_id,
                    'account_name': account_name,
                    'email': account_email,
                    'status': account_status,
                    'monthly_spend': spend,
                    'issues': issues
                })

    except org_client.exceptions.AWSOrganizationsNotInUseException:
        print("This AWS account is not part of an organization")
        results.append({
            'account_id': 'N/A',
            'account_name': 'Standalone Account',
            'email': 'N/A',
            'status': 'ACTIVE',
            'monthly_spend': 0,
            'issues': ['Account is not part of an AWS Organization']
        })

    except Exception as e:
        print(f"Error fetching accounts: {e}")
        results.append({
            'account_id': 'ERROR',
            'account_name': 'Unknown',
            'email': 'N/A',
            'status': 'UNKNOWN',
            'monthly_spend': 0,
            'issues': [f'Error: {str(e)[:100]}']
        })

    return results


if __name__ == "__main__":
    print("\n=== Unmanaged AWS Accounts ===")
    accounts = get_unmanaged_accounts()

    if not accounts:
        print("All accounts are properly managed")
    else:
        for a in accounts:
            print(f"\nAccount: {a['account_name']} ({a['account_id']})")
            print(f"Email: {a['email']}")
            print(f"Monthly Spend: ${a['monthly_spend']}")
            print(f"Issues: {', '.join(a['issues'])}")

def fix_account_tags(account_id, account_email, account_name):
    org_client = boto3.client('organizations', region_name='us-east-1')

    # Determine sensible defaults
    environment = 'production'
    if any(word in account_name.lower() for word in ['dev', 'test', 'staging', 'sandbox']):
        environment = 'development'
    elif any(word in account_name.lower() for word in ['prod', 'live']):
        environment = 'production'

    tags = [
        {'Key': 'Owner', 'Value': account_email},
        {'Key': 'Environment', 'Value': environment},
        {'Key': 'CostCenter', 'Value': 'engineering'}
    ]

    try:
        org_client.tag_resource(
            ResourceId=account_id,
            Tags=tags
        )

        return {
            'success': True,
            'account_id': account_id,
            'account_name': account_name,
            'tags_applied': {
                'Owner': account_email,
                'Environment': environment,
                'CostCenter': 'engineering'
            }
        }

    except Exception as e:
        return {
            'success': False,
            'account_id': account_id,
            'account_name': account_name,
            'error': str(e)
        }