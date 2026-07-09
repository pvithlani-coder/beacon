import asyncio
import os
from aiohttp import web
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from teams_bot import OpsBeaconTeamsBot
from dotenv import load_dotenv

load_dotenv()

SETTINGS = BotFrameworkAdapterSettings(
    app_id=os.environ.get('MICROSOFT_APP_ID', ''),
    app_password=os.environ.get('MICROSOFT_APP_PASSWORD', '')
)

ADAPTER = BotFrameworkAdapter(SETTINGS)
BOT = OpsBeaconTeamsBot()


async def messages(req: web.Request) -> web.Response:
    if 'application/json' in req.headers.get('Content-Type', ''):
        body = await req.json()
    else:
        return web.Response(status=415)

    activity = Activity().deserialize(body)
    auth_header = req.headers.get('Authorization', '')

    response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    if response:
        return web.json_response(data=response.body, status=response.status)
    return web.Response(status=201)


APP = web.Application()
APP.router.add_post('/api/messages', messages)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3978))
    print(f"OpsBeacon Teams bot starting on port {port}")
    print(f"Endpoint: http://localhost:{port}/api/messages")
    web.run_app(APP, host='0.0.0.0', port=port)