import boto3
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from aws_regions import get_regions

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def get_eks_clusters():
    regions = get_regions()
    all_clusters = []

    for region in regions:
        try:
            eks = boto3.client('eks', region_name=region)
            ec2 = boto3.client('ec2', region_name=region)

            response = eks.list_clusters()
            cluster_names = response.get('clusters', [])

            for cluster_name in cluster_names:
                try:
                    cluster = eks.describe_cluster(name=cluster_name)['cluster']
                    status = cluster.get('status', 'unknown')
                    version = cluster.get('version', 'unknown')
                    created = cluster.get('createdAt')

                    # Get node groups
                    ng_response = eks.list_nodegroups(clusterName=cluster_name)
                    nodegroups = []
                    total_nodes = 0
                    total_estimated_cost = 0

                    for ng_name in ng_response.get('nodegroups', []):
                        try:
                            ng = eks.describe_nodegroup(
                                clusterName=cluster_name,
                                nodegroupName=ng_name
                            )['nodegroup']

                            instance_type = ng.get('instanceTypes', ['unknown'])[0]
                            desired = ng.get('scalingConfig', {}).get('desiredSize', 0)
                            min_size = ng.get('scalingConfig', {}).get('minSize', 0)
                            max_size = ng.get('scalingConfig', {}).get('maxSize', 0)
                            disk_size = ng.get('diskSize', 20)

                            cost_map = {
                                't3.micro': 0.0104, 't3.small': 0.0208,
                                't3.medium': 0.0416, 't3.large': 0.0832,
                                't3.xlarge': 0.1664, 't3.2xlarge': 0.3328,
                                'm5.large': 0.096, 'm5.xlarge': 0.192,
                                'm5.2xlarge': 0.384, 'm5.4xlarge': 0.768,
                                'c5.large': 0.085, 'c5.xlarge': 0.17,
                                'r5.large': 0.126, 'r5.xlarge': 0.252,
                            }
                            hourly = cost_map.get(instance_type, 0.10)
                            monthly_cost = round(hourly * 24 * 30 * desired, 2)
                            total_estimated_cost += monthly_cost
                            total_nodes += desired

                            nodegroups.append({
                                'name': ng_name,
                                'instance_type': instance_type,
                                'desired': desired,
                                'min': min_size,
                                'max': max_size,
                                'disk_gb': disk_size,
                                'monthly_cost': monthly_cost,
                                'is_oversized': desired > min_size * 2 and desired > 2
                            })

                        except Exception:
                            continue

                    # EKS control plane cost: $0.10/hour = $72/month per cluster
                    control_plane_cost = 72.0
                    total_cost = round(total_estimated_cost + control_plane_cost, 2)

                    all_clusters.append({
                        'name': cluster_name,
                        'region': region,
                        'status': status,
                        'version': version,
                        'created': created.strftime('%Y-%m-%d') if created else 'unknown',
                        'total_nodes': total_nodes,
                        'nodegroups': nodegroups,
                        'control_plane_cost': control_plane_cost,
                        'node_cost': round(total_estimated_cost, 2),
                        'total_monthly_cost': total_cost,
                        'console_link': f"https://console.aws.amazon.com/eks/home?region={region}#/clusters/{cluster_name}"
                    })

                except Exception:
                    continue

        except Exception:
            continue

    return all_clusters


def get_eks_cost_summary():
    ce = boto3.client('ce', region_name=AWS_REGION)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=30)

    try:
        response = ce.get_cost_and_usage(
            TimePeriod={
                'Start': start.strftime('%Y-%m-%d'),
                'End': (end + timedelta(days=1)).strftime('%Y-%m-%d')
            },
            Granularity='MONTHLY',
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Elastic Kubernetes Service']
                }
            },
            Metrics=['UnblendedCost']
        )

        total = sum(
            float(r['Total']['UnblendedCost']['Amount'])
            for r in response['ResultsByTime']
        )

        return {'total_monthly_cost': round(total, 2)}

    except Exception as e:
        return {'total_monthly_cost': 0}


