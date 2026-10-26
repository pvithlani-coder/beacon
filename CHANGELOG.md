# OpsBeacon Changelog

---

## 2026-10-25

### Mintlify Docs Site (docs.opsbeacon.co)
- Fixed docs.json navigation schema to Mintlify v2 object format
- Fixed theme from "mint" to "maple"
- Created placeholder SVG logo/favicon files
- Docs site live at https://ops-beacon.mintlify.site

### Main Site (opsbeacon.co)
- Added Docs nav link and footer link pointing to https://docs.opsbeacon.co

### Slack Bot — Intent Routing Fixes
- Added schedule_standup and configure_standup intents to classify_intent()
- Fixed: scheduling commands no longer misrouted as standup triggers
- Fixed: add/remove section commands now route to configure_standup

### Slack Bot — Standup Section Configuration
- Added standup_config.db (SQLite) for per-channel section config
- Added init_standup_config_db(), get_standup_config(), save_standup_config(), update_standup_sections()
- Added schedule_standup and configure_standup handlers

### Slack Bot — send_daily_standup() Overhaul
- Reads per-channel sections config from standup_config.db
- Conditionally includes AI spend section if configured
- Calls Claude and posts via app.client.chat_postMessage, returns ts
- show_cost=False hides token cost footer from users

### Slack Bot — Chart Threading
- upload_chart_to_slack() now accepts thread_ts parameter
- Cost trend chart threads as reply under standup message
- Added process_before_response=True to App init
- Added thread-safe dedup and per-channel 30s rate limit for standup

### Known Issues
- PagerDuty 401 errors on check_and_alert_incidents — API key needs renewal
- get_ai_economics_data() needs verification it exists in ai_economics.py
- opsbeacon-teams.service disabled to prevent Slack duplicates
- Scheduled standup via schedule_standup not yet wired to APScheduler
