import urllib.request
import urllib.parse
import json
import os
from dotenv import load_dotenv

load_dotenv()

app_id = os.environ.get('MICROSOFT_APP_ID', '')
app_password = os.environ.get('MICROSOFT_APP_PASSWORD', '')

print(f"App ID: {app_id[:8]}...")
print(f"Password length: {len(app_password)}")

token_url = "https://login.microsoftonline.com/bb28152a-7e28-4793-9c7b-e903e87048ec/oauth2/v2.0/token"
token_data = urllib.parse.urlencode({
    "grant_type": "client_credentials",
    "client_id": app_id,
    "client_secret": app_password,
    "scope": "https://api.botframework.com/.default"
}).encode()

token_req = urllib.request.Request(token_url, data=token_data, method="POST")
token_req.add_header("Content-Type", "application/x-www-form-urlencoded")

try:
    with urllib.request.urlopen(token_req) as resp:
        result = json.loads(resp.read())
        print("Token obtained successfully")
        print(f"Token type: {result.get('token_type')}")
        print(f"Expires in: {result.get('expires_in')} seconds")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"Error {e.code}: {body}")