OpsBeacon v1.0 Release Notes
Nov 15, 2026 · @Prashant Vithlani
What is OpsBeacon
OpsBeacon is an AI-powered FinOps and InfraOps assistant that lives in Slack. It connects directly to your AWS environment — Cost Explorer, Security Hub, GuardDuty, CloudTrail, and more — and delivers cost intelligence, security analysis, FinOps scoring, and daily standups without leaving your workflow.
v1.0 marks the first stable, production-ready release. All core features are deployed, tested, and running on a live AWS EC2 instance with a persistent systemd service.
Core Features
Cost Intelligence
• AWS cost breakdown by service, account, and time period
• Anomaly detection with automated Slack alerts (every 6 hours)
• Weekly digest every Monday at 8am
• Rightsizing and savings recommendations
• Idle resource detection
• Reserved instance and savings plan expiry alerts
FinOps Scoring
• 10-dimension FinOps maturity scorecard (Cost Visibility, Tag Quality, Reservation Efficiency, Forecast Accuracy, Cost Anomalies, Waste Elimination, Security Economics, AI Efficiency, Savings Execution, Recommendation Closure)
• Score simulation: model the impact of closing specific gaps
• Savings Action Report (SAR) with approve, assign, snooze, and auto-fix workflows
Security and Compliance
• Security economics report with trade-off analysis
• GuardDuty and CloudTrail audit integration
• Tagging compliance and fix workflows
Daily Standup
• Automated standup posted every day at 8:45am
• Per-channel section configuration (cost, anomalies, FinOps score, security score, AI spend)
• Chart posted as thread reply
AI Economics
• AI project cost tracking and token efficiency analysis
• Root cause analysis for AI spend spikes
Advanced Commands
• Time Machine: what-if scenario modeling
• Decision Intelligence: trade-off analysis between options
• Deep Dive: resource-level cost investigation
• Executive Brief, Board Narrative, Cloud Economics Monthly Report
• CloudWatch metrics, S3, Lambda, EKS cost breakdowns
• Datadog usage and cost analysis
FinOps Score Monitoring
A new proactive alerting system tracks your FinOps score over time and notifies you when it drops.
Set an alert: @Beacon alert me if my FinOps score drops more than 5 points
Beacon records your current score as the baseline and checks daily at 9am. If the score drops by more than your threshold, it posts an alert in the same channel.
Cancel an alert: @Beacon cancel score alert
Score trend tracking — Beacon now records your FinOps score daily, enabling these queries:
• @Beacon how has my FinOps score changed this month?
• @Beacon show me my score trend for the last 90 days
• @Beacon what drove the score change this week?
The underlying history system is built to track any metric with a single record_metric() call. Additional metrics can be wired in future releases.
What's New in v1.0
Feature
Description
FinOps score drop alerts
Proactive Slack notification when score falls below threshold
Cancel score alert
Remove an active alert with a single command
Score history tracking
Daily score snapshots stored in SQLite
Score trend commands
3 new commands: monthly change, N-day trend, change driver
General metric history
Reusable infrastructure for tracking any metric over time
AI economics fix
Corrected get_ai_economics_data to get_ai_economics_summary in daily standup
Standup section config
Per-channel control over which sections appear in the daily standup
SAR workflows
Full savings action lifecycle: approve, assign, generate fix, explain, snooze
Known Limitations
• Score trend data: The score history commands return "not enough history" until daily snapshots accumulate. Resolves on its own within a few days.
• PagerDuty integration: Incident alerts return 401 errors due to an expired API key. Non-functional until a new key is configured.
• Dynamic standup scheduling: The schedule_standup command saves to the database but does not yet register a live APScheduler job. Standups run on the hardcoded 8:45am schedule only.
• Teams bot disabled: opsbeacon-teams.service is disabled to prevent duplicate Slack messages.
• Cost footer: The confidence score footer appears in some responses outside of the daily standup.
What's Next
• Wire dynamic standup scheduling to APScheduler
• Add security score to daily metric recording for trend tracking
• Fix PagerDuty API key to restore incident alerts
• Remove confidence score footer from non-standup responses
• Security findings in standup: surface highest severity finding by name
• Hunter.io sales agent: end-to-end test after account upgrade
• Python 3.9 to 3.10+ upgrade
