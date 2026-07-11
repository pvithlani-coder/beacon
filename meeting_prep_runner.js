
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
**FinOps & Infrastructure Review | July 9, 2026**

## EXECUTIVE SUMMARY

Cloud spend increased 113% week-over-week to $5.37, driven primarily by AWS Cost Explorer usage spike on July 8th. While we successfully realized $2.30 in savings through snapshot cleanup, $9.24 in identified savings remains uncaptured and four critical security services remain disabled at a $11/month remediation cost. With two overdue actions and accelerating spend trajectory, we need immediate decisions on security investment and commitment to execute pending optimizations before month-end forecast of $6.46 materializes.

## TALKING POINTS

• **Cloud spend jumped 113% last week** to $5.37, putting us on track for $6.46 this month and $1,861 annually—AWS Cost Explorer alone represents 68% of current spend at $3.65

• **We captured $2.30 in savings** this period through snapshot cleanup, but **$9.24 in additional savings sits unactured**, primarily in idle resources wasting $2.30 monthly

• **Four security services are currently disabled**, creating compliance exposure that costs only $11/month to remediate—a decision is needed on whether to enable

• **FinOps score of 81 (Grade B) is solid, but Security score of 71** indicates room for improvement, especially with two actions now overdue

• **Production database experienced high CPU** on June 16th costing an estimated $0.50 in performance impact—monitoring whether this becomes a pattern

• **No cost anomalies detected** and compliance checks passed, indicating good baseline controls despite the spending acceleration

• **Current trajectory projects $1,861 annual spend**—need to validate if this aligns with budget expectations and growth plans

## RISKS

**1. Uncaptured Savings Execution Risk**
- **Exposure:** $9.24 immediate, $110+ annually
- **Impact:** Two overdue optimization actions signal execution gap; idle resources continue burning $2.30/month
- **Mitigation:** Assign single owner for all optimization items with July 16th hard deadline; automate idle resource detection and shutdown

**2. Security Compliance Gaps**
- **Exposure:** $11/month remediation cost, unknown breach liability
- **Impact:** Four disabled security services create audit failures and potential vulnerability exposure
- **Mitigation:** Approve $11/month investment immediately; establish policy requiring security service justification for any disablement

**3. AWS Cost Explorer Spend Anomaly**
- **Exposure:** $3.65 current, potentially recurring
- **Impact:** Single service represents 68% of total spend; July 8th spike of $0.693 lacks clear business justification
- **Mitigation:** Audit Cost Explorer API calls and reporting frequency; implement usage alerts at $2/day threshold

**4. Spending Acceleration Without Visibility**
- **Exposure:** 113% week-over-week growth rate
- **Impact:** If sustained, month-end overage vs. forecast; annual projection uncertainty
- **Mitigation:** Implement weekly spend reviews through month-end; require business justification for any service over $1/week

## ACTIONS REQUIRED

**1. Approve Security Services Budget** (Owner: Infrastructure Director, Deadline: July 12)
- Decision needed: Allocate $11/month to enable four disabled security services or accept documented compliance risk

**2. Clear Overdue Optimization Backlog** (Owner: FinOps Lead, Deadline: July 16)
- Execute on $9.24 in identified savings; provide written explanation for two overdue items and recovery plan

**3. Investigate Cost Explorer Usage Spike** (Owner: Cloud Architect, Deadline: July 11)
- Root cause analysis for $3.65 spend concentration; implement controls to prevent recurrence

**4. Establish Spend Governance Thresholds** (Owner: Finance + Engineering, Deadline: July 23)
- Define approval requirements for new services; set automated alerts at service and account levels

**5. Production Database Capacity Review** (Owner: Database Team, Deadline: July 19)
- Assess June 16th CPU event; right-size or upgrade before performance degrades further`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "July 09, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$5.37", "Savings Available\n$0/mo", "Open Actions\n2", "FinOps Score\n81/100"].map(cell => {
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
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260709.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260709.docx');
});
