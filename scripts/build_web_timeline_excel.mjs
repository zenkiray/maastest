import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..");
const outputPath = path.join(root, "excel", "bank_benchmark_web_app_timeline_bilingual.xlsx");

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

const rows = [
  {
    no: 1,
    phaseZh: "准备",
    taskZh: "确认压缩版 MVP 范围与云主机运行方式",
    effort: 0.5,
    start: "2026-06-08",
    end: "2026-06-08",
    workdayStart: 1,
    workdayEnd: 1,
    dependency: "None",
    deliverableZh: "MVP范围清单、排除项、单用户/云主机运行假设",
    acceptanceZh: "确认网页版只覆盖配置选择、任务执行、进度查看、Shell/页面结果查看；不做多用户权限和数据库化历史管理",
    phaseEn: "Preparation",
    taskEn: "Confirm compressed MVP scope and cloud-host runtime mode",
    deliverableEn: "MVP scope list, exclusions, single-user/cloud-host runtime assumptions",
    acceptanceEn: "Confirmed web app covers config selection, execution, progress, and result viewing; multi-user auth and database-backed history are excluded",
  },
  {
    no: 2,
    phaseZh: "准备",
    taskZh: "锁定测试数据、配置模板和现有 CLI 基线",
    effort: 0.5,
    start: "2026-06-08",
    end: "2026-06-08",
    workdayStart: 1,
    workdayEnd: 1,
    dependency: "MVP scope",
    deliverableZh: "数据校验结果、config.local.yaml样例、CLI运行命令清单",
    acceptanceZh: "UC1/UC2数据可校验通过；Qdrant、LLM、embedding、reranker配置可复用",
    phaseEn: "Preparation",
    taskEn: "Lock benchmark data, config templates, and current CLI baseline",
    deliverableEn: "Dataset validation result, config.local.yaml sample, CLI command checklist",
    acceptanceEn: "UC1/UC2 data passes validation and Qdrant/LLM/embedding/reranker config can be reused",
  },
  {
    no: 3,
    phaseZh: "CLI/接口封装",
    taskZh: "整理 CLI 调用封装与结果解析接口",
    effort: 1,
    start: "2026-06-09",
    end: "2026-06-09",
    workdayStart: 2,
    workdayEnd: 2,
    dependency: "Locked CLI baseline",
    deliverableZh: "统一执行命令、进度输出读取、raw/summary结果解析函数",
    acceptanceZh: "后端能调用UC1/UC2脚本并识别成功、失败、日志路径和关键指标",
    phaseEn: "CLI/API Wrapper",
    taskEn: "Prepare CLI invocation wrapper and result parser",
    deliverableEn: "Unified command invocation, progress output reader, raw/summary result parser",
    acceptanceEn: "Backend can invoke UC1/UC2 scripts and identify success, failure, log paths, and key metrics",
  },
  {
    no: 4,
    phaseZh: "开发",
    taskZh: "搭建网页版骨架和配置选择页面",
    effort: 1,
    start: "2026-06-10",
    end: "2026-06-10",
    workdayStart: 3,
    workdayEnd: 3,
    dependency: "CLI/API wrapper",
    deliverableZh: "Web服务、首页、配置文件列表、配置校验、敏感字段脱敏显示",
    acceptanceZh: "云主机上可启动页面；能选择config目录下的配置文件并看到脱敏后的核心配置",
    phaseEn: "Development",
    taskEn: "Scaffold web app and config selection page",
    deliverableEn: "Web service, home page, config list, config validation, masked secret display",
    acceptanceEn: "Page starts on cloud host; user can choose a config file and view masked core settings",
  },
  {
    no: 5,
    phaseZh: "开发",
    taskZh: "实现测试参数向导与任务启动",
    effort: 1,
    start: "2026-06-11",
    end: "2026-06-11",
    workdayStart: 4,
    workdayEnd: 4,
    dependency: "Web scaffold",
    deliverableZh: "UC1/UC2选择、limit、并发档位、轮次、stream、reranker开关、启动按钮",
    acceptanceZh: "页面选择可正确映射到现有CLI参数，并能启动dry-run和live-run",
    phaseEn: "Development",
    taskEn: "Implement parameter wizard and job start flow",
    deliverableEn: "UC1/UC2 selection, limit, concurrency, runs, stream, reranker switch, start button",
    acceptanceEn: "Page selections map to existing CLI parameters and can start dry-run and live-run jobs",
  },
  {
    no: 6,
    phaseZh: "开发",
    taskZh: "实现实时进度、日志尾部和结果表",
    effort: 1,
    start: "2026-06-12",
    end: "2026-06-12",
    workdayStart: 5,
    workdayEnd: 5,
    dependency: "Job start flow",
    deliverableZh: "进度条、active/ok/error、elapsed/ETA、日志尾部、summary表、raw明细表",
    acceptanceZh: "长请求期间页面持续刷新；跑完后不用读JSONL即可看到latency、TTFT、TPOT、tokens、错误和答案摘要",
    phaseEn: "Development",
    taskEn: "Implement live progress, log tail, and result tables",
    deliverableEn: "Progress bar, active/ok/error, elapsed/ETA, log tail, summary table, raw detail table",
    acceptanceEn: "Page refreshes during long requests and shows latency, TTFT, TPOT, tokens, errors, and answer summary without reading JSONL",
  },
  {
    no: 7,
    phaseZh: "联调",
    taskZh: "UC1/UC2端到端联调和结果导出",
    effort: 1,
    start: "2026-06-15",
    end: "2026-06-15",
    workdayStart: 6,
    workdayEnd: 6,
    dependency: "Result tables",
    deliverableZh: "UC1小样本、UC2小样本、错误样例、CSV/Excel或日志下载、基础运行手册",
    acceptanceZh: "UC1和UC2均可从页面完成一次小样本测试；失败场景能显示可读错误",
    phaseEn: "Integration",
    taskEn: "Run UC1/UC2 end-to-end tests and result export",
    deliverableEn: "UC1 smoke, UC2 smoke, error sample, CSV/Excel or log download, basic runbook",
    acceptanceEn: "UC1 and UC2 smoke tests can be completed from the UI and failures show readable errors",
  },
  {
    no: 8,
    phaseZh: "交付",
    taskZh: "云主机部署、验收修正与交付演示",
    effort: 1,
    start: "2026-06-16",
    end: "2026-06-16",
    workdayStart: 7,
    workdayEnd: 7,
    dependency: "E2E integration",
    deliverableZh: "云主机启动命令、部署说明、最终代码包、演示记录、已知限制清单",
    acceptanceZh: "用户可按文档在云主机启动网页，并独立完成一次UC1/UC2小样本测试",
    phaseEn: "Delivery",
    taskEn: "Cloud deployment, acceptance fixes, and delivery walkthrough",
    deliverableEn: "Cloud start command, deployment notes, final code package, walkthrough notes, known limitations",
    acceptanceEn: "User can start the web app on a cloud host and independently complete UC1/UC2 smoke tests",
  },
];

