import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const reviewPath = path.join(root, "review", "chinese_review_tables.json");
const outputPath = path.join(root, "excel", "maas_synthetic_benchmark_dataset_review_cn_v3.xlsx");

function excelCol(index) {
  let n = index;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function stringifyCell(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
  if (Array.isArray(value)) return value.join(", ");
  return JSON.stringify(value, null, 2);
}

function writeTable(sheet, title, columns, rows) {
  const titleRange = sheet.getRange(`A1:${excelCol(columns.length)}1`);
  titleRange.values = [[title, ...Array(columns.length - 1).fill("")]];
  titleRange.format = {
    fill: { color: "#1F4E78" },
    font: { color: "#FFFFFF", bold: true, size: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  titleRange.format.rowHeightPx = 30;

  const headerRange = sheet.getRange(`A2:${excelCol(columns.length)}2`);
  headerRange.values = [columns.map((column) => column.label)];
  headerRange.format = {
    fill: { color: "#D9EAF7" },
    font: { color: "#000000", bold: true },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  headerRange.format.borders = { preset: "all", style: "thin", color: "#A6A6A6" };

  if (rows.length > 0) {
    const bodyRange = sheet.getRange(`A3:${excelCol(columns.length)}${rows.length + 2}`);
    bodyRange.values = rows.map((row) => columns.map((column) => stringifyCell(row[column.key])));
    bodyRange.format = { verticalAlignment: "top", wrapText: true };
    bodyRange.format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };
  }

  sheet.freezePanes.freezeRows(2);
  for (let idx = 1; idx <= columns.length; idx += 1) {
    sheet.getRange(`${excelCol(idx)}:${excelCol(idx)}`).format.columnWidth = columns[idx - 1].width ?? 18;
  }
}

async function main() {
  const review = JSON.parse(await fs.readFile(reviewPath, "utf8"));
  const workbook = Workbook.create();

  writeTable(workbook.worksheets.add("说明"), "中文审阅说明", [
    { key: "项目", label: "项目", width: 24 },
    { key: "说明", label: "说明", width: 100 },
  ], review["说明"]);

  const coverageRows = [
    ...review["覆盖统计"],
  ];
  const categoryCounts = {};
  for (const row of review["UC1_知识库"]) categoryCounts[row["主题大类"]] = (categoryCounts[row["主题大类"]] ?? 0) + 1;
  for (const [key, value] of Object.entries(categoryCounts)) coverageRows.push({ 类别: "UC1主题覆盖", 指标: key, 数值: value, 说明: "按客户要求覆盖银行主题" });
  const difficultyCounts = {};
  for (const row of review["UC1_FAQ"]) difficultyCounts[row["难度"]] = (difficultyCounts[row["难度"]] ?? 0) + 1;
  for (const [key, value] of Object.entries(difficultyCounts)) coverageRows.push({ 类别: "FAQ难度", 指标: key, 数值: value, 说明: "目标为60/30/10" });
  const bucketCounts = {};
  for (const row of review["UC2_通话"]) bucketCounts[row["长度桶"]] = (bucketCounts[row["长度桶"]] ?? 0) + 1;
  for (const [key, value] of Object.entries(bucketCounts)) coverageRows.push({ 类别: "通话长度桶", 指标: key, 数值: value, 说明: "短/中/长分布" });
  const callTypeCounts = {};
  for (const row of review["UC2_通话"]) callTypeCounts[row["通话类型"]] = (callTypeCounts[row["通话类型"]] ?? 0) + 1;
  for (const [key, value] of Object.entries(callTypeCounts)) coverageRows.push({ 类别: "通话类型", 指标: key, 数值: value, 说明: "咨询/争议、入催、外催" });

  writeTable(workbook.worksheets.add("覆盖统计"), "覆盖统计", [
    { key: "类别", label: "类别", width: 20 },
    { key: "指标", label: "指标", width: 32 },
    { key: "数值", label: "数值", width: 12 },
    { key: "说明", label: "说明", width: 72 },
  ], coverageRows);

  writeTable(workbook.worksheets.add("UC1_知识库"), "UC1 FAQ QA Bot - 中文知识库审阅", [
    { key: "article_id", label: "文章ID", width: 16 },
    { key: "产品/服务", label: "产品/服务", width: 32 },
    { key: "主题大类", label: "主题大类", width: 24 },
    { key: "主题", label: "主题", width: 34 },
    { key: "标题", label: "标题", width: 48 },
    { key: "中文正文", label: "中文正文", width: 120 },
    { key: "来源锚点", label: "来源锚点", width: 34 },
    { key: "估算Token", label: "估算Token", width: 14 },
    { key: "是否合成数据", label: "是否合成数据", width: 16 },
  ], review["UC1_知识库"]);

  writeTable(workbook.worksheets.add("UC1_FAQ"), "UC1 FAQ QA Bot - 中文问题审阅", [
    { key: "question_id", label: "问题ID", width: 16 },
    { key: "产品/服务", label: "产品/服务", width: 32 },
    { key: "主题大类", label: "主题大类", width: 24 },
    { key: "难度", label: "难度", width: 16 },
    { key: "中文问题", label: "中文问题", width: 78 },
    { key: "预期引用文章ID", label: "预期引用文章ID", width: 36 },
    { key: "预期引用主题", label: "预期引用主题", width: 70 },
    { key: "回答要求", label: "回答要求", width: 86 },
    { key: "估算Token", label: "估算Token", width: 14 },
    { key: "是否合成数据", label: "是否合成数据", width: 16 },
  ], review["UC1_FAQ"]);

  writeTable(workbook.worksheets.add("UC2_通话"), "UC2 Call Insight Analytics - 中文通话审阅", [
    { key: "transcript_id", label: "通话ID", width: 18 },
    { key: "产品/服务", label: "产品/服务", width: 34 },
    { key: "长度桶", label: "长度桶", width: 12 },
    { key: "通话类型", label: "通话类型", width: 22 },
    { key: "customer_id", label: "客户ID", width: 18 },
    { key: "account_id", label: "账户ID", width: 34 },
    { key: "主题", label: "主题", width: 34 },
    { key: "预估Token", label: "预估Token", width: 14 },
    { key: "预期工具调用", label: "预期工具调用", width: 46 },
    { key: "中文审阅摘要", label: "中文审阅摘要", width: 120 },
    { key: "是否合成数据", label: "是否合成数据", width: 16 },
  ], review["UC2_通话"]);

  writeTable(workbook.worksheets.add("UC2_账户"), "UC2 Mock Account Lookup - 中文账户审阅", [
    { key: "customer_id", label: "客户ID", width: 18 },
    { key: "account_id", label: "账户ID", width: 34 },
    { key: "产品/服务", label: "产品/服务", width: 34 },
    { key: "客户画像", label: "客户画像", width: 44 },
    { key: "状态", label: "状态", width: 12 },
    { key: "逾期天数", label: "逾期天数", width: 12 },
    { key: "未偿余额THB", label: "未偿余额THB", width: 18 },
    { key: "最低应还THB", label: "最低应还THB", width: 18 },
    { key: "上次还款日期", label: "上次还款日期", width: 18 },
    { key: "上次还款金额THB", label: "上次还款金额THB", width: 20 },
    { key: "是否合成数据", label: "是否合成数据", width: 16 },
  ], review["UC2_账户"]);

  for (const sheetName of ["说明", "覆盖统计", "UC1_知识库", "UC1_FAQ", "UC2_通话", "UC2_账户"]) {
    const png = await workbook.render({ sheetName, range: "A1:H18", scale: 1, format: "png" });
    if (!png) throw new Error(`Render failed: ${sheetName}`);
  }

  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const xlsx = await SpreadsheetFile.exportXlsx(workbook);
  await xlsx.save(outputPath);
  console.log(outputPath);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
