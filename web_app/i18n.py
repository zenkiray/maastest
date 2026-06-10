from __future__ import annotations

from typing import Any


SUPPORTED_LANGUAGES = {
    "en": "English",
    "zh": "中文",
    "th": "ไทย",
}


TRANSLATIONS: dict[str, dict[str, str]] = {
    "brand": {"en": "MaaS Benchmark", "zh": "MaaS 基准测试", "th": "การทดสอบ MaaS"},
    "language": {"en": "Language", "zh": "语言", "th": "ภาษา"},
    "nav.home": {"en": "Home", "zh": "首页", "th": "หน้าแรก"},
    "nav.datasets": {"en": "Datasets", "zh": "数据集", "th": "ชุดข้อมูล"},
    "nav.qdrant": {"en": "Knowledge Index", "zh": "知识库索引", "th": "ดัชนีความรู้"},
    "nav.uc1": {"en": "UC1 FAQ QA", "zh": "UC1 问答测试", "th": "UC1 ถามตอบ FAQ"},
    "nav.uc2": {"en": "UC2 Call Insight", "zh": "UC2 呼叫洞察", "th": "UC2 วิเคราะห์สายสนทนา"},
    "nav.jobs": {"en": "Jobs", "zh": "作业", "th": "งาน"},
    "nav.reports": {"en": "Reports", "zh": "报告", "th": "รายงาน"},
    "nav.settings": {"en": "Settings", "zh": "设置", "th": "การตั้งค่า"},
    "nav.sign_out": {"en": "Sign out", "zh": "退出", "th": "ออกจากระบบ"},
    "home.title": {"en": "MaaS Benchmark Portal", "zh": "MaaS 基准测试门户", "th": "พอร์ทัลทดสอบ MaaS"},
    "home.description": {
        "en": "Manage synthetic datasets, initialize the knowledge index, run UC1/UC2 tests, and review business-readable reports.",
        "zh": "管理合成数据集、初始化知识库索引、执行 UC1/UC2 测试并查看业务可读报告。",
        "th": "จัดการชุดข้อมูลสังเคราะห์ สร้างดัชนีความรู้ รันการทดสอบ UC1/UC2 และดูรายงานสำหรับผู้ใช้งานธุรกิจ",
    },
    "home.datasets": {"en": "Datasets", "zh": "数据集", "th": "ชุดข้อมูล"},
    "home.datasets_desc": {"en": "Registered benchmark datasets", "zh": "已登记数据集数量", "th": "จำนวนชุดข้อมูลที่ลงทะเบียน"},
    "home.manage_datasets": {"en": "Manage datasets", "zh": "管理数据集", "th": "จัดการชุดข้อมูล"},
    "home.settings": {"en": "Settings", "zh": "系统配置", "th": "การตั้งค่า"},
    "home.settings_ready": {"en": "Ready", "zh": "就绪", "th": "พร้อม"},
    "home.settings_todo": {"en": "Todo", "zh": "待配置", "th": "ต้องตั้งค่า"},
    "home.settings_desc": {"en": "Model, Qdrant, login, and pricing settings", "zh": "模型、Qdrant、登录和计价配置", "th": "การตั้งค่าโมเดล Qdrant การเข้าสู่ระบบ และราคา"},
    "home.open_settings": {"en": "Open settings", "zh": "打开设置", "th": "เปิดการตั้งค่า"},
    "home.jobs": {"en": "Jobs", "zh": "作业", "th": "งาน"},
    "home.jobs_desc": {"en": "All running and historical tasks", "zh": "运行中和历史作业", "th": "งานที่กำลังรันและงานย้อนหลัง"},
    "home.view_jobs": {"en": "View jobs", "zh": "查看作业", "th": "ดูงาน"},
    "home.reports": {"en": "Reports", "zh": "历史报告", "th": "รายงาน"},
    "home.reports_desc": {"en": "Recent benchmark reports", "zh": "最近报告数量", "th": "รายงานล่าสุด"},
    "home.view_reports": {"en": "View reports", "zh": "查看报告", "th": "ดูรายงาน"},
    "home.recent_reports": {"en": "Recent Reports", "zh": "最近报告", "th": "รายงานล่าสุด"},
    "home.no_reports": {"en": "No reports yet.", "zh": "暂无报告。", "th": "ยังไม่มีรายงาน"},
    "home.recent_jobs": {"en": "Recent Jobs", "zh": "最近作业", "th": "งานล่าสุด"},
    "home.no_jobs": {"en": "No jobs yet.", "zh": "暂无作业。", "th": "ยังไม่มีงาน"},
    "table.job": {"en": "Job", "zh": "任务", "th": "งาน"},
    "table.type": {"en": "Type", "zh": "类型", "th": "ประเภท"},
    "table.status": {"en": "Status", "zh": "状态", "th": "สถานะ"},
    "table.dataset": {"en": "Dataset", "zh": "数据集", "th": "ชุดข้อมูล"},
    "table.started": {"en": "Started", "zh": "开始时间", "th": "เริ่มต้น"},
    "table.finished": {"en": "Finished", "zh": "结束时间", "th": "เสร็จสิ้น"},
    "table.details": {"en": "Details", "zh": "详情", "th": "รายละเอียด"},
    "action.delete_selected": {"en": "Delete selected", "zh": "删除所选", "th": "ลบรายการที่เลือก"},
    "action.delete_this": {"en": "Delete", "zh": "删除", "th": "ลบ"},
    "confirm.delete_selected": {"en": "Delete selected items? This cannot be undone.", "zh": "确认删除所选项目？此操作不可撤销。", "th": "ลบรายการที่เลือกหรือไม่? ไม่สามารถย้อนกลับได้"},
    "confirm.delete_dataset": {"en": "Delete this dataset? Uploaded files and metadata will be removed.", "zh": "确认删除此数据集？上传文件和元数据都会被删除。", "th": "ลบชุดข้อมูลนี้หรือไม่? ไฟล์ที่อัปโหลดและ metadata จะถูกลบ"},
    "confirm.delete_job": {"en": "Delete this job? Logs and linked report files will be removed.", "zh": "确认删除此作业？日志和关联报告文件都会被删除。", "th": "ลบงานนี้หรือไม่? log และไฟล์รายงานที่เกี่ยวข้องจะถูกลบ"},
    "confirm.delete_report": {"en": "Delete this report? Raw and summary report files will be removed.", "zh": "确认删除此报告？原始日志和摘要文件都会被删除。", "th": "ลบรายงานนี้หรือไม่? ไฟล์ raw และ summary จะถูกลบ"},
    "login.title": {"en": "MaaS Benchmark Portal", "zh": "MaaS 基准测试门户", "th": "พอร์ทัลทดสอบ MaaS"},
    "login.description": {"en": "Sign in to manage datasets, model settings, and benchmark reports.", "zh": "登录后可管理数据集、模型配置和测试报告。", "th": "เข้าสู่ระบบเพื่อจัดการชุดข้อมูล การตั้งค่าโมเดล และรายงานทดสอบ"},
    "login.username": {"en": "Username", "zh": "用户名", "th": "ชื่อผู้ใช้"},
    "login.password": {"en": "Password", "zh": "密码", "th": "รหัสผ่าน"},
    "login.sign_in": {"en": "Sign in", "zh": "登录", "th": "เข้าสู่ระบบ"},
    "login.error": {"en": "Invalid username or password.", "zh": "用户名或密码不正确。", "th": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
    "login.default_hint": {"en": "Default account is admin/admin. Please change it in Settings after first login.", "zh": "默认账号密码为 admin/admin，首次登录后建议在设置中修改。", "th": "บัญชีเริ่มต้นคือ admin/admin ควรเปลี่ยนในหน้าการตั้งค่าหลังเข้าสู่ระบบครั้งแรก"},
    "uc1.title": {"en": "FAQ QA Bot Test", "zh": "智能问答测试", "th": "ทดสอบบอทถามตอบ FAQ"},
    "uc1.description": {"en": "Validate whether the assistant can answer customer questions from approved knowledge base evidence.", "zh": "验证助手是否能基于已批准知识库证据回答客户问题。", "th": "ตรวจสอบว่าผู้ช่วยตอบคำถามลูกค้าจากหลักฐานในฐานความรู้ที่อนุมัติแล้วได้หรือไม่"},
    "uc2.title": {"en": "Call Insight Analytics Test", "zh": "呼叫洞察测试", "th": "ทดสอบวิเคราะห์ข้อมูลสายสนทนา"},
    "uc2.description": {"en": "Validate whether multi-agent analysis can summarize calls, check compliance, score quality, and combine account context.", "zh": "验证多 Agent 是否能完成通话摘要、合规检查、质检评分并结合账户上下文。", "th": "ตรวจสอบว่า multi-agent สามารถสรุปสาย ตรวจ compliance ให้คะแนนคุณภาพ และรวมข้อมูลบัญชีได้หรือไม่"},
    "uc.settings_not_ready": {"en": "Settings are not ready. Please complete model and Qdrant configuration before running this test.", "zh": "系统配置尚未完成，请先配置模型和 Qdrant。", "th": "การตั้งค่ายังไม่พร้อม กรุณาตั้งค่าโมเดลและ Qdrant ก่อนเริ่มทดสอบ"},
    "uc.open_settings": {"en": "Open Settings", "zh": "打开设置", "th": "เปิดการตั้งค่า"},
    "uc.test_flow": {"en": "Test Flow", "zh": "测试流程", "th": "ขั้นตอนการทดสอบ"},
    "uc.start_test": {"en": "Start Test", "zh": "启动测试", "th": "เริ่มทดสอบ"},
    "uc.dataset": {"en": "Dataset", "zh": "数据集", "th": "ชุดข้อมูล"},
    "uc.dataset_help": {"en": "Choose the uploaded or built-in synthetic benchmark dataset.", "zh": "选择上传或内置的合成测试数据集。", "th": "เลือกชุดข้อมูลสังเคราะห์ที่อัปโหลดหรือมีอยู่ในระบบ"},
    "uc.test_size": {"en": "Test Size", "zh": "测试规模", "th": "ขนาดการทดสอบ"},
    "uc.test_size_help": {"en": "The option label shows the actual number of cases that will run; Full uses all records in the selected dataset.", "zh": "选项名称会显示实际执行条数；全量测试会使用所选数据集中的全部记录。", "th": "ชื่อ option แสดงจำนวนเคสที่จะรันจริง; Full ใช้ข้อมูลทั้งหมดในชุดข้อมูลที่เลือก"},
    "uc.load_level": {"en": "Load Level", "zh": "压力等级", "th": "ระดับโหลด"},
    "uc.load_level_help": {"en": "Choose how many requests run in parallel. Formal sweep and custom pressure profiles are hidden for now.", "zh": "选择同时运行的请求数量；正式扫描和自定义压力暂时隐藏。", "th": "เลือกจำนวนคำขอที่รันพร้อมกัน โดยซ่อน Formal sweep และ Custom ไว้ก่อน"},
    "uc.answer_mode": {"en": "Answer Mode", "zh": "答复模式", "th": "โหมดคำตอบ"},
    "uc.answer_mode_help": {"en": "Streaming is required for formal TTFT and TPOT metrics.", "zh": "正式 TTFT 和 TPOT 指标需要流式。", "th": "ตัวชี้วัด TTFT และ TPOT อย่างเป็นทางการต้องใช้ streaming"},
    "uc.dry_run": {"en": "Dry Run", "zh": "试运行", "th": "ทดลองรัน"},
    "uc.dry_run_help": {"en": "Use dry run to verify the flow without spending tokens.", "zh": "试运行不消耗模型 token。", "th": "ใช้ทดลองขั้นตอนโดยไม่ใช้ token ของโมเดล"},
    "uc.evidence_ranking": {"en": "Evidence Ranking", "zh": "证据重排序", "th": "จัดอันดับหลักฐาน"},
    "uc.evidence_ranking_help": {"en": "Reranking improves evidence order when the service is configured.", "zh": "已配置时可提升证据排序质量。", "th": "reranker ช่วยจัดลำดับหลักฐานเมื่อมีการตั้งค่าบริการแล้ว"},
    "uc.advanced": {"en": "Advanced parameters", "zh": "高级参数", "th": "พารามิเตอร์ขั้นสูง"},
    "uc.custom_limit": {"en": "Custom case limit", "zh": "自定义案例数", "th": "จำนวนเคสแบบกำหนดเอง"},
    "uc.custom_limit_help": {"en": "Only used when Test Size is Custom; 0 means all.", "zh": "仅自定义规模使用，0 表示全量。", "th": "ใช้เฉพาะเมื่อเลือก Custom; 0 หมายถึงทั้งหมด"},
    "uc.custom_concurrency": {"en": "Custom concurrency levels", "zh": "自定义并发", "th": "ระดับ concurrency แบบกำหนดเอง"},
    "uc.custom_concurrency_help": {"en": "Use one number for fixed pressure, or comma-separated values for a sweep, for example 4 or 4,8.", "zh": "固定压力填一个数字；扫描多个档位用逗号分隔，例如 4 或 4,8。", "th": "ใส่ตัวเลขเดียวสำหรับโหลดคงที่ หรือคั่นด้วย comma สำหรับ sweep เช่น 4 หรือ 4,8"},
    "uc.custom_runs": {"en": "Custom run rounds", "zh": "自定义轮次", "th": "จำนวนรอบแบบกำหนดเอง"},
    "uc.custom_runs_help": {"en": "Only used when Load Level is Custom.", "zh": "仅自定义压力使用。", "th": "ใช้เฉพาะเมื่อ Load Level เป็น Custom"},
    "uc.timeout": {"en": "Timeout seconds", "zh": "超时时间", "th": "เวลาหมดอายุเป็นวินาที"},
    "uc.timeout_help": {"en": "Maximum wait time for one API request.", "zh": "单次 API 请求最长等待时间。", "th": "เวลารอสูงสุดสำหรับคำขอ API หนึ่งครั้ง"},
    "uc.start_benchmark": {"en": "Start benchmark", "zh": "启动测试", "th": "เริ่ม benchmark"},
    "option.smoke": {"en": "Smoke - quick check", "zh": "冒烟测试", "th": "Smoke - ตรวจเร็ว"},
    "option.standard": {"en": "Standard - business review", "zh": "标准测试", "th": "Standard - ตรวจเชิงธุรกิจ"},
    "option.full": {"en": "Full - benchmark run", "zh": "全量测试", "th": "Full - ทดสอบเต็มชุด"},
    "option.custom": {"en": "Custom - use advanced value", "zh": "自定义", "th": "กำหนดเอง"},
    "option.single": {"en": "Single - lowest cost", "zh": "单线程", "th": "Single - ต้นทุนต่ำสุด"},
    "option.moderate": {"en": "Moderate - 4 parallel requests", "zh": "中等压力 4 并发", "th": "Moderate - 4 คำขอพร้อมกัน"},
    "option.high": {"en": "High - 16 parallel requests", "zh": "高压测试 16 并发", "th": "High - 16 คำขอพร้อมกัน"},
    "option.sweep": {"en": "Formal sweep - 1,4,16,64", "zh": "正式扫描 1,4,16,64", "th": "Formal sweep - 1,4,16,64"},
    "option.streaming": {"en": "Streaming metrics", "zh": "流式正式指标", "th": "ตัวชี้วัดแบบ streaming"},
    "option.no_stream": {"en": "Simple no-stream", "zh": "简化非流式", "th": "แบบไม่ streaming"},
    "option.live": {"en": "Live API run", "zh": "调用真实 API", "th": "รัน API จริง"},
    "option.dry": {"en": "Dry run without API calls", "zh": "不调用外部 API", "th": "ทดลองโดยไม่เรียก API ภายนอก"},
    "option.reranker_on": {"en": "Use reranker", "zh": "启用重排序", "th": "ใช้ reranker"},
    "option.reranker_off": {"en": "Skip reranker", "zh": "跳过重排序", "th": "ข้าม reranker"},
    "flow.parallel_specialist": {"en": "Parallel specialist analysis", "zh": "并行专家分析", "th": "วิเคราะห์โดยผู้เชี่ยวชาญแบบขนาน"},
    "flow.account_branch": {"en": "Account-context branch", "zh": "账户上下文分支", "th": "สายงานบริบทบัญชี"},
    "flow.account_branch_help": {"en": "Runs internally in tool-call order", "zh": "内部按工具调用顺序执行", "th": "รันตามลำดับการเรียกเครื่องมือภายใน"},
    "job.title": {"en": "Benchmark Job", "zh": "测试任务", "th": "งานทดสอบ"},
    "job.import_title": {"en": "Knowledge Index Import", "zh": "知识库索引导入", "th": "นำเข้าดัชนีความรู้"},
    "job.benchmark_kind": {"en": "Benchmark run", "zh": "测试执行", "th": "งานทดสอบ"},
    "job.import_kind": {"en": "Preparation task", "zh": "准备任务", "th": "งานเตรียมข้อมูล"},
    "job.dataset": {"en": "Dataset", "zh": "数据集", "th": "ชุดข้อมูล"},
    "job.progress": {"en": "Progress", "zh": "进度", "th": "ความคืบหน้า"},
    "job.message": {"en": "Message", "zh": "消息", "th": "ข้อความ"},
    "job.stop": {"en": "Stop test", "zh": "停止测试", "th": "หยุดทดสอบ"},
    "job.stop_import": {"en": "Stop import", "zh": "停止导入", "th": "หยุดนำเข้า"},
    "job.stop_confirm": {"en": "Stop this benchmark job?", "zh": "确认停止当前测试任务？", "th": "หยุดงานทดสอบนี้?"},
    "job.stop_import_confirm": {"en": "Stop this import task?", "zh": "确认停止当前导入任务？", "th": "หยุดงานนำเข้านี้?"},
    "job.import_progress": {"en": "Import Progress", "zh": "导入进度", "th": "ความคืบหน้าการนำเข้า"},
    "job.import_mode": {"en": "Import Mode", "zh": "导入模式", "th": "โหมดนำเข้า"},
    "job.collection": {"en": "Collection", "zh": "集合", "th": "Collection"},
    "job.articles": {"en": "Articles", "zh": "文章数", "th": "บทความ"},
    "job.imported_chunks": {"en": "Imported chunks", "zh": "已导入知识片段", "th": "ชิ้นส่วนที่นำเข้าแล้ว"},
    "job.total_chunks": {"en": "Total chunks", "zh": "知识片段总数", "th": "จำนวนชิ้นส่วนทั้งหมด"},
    "job.selected_params": {"en": "Selected Parameters", "zh": "已选测试参数", "th": "พารามิเตอร์ที่เลือก"},
    "job.process_flow": {"en": "Process Flow", "zh": "执行流程", "th": "ขั้นตอนการทำงาน"},
    "job.execution_channels": {"en": "Execution Channels", "zh": "执行通道", "th": "ช่องทางการทำงาน"},
    "job.stage_summary": {"en": "Stage Summary", "zh": "阶段统计", "th": "สรุปขั้นตอน"},
    "job.stage_summary_help": {"en": "Shows active worker threads in each stage, plus completed and failed cases.", "zh": "展示每个阶段当前活跃线程，以及已完成和异常的案例数。", "th": "แสดง worker ที่กำลังทำงานในแต่ละขั้นตอน รวมถึงเคสที่เสร็จและผิดพลาด"},
    "job.technical_details": {"en": "Technical details", "zh": "技术细节", "th": "รายละเอียดทางเทคนิค"},
    "job.log_tail": {"en": "Log Tail", "zh": "日志尾部", "th": "ท้าย log"},
    "job.view_report": {"en": "View report", "zh": "查看报告", "th": "ดูรายงาน"},
    "job.model_output": {"en": "Model Output", "zh": "大模型输出", "th": "ผลลัพธ์โมเดล"},
    "job.waiting_model": {"en": "Waiting for model response...", "zh": "等待大模型返回结果...", "th": "กำลังรอผลลัพธ์จากโมเดล..."},
    "job.errors": {"en": "errors", "zh": "异常", "th": "ข้อผิดพลาด"},
    "job.test_size": {"en": "Test Size", "zh": "测试规模", "th": "ขนาดการทดสอบ"},
    "job.load_level": {"en": "Load Level", "zh": "压力等级", "th": "ระดับโหลด"},
    "job.actual_concurrency": {"en": "Actual Concurrency", "zh": "实际并发", "th": "concurrency จริง"},
    "job.actual_concurrency_help": {"en": "Comma means sequential sweep.", "zh": "逗号表示顺序扫描多个档位。", "th": "comma หมายถึง sweep ตามลำดับ"},
    "job.run_rounds": {"en": "Run Rounds", "zh": "运行轮次", "th": "จำนวนรอบ"},
    "job.case_limit": {"en": "Case Limit", "zh": "案例数限制", "th": "จำกัดจำนวนเคส"},
    "job.case_limit_help": {"en": "0 means full set.", "zh": "0 表示全量。", "th": "0 หมายถึงทั้งหมด"},
    "job.timeout": {"en": "Timeout", "zh": "超时时间", "th": "timeout"},
    "job.answer_mode": {"en": "Answer Mode", "zh": "答复模式", "th": "โหมดคำตอบ"},
    "job.dry_run": {"en": "Dry Run", "zh": "试运行", "th": "ทดลองรัน"},
    "job.evidence_ranking": {"en": "Evidence Ranking", "zh": "证据重排序", "th": "จัดอันดับหลักฐาน"},
    "status.pending": {"en": "Pending", "zh": "未开始", "th": "รอดำเนินการ"},
    "status.running": {"en": "Running", "zh": "执行中", "th": "กำลังรัน"},
    "status.done": {"en": "Done", "zh": "已完成", "th": "เสร็จแล้ว"},
    "status.error": {"en": "Error", "zh": "异常", "th": "ผิดพลาด"},
    "metric.active": {"en": "Active", "zh": "活跃线程", "th": "กำลังทำงาน"},
    "metric.done": {"en": "Done", "zh": "已完成", "th": "เสร็จแล้ว"},
    "metric.error": {"en": "Error", "zh": "异常", "th": "ผิดพลาด"},
    "metric.avg": {"en": "Avg", "zh": "平均耗时", "th": "เฉลี่ย"},
    "metric.status": {"en": "Status", "zh": "阶段状态", "th": "สถานะ"},
    "stage.load_question": {"en": "Load Question", "zh": "读取问题", "th": "โหลดคำถาม"},
    "stage.embed_query": {"en": "Embed Query", "zh": "生成问题向量", "th": "สร้างเวกเตอร์คำถาม"},
    "stage.search_knowledge": {"en": "Search Knowledge Base", "zh": "检索知识库", "th": "ค้นฐานความรู้"},
    "stage.rank_evidence": {"en": "Rank Evidence", "zh": "证据重排序", "th": "จัดอันดับหลักฐาน"},
    "stage.generate_answer": {"en": "Generate Answer", "zh": "生成答复", "th": "สร้างคำตอบ"},
    "stage.record_metrics": {"en": "Record Metrics", "zh": "记录指标", "th": "บันทึกตัวชี้วัด"},
    "stage.report": {"en": "Report", "zh": "生成报告", "th": "รายงาน"},
    "stage.load_transcript": {"en": "Load Transcript", "zh": "读取通话记录", "th": "โหลดบันทึกการสนทนา"},
    "stage.summary": {"en": "Summary Agent", "zh": "摘要分析", "th": "Agent สรุป"},
    "stage.sentiment": {"en": "Sentiment Agent", "zh": "情绪分析", "th": "Agent วิเคราะห์อารมณ์"},
    "stage.compliance": {"en": "Compliance Agent", "zh": "合规检查", "th": "Agent ตรวจ compliance"},
    "stage.qa_score": {"en": "QA Score Agent", "zh": "质检评分", "th": "Agent ให้คะแนน QA"},
    "stage.intent_outcome": {"en": "Intent Agent", "zh": "意图与结果", "th": "Agent เจตนาและผลลัพธ์"},
    "stage.account_tool_call": {"en": "Account Tool Call", "zh": "账户工具调用", "th": "เรียกเครื่องมือบัญชี"},
    "stage.account_lookup": {"en": "Account Lookup", "zh": "查询账户", "th": "ค้นข้อมูลบัญชี"},
    "stage.account_context": {"en": "Account Context", "zh": "账户上下文", "th": "บริบทบัญชี"},
    "stage.synthesizer": {"en": "Final Insight", "zh": "汇总洞察", "th": "สรุป insight สุดท้าย"},
    "stage.validate_dataset": {"en": "Validate Dataset", "zh": "校验数据集", "th": "ตรวจชุดข้อมูล"},
    "stage.chunk_knowledge": {"en": "Split Knowledge", "zh": "拆分知识库", "th": "แบ่งความรู้"},
    "stage.prepare_collection": {"en": "Prepare Index", "zh": "准备索引", "th": "เตรียมดัชนี"},
    "stage.embed_batch": {"en": "Create Embeddings", "zh": "生成向量", "th": "สร้าง embeddings"},
    "stage.upsert_vectors": {"en": "Import Index", "zh": "导入索引", "th": "นำเข้าดัชนี"},
    "stage.complete": {"en": "Complete", "zh": "完成", "th": "เสร็จสิ้น"},
    "type.local_python": {"en": "Python", "zh": "本地 Python", "th": "Python ภายใน"},
    "type.embedding_model": {"en": "Embedding", "zh": "Embedding 模型", "th": "โมเดล Embedding"},
    "type.qdrant": {"en": "Qdrant", "zh": "Qdrant 检索", "th": "Qdrant"},
    "type.rerank_model": {"en": "Rerank", "zh": "重排序模型", "th": "โมเดล rerank"},
    "type.llm_model": {"en": "LLM", "zh": "大模型", "th": "LLM"},
    "type.local_record": {"en": "Record", "zh": "本地记录", "th": "บันทึกภายใน"},
}


def normalize_lang(value: str | None) -> str:
    if value in SUPPORTED_LANGUAGES:
        return value
    return "en"


def request_lang(request: Any) -> str:
    query_lang = normalize_lang(request.query_params.get("lang") if request else None)
    if request and request.query_params.get("lang") in SUPPORTED_LANGUAGES:
        return query_lang
    return normalize_lang(request.cookies.get("benchmark_lang") if request else None)


def translate(request: Any, key: str, default: str | None = None) -> str:
    lang = request_lang(request)
    row = TRANSLATIONS.get(key)
    if not row:
        return default if default is not None else key
    return row.get(lang) or row.get("en") or default or key


def pick_text(request: Any, en: str, zh: str, th: str | None = None) -> str:
    lang = request_lang(request)
    if lang == "zh":
        return zh
    if lang == "th":
        return th or en
    return en


def language_options(request: Any) -> list[dict[str, Any]]:
    current = request_lang(request)
    return [{"code": code, "label": label, "selected": code == current} for code, label in SUPPORTED_LANGUAGES.items()]
