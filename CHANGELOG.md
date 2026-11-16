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

---

## 2026-11-15

### Slack Bot — FinOps Score Drop Alerts
- Added `score_alert` intent to classify_intent()
- Added `init_score_alerts_db()`, `get_score_alert()`, `save_score_alert()`, `update_last_score()`, `check_score_drop_alerts()` functions
- Added `score_alerts` table to standup_config.db
- Handler parses threshold from message ("more than 5 points"), defaults to 5.0
- Seeds last_score with current score on setup so baseline is established immediately
- Scheduler job runs daily at 9:00am, compares current vs last known score, posts alert if drop exceeds threshold
- Added IMPORTANT rule to classifier: "alert/notify/warn" + "score/FinOps" + "drop/fall" → always score_alert
- Fixed: threshold regex now matches "X points" pattern correctly

### Pending
- [ ] `cancel score alert` command not yet implemented
- [ ] FinOps score history commands (`how has my score changed`, `show score trend`) — not yet built, docs should not reference them until implemented
