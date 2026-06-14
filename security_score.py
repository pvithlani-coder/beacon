import boto3
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = 'us-east-2'

# Proprietary weights - never expose these to customers
DIMENSION_WEIGHTS = {
    'coverage': 0.20,
    'tool_efficiency': 0.15,
    'detection_quality': 0.20,
    'asset_hygiene': 0.15,
    'logging_economy': 0.10,
    'compliance_health': 0.10,
    'governance': 0.10
}

# Industry benchmarks by company size
INDUSTRY_BENCHMARKS = {
    'startup': 58,
    'mid_market': 67,
    'enterprise': 74
}


def calculate_coverage_score():
    score = 100
    findings = []

    try:
        # GuardDuty
        gd = boto3.client('guardduty', region_name=AWS_REGION)
        detectors = gd.list_detectors()
        if not detectors['DetectorIds']:
            score -= 25
            findings.append({
                'dimension': 'coverage',
                'impact': -25,
                'issue': 'GuardDuty not enabled',
                'fix': 'Enable GuardDuty for threat detection',
                'monthly_cost': 2.00
            })
        else:
            detector = gd.get_detector(
                DetectorId=detectors['DetectorIds'][0])
            if detector['Status'] == 'DISABLED':
                score -= 25
                findings.append({
                    'dimension': 'coverage',
                    'impact': -25,
                    'issue': 'GuardDuty disabled',
                    'fix': 'Re-enable GuardDuty',
                    'monthly_cost': 2.00
                })

        # Security Hub
        try:
            sh = boto3.client('securityhub', region_name=AWS_REGION)
            sh.describe_hub()
        except Exception:
            score -= 20
            findings.append({
                'dimension': 'coverage',
                'impact': -20,
                'issue': 'Security Hub not enabled',
                'fix': 'Enable Security Hub for unified findings',
                'monthly_cost': 4.00
            })

        # CloudTrail
        ct = boto3.client('cloudtrail', region_name=AWS_REGION)
        trails = ct.describe_trails()
        active_trails = [
            t for t in trails['trailList']
            if t.get('HomeRegion') == AWS_REGION
            or t.get('IsMultiRegionTrail')
        ]
        if not active_trails:
            score -= 30
            findings.append({
                'dimension': 'coverage',
                'impact': -30,
                'issue': 'CloudTrail not configured',
                'fix': 'Enable CloudTrail for API audit logging',
                'monthly_cost': 2.00
            })
        else:
            status = ct.get_trail_status(
                Name=active_trails[0]['TrailARN'])
            if not status.get('IsLogging'):
                score -= 20
                findings.append({
                    'dimension': 'coverage',
                    'impact': -20,
                    'issue': 'CloudTrail exists but not logging',
                    'fix': 'Resume CloudTrail logging',
                    'monthly_cost': 2.00
                })

    except Exception as e:
        print(f"Coverage score error: {e}")

    return max(0, score), findings


def calculate_asset_hygiene_score():
    score = 100
    findings = []

    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)
        rds = boto3.client('rds', region_name=AWS_REGION)

        # Check EC2 tagging
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name',
                      'Values': ['running']}]
        )

        total_instances = 0
        untagged_instances = 0

        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                total_instances += 1
                tags = {t['Key']: t['Value']
                        for t in instance.get('Tags', [])}
                required = ['Name', 'Environment', 'Owner']
                if not all(t in tags for t in required):
                    untagged_instances += 1

        if total_instances > 0:
            tag_pct = ((total_instances - untagged_instances)
                       / total_instances) * 100
            if tag_pct < 100:
                penalty = int((100 - tag_pct) * 0.3)
                score -= penalty
                findings.append({
                    'dimension': 'asset_hygiene',
                    'impact': -penalty,
                    'issue': f'{untagged_instances} of {total_instances} EC2 instances missing required tags',
                    'fix': 'Run @Beacon fix tags to remediate',
                    'monthly_cost': 0
                })

        # Check for orphan volumes
        volumes = ec2.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )
        orphan_count = len(volumes['Volumes'])
        if orphan_count > 0:
            penalty = min(20, orphan_count * 5)
            score -= penalty
            findings.append({
                'dimension': 'asset_hygiene',
                'impact': -penalty,
                'issue': f'{orphan_count} orphan EBS volumes detected',
                'fix': 'Run @Beacon find idle resources to clean up',
                'monthly_cost': sum(
                    v['Size'] * 0.10 for v in volumes['Volumes'])
            })

        # Check old snapshots
        snapshots = ec2.describe_snapshots(OwnerIds=['self'])
        old_snaps = [
            s for s in snapshots['Snapshots']
            if (datetime.utcnow() -
                s['StartTime'].replace(tzinfo=None)).days > 30
        ]
        if old_snaps:
            penalty = min(15, len(old_snaps) * 3)
            score -= penalty
            findings.append({
                'dimension': 'asset_hygiene',
                'impact': -penalty,
                'issue': f'{len(old_snaps)} snapshots older than 30 days',
                'fix': 'Run @Beacon generate terraform to clean up',
                'monthly_cost': sum(
                    s['VolumeSize'] * 0.05 for s in old_snaps)
            })

    except Exception as e:
        print(f"Asset hygiene score error: {e}")

    return max(0, score), findings


