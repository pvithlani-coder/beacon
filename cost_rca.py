import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'


def investigate_compute_spike(service, current_amount, historical_avg):
    ec2 = boto3.client('ec2', region_name=AWS_REGION)
    findings = []

    try:
        # Check for recently launched instances
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name', 'Values': ['running', 'stopped']}]
        )

        recent_instances = []
        cutoff = datetime.now() - timedelta(days=7)

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                launch_time = instance['LaunchTime'].replace(tzinfo=None)
                if launch_time >= cutoff:
                    tags = {t['Key']: t['Value'] for t in instance.get('Tags', [])}
                    recent_instances.append({
                        'id': instance['InstanceId'],
                        'type': instance['InstanceType'],
                        'launched': launch_time.strftime('%Y-%m-%d %H:%M'),
                        'name': tags.get('Name', 'unnamed'),
                        'state': instance['State']['Name']
                    })

        if recent_instances:
            findings.append({
                'cause': 'New instances launched in last 7 days',
                'detail': recent_instances,
                'confidence': 'HIGH'
            })

        # Check for instance type distribution
        all_instances = []
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] == 'running':
                    all_instances.append(instance['InstanceType'])

        if all_instances:
            from collections import Counter
            type_counts = Counter(all_instances)
            findings.append({
                'cause': 'Current running instance distribution',
                'detail': dict(type_counts),
                'confidence': 'INFO'
            })

    except Exception as e:
        findings.append({
            'cause': 'Could not investigate EC2',
            'detail': str(e),
            'confidence': 'ERROR'
        })

    return findings


def investigate_storage_spike(service, current_amount, historical_avg):
    findings = []

    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)

        # Check for unattached volumes
        volumes = ec2.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )

        orphan_volumes = []
        for vol in volumes['Volumes']:
            tags = {t['Key']: t['Value'] for t in vol.get('Tags', [])}
            orphan_volumes.append({
                'id': vol['VolumeId'],
                'size_gb': vol['Size'],
                'type': vol['VolumeType'],
                'created': vol['CreateTime'].strftime('%Y-%m-%d'),
                'name': tags.get('Name', 'unnamed'),
                'monthly_cost': round(vol['Size'] * 0.10, 2)
            })

        if orphan_volumes:
            total_orphan_cost = sum(v['monthly_cost'] for v in orphan_volumes)
            findings.append({
                'cause': f'Orphan EBS volumes found ({len(orphan_volumes)} unattached)',
                'detail': orphan_volumes,
                'confidence': 'HIGH',
                'monthly_waste': total_orphan_cost
            })

        # Check for snapshots older than 30 days
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])
        old_snapshots = []
        cutoff = datetime.now() - timedelta(days=30)

        for snap in snapshots['Snapshots']:
            start_time = snap['StartTime'].replace(tzinfo=None)
            if start_time < cutoff:
                old_snapshots.append({
                    'id': snap['SnapshotId'],
                    'size_gb': snap['VolumeSize'],
                    'age_days': (datetime.now() - start_time).days,
                    'description': snap.get('Description', 'no description')[:50]
                })

        if old_snapshots:
            findings.append({
                'cause': f'Old snapshots accumulating ({len(old_snapshots)} older than 30 days)',
                'detail': old_snapshots[:5],
                'confidence': 'MEDIUM'
            })

    except Exception as e:
        findings.append({
            'cause': 'Could not investigate storage',
            'detail': str(e),
            'confidence': 'ERROR'
        })

    return findings


