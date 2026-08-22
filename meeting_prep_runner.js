
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
**FinOps & Infrastructure Team | August 21, 2026**

## EXECUTIVE SUMMARY

Cloud spending remains exceptionally stable at $0.76 for the last 30 days with zero variance, projecting to $2.34 by month-end and $1,838 annually. We achieved $2.30 in savings this period but have $10.04 in identified savings still unrealized and four critical security services remain disabled, creating $11/month in remediation costs. With three overdue actions and a FinOps score of 81 (Grade B), we need leadership approval to eliminate idle resources and enable security controls before these small exposures compound into material issues.

## TALKING POINTS

• **Financial health is strong**: $0.76 spent over 30 days with 0% week-over-week change demonstrates excellent cost predictability; we're tracking to $1,838 annually with EC2 representing 70% of spend at $0.53

• **We delivered savings**: Successfully realized $2.30 in cost reductions this period, demonstrating our team's optimization discipline and proactive management

• **Idle waste is immediate opportunity**: $2.30 per month in idle resources identified—this represents money we're spending with zero business value that can be eliminated this week

• **Security gaps create business risk**: Four security services currently disabled; addressing these costs only $11/month but leaving them disabled exposes us to compliance violations and potential breaches worth significantly more

• **Action completion lagging**: Three overdue actions with only one completed this period signals execution challenges that need addressing to maintain our Grade B FinOps score

• **No optimization pipeline**: Zero monthly or annual savings currently available suggests we've exhausted easy wins and need strategic optimization review

• **Anomaly detection working**: Zero active cost anomalies indicates our monitoring is effective and spending is predictable with no surprise overruns

## RISKS

**1. Security Compliance Exposure (HIGH)**
- Four security services disabled creating audit and breach vulnerability
- Dollar exposure: $11/month remediation cost plus potential compliance fines and incident response costs
- Mitigation: Enable all security services within 7 days; assign Security Lead to validate configuration

**2. Stagnant Optimization Pipeline (MEDIUM)**
- $0 in identified future savings means no proactive cost management strategy
- Dollar exposure: $10.04 in unrealized savings compounding monthly; opportunity cost of 12-18 months
- Mitigation: Conduct architecture review by September 15; establish quarterly optimization planning cycle

**3. Action Execution Breakdown (MEDIUM)**
- Three overdue actions indicate process failure or resource constraints
- Dollar exposure: Delayed decisions leading to continued waste and missed savings
- Mitigation: Immediate review of overdue items; reassign owners if capacity issues exist

**4. Idle Resource Waste (LOW but IMMEDIATE)**
- $2.30/month burning with no business value
- Dollar exposure: $27.60 annually if unaddressed
- Mitigation: Terminate or right-size idle resources within 48 hours

## ACTIONS REQUIRED

**1. Authorize Security Services Enablement**
Owner: CISO | Deadline: August 28, 2026
Approve $11/month spend to enable four disabled security services and eliminate compliance gaps

**2. Clear Overdue Action Backlog**
Owner: Infrastructure Director | Deadline: August 25, 2026
Complete all three overdue actions or formally close with business justification; prevent score degradation

**3. Eliminate Idle Resources**
Owner: FinOps Lead | Deadline: August 23, 2026
Terminate identified $2.30/month idle waste and recapture $10.04 in available savings

**4. Commission Q4 Optimization Strategy**
Owner: Infrastructure Director + FinOps Lead | Deadline: September 15, 2026
Conduct workload review to populate savings pipeline for next two quarters; target 15% efficiency improvement

**5. Establish Action Tracking Cadence**
Owner: Program Manager | Deadline: August 28, 2026
Implement weekly action review to prevent future overdue accumulation and maintain accountability`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "August 21, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$0.76", "Savings Available\n$0/mo", "Open Actions\n3", "FinOps Score\n81/100"].map(cell => {
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
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260821.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260821.docx');
});