def calculate_governance_score():
    score = 100
    findings = []

    try:
        # AWS Config
        config = boto3.client('config', region_name=AWS_REGION)
        recorders = config.describe_configuration_recorders()

        if not recorders['ConfigurationRecorders']:
            score -= 30
            findings.append({
                'dimension': 'governance',
                'impact': -30,
                'issue': 'AWS Config not enabled',
                'fix': 'Enable AWS Config for compliance tracking',
                'monthly_cost': 3.00
            })
        else:
            status = config.describe_configuration_recorder_status()
            if not status['ConfigurationRecordersStatus'][0].get(
                    'recording', False):
                score -= 20
                findings.append({
                    'dimension': 'governance',
                    'impact': -20,
                    'issue': 'AWS Config exists but not recording',
                    'fix': 'Resume AWS Config recording',
                    'monthly_cost': 3.00
                })

        # Check for untagged accounts
        try:
            org = boto3.client('organizations', region_name='us-east-1')
            accounts = org.list_accounts()['Accounts']
            for account in accounts:
                tags = org.list_tags_for_resource(
                    ResourceId=account['Id'])['Tags']
                tag_keys = [t['Key'] for t in tags]
                missing = [
                    t for t in ['Owner', 'Environment', 'CostCenter']
                    if t not in tag_keys
                ]
                if missing:
                    score -= 15
                    findings.append({
                        'dimension': 'governance',
                        'impact': -15,
                        'issue': f'Account {account["Name"]} missing governance tags: {missing}',
                        'fix': 'Run @Beacon fix tags to remediate',
                        'monthly_cost': 0
                    })
        except Exception:
            pass

    except Exception as e:
        print(f"Governance score error: {e}")

    return max(0, score), findings


def calculate_logging_economy_score():
    score = 100
    findings = []

    try:
        ce = boto3.client('ce', region_name=AWS_REGION)
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

        response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        costs = {}
        for group in response['ResultsByTime'][0]['Groups']:
            service = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            costs[service] = amount

        # Check CloudWatch costs
        cw_cost = costs.get('Amazon CloudWatch', 0)
        total_cost = sum(costs.values())

        if total_cost > 0:
            cw_pct = (cw_cost / total_cost) * 100
            if cw_pct > 20:
                penalty = int(cw_pct - 20)
                score -= penalty
                findings.append({
                    'dimension': 'logging_economy',
                    'impact': -penalty,
                    'issue': f'CloudWatch is {cw_pct:.1f}% of total spend - likely over-logging',
                    'fix': 'Review log retention policies and reduce verbose logging',
                    'monthly_cost': cw_cost
                })

        # Check Cost Explorer costs
        ce_cost = costs.get('AWS Cost Explorer', 0)
        if ce_cost > 5:
            score -= 10
            findings.append({
                'dimension': 'logging_economy',
                'impact': -10,
                'issue': f'Cost Explorer API costs ${ce_cost:.2f}/mo - optimize API call frequency',
                'fix': 'Cache Cost Explorer results instead of calling API repeatedly',
                'monthly_cost': ce_cost
            })

    except Exception as e:
        print(f"Logging economy score error: {e}")

    return max(0, score), findings


def calculate_detection_quality_score():
    score = 100
    findings = []

    try:
        gd = boto3.client('guardduty', region_name=AWS_REGION)
        detectors = gd.list_detectors()

        if not detectors['DetectorIds']:
            score -= 40
            findings.append({
                'dimension': 'detection_quality',
                'impact': -40,
                'issue': 'No active threat detection',
                'fix': 'Enable GuardDuty for ML-based threat detection',
                'monthly_cost': 2.00
            })
        else:
            detector_id = detectors['DetectorIds'][0]
            findings_response = gd.list_findings(
                DetectorId=detector_id,
                FindingCriteria={
                    'Criterion': {
                        'severity': {
                            'Gte': 7
                        }
                    }
                }
            )

            high_severity = len(findings_response['FindingIds'])
            if high_severity > 0:
                penalty = min(30, high_severity * 10)
                score -= penalty
                findings.append({
                    'dimension': 'detection_quality',
                    'impact': -penalty,
                    'issue': f'{high_severity} high severity GuardDuty findings unresolved',
                    'fix': 'Review and resolve GuardDuty findings immediately',
                    'monthly_cost': 0
                })

    except Exception as e:
        print(f"Detection quality score error: {e}")

    return max(0, score), findings


