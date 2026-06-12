import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def get_idle_ec2_instances():
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)

    idle_instances = []

    print("Checking for idle EC2 instances...")
    try:
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
        )

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                instance_id = instance['InstanceId']
                instance_type = instance['InstanceType']
                tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                name = tags.get('Name', 'unnamed')

                # Get average CPU over last 7 days
                end = datetime.utcnow()
                start = end - timedelta(days=7)

                metrics = cloudwatch.get_metric_statistics(
                    Namespace='AWS/EC2',
                    MetricName='CPUUtilization',
                    Dimensions=[{
                        'Name': 'InstanceId',
                        'Value': instance_id
                    }],
                    StartTime=start,
                    EndTime=end,
                    Period=86400,
                    Statistics=['Average']
                )

                if metrics['Datapoints']:
                    avg_cpu = sum(
                        d['Average'] for d in metrics['Datapoints']
                    ) / len(metrics['Datapoints'])

                    if avg_cpu < 5.0:
                        idle_instances.append({
                            'id': instance_id,
                            'name': name,
                            'type': instance_type,
                            'avg_cpu': round(avg_cpu, 2),
                            'days_checked': 7,
                            'recommendation': 'Stop or terminate if not needed',
                            'estimated_monthly_savings': estimate_instance_cost(instance_type)
                        })

    except Exception as e:
        print(f"EC2 idle check error: {e}")

    return idle_instances


def estimate_instance_cost(instance_type):
    # Approximate on-demand hourly rates
    pricing = {
        't3.micro': 0.0104,
        't3.small': 0.0208,
        't3.medium': 0.0416,
        't3.large': 0.0832,
        't3.xlarge': 0.1664,
        't4g.micro': 0.0084,
        't4g.small': 0.0168,
        't4g.medium': 0.0336,
        'm5.large': 0.096,
        'm5.xlarge': 0.192,
        'c5.large': 0.085,
        'c5.xlarge': 0.17,
        'r5.large': 0.126,
    }
    hourly = pricing.get(instance_type, 0.05)
    return round(hourly * 730, 2)


def get_orphan_ebs_volumes():
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    orphan_volumes = []

    print("Checking for orphan EBS volumes...")
    try:
        volumes = ec2.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )

        for vol in volumes['Volumes']:
            tags = {t['Key']: t['Value'] for t in vol.get('Tags', [])}
            age_days = (datetime.utcnow() -
                       vol['CreateTime'].replace(tzinfo=None)).days
            monthly_cost = round(vol['Size'] * 0.10, 2)

            orphan_volumes.append({
                'id': vol['VolumeId'],
                'name': tags.get('Name', 'unnamed'),
                'size_gb': vol['Size'],
                'type': vol['VolumeType'],
                'age_days': age_days,
                'monthly_cost': monthly_cost,
                'recommendation': 'Delete if no longer needed'
            })

    except Exception as e:
        print(f"EBS orphan check error: {e}")

    return orphan_volumes


def get_unused_elastic_ips():
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    unused_eips = []

    print("Checking for unused Elastic IPs...")
    try:
        addresses = ec2.describe_addresses()

        for eip in addresses['Addresses']:
            if 'AssociationId' not in eip:
                unused_eips.append({
                    'ip': eip['PublicIp'],
                    'allocation_id': eip.get('AllocationId', 'N/A'),
                    'monthly_cost': 3.65,
                    'recommendation': 'Release if not needed'
                })

    except Exception as e:
        print(f"Elastic IP check error: {e}")

    return unused_eips


