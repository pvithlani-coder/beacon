
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
**FinOps & Infrastructure | July 08, 2026**

## EXECUTIVE SUMMARY

Cloud spending is well-controlled at $5.74 for the period with strong downward momentum (-27.4% week-over-week), driven primarily by snapshot cleanup savings of $2.30. However, we have critical security exposure with 4 disabled services requiring $11/month to remediate, and $9.24 in identified savings remains unrealized due to 2 overdue action items. Leadership must approve security remediation budget and assign ownership to close the optimization backlog before month-end.

## TALKING POINTS

• **Spending is decreasing significantly**: Total spend of $5.74 represents a 27% reduction from last week, forecasting only $2.28 by month-end versus typical $5-6 run rates, demonstrating effective cost management.

• **Cleanup initiatives delivered results**: Snapshot cleanup completed June 9th eliminated $2.30 in monthly waste, proving our optimization process works when executed.

• **We're leaving money on the table**: $9.24 in annual savings sits unimplemented with 2 overdue actions, representing 160% of our monthly spend that could be eliminated.

• **Security posture needs immediate attention**: Four security services remain disabled with a compliance score of 71/100, creating audit risk and requiring only $11/month investment to resolve.

• **AWS Cost Explorer charges need investigation**: Our cost monitoring tool became our largest expense at $3.94—we're spending 69% of our budget on cost visibility, which requires immediate optimization.

• **Operations remain stable**: Zero cost anomalies and successful compliance checks indicate solid baseline operations, though the June 16th database CPU spike warrants monitoring.

• **Strong FinOps foundation**: 83/100 FinOps score (Grade B) demonstrates process maturity, with clear opportunity to reach A-grade by closing security gaps and executing pending actions.

## RISKS

**RISK 1: Security Compliance Failure** — Four disabled security services expose us to audit failures and potential breaches. Annual exposure: $132 remediation cost plus unknown incident costs. **Mitigation**: Approve $11/month budget immediately and enable services by July 15th.

**RISK 2: Cost Monitoring Tool Inefficiency** — AWS Cost Explorer at $3.94/month (69% of total spend) indicates misconfiguration or unnecessary API calls. Annual exposure: $47. **Mitigation**: Audit Cost Explorer usage patterns and optimize queries or consider alternative monitoring approach by July 22nd.

**RISK 3: Stalled Optimization Program** — $9.24 annual savings identified but not implemented due to 2 overdue actions, representing 100% failure rate on current action items. Exposure: Direct waste plus team credibility. **Mitigation**: Reassign ownership with executive sponsorship and weekly check-ins until completion.

**RISK 4: Database Performance Degradation** — High CPU alert on production database June 16th with $0.50 impact suggests capacity constraints. Exposure: Potential outage costs and emergency scaling expenses. **Mitigation**: Conduct capacity review and right-size database by July 20th.

## ACTIONS REQUIRED

**ACTION 1**: Approve $11/month security services budget and assign Security Lead to enable all four services by July 15th. Board decision required.

**ACTION 2**: CFO to assign dedicated owner to two overdue optimization actions with daily standup accountability until $9.24 savings realized by July 18th.

**ACTION 3**: Infrastructure Lead to audit AWS Cost Explorer configuration and reduce monitoring costs by 50% ($2/month target) by July 22nd with implementation report.

**ACTION 4**: CTO to review production database capacity plan and approve rightsizing recommendation by July 20th to prevent performance incidents.

**ACTION 5**: FinOps Lead to present revised action tracking process with enforcement mechanisms at next MBR to prevent future overdue items.`;
const lines = content.split('\n');

const children = [
  new Paragraph({
    children: [new TextRun({ text: "OpsBeacon MBR Prep", bold: true, size: 48, color: BRAND, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 200 }
  }),
  new Paragraph({
    children: [new TextRun({ text: "July 08, 2026 | Period: Last 30 days", size: 22, color: GRAY, font: "Arial" })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 400 }
  }),
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    rows: [new TableRow({
      children: [
        ...["Total Spend\n$5.74", "Savings Available\n$0/mo", "Open Actions\n2", "FinOps Score\n83/100"].map(cell => {
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
  fs.writeFileSync('C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260708.docx', buffer);
  console.log('Document created: C:/Users/pvith/OneDrive/Desktop/OpsBeacon_MBR_Prep_20260708.docx');
});
