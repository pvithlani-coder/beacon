import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
import anthropic

load_dotenv()

claude = anthropic.Anthropic()


def get_meeting_data(meeting_type='mbr'):
    from aws_costs import get_aws_costs, get_cost_anomalies, get_savings_recommendations, get_forecast_recalculation
    from aws_compliance import get_security_cost_tradeoffs
    from actions_dashboard import get_actions_summary
    from timeline_replay import get_full_timeline
    from finops_score import calculate_finops_score
    from security_score import calculate_security_cost_score
    from idle_resources import get_all_idle_resources

    print(f"Gathering data for {meeting_type.upper()}...")

    costs = get_aws_costs()
    total_spend = sum(costs.values())
    top_services = list(costs.items())[:3]

    forecast = get_forecast_recalculation()
    anomalies = get_cost_anomalies()
    savings = get_savings_recommendations()
    security = get_security_cost_tradeoffs()
    actions = get_actions_summary()
    idle = get_all_idle_resources()

    if meeting_type in ['mbr', 'qbr']:
        finops = calculate_finops_score()
        sec_score = calculate_security_cost_score()
    else:
        finops = None
        sec_score = None

    days = 30 if meeting_type == 'mbr' else 90 if meeting_type == 'qbr' else 7
    timeline = get_full_timeline(days=days)

    return {
        'meeting_type': meeting_type.upper(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'period': f"Last {days} days",
        'total_spend': round(total_spend, 2),
        'top_services': top_services,
        'forecast': forecast,
        'anomalies': len(anomalies),
        'savings_monthly': savings['total_monthly_savings'],
        'savings_annual': savings['total_annual_savings'],
        'security_disabled': len(security['disabled_services']),
        'security_fix_cost': security['total_monthly_cost_to_fix'],
        'actions_open': actions['total_open'],
        'actions_overdue': actions['overdue_count'],
        'actions_completed': actions['total_completed'],
        'savings_realized': actions['savings_realized'],
        'savings_at_stake': actions['savings_at_stake'],
        'idle_waste': idle['total_monthly_waste'],
        'timeline_events': len(timeline),
        'finops_score': finops['overall_score'] if finops else None,
        'finops_grade': finops['grade'] if finops else None,
        'security_score': sec_score['overall_score'] if sec_score else None,
        'timeline': timeline[-10:] if timeline else []
    }


def generate_meeting_prep(meeting_type='mbr'):
    data = get_meeting_data(meeting_type)

    trend_text = ""
    if data['forecast']:
        trend = data['forecast']['trend_direction']
        pct = data['forecast']['trend_pct']
        sign = "+" if pct > 0 else ""
        trend_text = f"Trend: {trend} ({sign}{pct}% vs prior week)"

    timeline_text = "\n".join([
        f"- {e['timestamp'][:10]}: {e['title']} (impact: ${e['cost_impact']})"
        for e in data['timeline']
    ]) if data['timeline'] else "No major events recorded"

    scores_text = ""
    if data['finops_score']:
        scores_text = f"""
FinOps Score: {data['finops_score']}/100 Grade {data['finops_grade']}
Security Score: {data['security_score']}/100"""

    prompt = f"""You are preparing a {data['meeting_type']} (Monthly Business Review) for a FinOps and Infrastructure team.

Meeting Date: {data['date']}
Period: {data['period']}

FINANCIAL DATA:
Total cloud spend: ${data['total_spend']}
Top services: {', '.join([f"{s[0]}: ${s[1]}" for s in data['top_services']])}
{trend_text}
Month end forecast: ${data['forecast']['month_end_forecast'] if data['forecast'] else 'N/A'}
Annual forecast: ${data['forecast']['annual_forecast'] if data['forecast'] else 'N/A'}

OPTIMIZATION:
Monthly savings available: ${data['savings_monthly']}
Annual savings available: ${data['savings_annual']}
Savings realized this period: ${data['savings_realized']}
Savings still at stake: ${data['savings_at_stake']}
Idle resource waste: ${data['idle_waste']}/mo

RISK AND COMPLIANCE:
Active cost anomalies: {data['anomalies']}
Security services disabled: {data['security_disabled']}
Monthly cost to fix security gaps: ${data['security_fix_cost']}

ACTIONS:
Open actions: {data['actions_open']}
Overdue actions: {data['actions_overdue']}
Completed this period: {data['actions_completed']}
{scores_text}

KEY EVENTS THIS PERIOD:
{timeline_text}

Generate a complete {data['meeting_type']} preparation package with EXACTLY these four sections:

## EXECUTIVE SUMMARY
3-4 sentences. Plain business language. What happened, what it means, what decision is needed.

## TALKING POINTS
5-7 bullet points a presenter can read directly. Specific numbers. Business context not technical jargon.

## RISKS
3-5 risks ranked by business impact. Each with: what the risk is, dollar exposure, and recommended mitigation.

## ACTIONS REQUIRED
3-5 decisions or actions needed from meeting attendees. Each with owner suggestion and deadline.

## SLIDES OUTLINE
Section by section structure for a presentation deck:
Slide 1: Title
Slide 2-3: Financial Overview
Slide 4-5: Risks and Mitigation
Slide 6-7: Optimization Opportunities
Slide 8: Actions and Owners
Slide 9: Next Period Forecast

Keep the entire output professional, boardroom ready, and under 600 words total."""

    message = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return {
        'content': message.content[0].text,
        'data': data
    }


def create_meeting_doc(meeting_prep):
    import subprocess
    import tempfile

    content = meeting_prep['content']
    data = meeting_prep['data']

    output_filename = f"OpsBeacon_{data['meeting_type']}_Prep_{datetime.now().strftime('%Y%m%d')}.docx"
    desktop_path = os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop', output_filename)
    output_path_js = desktop_path.replace('\\', '/')

    safe_content = content.replace('\\', '\\\\').replace('`', "'").replace('${', '\\${')

    js_code = f"""
const {{ Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
        LevelFormat }} = require('docx');
const fs = require('fs');

const BRAND = "1B3A6B";
const ACCENT = "2563EB";
const GRAY = "666666";
const border = {{ style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }};
const borders = {{ top: border, bottom: border, left: border, right: border }};

function heading(text, level) {{
  return new Paragraph({{
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    children: [new TextRun({{ text, bold: true, size: level===1?32:26, color: BRAND, font: "Arial" }})]
  }});
}}

function body(text, bold) {{
  return new Paragraph({{
    children: [new TextRun({{ text, size: 22, font: "Arial", bold: bold||false, color: "333333" }})],
    spacing: {{ before: 80, after: 80 }}
  }});
}}

function bullet(text) {{
  return new Paragraph({{
    numbering: {{ reference: "bullets", level: 0 }},
    children: [new TextRun({{ text, size: 22, font: "Arial", color: "333333" }})],
    spacing: {{ before: 60, after: 60 }}
  }});
}}

function spacer() {{
  return new Paragraph({{ children: [new TextRun("")], spacing: {{ before: 160 }} }});
}}

const content = `{safe_content}`;
const lines = content.split('\\n');

const children = [
  new Paragraph({{
    children: [new TextRun({{ text: "OpsBeacon {data['meeting_type']} Prep", bold: true, size: 48, color: BRAND, font: "Arial" }})],
    alignment: AlignmentType.CENTER,
    spacing: {{ before: 0, after: 200 }}
  }}),
  new Paragraph({{
    children: [new TextRun({{ text: "{data['date']} | Period: {data['period']}", size: 22, color: GRAY, font: "Arial" }})],
    alignment: AlignmentType.CENTER,
    spacing: {{ before: 0, after: 400 }}
  }}),
  new Table({{
    width: {{ size: 9360, type: WidthType.DXA }},
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({{
      children: [
        ...["Total Spend\\n${data['total_spend']}", "Savings Available\\n${data['savings_monthly']}/mo", "Open Actions\\n{data['actions_open']}", "FinOps Score\\n{data['finops_score'] or 'N/A'}/100"].map(cell => {{
          const [label, value] = cell.split('\\n');
          return new TableCell({{
            borders,
            width: {{ size: 2340, type: WidthType.DXA }},
            shading: {{ fill: "E8F0FB", type: ShadingType.CLEAR }},
            margins: {{ top: 120, bottom: 120, left: 150, right: 150 }},
            children: [
              new Paragraph({{ children: [new TextRun({{ text: value, bold: true, size: 32, color: ACCENT, font: "Arial" }})], alignment: AlignmentType.CENTER }}),
              new Paragraph({{ children: [new TextRun({{ text: label, size: 18, color: GRAY, font: "Arial" }})], alignment: AlignmentType.CENTER }})
            ]
          }});
        }})
      ]
    }})]
  }}),
  spacer(),
];

for (const line of lines) {{
  const trimmed = line.trim();
  if (!trimmed) {{
    children.push(spacer());
  }} else if (trimmed.startsWith('## ')) {{
    children.push(spacer());
    children.push(heading(trimmed.replace('## ', ''), 1));
  }} else if (trimmed.startsWith('### ')) {{
    children.push(heading(trimmed.replace('### ', ''), 2));
  }} else if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {{
    children.push(bullet(trimmed.replace(/^[-*•] /, '')));
  }} else if (trimmed.match(/^\\d+\\./)) {{
    children.push(bullet(trimmed.replace(/^\\d+\\.\\s*/, '')));
  }} else if (trimmed.startsWith('**') && trimmed.endsWith('**')) {{
    children.push(body(trimmed.replace(/\\*\\*/g, ''), true));
  }} else {{
    children.push(body(trimmed));
  }}
}}

const doc = new Document({{
  numbering: {{
    config: [{{
      reference: "bullets",
      levels: [{{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: {{ paragraph: {{ indent: {{ left: 720, hanging: 360 }} }} }} }}]
    }}]
  }},
  styles: {{
    default: {{ document: {{ run: {{ font: "Arial", size: 22 }} }} }},
    paragraphStyles: [
      {{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: {{ size: 32, bold: true, font: "Arial", color: BRAND }},
        paragraph: {{ spacing: {{ before: 240, after: 120 }}, outlineLevel: 0 }} }},
      {{ id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: {{ size: 26, bold: true, font: "Arial", color: BRAND }},
        paragraph: {{ spacing: {{ before: 180, after: 80 }}, outlineLevel: 1 }} }}
    ]
  }},
  sections: [{{
    properties: {{
      page: {{
        size: {{ width: 12240, height: 15840 }},
        margin: {{ top: 1080, right: 1080, bottom: 1080, left: 1080 }}
      }}
    }},
    children
  }}]
}});

Packer.toBuffer(doc).then(buffer => {{
  fs.writeFileSync('{output_path_js}', buffer);
  console.log('Document created: {output_path_js}');
}});
"""

    costbot_dir = os.path.dirname(os.path.abspath(__file__))
    js_file = os.path.join(costbot_dir, 'meeting_prep_runner.js')
    with open(js_file, 'w', encoding='utf-8') as f:
        f.write(js_code)

    costbot_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        ['node', js_file],
        capture_output=True,
        text=True,
        cwd=costbot_dir
    )

    if result.returncode == 0:
        print(f"Document saved to: {desktop_path}")
        return desktop_path
    else:
        print(f"Doc error: {result.stderr}")
        return None


if __name__ == "__main__":
    print("\n=== Meeting Prep Agent Test ===")
    print("Generating MBR prep package...")
    prep = generate_meeting_prep('mbr')
    print("\nSlack output preview:")
    print(prep['content'][:500])
    print("\nGenerating Word document...")
    doc_path = create_meeting_doc(prep)
    if doc_path:
        print(f"Document created: {doc_path}")
    else:
        print("Document generation failed")