def get_idle_rds_instances():
    rds = boto3.client('rds', region_name=AWS_REGION)
    cloudwatch = boto3.client('cloudwatch', region_name=AWS_REGION)
    idle_rds = []

    print("Checking for idle RDS instances...")
    try:
        dbs = rds.describe_db_instances()

        for db in dbs['DBInstances']:
            db_id = db['DBInstanceIdentifier']
            db_class = db['DBInstanceClass']
            status = db['DBInstanceStatus']

            if status != 'available':
                continue

            end = datetime.utcnow()
            start = end - timedelta(days=7)

            metrics = cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='DatabaseConnections',
                Dimensions=[{
                    'Name': 'DBInstanceIdentifier',
                    'Value': db_id
                }],
                StartTime=start,
                EndTime=end,
                Period=86400,
                Statistics=['Average']
            )

            if metrics['Datapoints']:
                avg_connections = sum(
                    d['Average'] for d in metrics['Datapoints']
                ) / len(metrics['Datapoints'])

                if avg_connections < 1.0:
                    idle_rds.append({
                        'id': db_id,
                        'class': db_class,
                        'avg_connections': round(avg_connections, 2),
                        'days_checked': 7,
                        'recommendation': 'Stop or downsize if connections remain low',
                        'monthly_cost': db.get('AllocatedStorage', 0) * 0.115
                    })

    except Exception as e:
        print(f"RDS idle check error: {e}")

    return idle_rds


def get_old_snapshots():
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    old_snapshots = []

    print("Checking for old snapshots...")
    try:
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])

        for snap in snapshots['Snapshots']:
            start_time = snap['StartTime'].replace(tzinfo=None)
            age_days = (datetime.utcnow() - start_time).days

            if age_days > 30:
                monthly_cost = round(snap['VolumeSize'] * 0.05, 2)
                old_snapshots.append({
                    'id': snap['SnapshotId'],
                    'size_gb': snap['VolumeSize'],
                    'age_days': age_days,
                    'description': snap.get('Description', 'no description')[:60],
                    'monthly_cost': monthly_cost,
                    'recommendation': 'Delete if no longer needed for recovery'
                })

    except Exception as e:
        print(f"Snapshot check error: {e}")

    return old_snapshots


def get_all_idle_resources():
    idle_ec2 = get_idle_ec2_instances()
    orphan_ebs = get_orphan_ebs_volumes()
    unused_eips = get_unused_elastic_ips()
    idle_rds = get_idle_rds_instances()
    old_snapshots = get_old_snapshots()

    total_monthly_waste = (
        sum(r['estimated_monthly_savings'] for r in idle_ec2) +
        sum(r['monthly_cost'] for r in orphan_ebs) +
        sum(r['monthly_cost'] for r in unused_eips) +
        sum(r['monthly_cost'] for r in idle_rds) +
        sum(r['monthly_cost'] for r in old_snapshots)
    )

    return {
        'idle_ec2': idle_ec2,
        'orphan_ebs': orphan_ebs,
        'unused_eips': unused_eips,
        'idle_rds': idle_rds,
        'old_snapshots': old_snapshots,
        'total_monthly_waste': round(total_monthly_waste, 2),
        'total_annual_waste': round(total_monthly_waste * 12, 2)
    }


if __name__ == "__main__":
    import json
    print("\n=== Idle Resource Detection ===")
    data = get_all_idle_resources()

    print(f"\nTotal Monthly Waste: ${data['total_monthly_waste']}")
    print(f"Total Annual Waste: ${data['total_annual_waste']}")

    print(f"\nIdle EC2 Instances: {len(data['idle_ec2'])}")
    for r in data['idle_ec2']:
        print(f"  {r['name']} ({r['id']}): {r['avg_cpu']}% avg CPU - saves ${r['estimated_monthly_savings']}/mo")

    print(f"\nOrphan EBS Volumes: {len(data['orphan_ebs'])}")
    for r in data['orphan_ebs']:
        print(f"  {r['name']} ({r['id']}): {r['size_gb']}GB, {r['age_days']} days old - ${r['monthly_cost']}/mo")

    print(f"\nUnused Elastic IPs: {len(data['unused_eips'])}")
    for r in data['unused_eips']:
        print(f"  {r['ip']}: ${r['monthly_cost']}/mo")

    print(f"\nIdle RDS Instances: {len(data['idle_rds'])}")
    for r in data['idle_rds']:
        print(f"  {r['id']}: {r['avg_connections']} avg connections - ${r['monthly_cost']}/mo")

    print(f"\nOld Snapshots (30+ days): {len(data['old_snapshots'])}")
    for r in data['old_snapshots']:
        print(f"  {r['id']}: {r['size_gb']}GB, {r['age_days']} days old - ${r['monthly_cost']}/mo")