def get_eks_savings_opportunities(clusters):
    opportunities = []

    for cluster in clusters:
        for ng in cluster['nodegroups']:
            if ng['is_oversized']:
                savings = round(ng['monthly_cost'] * 0.3, 2)
                opportunities.append({
                    'cluster': cluster['name'],
                    'nodegroup': ng['name'],
                    'issue': f"Node group running {ng['desired']} nodes with min={ng['min']} — possibly oversized",
                    'potential_savings': savings,
                    'action': f"Review autoscaling — reduce desired to {ng['min']} during off-hours",
                    'console_link': cluster['console_link']
                })

        if cluster['total_nodes'] == 0:
            opportunities.append({
                'cluster': cluster['name'],
                'nodegroup': 'all',
                'issue': 'Cluster has no running nodes but control plane still active ($72/mo)',
                'potential_savings': 72.0,
                'action': 'Delete cluster if unused or scale up node groups',
                'console_link': cluster['console_link']
            })

    return opportunities


def format_eks_for_slack(data):
    clusters = data.get('clusters', [])
    opportunities = data.get('opportunities', [])
    cost_summary = data.get('cost_summary', {})

    total_cost = sum(c['total_monthly_cost'] for c in clusters)
    total_nodes = sum(c['total_nodes'] for c in clusters)

    lines = [
        '*OpsBeacon EKS/Kubernetes Intelligence*',
        '━━━━━━━━━━━━━━━━━━━━',
        '',
        f'*Total EKS Cost (estimated):* ${round(total_cost, 2)}/mo',
        f'*Total Clusters:* {len(clusters)}',
        f'*Total Nodes:* {total_nodes}',
        '',
    ]

    if clusters:
        for c in clusters:
            status_emoji = '✅' if c['status'] == 'ACTIVE' else '⚠️'
            lines.append(f'*{status_emoji} Cluster: `{c["name"]}`* ({c["region"]})')
            lines.append(f'  Version: {c["version"]} · Status: {c["status"]}')
            lines.append(f'  Nodes: {c["total_nodes"]} · Cost: ${c["total_monthly_cost"]}/mo')
            lines.append(f'  Control plane: ${c["control_plane_cost"]}/mo · Nodes: ${c["node_cost"]}/mo')

            if c['nodegroups']:
                lines.append('  *Node Groups:*')
                for ng in c['nodegroups']:
                    oversized = ' ⚠️ oversized' if ng['is_oversized'] else ''
                    lines.append(
                        f'    → `{ng["name"]}` {ng["instance_type"]} '
                        f'×{ng["desired"]} nodes · ${ng["monthly_cost"]}/mo{oversized}'
                    )
            lines.append(f'  <{c["console_link"]}|Open in EKS Console>')
            lines.append('')
    else:
        lines.append('*No EKS clusters found across all regions.*')
        lines.append('If you are running Kubernetes consider migrating to EKS for better cost visibility.')
        lines.append('')

    if opportunities:
        lines.append(f'*💡 Savings Opportunities: {len(opportunities)}*')
        for opp in opportunities[:3]:
            lines.append(f'  → {opp["issue"]}')
            lines.append(f'    Save ~${opp["potential_savings"]}/mo')
            lines.append(f'    <{opp["console_link"]}|Open in EKS Console>')
    else:
        lines.append('*Savings Opportunities:* None identified')

    lines.append('')
    lines.append(f'<https://console.aws.amazon.com/eks/home?region={AWS_REGION}#/clusters|View all clusters in EKS Console>')
    lines.append('_Powered by OpsBeacon EKS Intelligence_')
    return '\n'.join(lines)


if __name__ == '__main__':
    print('\n=== EKS Cost Summary ===')
    cost = get_eks_cost_summary()
    print(f"Total EKS cost: ${cost['total_monthly_cost']}")

    print('\n=== EKS Clusters ===')
    clusters = get_eks_clusters()
    print(f"Total clusters: {len(clusters)}")
    for c in clusters:
        print(f"  {c['name']} ({c['region']}): {c['total_nodes']} nodes ${c['total_monthly_cost']}/mo")
        for ng in c['nodegroups']:
            print(f"    {ng['name']}: {ng['instance_type']} x{ng['desired']} ${ng['monthly_cost']}/mo")

    print('\n=== Savings Opportunities ===')
    opps = get_eks_savings_opportunities(clusters)
    print(f"Opportunities: {len(opps)}")
    for o in opps:
        print(f"  {o['cluster']}/{o['nodegroup']}: {o['issue']}")