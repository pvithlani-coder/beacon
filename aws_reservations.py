import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def get_expiring_reservations(days_threshold=90):
    results = []
    today = datetime.today()
    threshold_date = today + timedelta(days=days_threshold)

    # Check EC2 Reserved Instances
    try:
        print("Checking EC2 Reserved Instances...")
        ec2_client = boto3.client('ec2', region_name=AWS_REGION)

        reservations = ec2_client.describe_reserved_instances(
            Filters=[{'Name': 'state', 'Values': ['active']}]
        )

        for ri in reservations['ReservedInstances']:
            end_date = ri.get('End')
            if not end_date:
                continue

            if isinstance(end_date, str):
                end_date = datetime.strptime(
                    end_date, '%Y-%m-%dT%H:%M:%S.%fZ')

            end_date = end_date.replace(tzinfo=None)
            days_remaining = (end_date - today).days

            if days_remaining <= days_threshold:
                monthly_cost = float(
                    ri.get('RecurringCharges', [{}])[0].get('Amount', 0)
                ) if ri.get('RecurringCharges') else 0

                results.append({
                    'type': 'EC2 Reserved Instance',
                    'id': ri['ReservedInstancesId'],
                    'instance_type': ri.get('InstanceType', 'Unknown'),
                    'count': ri.get('InstanceCount', 1),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days_remaining': days_remaining,
                    'monthly_cost': round(monthly_cost, 2),
                    'urgency': 'HIGH' if days_remaining <= 30 else
                               'MEDIUM' if days_remaining <= 60 else 'LOW'
                })

    except Exception as e:
        print(f"EC2 RI check error: {e}")

    # Check RDS Reserved Instances
    try:
        print("Checking RDS Reserved Instances...")
        rds_client = boto3.client('rds', region_name=AWS_REGION)

        rds_reservations = rds_client.describe_reserved_db_instances()

        for ri in rds_reservations['ReservedDBInstances']:
            if ri.get('State') != 'active':
                continue

            start_time = ri.get('StartTime')
            duration = ri.get('Duration', 0)

            if start_time:
                if hasattr(start_time, 'replace'):
                    start_time = start_time.replace(tzinfo=None)
                end_date = start_time + timedelta(seconds=duration)
                days_remaining = (end_date - today).days

                if days_remaining <= days_threshold:
                    results.append({
                        'type': 'RDS Reserved Instance',
                        'id': ri['ReservedDBInstanceId'],
                        'instance_type': ri.get(
                            'DBInstanceClass', 'Unknown'),
                        'count': ri.get('DBInstanceCount', 1),
                        'end_date': end_date.strftime('%Y-%m-%d'),
                        'days_remaining': days_remaining,
                        'monthly_cost': round(
                            ri.get('FixedPrice', 0) / 12, 2),
                        'urgency': 'HIGH' if days_remaining <= 30 else
                                   'MEDIUM' if days_remaining <= 60
                                   else 'LOW'
                    })

    except Exception as e:
        print(f"RDS RI check error: {e}")

    # Check Savings Plans
    try:
        print("Checking Savings Plans...")
        sp_client = boto3.client('savingsplans', region_name='us-east-1')

        savings_plans = sp_client.describe_savings_plans(
            states=['active']
        )

        for sp in savings_plans.get('savingsPlans', []):
            end_date_str = sp.get('end')
            if not end_date_str:
                continue

            end_date = datetime.strptime(
                end_date_str, '%Y-%m-%dT%H:%M:%SZ')
            days_remaining = (end_date - today).days

            if days_remaining <= days_threshold:
                results.append({
                    'type': 'Savings Plan',
                    'id': sp['savingsPlanId'],
                    'instance_type': sp.get('savingsPlanType', 'Unknown'),
                    'count': 1,
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'days_remaining': days_remaining,
                    'monthly_cost': round(
                        float(sp.get('commitment', 0)) * 730, 2),
                    'urgency': 'HIGH' if days_remaining <= 30 else
                               'MEDIUM' if days_remaining <= 60 else 'LOW'
                })

    except Exception as e:
        print(f"Savings Plans check error: {e}")

    results.sort(key=lambda x: x['days_remaining'])

    return results


if __name__ == "__main__":
    print("\n=== Expiring Reservations (Next 90 Days) ===")
    reservations = get_expiring_reservations()

    if not reservations:
        print("No reservations expiring in the next 90 days")
    else:
        for r in reservations:
            print(f"\nType: {r['type']}")
            print(f"ID: {r['id']}")
            print(f"Instance: {r['instance_type']} x{r['count']}")
            print(f"Expires: {r['end_date']} ({r['days_remaining']} days)")
            print(f"Monthly Cost: ${r['monthly_cost']}")
            print(f"Urgency: {r['urgency']}")