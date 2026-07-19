import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  AlignmentType,
  Document,
  Footer,
  Header,
  HeadingLevel,
  ImportedXmlComponent,
  Packer,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  convertInchesToTwip,
} from "docx";

const outputPath = process.argv[2];
if (!outputPath) {
  throw new Error("Usage: node build_report.js /absolute/path/output.docx");
}

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const mdPath = path.join(scriptDir, "00_商用交付差距审计报告.md");
const md = fs.readFileSync(mdPath, "utf8");

// ---------- visual defaults ----------
const palette = {
  dark: "37474F",     // blue-gray 800
  primary: "546E7A",  // blue-gray 600
  light: "90A4AE",    // blue-gray 300
  border: "CFD8DC",   // blue-gray 100
  fill: "ECEFF1",     // blue-gray 50
  quoteBg: "F5F7F8",
};

const font = {
  ascii: "Calibri",
  hAnsi: "Calibri",
  cs: "Calibri",
  eastAsia: "DengXian",
};

const run = (text, options = {}) => new TextRun({ text, font, size: 22, ...options });
const para = (children, options = {}) =>
  new Paragraph({
    spacing: { after: 140, line: 300 },
    ...options,
    children: Array.isArray(children) ? children : [children],
  });

// ---------- inline parsing: **bold** and `code` ----------
function inlineRuns(text, baseOptions = {}) {
  const parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return run(part.slice(2, -2), { ...baseOptions, bold: true });
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return new TextRun({
        text: part.slice(1, -1),
        font: { ascii: "Consolas", hAnsi: "Consolas", cs: "Consolas", eastAsia: "DengXian" },
        size: 20,
        color: "6D4C41",
        ...baseOptions,
      });
    }
    return run(part, baseOptions);
  });
}

