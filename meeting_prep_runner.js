
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        AlignmentType, HeadingLevel, BorderStyle, WidthType, ShadingType,
        LevelFormat } = require('docx');
const fs = require('fs');

const BRAND = "1B3A6B";
const ACCENT = "2563EB";
const GRAY = "666666";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function heading(text, level) {
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: level===1?32:26, color: BRAND, font: "Arial" })]
  });
}

function body(text, bold) {
  return new Paragraph({
    children: [new TextRun({ text, size: 22, font: "Arial", bold: bold||false, color: "333333" })],
    spacing: { before: 80, after: 80 }
  });
}

function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, size: 22, font: "Arial", color: "333333" })],
    spacing: { before: 60, after: 60 }
  });
}

function spacer() {
  return new Paragraph({ children: [new TextRun("")], spacing: { before: 160 } });
}

const content = `# MBR PREPARATION PACKAGE
**FinOps & Infrastructure Review | August 27, 2026**

## EXECUTIVE SUMMARY

Cloud spending is accelerating rapidly with a 384% week-over-week increase, projecting $5.25 by month-end and nearly $1,900 annually if unchecked. While we've realized $2.30 in savings this period, we're carrying $10.04 in unrealized savings and $2.30 in monthly idle resource waste. Critical security gaps remain with four disabled services requiring $11/month to remediate, and three overdue action items demand immediate attention. Leadership must approve immediate cost controls and security remediation before spending trajectory becomes unmanageable.

## TALKING POINTS

• **Current spend is $0.30 but accelerating at 384% week-over-week**, driven primarily by EC2 ($0.21) and RDS ($0.09), with a cost spike of $0.255 detected on August 23rd requiring investigation.

• **Monthly forecast of $5.25 projects to nearly $1,900 annually**, representing significant budget exposure if current growth continues unchecked through Q4.

• **We've captured $2.30 in savings this period but $10.04 remains on the table**, primarily from idle resources wasting $2.30 monthly that should be decommissioned immediately.

• **Security posture shows gaps with 4 disabled services and a score of 71/100**, requiring only $11 monthly investment to remediate critical vulnerabilities before they become incidents.

• **Three action items are overdue**, creating operational risk and preventing optimization progress; only one item was completed this period.

• **FinOps score of 79 (Grade C) indicates room for improvement** in resource optimization, tagging compliance, and commitment-based discount utilization.

• **No active cost anomalies currently detected**, suggesting monitoring systems are functioning but the August 23rd spike warrants root cause analysis.

## RISKS

**1. Uncontrolled Cost Acceleration (High Impact: $1,876 annual exposure)**
Current 384% growth rate could exhaust annual budget within weeks. Mitigation: Implement immediate spending alerts at $1/day threshold and require approval for new resource provisioning above $50.

**2. Unrealized Savings Deterioration (Medium Impact: $10.04 immediate + $2.30/month recurring)**
Idle resources and unimplemented recommendations compound monthly waste. Mitigation: Execute emergency cleanup sprint to eliminate idle resources and implement top 3 savings recommendations by September 10th.

**3. Security Compliance Gaps (Medium Impact: $11/month + potential breach exposure)**
Four disabled security services create audit failures and vulnerability exposure disproportionate to remediation cost. Mitigation: Enable all security services immediately; cost is negligible versus compliance or breach risk.

**4. Operational Debt from Overdue Actions (Low Impact: Process degradation)**
Three overdue items indicate broken accountability and could mask larger infrastructure issues. Mitigation: Conduct action item review in this meeting with forced closure or re-assignment.

## ACTIONS REQUIRED

**1. Approve Emergency Cost Controls (Owner: Infrastructure Director, Deadline: August 28)**
Implement daily spending cap of $1 and require VP approval for new resources exceeding $50 until growth stabilizes and forecast clarity improves.

**2. Execute Security Remediation (Owner: Security Lead, Deadline: August 30)**
Enable four disabled security services immediately; $11/month cost pre-approved given compliance requirements and minimal budget impact.

**3. Complete Savings Implementation Sprint (Owner: FinOps Manager, Deadline: September 10)**
Decommission all identified idle resources ($2.30/month) and implement top three optimization recommendations to capture $10.04 in available savings.

**4. Resolve Overdue Action Items (Owner: All attendees, Deadline: Today)**
Review three overdue items during this meeting; each must be closed, reassigned with commitment, or explicitly cancelled with documented rationale.

**5. Investigate August 23rd Cost Spike (Owner: FinOps Analyst, Deadline: September 3)**
Complete root cause analysis of $0.255 AWS Cost Explorer anomaly and present findings with prevention measures.`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "August 27, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$0.3", "Savings Available\n$0/mo", "Open Actions\n3", "FinOps Score\n79/100"].map(cell => {
          const [label, value] = cell.split('\n');
          return new TableCell({
            borders,
            width: { size: 2340, type: WidthType.DXA },
            shading: { fill: "E8F0FB", type: ShadingType.CLEAR },
            margins: { top: 120, bottom: 120, left: 150, right: 150 },
            children: [
              new Paragraph({ children: [new TextRun({ text: value, bold: true, size: 32, color: ACCENT, font: "Arial" })], alignment: AlignmentType.CENTER }),
              new Paragraph({ children: [new TextRun({ text: label, size: 18, color: GRAY, font: "Arial" })], alignment: AlignmentType.CENTER })
            ]
          });
        })
      ]
    })]
  }),
  spacer(),
];

for (const line of lines) {
  const trimmed = line.trim();
  if (!trimmed) {
    children.push(spacer());
  } else if (trimmed.startsWith('## ')) {
    children.push(spacer());
    children.push(heading(trimmed.replace('## ', ''), 1));
  } else if (trimmed.startsWith('### ')) {
    children.push(heading(trimmed.replace('### ', ''), 2));
  } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ') || trimmed.startsWith('• ')) {
    children.push(bullet(trimmed.replace(/^[-*•] /, '')));
  } else if (trimmed.match(/^\d+\./)) {
    children.push(bullet(trimmed.replace(/^\d+\.\s*/, '')));
  } else if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
    children.push(body(trimmed.replace(/\*\*/g, ''), true));
  } else {
    children.push(body(trimmed));
  }
}

const doc = new Document({
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
    }]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: BRAND },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Arial", color: BRAND },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 1 } }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
      }
    },
    children
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260827.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260827.docx');
});
