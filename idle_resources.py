import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aws_regions import get_regions, get_primary_region

load_dotenv()

AWS_REGION = get_primary_region()


def estimate_instance_cost(instance_type):
    pricing = {
        't3.micro': 0.0104, 't3.small': 0.0208, 't3.medium': 0.0416,
        't3.large': 0.0832, 't3.xlarge': 0.1664, 't4g.micro': 0.0084,
        't4g.small': 0.0168, 't4g.medium': 0.0336, 'm5.large': 0.096,
        'm5.xlarge': 0.192, 'c5.large': 0.085, 'c5.xlarge': 0.17,
        'r5.large': 0.126,
    }
    hourly = pricing.get(instance_type, 0.05)
    return round(hourly * 730, 2)


def get_idle_ec2_instances():
    regions = get_regions()
    idle_instances = []

    for region in regions:
        print(f"Checking for idle EC2 instances in {region}...")
        try:
            ec2 = boto3.client('ec2', region_name=region)
            cloudwatch = boto3.client('cloudwatch', region_name=region)

            instances = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )

            for reservation in instances['Reservations']:
                for instance in reservation['Instances']:
                    instance_id = instance['InstanceId']
                    instance_type = instance['InstanceType']
                    tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                    name = tags.get('Name', 'unnamed')

                    end = datetime.utcnow()
                    start = end - timedelta(days=7)

                    metrics = cloudwatch.get_metric_statistics(
                        Namespace='AWS/EC2',
                        MetricName='CPUUtilization',
                        Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                        StartTime=start, EndTime=end,
                        Period=86400, Statistics=['Average']
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
                                'region': region,
                                'avg_cpu': round(avg_cpu, 2),
                                'days_checked': 7,
                                'recommendation': 'Stop or terminate if not needed',
                                'estimated_monthly_savings': estimate_instance_cost(instance_type)
                            })

        except Exception as e:
            print(f"EC2 idle check error in {region}: {e}")

    return idle_instances


def get_orphan_ebs_volumes():
    regions = get_regions()
    orphan_volumes = []

    for region in regions:
        print(f"Checking for orphan EBS volumes in {region}...")
        try:
            ec2 = boto3.client('ec2', region_name=region)
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
                    'region': region,
                    'age_days': age_days,
                    'monthly_cost': monthly_cost,
                    'recommendation': 'Delete if no longer needed'
                })

        except Exception as e:
            print(f"EBS orphan check error in {region}: {e}")

    return orphan_volumes


def get_unused_elastic_ips():
    regions = get_regions()
    unused_eips = []

    for region in regions:
        print(f"Checking for unused Elastic IPs in {region}...")
        try:
            ec2 = boto3.client('ec2', region_name=region)
            addresses = ec2.describe_addresses()

            for eip in addresses['Addresses']:
                if 'AssociationId' not in eip:
                    unused_eips.append({
                        'ip': eip['PublicIp'],
                        'allocation_id': eip.get('AllocationId', 'N/A'),
                        'region': region,
                        'monthly_cost': 3.65,
                        'recommendation': 'Release if not needed'
                    })

        except Exception as e:
            print(f"Elastic IP check error in {region}: {e}")

    return unused_eips


def get_idle_rds_instances():
    regions = get_regions()
    idle_rds = []

    for region in regions:
        print(f"Checking for idle RDS instances in {region}...")
        try:
            rds = boto3.client('rds', region_name=region)
            cloudwatch = boto3.client('cloudwatch', region_name=region)
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
                    StartTime=start, EndTime=end,
                    Period=86400, Statistics=['Average']
                )

                if metrics['Datapoints']:
                    avg_connections = sum(
                        d['Average'] for d in metrics['Datapoints']
                    ) / len(metrics['Datapoints'])

                    if avg_connections < 1.0:
                        idle_rds.append({
                            'id': db_id,
                            'class': db_class,
                            'region': region,
                            'avg_connections': round(avg_connections, 2),
                            'days_checked': 7,
                            'recommendation': 'Stop or downsize if connections remain low',
                            'monthly_cost': db.get('AllocatedStorage', 0) * 0.115
                        })

        except Exception as e:
            print(f"RDS idle check error in {region}: {e}")

    return idle_rds


def get_old_snapshots():
    regions = get_regions()
    old_snapshots = []

    for region in regions:
        print(f"Checking for old snapshots in {region}...")
        try:
            ec2 = boto3.client('ec2', region_name=region)
            snapshots = ec2.describe_snapshots(OwnerIds=['self'])

            for snap in snapshots['Snapshots']:
                start_time = snap['StartTime'].replace(tzinfo=None)
                age_days = (datetime.utcnow() - start_time).days

                if age_days > 30:
                    monthly_cost = round(snap['VolumeSize'] * 0.05, 2)
                    old_snapshots.append({
                        'id': snap['SnapshotId'],
                        'size_gb': snap['VolumeSize'],
                        'region': region,
                        'age_days': age_days,
                        'description': snap.get('Description', 'no description')[:60],
                        'monthly_cost': monthly_cost,
                        'recommendation': 'Delete if no longer needed for recovery'
                    })

        except Exception as e:
            print(f"Snapshot check error in {region}: {e}")

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
        'total_annual_waste': round(total_monthly_waste * 12, 2),
        'regions_scanned': get_regions()
    }


if __name__ == "__main__":
    print(f"\n=== Multi-Region Idle Resource Detection ===")
    print(f"Scanning regions: {get_regions()}")
    data = get_all_idle_resources()

    print(f"\nTotal Monthly Waste: ${data['total_monthly_waste']}")
    print(f"Regions scanned: {', '.join(data['regions_scanned'])}")

    print(f"\nIdle EC2: {len(data['idle_ec2'])}")
    print(f"Orphan EBS: {len(data['orphan_ebs'])}")
    print(f"Unused EIPs: {len(data['unused_eips'])}")
    print(f"Idle RDS: {len(data['idle_rds'])}")
    print(f"Old Snapshots: {len(data['old_snapshots'])}")
    for r in data['old_snapshots']:
        print(f"  {r['id']} ({r['region']}): {r['age_days']} days - ${r['monthly_cost']}/mo")