// ---------- markdown block parsing ----------
const lines = md.split(/\r?\n/);
const blocks = [];
let i = 0;
let docTitle = "";
while (i < lines.length) {
  const line = lines[i];
  if (!line.trim()) { i++; continue; }

  const h = line.match(/^(#{1,6})\s+(.*)$/);
  if (h) {
    const level = h[1].length;
    if (level === 1 && !docTitle) { docTitle = h[2].trim(); i++; continue; }
    blocks.push({ type: "heading", level: level - 1, text: h[2].trim() }); // ## ->1, ### ->2
    i++; continue;
  }

  if (/^-{3,}\s*$/.test(line)) { i++; continue; }

  if (line.trim().startsWith("|")) {
    const rows = [];
    while (i < lines.length && lines[i].trim().startsWith("|")) {
      const raw = lines[i].trim();
      const cells = raw.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
      const isSep = cells.every((c) => /^:?-{2,}:?$/.test(c) || c === "");
      if (!isSep) rows.push(cells);
      i++;
    }
    if (rows.length) blocks.push({ type: "table", rows });
    continue;
  }

  if (line.trim().startsWith(">")) {
    const qlines = [];
    while (i < lines.length && lines[i].trim().startsWith(">")) {
      qlines.push(lines[i].trim().replace(/^>\s?/, ""));
      i++;
    }
    blocks.push({ type: "quote", text: qlines.join("\n") });
    continue;
  }

  const ol = line.match(/^(\d+)\.\s+(.*)$/);
  if (ol) { blocks.push({ type: "olist", num: ol[1], text: ol[2].trim() }); i++; continue; }

  if (line.trim().startsWith("- ")) { blocks.push({ type: "ulist", text: line.trim().slice(2) }); i++; continue; }

  if (/^\*[^*].*\*$/.test(line.trim())) {
    blocks.push({ type: "italic", text: line.trim().replace(/^\*/, "").replace(/\*$/, "") });
    i++; continue;
  }

  blocks.push({ type: "para", text: line.trim() });
  i++;
}

// ---------- TOC entries + rough page estimates ----------
function visualLen(s) {
  let n = 0;
  for (const ch of String(s)) n += /[⺀-鿿豈-﫿＀-￯　-〿]/.test(ch) ? 2 : 1;
  return n;
}

const tocEntries = [];
let weight = 0;
const PAGE_CAPACITY = 46;
for (const b of blocks) {
  if (b.type === "heading") {
    const page = 3 + Math.floor(weight / PAGE_CAPACITY);
    tocEntries.push({ title: b.text, level: b.level, page });
    weight += b.level === 1 ? 4 : 2;
  } else if (b.type === "table") {
    weight += b.rows.length * 1.6 + 2;
  } else if (b.type === "para" || b.type === "quote") {
    weight += Math.max(1, Math.ceil(visualLen(b.text) / 46));
  } else {
    weight += Math.max(1, Math.ceil(visualLen(b.text) / 44));
  }
}

// ---------- TOC XML (skill-provided shape) ----------
const xmlEscape = (value) =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const toc = (entries) => {
  const cached = entries
    .map(({ title: t, level, page }) => {
      const indent = Math.max(0, level - 1) * 360;
      return `<w:p>
        <w:pPr>
          <w:pStyle w:val="TOC${level}"/>
          <w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9000"/></w:tabs>
          <w:ind w:left="${indent}"/>
        </w:pPr>
        <w:r><w:t>${xmlEscape(t)}</w:t></w:r>
        <w:r><w:tab/></w:r>
        <w:r><w:t>${xmlEscape(page)}</w:t></w:r>
      </w:p>`;
    })
    .join("");

  return ImportedXmlComponent.fromXmlString(`<w:sdt xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:sdtPr><w:alias w:val="目录"/></w:sdtPr>
    <w:sdtContent>
      <w:p>
        <w:r>
          <w:fldChar w:fldCharType="begin" w:dirty="true"/>
          <w:instrText xml:space="preserve"> TOC \\o &quot;1-3&quot; \\h \\z \\u </w:instrText>
          <w:fldChar w:fldCharType="separate"/>
        </w:r>
      </w:p>
      ${cached}
      <w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
    </w:sdtContent>
  </w:sdt>`).root[0];
};

// ---------- table builder ----------
const TOTAL_WIDTH = 9360;
function buildTable(rows) {
  const colCount = Math.max(...rows.map((r) => r.length));
  const weights = new Array(colCount).fill(6);
  for (const row of rows) {
    for (let c = 0; c < colCount; c++) {
      const len = Math.min(30, Math.max(4, visualLen(row[c] ?? "")));
      weights[c] = Math.max(weights[c], len);
    }
  }
  const sum = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map((w) => Math.max(800, Math.round((w / sum) * TOTAL_WIDTH)));

  const cellPara = (text, bold) =>
    new Paragraph({
      spacing: { after: 40, line: 260 },
      children: inlineRuns(text, bold ? { bold: true } : {}),
    });

  const tableRows = rows.map(
    (row, rIdx) =>
      new TableRow({
        tableHeader: rIdx === 0,
        children: Array.from({ length: colCount }, (_, c) => {
          const isHeader = rIdx === 0;
          return new TableCell({
            children: [cellPara(row[c] ?? "", isHeader)],
            margins: { top: 100, bottom: 100, left: 100, right: 100 },
            width: { size: widths[c], type: WidthType.DXA },
            shading: isHeader
              ? { type: ShadingType.CLEAR, fill: palette.fill }
              : undefined,
          });
        }),
      }),
  );

  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: widths,
    borders: {
      top: { style: "single", size: 4, color: palette.border },
      bottom: { style: "single", size: 4, color: palette.border },
      left: { style: "single", size: 4, color: palette.border },
      right: { style: "single", size: 4, color: palette.border },
      insideHorizontal: { style: "single", size: 4, color: palette.border },
      insideVertical: { style: "single", size: 4, color: palette.border },
    },
    rows: tableRows,
  });
}

