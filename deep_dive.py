import boto3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aws_regions import get_regions

load_dotenv()

AWS_REGION = os.environ.get('AWS_DEFAULT_REGION', 'us-east-2')


def deep_dive_ec2(region=None):
    regions = [region] if region else get_regions()
    findings = []

    for r in regions:
        try:
            ec2 = boto3.client('ec2', region_name=r)
            ce = boto3.client('ce', region_name=AWS_REGION)

            instances = ec2.describe_instances(
                Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
            )

            for reservation in instances['Reservations']:
                for inst in reservation['Instances']:
                    instance_id = inst['InstanceId']
                    instance_type = inst['InstanceType']
                    launch_time = inst['LaunchTime']
                    days_running = (datetime.now(launch_time.tzinfo) - launch_time).days

                    tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                    name = tags.get('Name', instance_id)
                    owner = tags.get('Owner', tags.get('Team', tags.get('Environment', 'untagged')))
                    environment = tags.get('Environment', 'unknown')

                    # Get CPU metrics
                    cw = boto3.client('cloudwatch', region_name=r)
                    end = datetime.utcnow()
                    start = end - timedelta(days=7)

                    try:
                        cpu_response = cw.get_metric_statistics(
                            Namespace='AWS/EC2',
                            MetricName='CPUUtilization',
                            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                            StartTime=start,
                            EndTime=end,
                            Period=86400,
                            Statistics=['Average']
                        )
                        datapoints = cpu_response['Datapoints']
                        avg_cpu = round(
                            sum(d['Average'] for d in datapoints) / len(datapoints), 2
                        ) if datapoints else 0
                    except Exception:
                        avg_cpu = 0

                    # Estimate hourly cost
                    cost_map = {
                        't3.micro': 0.0104, 't3.small': 0.0208,
                        't3.medium': 0.0416, 't3.large': 0.0832,
                        't3.xlarge': 0.1664, 't3.2xlarge': 0.3328,
                        'm5.large': 0.096, 'm5.xlarge': 0.192,
                        'm5.2xlarge': 0.384, 'c5.large': 0.085,
                        'r5.large': 0.126
                    }
                    hourly_cost = cost_map.get(instance_type, 0.05)
                    monthly_cost = round(hourly_cost * 24 * 30, 2)

                    # Calculate confidence
                    confidence = 50
                    if avg_cpu < 5:
                        confidence += 30
                    if days_running > 30:
                        confidence += 10
                    if environment.lower() in ['dev', 'development', 'staging', 'test']:
                        confidence += 10
                    if owner == 'untagged':
                        confidence -= 10
                    confidence = min(95, max(40, confidence))

                    # Recommendation
                    if avg_cpu < 1:
                        recommendation = f"Stop immediately — CPU {avg_cpu}% indicates completely idle"
                        action = 'stop'
                    elif avg_cpu < 5:
                        recommendation = f"Right-size or stop — CPU {avg_cpu}% is well below threshold"
                        action = 'rightsize'
                    else:
                        recommendation = f"Monitor — CPU {avg_cpu}% is low but may have bursting patterns"
                        action = 'monitor'
                        confidence = max(40, confidence - 20)

                    findings.append({
                        'type': 'EC2',
                        'resource_id': instance_id,
                        'name': name,
                        'instance_type': instance_type,
                        'region': r,
                        'owner': owner,
                        'environment': environment,
                        'days_running': days_running,
                        'avg_cpu': avg_cpu,
                        'monthly_cost': monthly_cost,
                        'confidence': confidence,
                        'recommendation': recommendation,
                        'action': action,
                        'cli_command': f"aws ec2 stop-instances --instance-ids {instance_id} --region {r}",
                        'launch_time': launch_time.strftime('%Y-%m-%d')
                    })

        except Exception as e:
            print(f"EC2 deep dive error in {r}: {e}")

    findings.sort(key=lambda x: x['confidence'], reverse=True)
    return findings


