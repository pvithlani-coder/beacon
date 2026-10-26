# OpsBeacon — Project Context

Read this at the start of every session to restore working memory.

---

## What This Is
OpsBeacon is an AI FinOps Slack bot. Connects to AWS Cost Explorer, Security Hub, and other services to deliver cost intelligence, security analysis, FinOps scoring, and daily standups via Slack.

---

## Infrastructure
- Server: EC2, Amazon Linux, /home/ec2-user/costbot/
- Python: 3.9, venv at /home/ec2-user/costbot/venv/
- Service: sudo systemctl restart opsbeacon
- Teams service: opsbeacon-teams.service — DISABLED (shares Slack token, causes duplicates)
- Slack mode: Socket Mode (SLACK_APP_TOKEN)
- Scheduler: APScheduler BackgroundScheduler

---

## Key Files
- app.py — main bot, all intent handling
- teams_app.py — Teams bot, keep disabled
- aws_costs.py — AWS Cost Explorer queries
- security_score.py — security scoring
- ai_economics.py — AI spend analysis
- chart_generator.py — cost trend and radar charts
- standup_config.db — per-channel standup section config
- seen_prospects.db — Hunter.io prospect dedup

---

## Standup Section Config
Table: standup_schedules in standup_config.db
Default sections: cost,anomalies,finops_score,security_score
Valid keys: cost, anomalies, finops_score, security_score, ai_spend

---

## Pending Work
- get_ai_economics_data() — verify exists in ai_economics.py
- PagerDuty API key *qpMQ — 401, needs renewal
- Confidence score in standup — decide keep or remove
- Dynamic APScheduler wiring for schedule_standup handler
- Hunter.io upgrade — test sales agent after upgrade
- Security findings should name highest severity, not just count

---

## Docs Site
- Live: https://ops-beacon.mintlify.site
- Custom domain: https://docs.opsbeacon.co
- Config: docs.json (Mintlify v2)

---

## Session Start Checklist
1. Read CONTEXT.md and CHANGELOG.md
2. sudo systemctl status opsbeacon
3. sudo journalctl -u opsbeacon -n 20 --no-pager
