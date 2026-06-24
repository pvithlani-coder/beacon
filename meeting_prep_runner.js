
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
**FinOps & Infrastructure Team | June 21, 2026**

## EXECUTIVE SUMMARY

Cloud spend is trending significantly downward at $1.48 for the last 30 days, a 50% deceleration from prior week, positioning us to end the month at $3.41 against an annual forecast of $1,835. The team successfully realized $2.30 in savings through snapshot cleanup, but $9.24 in additional annual savings remains uncaptured from an identified RDS reserved instance opportunity. Four disabled security services present an $11/month exposure that requires immediate remediation, pulling our Security Score to 70/100 despite maintaining a strong FinOps Score of 87/100.

## TALKING POINTS

- **Costs are declining sharply**: Last 30 days totaled just $1.48, down 50% week-over-week, driven primarily by AWS Cost Explorer optimization and reduced EC2 usage
- **We captured $2.30 in monthly savings** by cleaning up idle snapshots identified on May 22nd, demonstrating effective waste management
- **$9.24 in annual savings is sitting on the table**: RDS reserved instance commitment identified June 5th remains unpurchased—needs approval to proceed
- **Security posture requires investment**: Four security services are disabled, creating potential compliance exposure with $11/month cost to remediate
- **Team execution is strong but follow-through lags**: We completed 1 action this period but have 1 overdue item and 2 still open from previous reviews
- **Database performance incident on June 16th** spiked costs by $0.50 and signals potential need for capacity planning review
- **Annual forecast of $1,835 remains stable** with current trajectory supporting year-end budget adherence

## RISKS

**1. Security Compliance Gap - $132 annual exposure**
Four security services currently disabled with $11/month remediation cost. Risk of audit findings, regulatory penalties, or breach exposure far exceeds the nominal investment. **Mitigation**: Approve security service activation within 5 business days; assign Security Lead to implement.

**2. Unrealized RDS Savings - $9.24 annual opportunity**
Reserved instance commitment identified 16 days ago remains unpurchased while we continue paying on-demand rates. Delay erodes ROI. **Mitigation**: Finance approval needed this meeting to commit to RI purchase; Infrastructure Lead to execute within 48 hours.

**3. Database Performance Instability - Unknown exposure**
High CPU alert on production database June 16th resulted in $0.50 impact and suggests capacity constraints. Risk of customer-facing outages or emergency scaling costs. **Mitigation**: Conduct capacity planning assessment by June 30th; consider reserved capacity commitment.

**4. Overdue Action Items - Execution risk**
One overdue action and operational debt accumulation threatens team credibility and compounds technical debt. **Mitigation**: Review action ownership assignments today; establish weekly accountability check-ins.

## ACTIONS REQUIRED

**1. Approve Security Service Activation - CFO/Security Lead**
Authorize $11/month spend to enable four disabled security services. Decision needed today; implementation by June 28th to improve Security Score from 70 to target 85+.

**2. Commit to RDS Reserved Instance - Finance Director**
Approve $9.24 annual savings opportunity through RI purchase. Decision needed this meeting; Infrastructure team to execute commitment by June 23rd.

**3. Resolve Overdue Action Item - FinOps Manager**
Review and close outstanding overdue action before month-end. Owner confirmation and completion deadline: June 25th.

**4. Database Capacity Assessment - Infrastructure Lead**
Commission performance review following June 16th high-CPU incident. Deliver recommendations with cost implications by June 30th for Q3 planning.

## SLIDES OUTLINE

**Slide 1**: Title - Monthly Business Review, FinOps & Infrastructure

**Slide 2**: Financial Overview - 30-day spend trend, deceleration narrative, top service breakdown

**Slide 3**: Forecast Position - Month-end $3.41 projection, annual $1,835 tracking, variance analysis

**Slide 4**: Risk Dashboard - Four risks ranked by exposure with current scores (FinOps 87, Security 70)

**Slide 5**: Security Investment Requirement - $11/month gap detail, compliance implications

**Slide 6**: Optimization Wins - $2.30 realized savings story, snapshot cleanup success

**Slide 7**: Optimization Pipeline - $9.24 RDS opportunity, approval pathway, ROI timeline

**Slide 8**: Actions & Owners - Four decisions required with owners and deadlines

**Slide 9**: Next Period Outlook - Forecast stability, planned initiatives, success metrics`;
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