def deep_dive_rds(region=None):
    regions = [region] if region else get_regions()
    findings = []

    for r in regions:
        try:
            rds = boto3.client('rds', region_name=r)
            instances = rds.describe_db_instances()

            for db in instances['DBInstances']:
                db_id = db['DBInstanceIdentifier']
                db_class = db['DBInstanceClass']
                engine = db['Engine']
                status = db['DBInstanceStatus']
                multi_az = db['MultiAZ']
                storage = db['AllocatedStorage']

                cost_map = {
                    'db.t3.micro': 0.017, 'db.t3.small': 0.034,
                    'db.t3.medium': 0.068, 'db.t3.large': 0.136,
                    'db.m5.large': 0.171, 'db.m5.xlarge': 0.342,
                    'db.r5.large': 0.24
                }
                hourly = cost_map.get(db_class, 0.10)
                if multi_az:
                    hourly *= 2
                monthly_cost = round(hourly * 24 * 30 + storage * 0.115, 2)

                confidence = 70
                tags_response = rds.list_tags_for_resource(
                    ResourceName=db['DBInstanceArn'])
                tags = {t['Key']: t['Value']
                        for t in tags_response.get('TagList', [])}
                environment = tags.get('Environment', 'unknown')

                if environment.lower() in ['dev', 'development', 'staging']:
                    confidence += 15
                    recommendation = f"Consider stopping during off-hours — dev/staging DB at ${monthly_cost}/mo"
                elif multi_az and monthly_cost < 100:
                    confidence += 10
                    recommendation = f"Review Multi-AZ need — small DB with Multi-AZ adds cost without clear benefit"
                else:
                    confidence = 55
                    recommendation = f"Review instance class — {db_class} at ${monthly_cost}/mo"

                findings.append({
                    'type': 'RDS',
                    'resource_id': db_id,
                    'db_class': db_class,
                    'engine': engine,
                    'region': r,
                    'environment': environment,
                    'multi_az': multi_az,
                    'storage_gb': storage,
                    'monthly_cost': monthly_cost,
                    'confidence': min(92, confidence),
                    'recommendation': recommendation,
                    'cli_command': f"aws rds stop-db-instance --db-instance-identifier {db_id} --region {r}",
                })

        except Exception as e:
            print(f"RDS deep dive error in {r}: {e}")

    findings.sort(key=lambda x: x['confidence'], reverse=True)
    return findings


def deep_dive_ai(project_name=None):
    from ai_economics import get_ai_economics_summary, get_project_detail

    findings = []
    data = get_ai_economics_summary()

    projects = data['projects_by_spend']
    if project_name:
        projects = [p for p in projects
                    if project_name.lower() in p['name'].lower()]

    for project in projects:
        efficiency = project['efficiency_score']
        monthly = project['monthly_spend']
        trend = project.get('spend_trend_pct', project.get('spend_trend', 0))

        confidence = 60
        recommendations = []

        if efficiency < 60:
            confidence += 25
            recommendations.append(
                f"Audit prompt structure — efficiency {efficiency}/100 "
                f"suggests significant waste")
        if trend > 20:
            confidence += 15
            recommendations.append(
                f"Investigate {trend:.0f}% cost increase — "
                f"check for prompt bloat or increased usage")
        if monthly > 500:
            confidence += 10
            recommendations.append(
                f"Evaluate model tier — ${monthly}/mo may justify "
                f"switching to a lower-cost model")

        if not recommendations:
            recommendations.append(
                f"Monitor — efficiency {efficiency}/100 is acceptable")
            confidence = 55

        findings.append({
            'type': 'AI Project',
            'resource_id': project['name'],
            'name': project['name'],
            'model': project.get('model', 'unknown'),
            'monthly_cost': monthly,
            'efficiency_score': efficiency,
            'spend_trend_pct': trend,
            'confidence': min(93, confidence),
            'recommendations': recommendations,
            'potential_savings': round(monthly * 0.35, 2)
        })

    findings.sort(key=lambda x: x['confidence'], reverse=True)
    return findings


def run_deep_dive(service=None):
    if not service:
        # Auto-detect highest anomaly
        from aws_costs import get_cost_anomalies
        anomalies = get_cost_anomalies()
        if anomalies:
            top = anomalies[0]
            service_name = top['service'].lower()
            if 'ec2' in service_name:
                service = 'ec2'
            elif 'rds' in service_name:
                service = 'rds'
            elif 'ai' in service_name or 'openai' in service_name:
                service = 'ai'
            else:
                service = 'ec2'
        else:
            service = 'ec2'

    service = service.lower()
    if 'ec2' in service or 'instance' in service or 'compute' in service:
        return 'EC2', deep_dive_ec2()
    elif 'rds' in service or 'database' in service or 'db' in service:
        return 'RDS', deep_dive_rds()
    elif 'ai' in service or 'token' in service or 'gpt' in service or 'legal' in service:
        return 'AI', deep_dive_ai(service if 'legal' in service or 'copilot' in service else None)
    else:
        return 'EC2', deep_dive_ec2()