function writeTable(sheet, title, columns, tableRows, note) {
  const lastCol = excelCol(columns.length);
  const titleRange = sheet.getRange(`A1:${lastCol}1`);
  titleRange.values = [[title, ...Array(columns.length - 1).fill("")]];
  titleRange.format = {
    fill: { color: "#1F4E78" },
    font: { color: "#FFFFFF", bold: true, size: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
  };
  titleRange.format.rowHeightPx = 30;

  const noteRange = sheet.getRange(`A2:${lastCol}2`);
  noteRange.values = [[note, ...Array(columns.length - 1).fill("")]];
  noteRange.format = {
    fill: { color: "#EAF3F8" },
    font: { color: "#1F2937", italic: true },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    wrapText: true,
  };
  noteRange.format.rowHeightPx = 42;

  const headerRange = sheet.getRange(`A3:${lastCol}3`);
  headerRange.values = [columns.map((column) => column.label)];
  headerRange.format = {
    fill: { color: "#D9EAF7" },
    font: { color: "#000000", bold: true },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  headerRange.format.borders = { preset: "all", style: "thin", color: "#A6A6A6" };

  const bodyRange = sheet.getRange(`A4:${lastCol}${tableRows.length + 3}`);
  bodyRange.values = tableRows.map((row) => columns.map((column) => row[column.key] ?? ""));
  bodyRange.format = { verticalAlignment: "top", wrapText: true };
  bodyRange.format.borders = { preset: "all", style: "thin", color: "#D9D9D9" };

  sheet.freezePanes.freezeRows(3);
  for (let idx = 1; idx <= columns.length; idx += 1) {
    sheet.getRange(`${excelCol(idx)}:${excelCol(idx)}`).format.columnWidth = columns[idx - 1].width ?? 18;
  }
}

async function main() {
  const workbook = Workbook.create();
  const totalEffort = rows.reduce((sum, row) => sum + row.effort, 0);
  const noteZh = `压缩MVP排期：1名中级程序员，2026-06-08开始，2026-06-16结束；合计约${totalEffort}人日，分摊在7个工作日内完成。假设已有CLI和测试数据可复用，范围不含多用户权限、数据库化历史管理和复杂部署自动化。`;
  const noteEn = `Compressed MVP schedule: one mid-level developer, from 2026-06-08 to 2026-06-16; total ${totalEffort} person-days across 7 business days. Assumes reusable CLI and benchmark data; excludes multi-user auth, database-backed history, and complex deployment automation.`;

  writeTable(
    workbook.worksheets.add("中文排期"),
    "网页版测试程序压缩排期 - 中文",
    [
      { key: "no", label: "序号", width: 8 },
      { key: "phaseZh", label: "阶段", width: 16 },
      { key: "taskZh", label: "任务", width: 36 },
      { key: "effort", label: "工作量(人日)", width: 14 },
      { key: "start", label: "开始日期", width: 14 },
      { key: "end", label: "结束日期", width: 14 },
      { key: "workdayStart", label: "工作日起", width: 12 },
      { key: "workdayEnd", label: "工作日止", width: 12 },
      { key: "dependency", label: "依赖", width: 24 },
      { key: "deliverableZh", label: "交付物", width: 52 },
      { key: "acceptanceZh", label: "验收标准", width: 64 },
    ],
    rows,
    noteZh
  );

  writeTable(
    workbook.worksheets.add("English Schedule"),
    "Compressed Web Benchmark Runner Timeline - English",
    [
      { key: "no", label: "No.", width: 8 },
      { key: "phaseEn", label: "Phase", width: 18 },
      { key: "taskEn", label: "Task", width: 42 },
      { key: "effort", label: "Effort (PD)", width: 14 },
      { key: "start", label: "Start Date", width: 14 },
      { key: "end", label: "End Date", width: 14 },
      { key: "workdayStart", label: "Workday Start", width: 14 },
      { key: "workdayEnd", label: "Workday End", width: 14 },
      { key: "dependency", label: "Dependency", width: 24 },
      { key: "deliverableEn", label: "Deliverable", width: 56 },
      { key: "acceptanceEn", label: "Acceptance Criteria", width: 68 },
    ],
    rows,
    noteEn
  );

  for (const sheetName of ["中文排期", "English Schedule"]) {
    const png = await workbook.render({ sheetName, range: "A1:K12", scale: 1, format: "png" });
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