def calculate_compliance_health_score():
    score = 100
    findings = []

    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)

        # Check for public S3 buckets
        s3 = boto3.client('s3')
        buckets = s3.list_buckets()
        public_buckets = []

        for bucket in buckets['Buckets']:
            try:
                acl = s3.get_bucket_acl(Bucket=bucket['Name'])
                for grant in acl['Grants']:
                    grantee = grant.get('Grantee', {})
                    if grantee.get('URI') == \
                            'http://acs.amazonaws.com/groups/global/AllUsers':
                        public_buckets.append(bucket['Name'])
            except Exception:
                pass

        if public_buckets:
            penalty = min(40, len(public_buckets) * 20)
            score -= penalty
            findings.append({
                'dimension': 'compliance_health',
                'impact': -penalty,
                'issue': f'{len(public_buckets)} public S3 buckets detected',
                'fix': 'Restrict public access on S3 buckets immediately',
                'monthly_cost': 0
            })

        # Check for instances in non-standard regions
        instances = ec2.describe_instances(
            Filters=[{'Name': 'instance-state-name',
                      'Values': ['running']}]
        )
        total = sum(
            len(r['Instances'])
            for r in instances['Reservations']
        )

        if total == 0:
            findings.append({
                'dimension': 'compliance_health',
                'impact': 0,
                'issue': 'No running instances to evaluate',
                'fix': 'N/A',
                'monthly_cost': 0
            })

    except Exception as e:
        print(f"Compliance health score error: {e}")

    return max(0, score), findings


def calculate_tool_efficiency_score():
    score = 100
    findings = []

    try:
        ce = boto3.client('ce', region_name=AWS_REGION)
        end = datetime.today().strftime('%Y-%m-%d')
        start = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')

        response = ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )

        total_spend = sum(
            float(g['Metrics']['UnblendedCost']['Amount'])
            for g in response['ResultsByTime'][0]['Groups']
        )

        security_spend = 0
        for group in response['ResultsByTime'][0]['Groups']:
            service = group['Keys'][0]
            amount = float(group['Metrics']['UnblendedCost']['Amount'])
            if any(s in service for s in
                   ['GuardDuty', 'Security Hub', 'Config',
                    'CloudTrail', 'Shield']):
                security_spend += amount

        if total_spend > 0:
            security_ratio = (security_spend / total_spend) * 100
            if security_ratio < 2:
                score -= 20
                findings.append({
                    'dimension': 'tool_efficiency',
                    'impact': -20,
                    'issue': f'Security spend is only {security_ratio:.1f}% of total cloud spend - likely under-invested',
                    'fix': 'Enable core security services to reach recommended 5-8% of cloud spend',
                    'monthly_cost': 0
                })

    except Exception as e:
        print(f"Tool efficiency score error: {e}")

    return max(0, score), findings


