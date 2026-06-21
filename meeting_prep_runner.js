
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

const content = `# MONTHLY BUSINESS REVIEW - FinOps & Infrastructure
**Period:** May 22 - June 21, 2026 | **Presented:** June 21, 2026

## EXECUTIVE SUMMARY

Cloud spend decreased 55.8% week-over-week to $1.48, driven by successful snapshot cleanup saving $2.30/month and recent cost reductions in AWS Cost Explorer and EC2 services. While our FinOps score of 87/100 demonstrates strong cost discipline, four disabled security services present a $11/month remediation cost with potential compliance exposure. Critical decisions needed: commit to RDS reserved instance ($9.24 annual savings) and authorize security service enablement.

## TALKING POINTS

• **Strong cost trajectory**: Monthly spend trending toward $3.25, 82% below our $1,832 annual forecast run-rate, reflecting aggressive optimization efforts and successful waste elimination.

• **Cleanup initiative delivered**: Completed snapshot cleanup this period, eliminating $2.30 in monthly idle resource waste and demonstrating our team's responsiveness to flagged opportunities.

• **$9.24 annual savings opportunity**: RDS reserved instance commitment identified June 5th remains unactioned; requires procurement approval to lock in savings before month-end.

• **Security-cost tradeoff surfacing**: Four security services currently disabled to manage costs, but remediation investment of $11/month significantly outweighed by potential compliance risk exposure.

• **Operational stability maintained**: Zero cost anomalies active, one high-CPU alert resolved, compliance check cleared—infrastructure performance remains solid despite optimization pressure.

• **Action backlog concern**: One overdue action item with two still open; need clearer ownership assignment and accountability framework going forward.

• **Grade B performance**: FinOps score of 87/100 reflects mature cost management; Security score of 70/100 indicates vulnerability requiring immediate attention.

## RISKS

**1. Security Compliance Exposure ($15.30/month impact)**
Four security services disabled, creating audit and breach vulnerabilities. Monthly remediation cost of $11 is minimal compared to potential compliance fines or incident response costs. **Mitigation**: Authorize immediate re-enablement; absorb $11 monthly cost as non-negotiable infrastructure baseline.

**2. Delayed Reserved Instance Commitment ($9.24 annual savings at stake)**
RDS reservation opportunity identified 16 days ago remains uncommitted. Delay risks pricing changes or capacity availability. **Mitigation**: Finance approval required by June 25th; FinOps team to complete purchase by month-end.

**3. Database Performance Degradation ($0.50 immediate, unknown long-term)**
High CPU alert on production database June 16th signals potential scaling need or optimization gap. **Mitigation**: Infrastructure team to complete root cause analysis by June 28th; present rightsizing recommendation vs. performance tuning options.

**4. Action Item Accountability Gap (1 overdue, operational risk)**
Overdue action indicates process breakdown in task management and ownership clarity. **Mitigation**: Implement weekly action review cadence with assigned DRIs and escalation protocol.

## ACTIONS REQUIRED

**1. Approve Security Services Re-enablement** | Owner: Director of Infrastructure | Deadline: June 23, 2026
Authorize $11/month spend to restore four disabled security services and eliminate compliance risk flagged in Security Cost Score.

**2. Execute RDS Reserved Instance Purchase** | Owner: FinOps Lead | Deadline: June 30, 2026
Secure procurement approval and commit to identified RDS reservation, locking in $9.24 annual savings before end of month.

**3. Resolve Database Performance Investigation** | Owner: Infrastructure Team Lead | Deadline: June 28, 2026
Complete CPU utilization analysis and present costed options for resolution (scaling vs. optimization) with implementation timeline.

**4. Implement Action Tracking Governance** | Owner: Program Manager | Deadline: June 27, 2026
Establish weekly action review meeting, assign explicit DRIs to all open items, and create escalation path for items approaching due dates.`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "June 21, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$1.48", "Savings Available\n$0/mo", "Open Actions\n2", "FinOps Score\n87/100"].map(cell => {
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
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260621.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260621.docx');
});