def format_deep_dive_for_slack(service_name, findings, max_findings=3):
    if not findings:
        return (f"*Deep Dive: {service_name}*\n\n"
                f"No issues found. {service_name} resources look healthy.")

    total_savings = sum(f.get('monthly_cost', 0) for f in findings[:max_findings]
                        if f.get('action') in ['stop', 'rightsize', None])

    lines = [
        f"*Deep Dive: {service_name} Cost Investigation*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"*{min(len(findings), max_findings)} findings ranked by confidence*",
        f""
    ]

    for i, f in enumerate(findings[:max_findings]):
        confidence = f['confidence']
        if confidence >= 85:
            conf_emoji = '🟢'
        elif confidence >= 65:
            conf_emoji = '🟡'
        else:
            conf_emoji = '🔴'

        lines.append(
            f"*Finding {i+1}* — {conf_emoji} Confidence: {confidence}%")

        if f['type'] == 'EC2':
            lines.append(
                f"  `{f['resource_id']}` ({f['instance_type']}) "
                f"{f['region']}")
            lines.append(
                f"  Running {f['days_running']} days · "
                f"CPU {f['avg_cpu']}% · "
                f"Owner: {f['owner']}")
            lines.append(f"  Cost: ${f['monthly_cost']}/mo")
            lines.append(f"  → {f['recommendation']}")
            lines.append(f"  ```{f['cli_command']}```")

        elif f['type'] == 'RDS':
            lines.append(
                f"  `{f['resource_id']}` ({f['db_class']}) "
                f"{f['region']}")
            lines.append(
                f"  Engine: {f['engine']} · "
                f"Multi-AZ: {f['multi_az']} · "
                f"Storage: {f['storage_gb']}GB")
            lines.append(f"  Cost: ${f['monthly_cost']}/mo")
            lines.append(f"  → {f['recommendation']}")
            lines.append(f"  ```{f['cli_command']}```")

        elif f['type'] == 'AI Project':
            lines.append(
                f"  `{f['name']}` — "
                f"Efficiency: {f['efficiency_score']}/100 · "
                f"Trend: +{f['spend_trend_pct']:.0f}%")
            lines.append(f"  Cost: ${f['monthly_cost']}/mo")
            for rec in f['recommendations']:
                lines.append(f"  → {rec}")
            lines.append(
                f"  Potential savings: ${f['potential_savings']}/mo")

        lines.append("")

    lines.append(
        f"*Total potential savings: "
        f"${round(total_savings, 2)}/mo "
        f"(${round(total_savings * 12, 2)}/yr)*")
    lines.append(
        f"*Highest confidence action:* "
        f"{findings[0].get('recommendation', findings[0].get('recommendations', ['Review'])[0])}")
    lines.append(f"")
    lines.append(f"_Powered by OpsBeacon Deep Dive Intelligence_")

    return "\n".join(lines)


if __name__ == "__main__":
    print("\n=== Deep Dive Test ===")

    print("\nEC2 Deep Dive:")
    findings = deep_dive_ec2()
    if findings:
        print(f"Found {len(findings)} EC2 findings")
        for f in findings[:2]:
            print(f"  {f['resource_id']}: CPU {f['avg_cpu']}% "
                  f"confidence {f['confidence']}%")
    else:
        print("No EC2 findings")

    print("\nRDS Deep Dive:")
    findings = deep_dive_rds()
    if findings:
        print(f"Found {len(findings)} RDS findings")
        for f in findings[:2]:
            print(f"  {f['resource_id']}: ${f['monthly_cost']}/mo "
                  f"confidence {f['confidence']}%")
    else:
        print("No RDS findings")

    print("\nAI Deep Dive:")
    findings = deep_dive_ai()
    if findings:
        print(f"Found {len(findings)} AI findings")
        for f in findings[:2]:
            print(f"  {f['name']}: efficiency {f['efficiency_score']} "
                  f"confidence {f['confidence']}%")
    else:
        print("No AI findings")