def calculate_security_cost_score(company_size='mid_market'):
    print("Calculating OpsBeacon Security Cost Score...")

    coverage, coverage_findings = calculate_coverage_score()
    print(f"  Coverage: {coverage}")

    asset_hygiene, hygiene_findings = calculate_asset_hygiene_score()
    print(f"  Asset Hygiene: {asset_hygiene}")

    governance, governance_findings = calculate_governance_score()
    print(f"  Governance: {governance}")

    logging_economy, logging_findings = calculate_logging_economy_score()
    print(f"  Logging Economy: {logging_economy}")

    detection_quality, detection_findings = calculate_detection_quality_score()
    print(f"  Detection Quality: {detection_quality}")

    compliance_health, compliance_findings = calculate_compliance_health_score()
    print(f"  Compliance Health: {compliance_health}")

    tool_efficiency, efficiency_findings = calculate_tool_efficiency_score()
    print(f"  Tool Efficiency: {tool_efficiency}")

    # Calculate weighted overall score
    overall = int(
        coverage * DIMENSION_WEIGHTS['coverage'] +
        tool_efficiency * DIMENSION_WEIGHTS['tool_efficiency'] +
        detection_quality * DIMENSION_WEIGHTS['detection_quality'] +
        asset_hygiene * DIMENSION_WEIGHTS['asset_hygiene'] +
        logging_economy * DIMENSION_WEIGHTS['logging_economy'] +
        compliance_health * DIMENSION_WEIGHTS['compliance_health'] +
        governance * DIMENSION_WEIGHTS['governance']
    )

    # Collect all findings
    all_findings = (
        coverage_findings + hygiene_findings +
        governance_findings + logging_findings +
        detection_findings + compliance_findings +
        efficiency_findings
    )

    # Filter out zero impact findings
    actionable = [f for f in all_findings if f['impact'] < 0]
    actionable.sort(key=lambda x: x['impact'])

    # Calculate risk exposure
    monthly_risk = sum(
        f['monthly_cost'] for f in actionable
        if f['monthly_cost'] > 0
    )

    # Determine risk level
    if overall >= 80:
        risk_level = 'LOW'
        risk_emoji = 'GREEN'
    elif overall >= 60:
        risk_level = 'MODERATE'
        risk_emoji = 'YELLOW'
    elif overall >= 40:
        risk_level = 'HIGH'
        risk_emoji = 'ORANGE'
    else:
        risk_level = 'CRITICAL'
        risk_emoji = 'RED'

    benchmark = INDUSTRY_BENCHMARKS.get(company_size, 67)
    vs_benchmark = overall - benchmark

    dimensions = {
        'Coverage': coverage,
        'Tool Efficiency': tool_efficiency,
        'Detection Quality': detection_quality,
        'Asset Hygiene': asset_hygiene,
        'Logging Economy': logging_economy,
        'Compliance Health': compliance_health,
        'Governance': governance
    }

    return {
        'overall_score': overall,
        'risk_level': risk_level,
        'risk_emoji': risk_emoji,
        'dimensions': dimensions,
        'actionable_findings': actionable[:5],
        'monthly_risk_exposure': round(monthly_risk, 2),
        'benchmark': benchmark,
        'vs_benchmark': vs_benchmark,
        'company_size': company_size,
        'calculated_at': datetime.now().strftime('%Y-%m-%d %H:%M')
    }


def format_score_for_slack(score_data):
    overall = score_data['overall_score']
    risk = score_data['risk_level']
    benchmark = score_data['benchmark']
    vs_benchmark = score_data['vs_benchmark']
    vs_sign = "+" if vs_benchmark >= 0 else ""

    # Score bar
    filled = int(overall / 10)
    empty = 10 - filled
    bar = "█" * filled + "░" * empty

    # Dimension lines
    dim_lines = "\n".join([
        f"  {name:<20} {score:>3}/100"
        for name, score in score_data['dimensions'].items()
    ])

    # Top findings
    finding_lines = "\n".join([
        f"  {f['issue'][:60]} ({f['impact']} pts)"
        for f in score_data['actionable_findings'][:3]
    ])

    # Top actions
    action_lines = "\n".join([
        f"  {i+1}. {f['fix']}"
        for i, f in enumerate(score_data['actionable_findings'][:3])
    ])

    message = f"""*OpsBeacon Security Cost Score*
━━━━━━━━━━━━━━━━━━━━

*Overall Score: {overall}/100*
{bar}

*Risk Level:* {risk}
*vs Industry Benchmark:* {vs_sign}{vs_benchmark} pts (benchmark: {benchmark})
*Monthly Risk Exposure:* ${score_data['monthly_risk_exposure']}

*Dimension Breakdown:*
{dim_lines}

*Top Score Drivers:*
{finding_lines}

*Recommended Actions:*
{action_lines}

_Calculated: {score_data['calculated_at']} | Powered by OpsBeacon_"""

    return message


if __name__ == "__main__":
    print("\n=== OpsBeacon Security Cost Score ===")
    score_data = calculate_security_cost_score()
    print(f"\nOverall Score: {score_data['overall_score']}/100")
    print(f"Risk Level: {score_data['risk_level']}")
    print(f"vs Benchmark: {score_data['vs_benchmark']:+d} pts")
    print(f"\nDimension Scores:")
    for dim, score in score_data['dimensions'].items():
        print(f"  {dim}: {score}/100")
    print(f"\nTop Findings:")
    for f in score_data['actionable_findings'][:3]:
        print(f"  [{f['impact']} pts] {f['issue']}")
    print(f"\nFormatted Slack Output:")
    print(format_score_for_slack(score_data))