def investigate_network_spike(service, current_amount, historical_avg):
    findings = []

    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)

        # Check for NAT Gateways
        nat_gateways = ec2.describe_nat_gateways(
            Filters=[{'Name': 'state', 'Values': ['available']}]
        )

        if nat_gateways['NatGateways']:
            findings.append({
                'cause': f"{len(nat_gateways['NatGateways'])} NAT Gateway(s) running",
                'detail': [
                    {
                        'id': ng['NatGatewayId'],
                        'subnet': ng['SubnetId'],
                        'created': ng['CreateTime'].strftime('%Y-%m-%d')
                    }
                    for ng in nat_gateways['NatGateways']
                ],
                'confidence': 'HIGH',
                'note': 'NAT Gateways charge $0.045/hour plus $0.045/GB data processed'
            })

        # Check for Elastic IPs
        eips = ec2.describe_addresses()
        unassociated = [
            eip for eip in eips['Addresses']
            if 'AssociationId' not in eip
        ]

        if unassociated:
            findings.append({
                'cause': f'{len(unassociated)} unassociated Elastic IPs',
                'detail': [eip['PublicIp'] for eip in unassociated],
                'confidence': 'MEDIUM',
                'note': 'Unassociated EIPs cost $0.005/hour each'
            })

    except Exception as e:
        findings.append({
            'cause': 'Could not investigate network',
            'detail': str(e),
            'confidence': 'ERROR'
        })

    return findings


def investigate_ai_spike(service, current_amount, historical_avg):
    findings = []

    try:
        from token_intelligence import get_token_intelligence
        token_data = get_token_intelligence()

        if token_data['total_cost_mtd'] > 0:
            feature_breakdown = token_data['feature_breakdown']
            sorted_features = sorted(
                feature_breakdown.items(),
                key=lambda x: x[1]['total_cost'],
                reverse=True
            )

            findings.append({
                'cause': 'AI token usage breakdown by feature',
                'detail': {
                    feature: {
                        'calls': stats['calls'],
                        'tokens': stats['total_tokens'],
                        'cost': stats['total_cost']
                    }
                    for feature, stats in sorted_features[:5]
                },
                'confidence': 'HIGH'
            })

            findings.append({
                'cause': f"Projected monthly AI spend: ${token_data['projected_monthly_cost']}",
                'detail': f"Most expensive feature: {token_data['most_expensive_feature']}",
                'confidence': 'INFO'
            })

    except Exception as e:
        findings.append({
            'cause': 'Could not investigate AI costs',
            'detail': str(e),
            'confidence': 'ERROR'
        })

    return findings


def run_cost_rca(anomalies=None):
    from aws_costs import get_cost_anomalies, get_aws_costs

    if anomalies is None:
        anomalies = get_cost_anomalies()

    if not anomalies:
        # Run on current costs even without anomalies for on-demand RCA
        costs = get_aws_costs()
        anomalies = [
            {
                'service': service,
                'latest': amount,
                'average': amount,
                'increase_pct': 0
            }
            for service, amount in list(costs.items())[:3]
        ]

    rca_results = []

    for anomaly in anomalies:
        service = anomaly['service']
        current = anomaly['latest']
        avg = anomaly['average']
        increase_pct = anomaly['increase_pct']

        findings = []

        # Route to right investigator based on service type
        if any(keyword in service.lower() for keyword in
               ['ec2', 'compute', 'elastic']):
            findings = investigate_compute_spike(service, current, avg)

        elif any(keyword in service.lower() for keyword in
                 ['s3', 'ebs', 'storage', 'rds', 'backup']):
            findings = investigate_storage_spike(service, current, avg)

        elif any(keyword in service.lower() for keyword in
                 ['transfer', 'network', 'vpc', 'cloudfront']):
            findings = investigate_network_spike(service, current, avg)

        elif any(keyword in service.lower() for keyword in
                 ['bedrock', 'sagemaker', 'rekognition', 'comprehend']):
            findings = investigate_ai_spike(service, current, avg)

        else:
            # General investigation for other services
            findings = [{
                'cause': f'Unusual spend detected on {service}',
                'detail': f'Current: ${current} vs average: ${avg}',
                'confidence': 'MEDIUM'
            }]

        rca_results.append({
            'service': service,
            'current_spend': current,
            'historical_avg': avg,
            'increase_pct': increase_pct,
            'findings': findings
        })

    return rca_results


if __name__ == "__main__":
    import json
    print("\n=== Cost Spike RCA ===")
    results = run_cost_rca()

    for r in results:
        print(f"\nService: {r['service']}")
        print(f"Current: ${r['current_spend']} vs Avg: ${r['historical_avg']}")
        print(f"Increase: {r['increase_pct']}%")
        print("Findings:")
        for f in r['findings']:
            print(f"  [{f['confidence']}] {f['cause']}")