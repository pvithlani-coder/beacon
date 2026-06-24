import os
from dotenv import load_dotenv

load_dotenv()

def get_regions():
    regions_str = os.environ.get('AWS_REGIONS', 'us-east-1')
    regions = [r.strip() for r in regions_str.split(',')]
    return regions

def get_primary_region():
    regions = get_regions()
    return regions[0] if regions else 'us-east-1'

def get_all_regions_boto3(service):
    import boto3
    try:
        ec2 = boto3.client('ec2', region_name='us-east-1')
        response = ec2.describe_regions(AllRegions=False)
        return [r['RegionName'] for r in response['Regions']]
    except Exception as e:
        print(f"Could not fetch regions: {e}")
        return get_regions()