// ---------- body rendering ----------
const bodyChildren = [];
for (const b of blocks) {
  switch (b.type) {
    case "heading": {
      const isH1 = b.level === 1;
      bodyChildren.push(
        para(run(b.text, { bold: true, size: isH1 ? 30 : 26, color: palette.dark }), {
          heading: isH1 ? HeadingLevel.HEADING_1 : HeadingLevel.HEADING_2,
          spacing: { before: isH1 ? 320 : 220, after: 120 },
        }),
      );
      break;
    }
    case "para":
      bodyChildren.push(
        para(inlineRuns(b.text), {
          indent: { firstLine: convertInchesToTwip(0.31) },
        }),
      );
      break;
    case "quote":
      for (const qline of b.text.split("\n")) {
        bodyChildren.push(
          para(inlineRuns(qline, { color: palette.primary }), {
            indent: { left: convertInchesToTwip(0.3) },
            spacing: { after: 60, line: 280 },
            shading: { type: ShadingType.CLEAR, fill: palette.quoteBg },
          }),
        );
      }
      break;
    case "ulist":
      bodyChildren.push(
        para(inlineRuns(b.text), {
          bullet: { level: 0 },
          spacing: { after: 80, line: 300 },
        }),
      );
      break;
    case "olist":
      bodyChildren.push(
        para([run(`${b.num}. `, { bold: true, color: palette.primary }), ...inlineRuns(b.text)], {
          indent: { left: convertInchesToTwip(0.25) },
          spacing: { after: 80, line: 300 },
        }),
      );
      break;
    case "table":
      bodyChildren.push(buildTable(b.rows));
      bodyChildren.push(para(run("", { size: 8 }), { spacing: { after: 120 } }));
      break;
    case "italic":
      bodyChildren.push(
        para(inlineRuns(b.text, { italics: true, color: palette.light }), {
          alignment: AlignmentType.CENTER,
          spacing: { before: 240 },
        }),
      );
      break;
  }
}

// ---------- cover ----------
const cover = [
  para(run("", { size: 20 }), { spacing: { before: 2200 } }),
  para(run(docTitle || "X-Agent 商用交付差距审计报告", { bold: true, size: 48, color: palette.dark }), {
    heading: HeadingLevel.TITLE,
    alignment: AlignmentType.CENTER,
    spacing: { after: 360 },
  }),
  para(run("Commercial Delivery Gap Audit Report", { size: 24, color: palette.light }), {
    alignment: AlignmentType.CENTER,
    spacing: { after: 900 },
  }),
  para(run("报告日期：2026-07-19", { size: 22, color: palette.primary }), {
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
  }),
  para(run("审计对象：X-Agent Core v0.1.0", { size: 22, color: palette.primary }), {
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
  }),
  para(run("9 份并行分报告集成总报告", { size: 22, color: palette.primary }), {
    alignment: AlignmentType.CENTER,
    spacing: { after: 120 },
  }),
  new Paragraph({ children: [], pageBreakBefore: true }),
];

// ---------- TOC page ----------
const tocPage = [
  para(run("目录", { bold: true, size: 30, color: palette.dark }), {
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 160 },
  }),
  para(run("右键目录并选择“更新域”可刷新页码。", { italics: true, size: 18, color: palette.light }), {
    spacing: { after: 160 },
  }),
  toc(tocEntries),
  new Paragraph({ children: [], pageBreakBefore: true }),
];

// ---------- document ----------
const doc = new Document({
  features: { updateFields: true },
  styles: {
    default: {
      document: { run: { font, size: 22 } },
    },
  },
  sections: [
    {
      properties: {
        page: { margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } },
      },
      headers: {
        default: new Header({
          children: [
            para(run(docTitle || "X-Agent 商用交付差距审计报告", { bold: true, size: 18, color: palette.primary }), {
              alignment: AlignmentType.CENTER,
              spacing: { after: 40 },
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            para(new TextRun({ children: [PageNumber.CURRENT], font, size: 18, color: palette.primary }), {
              alignment: AlignmentType.CENTER,
            }),
          ],
        }),
      },
      children: [...cover, ...tocPage, ...bodyChildren],
    },
  ],
});

const buffer = await Packer.toBuffer(doc);
fs.writeFileSync(outputPath, buffer);
console.log(`OK blocks=${blocks.length} tocEntries=${tocEntries.length}`);
