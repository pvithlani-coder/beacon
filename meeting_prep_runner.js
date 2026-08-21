
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
**FinOps & Infrastructure Team | August 20, 2026**

## EXECUTIVE SUMMARY

Cloud spend remains stable at $0.83 for the 30-day period with a projected monthly run rate of $2.34, tracking toward an annual spend of $1,838. While we achieved $2.30 in savings this period and maintain a solid FinOps score of 81/100, we have $10.04 in unrealized savings from idle resources and face $11/month in costs to address four critical security service gaps (Security Score: 71/100). Immediate decisions are needed on security remediation investments and overdue action items to prevent compliance exposure and resource waste.

## TALKING POINTS

• **Cloud spend is stable and predictable** – $0.83 spent in the last 30 days with zero variance from prior week; annual forecast of $1,838 shows controlled growth with EC2 representing 70% of costs and RDS accounting for 30%

• **We captured $2.30 in savings this period** through optimization efforts, demonstrating the team's ability to identify and eliminate waste without impacting operations

• **$10.04 per month is being wasted on idle resources** – this represents low-hanging fruit that should be addressed immediately to prevent $120+ in annual waste

• **Four security services are currently disabled** creating compliance risk and requiring $11/month investment to remediate – the cost to fix is nominal compared to potential breach exposure

• **Action item completion is lagging** – only 1 item completed while 3 remain overdue, indicating potential resource constraints or prioritization challenges that need addressing

• **FinOps performance is strong at B-grade (81/100)** but security posture at 71/100 needs improvement to meet enterprise standards

• **No cost anomalies detected** this period, confirming our monitoring and guardrails are effectively preventing runaway spending

## RISKS

**1. Security Compliance Exposure** – Four critical security services remain disabled, creating potential audit failures and breach vulnerability. Dollar exposure: Difficult to quantify but remediation cost is only $11/month. *Mitigation: Approve $11/month security investment immediately and enable all four services within 7 days.*

**2. Unrealized Savings Leakage** – $10.04/month in idle resource waste ($120/year) indicates resources provisioned but not decommissioned. *Mitigation: Implement automated idle resource detection and mandatory 14-day decommissioning workflow.*

**3. Action Item Accountability Gap** – Three overdue actions with only one completion suggests either inadequate resourcing or unclear ownership. *Mitigation: Reassign overdue items with executive sponsorship and implement weekly accountability check-ins.*

**4. Forecast Accuracy Validation** – Current $0.83/30-day spend projects to $2.34/month, but requires validation against actual usage patterns. *Mitigation: Conduct mid-month forecast review to confirm projection accuracy and adjust if needed.*

## ACTIONS REQUIRED

**1. Approve Security Remediation Budget** – $11/month to enable four disabled security services. *Owner: Infrastructure Director | Deadline: August 22, 2026*

**2. Execute Idle Resource Cleanup** – Eliminate $10.04/month waste through resource decommissioning audit. *Owner: FinOps Lead | Deadline: September 3, 2026*

**3. Resolve Overdue Action Items** – Close all three overdue items or provide revised timeline with justification. *Owner: Team Leads | Deadline: August 27, 2026*

**4. Implement Automated Waste Detection** – Deploy tooling to prevent future idle resource accumulation. *Owner: Engineering Manager | Deadline: September 15, 2026*

## SLIDES OUTLINE

**Slide 1:** Title – FinOps & Infrastructure MBR | August 2026

**Slides 2-3:** Financial Overview – 30-day spend breakdown, trend analysis, forecast vs. actual, top service costs

**Slides 4-5:** Risks & Mitigation – Security gaps, idle waste, action item delays with mitigation plans

**Slides 6-7:** Optimization Opportunities – Savings realized ($2.30), savings at stake ($10.04), efficiency recommendations

**Slide 8:** Actions & Owners – Four decisions with assigned owners and deadlines

**Slide 9:** Next Period Forecast – September projections, key initiatives, success metrics`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "August 20, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$0.83", "Savings Available\n$0/mo", "Open Actions\n3", "FinOps Score\n81/100"].map(cell => {
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
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260820.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260820.docx');
});
