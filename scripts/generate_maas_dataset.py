#!/usr/bin/env python3
"""Generate MaaS benchmark synthetic data.

The formal benchmark data is Thai-dominant with English banking terms. A
Chinese review table is generated from the same synthetic records for business
review. No real customer data or credentials are used.
"""

from __future__ import annotations

import json
import random
import re
from datetime import date, timedelta
from pathlib import Path


SEED = 20260609
BASE_DATE = date(2026, 6, 9)
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmark_data"
REVIEW = ROOT / "review"


def estimate_tokens(text: str) -> int:
    thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", text))
    chinese_chars = len(re.findall(r"[\u4E00-\u9FFF]", text))
    latin_terms = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9_./:-]*", text))
    punctuation = len(re.findall(r"[^\w\s\u0E00-\u0E7F\u4E00-\u9FFF]", text))
    return max(1, round(thai_chars / 2.75 + chinese_chars / 1.55 + latin_terms * 1.12 + punctuation * 0.12))


def thai_ratio(text: str) -> float:
    thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", text))
    latin_chars = len(re.findall(r"[A-Za-z]", text))
    total = thai_chars + latin_chars
    return 0.0 if total == 0 else thai_chars / total


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


SOURCE_ANCHORS = [
    {
        "source_id": "Bank_CARD_FAQ",
        "url": "https://example.com/maas-benchmark/source/card-faq",
        "notes": "card application, card status, lost/replacement card, card suspension, payment due date and service channels",
    },
    {
        "source_id": "Bank_LOAN_FAQ",
        "url": "https://example.com/maas-benchmark/source/loan-faq",
        "notes": "loan applicant qualifications, documents, repayment and document request flows used only as public reference for plausible CardX/AutoX synthetic content",
    },
    {
        "source_id": "Bank_CARDX_PERSONAL_LOANS",
        "url": "https://example.com/maas-benchmark/source/personal-loans",
        "notes": "CardX SPEEDY CASH and CardX SPEEDY LOAN product positioning",
    },
    {
        "source_id": "Bank_AUTOX_NGERN_CHAIYO",
        "url": "https://example.com/maas-benchmark/source/autox-title-loan",
        "notes": "AutoX / Ngern Chaiyo title loan channels and financial inclusion positioning",
    },
]


TOPICS = [
    {
        "topic_id": "cardx_credit_card_application",
        "category": "credit_cards",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ"],
        "title_th": "การสมัครบัตรเครดิต CardX และ e-KYC",
        "title_zh": "CardX信用卡申请与e-KYC",
        "details_th": [
            "ลูกค้าสมัครบัตรเครดิต CardX ผ่านช่องทางที่กำหนด โดยต้องยืนยันตัวตนและให้ consent สำหรับตรวจสอบคุณสมบัติ",
            "เงื่อนไขทั่วไปใช้ข้อมูลอายุ รายได้ เอกสาร KYC ประวัติสินเชื่อ และผลตรวจจากระบบ risk rule",
            "ถ้าเอกสารไม่ครบ เจ้าหน้าที่แจ้งรายการที่ต้อง补ส่งผ่าน official channel และไม่ขอ OTP, PIN หรือ password",
        ],
        "details_zh": [
            "客户通过指定渠道申请CardX信用卡，需要完成身份验证并授权资格审核。",
            "资格判断参考年龄、收入、KYC文件、信用记录和风险规则。",
            "如资料不完整，坐席只通过官方渠道提示补件，不索要OTP、PIN或password。",
        ],
    },
    {
        "topic_id": "cardx_statement_minimum_payment",
        "category": "credit_cards",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ"],
        "title_th": "statement, due date และ minimum payment ของ CardX",
        "title_zh": "CardX账单、到期日与最低还款",
        "details_th": [
            "statement แสดงยอดใช้จ่าย รอบบัญชี due date minimum payment total outstanding และค่าธรรมเนียมถ้ามี",
            "ลูกค้าชำระผ่าน CardX official channel, direct debit, ATM/CDM หรือช่องทางรับชำระที่กำหนด โดยสถานะขึ้นกับ cut-off และ clearing",
            "การจ่ายขั้นต่ำต่อเนื่องทำให้เกิด interest และใช้เวลานานขึ้นในการปิดยอดทั้งหมด",
        ],
        "details_zh": [
            "statement展示消费、账期、due date、minimum payment、total outstanding和可能的费用。",
            "还款可通过CardX官方渠道、direct debit、ATM/CDM或指定渠道完成，状态受cut-off和clearing影响。",
            "持续只还最低额会产生interest，并拉长结清时间。",
        ],
    },
    {
        "topic_id": "cardx_credit_limit_card_control",
        "category": "credit_cards",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ"],
        "title_th": "วงเงินบัตร CardX, temporary limit และ Card Control",
        "title_zh": "CardX额度、临时额度与Card Control",
        "details_th": [
            "ลูกค้าสามารถสอบถามวงเงินคงเหลือ ยอดที่ต้องชำระ และ payment due date ผ่านช่องทางบริการ",
            "temporary credit limit ต้องยืนยันตัวตนและขึ้นกับเกณฑ์อนุมัติของบริษัท",
            "กรณีบัตรหายหรือสงสัย fraud ลูกค้าควร suspend card, block card หรือขอ replacement ผ่าน CardX official service channel",
        ],
        "details_zh": [
            "客户可通过服务渠道查询可用额度、应还金额和payment due date。",
            "temporary credit limit需要身份验证，并受审批规则约束。",
            "卡片遗失或疑似欺诈时，应通过CardX/Bank渠道暂停、冻结或申请补卡。",
        ],
    },
    {
        "topic_id": "cardx_installment_rewards",
        "category": "credit_cards",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ"],
        "title_th": "installment plan, reward points และ cashback ของ CardX",
        "title_zh": "CardX分期、积分与返现",
        "details_th": [
            "รายการที่เข้าเกณฑ์สามารถเปลี่ยนเป็น installment plan โดยแสดง tenor, monthly installment, interest และ fee ก่อนยืนยัน",
            "reward points หรือ cashback ขึ้นกับ eligible spending, merchant category, campaign period และ cap",
            "การคืนสินค้า, reversal หรือ dispute อาจทำให้ points/cashback ถูกปรับกลับ",
        ],
        "details_zh": [
            "符合条件的交易可转为installment plan，确认前展示tenor、monthly installment、interest和fee。",
            "reward points或cashback取决于eligible spending、merchant category、campaign period和cap。",
            "退货、reversal或dispute可能导致积分/返现冲回。",
        ],
    },
    {
        "topic_id": "cardx_speedy_cash",
        "category": "personal_loans",
        "product": "CardX SPEEDY CASH",
        "source_ids": ["Bank_CARDX_PERSONAL_LOANS"],
        "title_th": "CardX SPEEDY CASH วงเงินหมุนเวียนไม่ใช้หลักประกัน",
        "title_zh": "CardX SPEEDY CASH无抵押循环额度",
        "details_th": [
            "CardX SPEEDY CASH เป็นสินเชื่อหมุนเวียนที่ไม่ต้องใช้หลักประกันหรือผู้ค้ำประกันตามข้อมูลผลิตภัณฑ์",
            "ลูกค้าสามารถใช้วงเงินเพื่อเบิกเงินสดหรือโอนเงินตามช่องทางที่รองรับ โดยต้องอยู่ในวงเงินที่ได้รับอนุมัติ",
            "เจ้าหน้าที่ควรอธิบาย interest, fee, repayment due date และผลของการจ่ายล่าช้าอย่างชัดเจน",
        ],
        "details_zh": [
            "CardX SPEEDY CASH是无抵押、无担保人的循环信用产品。",
            "客户可在获批额度内通过支持渠道取现或转账。",
            "坐席应清楚说明interest、fee、repayment due date和逾期后果。",
        ],
    },
    {
        "topic_id": "cardx_speedy_loan",
        "category": "personal_loans",
        "product": "CardX SPEEDY LOAN",
        "source_ids": ["Bank_CARDX_PERSONAL_LOANS", "Bank_LOAN_FAQ"],
        "title_th": "CardX SPEEDY LOAN และ repayment schedule",
        "title_zh": "CardX SPEEDY LOAN与还款计划",
        "details_th": [
            "CardX SPEEDY LOAN เป็น personal loan สำหรับใช้จ่ายตามต้องการ โดยมีระยะเวลาผ่อนชำระได้สูงสุดตามผลิตภัณฑ์ที่กำหนด",
            "ผู้สมัครต้องผ่านเกณฑ์อายุ รายได้ เอกสาร และการพิจารณาความสามารถในการชำระหนี้",
            "repayment schedule แสดง due date, installment, principal, interest และ remaining balance",
        ],
        "details_zh": [
            "CardX SPEEDY LOAN是个人现金贷款，可按产品规则分期偿还。",
            "申请人需满足年龄、收入、文件和还款能力评估要求。",
            "repayment schedule展示due date、installment、principal、interest和remaining balance。",
        ],
    },
    {
        "topic_id": "autox_ngern_chaiyo_title_loan",
        "category": "auto_title_loans",
        "product": "AutoX / Ngern Chaiyo title loan",
        "source_ids": ["Bank_AUTOX_NGERN_CHAIYO"],
        "title_th": "AutoX / Ngern Chaiyo title loan และช่องทางบริการ",
        "title_zh": "AutoX / Ngern Chaiyo车辆/产权贷款与服务渠道",
        "details_th": [
            "AutoX ให้บริการ title loan ผ่านแบรนด์ Ngern Chaiyo ทั้งช่องทาง online และ offline",
            "ช่องทางบริการครอบคลุมสาขา Ngern Chaiyo, app, Line Connect, agent, home delivery personnel และ partners",
            "เจ้าหน้าที่ต้องเน้นความเข้าใจ เข้าถึงง่าย และเชื่อถือได้ โดยอธิบายเงื่อนไขก่อนลูกค้าตัดสินใจ",
        ],
        "details_zh": [
            "AutoX是title loan服务方，品牌为Ngern Chaiyo，覆盖线上和线下渠道。",
            "服务渠道包括Ngern Chaiyo分行、App、Line Connect、代理、上门人员和合作伙伴。",
            "坐席需强调理解客户、可触达和可信赖，在客户决定前说明条件。",
        ],
    },
    {
        "topic_id": "autox_vehicle_document_repayment",
        "category": "auto_title_loans",
        "product": "AutoX / Ngern Chaiyo title loan",
        "source_ids": ["Bank_LOAN_FAQ", "Bank_AUTOX_NGERN_CHAIYO"],
        "title_th": "เอกสารรถ, collateral, repayment และ overdue ของ AutoX",
        "title_zh": "AutoX车辆文件、抵押、还款与逾期",
        "details_th": [
            "สินเชื่อที่เกี่ยวกับรถต้องตรวจเอกสารประจำตัว ทะเบียนบ้าน statement รายได้ และ vehicle registration book ตามประเภทสินเชื่อ",
            "การชำระค่างวดสามารถอ้างอิงช่องทางดิจิทัลและช่องทางชำระที่รองรับ พร้อมตรวจยอดล่าสุดก่อนชำระ",
            "เมื่อ overdue เจ้าหน้าที่ต้องแจ้งวัตถุประสงค์การติดต่อ ยอดค้าง ช่องทางชำระ และตัวเลือกช่วยเหลือโดยไม่ข่มขู่ลูกค้า",
        ],
        "details_zh": [
            "车相关贷款需按类型核验身份证明、户籍、流水、收入和vehicle registration book。",
            "还款可参考支持的数字和线下渠道，付款前应核对最新账单金额。",
            "逾期联系时必须说明联系目的、欠款金额、还款渠道和援助选择，不得威胁客户。",
        ],
    },
    {
        "topic_id": "kyc_onboarding_update",
        "category": "kyc_onboarding",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ", "Bank_CARDX_PERSONAL_LOANS"],
        "title_th": "KYC/onboarding, profile update และ consent",
        "title_zh": "KYC/开户、资料更新与授权",
        "details_th": [
            "KYC ใช้สำหรับยืนยันตัวตน ตรวจเอกสาร และประเมินความเหมาะสมของผลิตภัณฑ์ตามช่องทางบริการ",
            "การ update เบอร์โทร ที่อยู่ รายได้ หรือข้อมูลอาชีพอาจทำให้เกิด risk review หรือ pending status",
            "เจ้าหน้าที่ต้องให้ลูกค้าใช้ official channel สำหรับเอกสาร และไม่รับข้อมูลลับผ่านแชททั่วไป",
        ],
        "details_zh": [
            "KYC用于身份验证、文件检查和产品适配评估。",
            "更新电话、地址、收入或职业信息可能触发risk review或pending status。",
            "坐席必须引导客户使用official channel提交文件，不通过普通聊天接收敏感信息。",
        ],
    },
    {
        "topic_id": "dispute_chargeback_refund",
        "category": "disputes_chargebacks",
        "product": "CardX credit card",
        "source_ids": ["Bank_CARD_FAQ"],
        "title_th": "dispute, chargeback, refund tracing และ fraud review",
        "title_zh": "争议、拒付、退款追踪与欺诈复核",
        "details_th": [
            "ลูกค้าสามารถแจ้ง transaction ที่ไม่รู้จัก ยอดซ้ำ หรือ merchant ไม่ส่งมอบสินค้าเพื่อเปิด dispute",
            "เจ้าหน้าที่ต้องขอ reference ID, amount, transaction date, merchant name และหลักฐานที่จำเป็นโดยไม่ขอรหัสลับ",
            "กรณี refund หรือ transfer ผิดปกติ ต้องตรวจสถานะ transaction และแจ้ง timeline ตามช่องทาง",
        ],
        "details_zh": [
            "客户可对陌生交易、重复扣款或商户未履约发起dispute。",
            "坐席需收集reference ID、amount、transaction date、merchant name和必要证明，不索要密码。",
            "refund或异常转账需检查交易状态，并按渠道说明timeline。",
        ],
    },
]

CARDX_AUTOX_ALLOWED_PRODUCTS = {
    "CardX credit card",
    "CardX SPEEDY CASH",
    "CardX SPEEDY LOAN",
    "AutoX / Ngern Chaiyo title loan",
}

TOPICS = [topic for topic in TOPICS if topic["product"] in CARDX_AUTOX_ALLOWED_PRODUCTS]


CUSTOMER_PROFILES = [
    ("first_time_digital", "ลูกค้าใหม่ที่ใช้บริการ online เป็นครั้งแรก", "第一次使用线上服务的新客户"),
    ("mobile_first", "ลูกค้าที่ใช้ mobile service เป็นประจำและสนใจ payment status", "经常使用移动服务并关注支付状态的客户"),
    ("fee_sensitive", "ลูกค้าที่กังวลเรื่อง fee, interest และ due date", "对费用、利息和到期日敏感的客户"),
    ("cashflow_stress", "ลูกค้าที่มี cash flow ตึงและต้องการปรับ repayment", "现金流紧张、希望调整还款的客户"),
    ("security_concern", "ลูกค้าที่กังวล fraud และต้องการยืนยัน official channel", "担心欺诈、反复确认官方渠道的客户"),
    ("remote_customer", "ลูกค้าอยู่ต่างจังหวัด ไม่สะดวกไป branch", "外府客户，不方便去网点"),
    ("pending_docs", "ลูกค้าส่งเอกสารแล้วแต่ status ยัง pending", "已提交文件但状态仍pending的客户"),
    ("mixed_products", "ลูกค้ามีหลายผลิตภัณฑ์และสับสนเรื่อง statement กับ due date", "有多个产品、容易混淆账单和到期日的客户"),
]


PAD_TH = [
    "เจ้าหน้าที่ควรตอบด้วยภาษาสุภาพ สรุป next step และระบุช่องทาง official channel ให้ชัดเจน",
    "หากข้อมูลไม่พอ ให้ถามข้อมูลอ้างอิงที่ไม่ใช่ข้อมูลลับ เช่น reference ID, วันที่ทำรายการ หรือ product type",
    "ห้ามขอ OTP, PIN, password, full card number หรือข้อมูลยืนยันตัวตนที่ไม่จำเป็นในบทสนทนา",
    "คำตอบต้องอิง policy snippet ที่ค้นคืนได้ ไม่สร้างเงื่อนไขใหม่และไม่รับประกันผลอนุมัติที่ยังไม่เสร็จ",
    "กรณีเกี่ยวกับ payment status, refund, dispute หรือ collection ให้เก็บ case ID และ timeline เพื่อ follow up",
]

PAD_ZH = [
    "坐席应使用礼貌语言，总结next step，并明确official channel。",
    "信息不足时，只询问非敏感参考信息，例如reference ID、交易日期或product type。",
    "对话中不得索要OTP、PIN、password、完整卡号或不必要的身份信息。",
    "回答必须依据检索到的policy snippet，不新增条件，也不承诺未完成的审批结果。",
    "涉及payment status、refund、dispute或collection时，应保留case ID和timeline便于跟进。",
]

THAI_RATIO_PAD = [
    "คำอธิบายหลักต้องเป็นภาษาไทยเพื่อให้เหมือนบทสนทนาลูกค้าจริงในประเทศไทย และใช้คำอังกฤษเฉพาะคำศัพท์ธนาคารที่จำเป็นเท่านั้น",
    "เมื่อตอบลูกค้า เจ้าหน้าที่ควรทวนความเข้าใจเป็นภาษาไทยก่อน แล้วค่อยระบุคำศัพท์เฉพาะที่เกี่ยวข้องกับผลิตภัณฑ์",
    "หากมีหลายขั้นตอน ให้แบ่งคำตอบเป็นข้อสั้น ๆ เป็นภาษาไทย เพื่อให้ลูกค้าเข้าใจง่ายและลดความเสี่ยงจากการตีความผิด",
]


def article_body(topic: dict, index: int) -> tuple[str, str]:
    profile = CUSTOMER_PROFILES[(index + 2) % len(CUSTOMER_PROFILES)]
    paragraphs_th = [
        f"บทความนี้เป็น synthetic policy snippet สำหรับ {topic['product']} เรื่อง {topic['title_th']} ใช้ใน MaaS benchmark เท่านั้น",
        f"สถานการณ์ลูกค้าตัวอย่าง: {profile[1]}",
        f"ขอบเขตบริการ: {topic['details_th'][0]}",
        f"เงื่อนไขหรือเอกสารสำคัญ: {topic['details_th'][1]}",
        f"ข้อควรแจ้งลูกค้า: {topic['details_th'][2]}",
    ]
    paragraphs_zh = [
        f"本文是用于MaaS benchmark的合成policy snippet，产品/服务为{topic['product']}，主题为{topic['title_zh']}。",
        f"示例客户画像：{profile[2]}。",
        f"服务范围：{topic['details_zh'][0]}",
        f"关键条件或文件：{topic['details_zh'][1]}",
        f"客户提示：{topic['details_zh'][2]}",
    ]
    cursor = index
    while estimate_tokens("\n".join(paragraphs_th)) < 230 + (index % 7) * 25:
        paragraphs_th.append(PAD_TH[cursor % len(PAD_TH)])
        paragraphs_zh.append(PAD_ZH[cursor % len(PAD_ZH)])
        cursor += 1
    while thai_ratio("\n".join(paragraphs_th)) < 0.74:
        paragraphs_th.append(THAI_RATIO_PAD[cursor % len(THAI_RATIO_PAD)])
        paragraphs_zh.append("为贴近泰国真实客户服务语境，主说明以泰语表达，只保留必要英文银行术语。")
        cursor += 1
    return "\n".join(paragraphs_th), "\n".join(paragraphs_zh)


def generate_articles() -> tuple[list[dict], list[dict]]:
    articles: list[dict] = []
    review_rows: list[dict] = []
    for i in range(60):
        topic = TOPICS[i % len(TOPICS)]
        body_th, body_zh = article_body(topic, i)
        article_id = f"KB-MAAS-{i + 1:03d}"
        article = {
            "article_id": article_id,
            "product": topic["product"],
            "category": topic["category"],
            "topic_id": topic["topic_id"],
            "title": f"{topic['title_th']} ({topic['source_ids'][0]}-{(i % 99) + 1:03d})",
            "body": body_th,
            "source_ids": topic["source_ids"],
            "language_mix": "thai_dominant_with_english_banking_terms",
            "synthetic_only": True,
            "target_token_estimate": estimate_tokens(body_th),
            "thai_char_ratio_estimate": round(thai_ratio(body_th), 4),
            "tags": [topic["category"], topic["product"], topic["topic_id"], "synthetic"],
        }
        articles.append(article)
        review_rows.append(
            {
                "article_id": article_id,
                "产品/服务": topic["product"],
                "主题大类": topic["category"],
                "主题": topic["title_zh"],
                "标题": f"{topic['title_zh']}（{topic['source_ids'][0]}-{(i % 99) + 1:03d}）",
                "中文正文": body_zh,
                "来源锚点": ", ".join(topic["source_ids"]),
                "估算Token": article["target_token_estimate"],
                "是否合成数据": "是",
            }
        )
    return articles, review_rows


QUESTION_TEMPLATES = {
    "simple": [
        "ถ้าลูกค้าถามเรื่อง {title} ของ {product} ควรเริ่มอธิบายจากขั้นตอนไหน",
        "{product} ต้องใช้ข้อมูลหรือเอกสารอะไรในกรณี {title}",
        "ลูกค้าต้องเก็บ reference ID หรือ slip เมื่อถามเรื่อง {title} หรือไม่",
        "กรณี {title} เจ้าหน้าที่ห้ามขอข้อมูลลับอะไรจากลูกค้า",
        "ถ้าสถานะยัง pending ในเรื่อง {title} ควรแจ้งลูกค้าอย่างไร",
        "ช่องทาง official channel ที่ควรแนะนำในกรณี {title} คืออะไร",
    ],
    "multi_fact": [
        "ลูกค้าถามทั้ง {title} และ fee/timeline ควรดึง KB ใดมาอธิบายร่วมกัน",
        "ถ้าลูกค้าต้องการแก้ข้อมูล KYC และดำเนินการ {product} ต่อ ควรเรียงขั้นตอนอย่างไร",
        "ลูกค้ากังวลเรื่อง outstanding, due date และ hardship ใน {product} ควรตอบเป็นส่วน ๆ อย่างไร",
        "ถ้าลูกค้าขอให้รับประกันผลอนุมัติหรือ refund ทันที ควรอ้าง policy boundary อย่างไร",
    ],
    "ambiguous_edge": [
        "ลูกค้าสับสนระหว่าง CardX, AutoX และ account ควรถามกลับเพื่อแยก product อย่างไร",
        "ลูกค้าไม่มี reference ID ครบ แต่ต้องการให้ตรวจ status ทันที ควรตอบแบบระมัดระวังอย่างไร",
        "ลูกค้าต้องการส่ง OTP หรือเอกสารลับผ่าน chat เพื่อเร่งงาน เจ้าหน้าที่ควรปฏิเสธและแนะนำอย่างไร",
    ],
}

QUESTION_TEMPLATES_ZH = {
    "simple": [
        "如果客户询问{product}的「{title}」，坐席应从哪一步开始说明？",
        "{product}在「{title}」场景需要哪些信息或文件？",
        "客户询问「{title}」时，是否需要保存reference ID或slip？",
        "在「{title}」场景下，坐席不得向客户索要哪些敏感信息？",
        "如果「{title}」状态仍为pending，应如何告知客户？",
        "在「{title}」场景下，应建议客户使用哪些official channel？",
    ],
    "multi_fact": [
        "客户同时询问「{title}」和fee/timeline，应结合哪些KB说明？",
        "如果客户既要更新KYC，又要继续办理{product}，步骤应如何排序？",
        "客户对{product}的outstanding、due date和hardship都有疑问，应如何分段回答？",
        "客户要求立即承诺审批或refund结果时，应如何说明policy boundary？",
    ],
    "ambiguous_edge": [
        "客户混淆CardX、AutoX和account时，应如何反问确认product？",
        "客户没有完整reference ID但坚持查询status时，应如何谨慎处理？",
        "客户想通过chat发送OTP或敏感文件来加急，坐席应如何拒绝并引导？",
    ],
}


def generate_questions(articles: list[dict], review_articles: list[dict]) -> tuple[list[dict], list[dict]]:
    questions: list[dict] = []
    review_rows: list[dict] = []
    difficulties = ["simple"] * 60 + ["multi_fact"] * 30 + ["ambiguous_edge"] * 10
    article_by_id = {row["article_id"]: row for row in articles}
    review_by_id = {row["article_id"]: row for row in review_articles}
    for i, difficulty in enumerate(difficulties):
        primary = articles[(i * 3) % len(articles)]
        topic = next(t for t in TOPICS if t["topic_id"] == primary["topic_id"])
        template_index = i % len(QUESTION_TEMPLATES[difficulty])
        question = QUESTION_TEMPLATES[difficulty][template_index].format(title=topic["title_th"], product=topic["product"])
        question_zh = QUESTION_TEMPLATES_ZH[difficulty][template_index].format(title=topic["title_zh"], product=topic["product"])
        if difficulty == "simple":
            refs = [primary["article_id"]]
        else:
            refs = sorted({primary["article_id"], articles[(i * 3 + 11) % len(articles)]["article_id"], articles[(i * 3 + 23) % len(articles)]["article_id"]})
        row = {
            "question_id": f"FAQ-MAAS-{i + 1:03d}",
            "product": primary["product"],
            "category": primary["category"],
            "topic_id": primary["topic_id"],
            "difficulty": difficulty,
            "question": question,
            "expected_article_ids": refs,
            "expected_answer_guidance": "ตอบให้ concise และ compliant โดยอ้างอิง retrieved chunks เท่านั้น ระบุ next step, required documents, fee/timeline caveat และห้ามขอ OTP/PIN/password",
            "language_mix": "thai_dominant_with_english_banking_terms",
            "synthetic_only": True,
            "token_estimate": estimate_tokens(question),
        }
        questions.append(row)
        review_rows.append(
            {
                "question_id": row["question_id"],
                "产品/服务": row["product"],
                "主题大类": row["category"],
                "难度": {"simple": "简单单事实", "multi_fact": "多事实组合", "ambiguous_edge": "模糊/边界问题"}[difficulty],
                "中文问题": question_zh,
                "预期引用文章ID": ", ".join(refs),
                "预期引用主题": " | ".join(review_by_id[ref]["主题"] for ref in refs if ref in review_by_id),
                "回答要求": "回答应简洁合规，只依据检索到的KB；说明next step、所需文件、费用/时效边界；不得索要OTP/PIN/password。",
                "估算Token": row["token_estimate"],
                "是否合成数据": "是",
            }
        )
        assert all(ref in article_by_id for ref in refs)
    return questions, review_rows


CALL_TYPES = ["inbound_inquiry_dispute", "inbound_collection", "outbound_collection"]
LENGTH_BUCKETS = ["short"] * 34 + ["medium"] * 33 + ["long"] * 33
TARGETS = {"short": 1500, "medium": 4000, "long": 8000}


def account_product_for(i: int) -> str:
    product_cycle = [
        "CardX credit card",
        "CardX SPEEDY CASH",
        "CardX SPEEDY LOAN",
        "AutoX / Ngern Chaiyo title loan",
    ]
    return product_cycle[i % len(product_cycle)]


def generate_accounts() -> tuple[list[dict], list[dict]]:
    accounts: list[dict] = []
    review_rows: list[dict] = []
    for i in range(100):
        call_type = CALL_TYPES[i % len(CALL_TYPES)]
        overdue = "collection" in call_type
        product = account_product_for(i)
        base = 320_000 if "AutoX" in product else 78_000 if "SPEEDY" in product else 31_000
        account_id_prefix = re.sub(r"[^A-Z0-9]+", "-", product.upper()).strip("-")
        days_overdue = 0 if not overdue else [7, 14, 22, 31, 46, 62, 75][i % 7]
        status = "overdue" if overdue else "current"
        row = {
            "customer_id": f"SYN-CUST-{i + 1:04d}",
            "account_id": f"{account_id_prefix}-SYN-{i + 1:04d}",
            "product": product,
            "customer_profile": CUSTOMER_PROFILES[i % len(CUSTOMER_PROFILES)][0],
            "status": status,
            "days_overdue": days_overdue,
            "outstanding_balance_thb": base + i * (3_200 if "AutoX" in product else 920),
            "minimum_due_thb": 0 if not overdue else 1_400 + (i % 8) * 650,
            "last_payment_date": (BASE_DATE - timedelta(days=8 + (i % 18))).isoformat(),
            "last_payment_amount_thb": 900 + (i % 13) * 720,
            "synthetic_only": True,
        }
        accounts.append(row)
        review_rows.append(
            {
                "customer_id": row["customer_id"],
                "account_id": row["account_id"],
                "产品/服务": product,
                "客户画像": CUSTOMER_PROFILES[i % len(CUSTOMER_PROFILES)][2],
                "状态": "逾期" if overdue else "正常",
                "逾期天数": days_overdue,
                "未偿余额THB": row["outstanding_balance_thb"],
                "最低应还THB": row["minimum_due_thb"],
                "上次还款日期": row["last_payment_date"],
                "上次还款金额THB": row["last_payment_amount_thb"],
                "是否合成数据": "是",
            }
        )
    return accounts, review_rows


def call_topic_for(account: dict, index: int) -> dict:
    product = account["product"]
    candidates = [t for t in TOPICS if t["product"] == product]
    if not candidates:
        candidates = TOPICS
    return candidates[index % len(candidates)]


def render_block(lines: list[str], account: dict, topic: dict) -> str:
    return "\n".join(line.format(
        product=account["product"],
        account_id=account["account_id"],
        customer_id=account["customer_id"],
        outstanding=f"{account['outstanding_balance_thb']:,}",
        minimum_due=f"{account['minimum_due_thb']:,}",
        days_overdue=account["days_overdue"],
        title=topic["title_th"],
    ) for line in lines)


INQUIRY_BLOCKS = [
    [
        "Agent: สวัสดีค่ะ ติดต่อศูนย์บริการ {product} ขอ verify synthetic customer ID {customer_id} ก่อนให้ข้อมูลนะคะ",
        "Customer: วันนี้อยากถามเรื่อง {title} เพราะ status ในระบบยังไม่ตรงกับที่คาดไว้",
        "Agent: ดิฉันจะอธิบายตาม policy ก่อนนะคะ ต้องดู product, account status, reference ID, due date และเอกสารที่เกี่ยวข้อง",
        "Customer: ถ้าส่งเอกสารหรือชำระวันนี้ status จะ update เมื่อไร",
        "Agent: ขึ้นกับ cut-off time, clearing และ review queue ค่ะ แนะนำเก็บ reference ID และตรวจผ่าน official channel",
    ],
    [
        "Customer: ขอคำตอบแบบชัด ๆ ได้ไหมว่าจะ approved หรือ refund วันนี้เลย",
        "Agent: ยังรับประกันผลที่ยังไม่ review เสร็จไม่ได้ค่ะ แต่สามารถแจ้ง next step, required documents และ timeline caveat ได้",
        "Customer: ถ้าข้อมูลไม่ครบต้องส่งอะไรเพิ่ม",
        "Agent: ส่งเฉพาะเอกสารที่กำหนดผ่าน official channel เท่านั้น ไม่ส่ง OTP, PIN, password หรือ full card number ผ่าน chat",
    ],
    [
        "Customer: กังวลว่าอาจเป็น fraud call จะตรวจสอบอย่างไร",
        "Agent: ลูกค้าสามารถวางสายแล้วเข้า CardX/AutoX official channel เองได้ค่ะ เจ้าหน้าที่จะไม่ขอ remote control หรือ secret code",
        "Customer: ช่วยสรุปขั้นตอนให้หน่อย",
        "Agent: ยืนยัน product, ตรวจ status, เก็บ reference ID, ทำรายการผ่านช่องทางทางการ แล้วรอผลตาม SLA ของแต่ละ service",
    ],
]

DISPUTE_BLOCKS = [
    [
        "Customer: เห็น transaction ที่ไม่รู้จัก อยากเปิด dispute หรือ chargeback",
        "Agent: ต้องใช้ merchant name, amount, transaction date, reference ID และหลักฐานที่จำเป็น โดยไม่ขอรหัสลับใด ๆ",
        "Customer: ระหว่างตรวจสอบต้องชำระ minimum payment ไหม",
        "Agent: ถ้าเป็น CardX statement ลูกค้าควรตรวจ minimum payment และ due date ส่วน provisional credit จะแสดงใน account activity หากเข้าเกณฑ์",
    ],
    [
        "Customer: ร้านค้าบอก refund แล้ว แต่ payment status ยังไม่เห็นเงินเข้า",
        "Agent: ต้องแยกสถานะ pending, posted, reversed หรือ failed ก่อน ถ้าเกิน SLA จะเปิด case เพื่อติดตาม refund tracing",
        "Customer: ต้องจ่ายซ้ำไหม",
        "Agent: ไม่ควรจ่ายซ้ำจนกว่าจะยืนยัน transaction status เพื่อหลีกเลี่ยง duplicate debit",
    ],
]

COLLECTION_BLOCKS = [
    [
        "Agent: สวัสดีค่ะ ดิฉันติดต่อจากทีมบริการ {product} เรื่อง synthetic account {account_id} วัตถุประสงค์คือแจ้งยอดค้างและทางเลือกการชำระ การสนทนาอาจถูกบันทึกเพื่อ quality monitoring",
        "Agent: ข้อมูลนี้แจ้งเฉพาะเจ้าของบัญชีเท่านั้น และเราจะไม่ขอ OTP, PIN หรือ password",
        "Customer: พูดได้ครับ เห็นว่ามี overdue แต่ไม่แน่ใจยอดขั้นต่ำ",
        "Agent: outstanding ปัจจุบันคือ {outstanding} บาท overdue {days_overdue} วัน และ minimum due คือ {minimum_due} บาทค่ะ",
        "Customer: เดือนนี้ cash flow ตึง ขอจ่ายบางส่วนก่อนได้ไหม",
        "Agent: สามารถคุยเรื่อง payment arrangement, promise-to-pay หรือ hardship review โดยบันทึกวันที่และจำนวนที่ลูกค้ารับไหว",
    ],
    [
        "Customer: ถ้าจ่ายบางส่วน late fee หรือ interest จะหยุดทันทีไหม",
        "Agent: partial payment ช่วยลดยอด outstanding แต่ fee และ interest เป็นไปตาม policy ของ {product} จนกว่า payment clearing จะเสร็จ",
        "Customer: ไม่อยากรับสายบ่อย สามารถเลือกเวลาติดต่อได้ไหม",
        "Agent: บันทึก preferred contact window ได้ และจะติดตามภายใต้กติกา collection ที่เหมาะสม ไม่เปิดเผยข้อมูลแก่บุคคลอื่น",
    ],
    [
        "Customer: ถ้าขอ hardship จะกระทบ product อื่นไหม",
        "Agent: ต้องส่งเข้า review และดู repayment behavior ภายหลังค่ะ เราจะไม่รับประกันผลก่อนพิจารณาเสร็จ",
        "Customer: ต้องใช้เอกสารอะไร",
        "Agent: ใช้ข้อมูลรายได้หรือเหตุจำเป็นแบบ synthetic, consent และแผนชำระที่เป็นไปได้ ผ่าน official channel เท่านั้น",
    ],
]

PRODUCT_BLOCKS = [
    [
        "Customer: ถ้าเป็น AutoX title loan ต้องใช้ vehicle registration book ไหม",
        "Agent: ต้องตรวจเอกสารรถและ collateral status ตามประเภทสินเชื่อ รวมถึงช่องทาง Ngern Chaiyo ที่ลูกค้าใช้สมัคร",
    ],
    [
        "Customer: ถ้าเป็น CardX SPEEDY LOAN อยากปรับ repayment schedule ต้องทำอย่างไร",
        "Agent: ต้องดู eligibility, current status, due date และเอกสารรายได้ก่อนเสนอ payment arrangement หรือ hardship review",
    ],
    [
        "Customer: ถ้าเป็น CardX credit card แล้ว payment status ไม่ update ต้องทำอย่างไร",
        "Agent: ให้เก็บ slip หรือ reference ID ตรวจ cut-off/clearing และยังไม่ควรทำรายการซ้ำจนกว่าจะรู้ status",
    ],
]


def generate_dialogue(account: dict, topic: dict, bucket: str, call_type: str) -> str:
    parts = [
        f"Transcript synthetic_id=CALL-MAAS-{int(account['customer_id'].split('-')[-1]):04d}; product={account['product']}; customer_id={account['customer_id']}; account_id={account['account_id']}; call_type={call_type}; language=Thai with English banking terms",
    ]
    blocks = COLLECTION_BLOCKS if "collection" in call_type else INQUIRY_BLOCKS + DISPUTE_BLOCKS
    blocks = blocks + PRODUCT_BLOCKS + INQUIRY_BLOCKS[1:]
    cursor = 0
    target = TARGETS[bucket]
    while estimate_tokens("\n".join(parts)) < target:
        parts.append(render_block(blocks[cursor % len(blocks)], account, topic))
        parts.append(
            f"Agent: สรุป next step คือใช้ official channel, เก็บ reference ID, ตรวจ product={account['product']} และรอ status update ตาม SLA ของ service\n"
            "Customer: รับทราบครับ ช่วยบันทึก synthetic case นี้ไว้เพื่อ follow up ครั้งถัดไป"
        )
        cursor += 1
    while thai_ratio("\n".join(parts)) < 0.72:
        parts.append("Agent: เพื่อความชัดเจน ดิฉันขอสรุปเป็นภาษาไทยอีกครั้ง ลูกค้าควรตรวจสอบช่องทางทางการ เก็บหลักฐานการทำรายการ และรอผลตามรอบการประมวลผลที่แจ้งไว้")
        parts.append("Customer: เข้าใจแล้วครับ แบบนี้ชัดเจนขึ้นและไม่ต้องส่งข้อมูลลับเพิ่มเติม")
    return "\n\n".join(parts)


def dialogue_zh(account_review: dict, topic: dict, bucket_zh: str, call_type_zh: str, token_estimate: int) -> str:
    return (
        f"通话记录：产品/服务={account_review['产品/服务']}；客户ID={account_review['customer_id']}；账户ID={account_review['account_id']}；"
        f"通话类型={call_type_zh}；长度桶={bucket_zh}；估算Token={token_estimate}。\n"
        f"客户画像：{account_review['客户画像']}。\n"
        f"主题：{topic['title_zh']}。\n"
        "示例内容：坐席先确认synthetic customer ID，说明不会索要OTP/PIN/password；客户描述状态、付款、文件或争议问题；"
        "坐席依据官方流程说明next step、required documents、fee/timeline caveat和official channel。"
        "若为催收场景，坐席会先说明联系目的、欠款金额、还款选择和quality monitoring，并避免威胁或向第三方披露信息。"
    )


def generate_transcripts(accounts: list[dict], review_accounts: list[dict]) -> tuple[list[dict], list[dict]]:
    transcripts: list[dict] = []
    review_rows: list[dict] = []
    bucket_zh = {"short": "短", "medium": "中", "long": "长"}
    call_type_zh = {
        "inbound_inquiry_dispute": "来电咨询/争议处理",
        "inbound_collection": "来电催收/还款安排",
        "outbound_collection": "外呼催收/还款安排",
    }
    for i, account in enumerate(accounts):
        bucket = LENGTH_BUCKETS[i]
        call_type = CALL_TYPES[i % len(CALL_TYPES)]
        topic = call_topic_for(account, i)
        text = generate_dialogue(account, topic, bucket, call_type)
        transcript_id = f"CALL-MAAS-{i + 1:04d}"
        row = {
            "transcript_id": transcript_id,
            "product": account["product"],
            "length_bucket": bucket,
            "call_type": call_type,
            "customer_id": account["customer_id"],
            "account_id": account["account_id"],
            "topic_id": topic["topic_id"],
            "dialogue": text,
            "expected_tool_call": {"name": "get_account_summary", "arguments": {"customer_id": account["customer_id"]}},
            "approx_token_estimate": estimate_tokens(text),
            "language_mix": "thai_dominant_with_english_banking_terms",
            "synthetic_only": True,
        }
        transcripts.append(row)
        review_rows.append(
            {
                "transcript_id": transcript_id,
                "产品/服务": account["product"],
                "长度桶": bucket_zh[bucket],
                "通话类型": call_type_zh[call_type],
                "customer_id": account["customer_id"],
                "account_id": account["account_id"],
                "主题": topic["title_zh"],
                "预估Token": row["approx_token_estimate"],
                "预期工具调用": f"get_account_summary(customer_id=\"{account['customer_id']}\")",
                "中文审阅摘要": dialogue_zh(review_accounts[i], topic, bucket_zh[bucket], call_type_zh[call_type], row["approx_token_estimate"]),
                "是否合成数据": "是",
            }
        )
    return transcripts, review_rows


def vector_index_spec() -> dict:
    return {
        "embedding_model": {
            "configured_by": "config/config.local.yaml",
            "requirement": "same embedding model, API and weights for both platforms",
            "extra_params_config_key": "embedding.params",
        },
        "vector_store": {
            "type": "qdrant",
            "url_config_key": "qdrant.url",
            "collection_config_key": "qdrant.collection_name",
        },
        "chunking": {
            "source_field": "body",
            "target_chunk_tokens": 420,
            "overlap_tokens": 60,
        },
        "retrieval": {
            "top_k_config_key": "runtime.top_k",
            "reranker": "optional, controlled by reranker.enabled",
            "rerank_top_n_config_key": "runtime.rerank_top_n",
        },
        "neutral_tooling_rule": "Do not use platform-native vector/embedding services unless both platforms use exactly the same external service and it is disclosed.",
    }


def manifest(articles: list[dict], questions: list[dict], transcripts: list[dict], accounts: list[dict]) -> dict:
    def counts(rows: list[dict], key: str) -> dict:
        out: dict[str, int] = {}
        for row in rows:
            out[str(row[key])] = out.get(str(row[key]), 0) + 1
        return out

    return {
        "dataset_date": BASE_DATE.isoformat(),
        "seed": SEED,
        "synthetic_only": True,
        "language_mix_target": "approximately 85% Thai / 15% English banking terms",
        "token_control": "local approximate estimator; benchmark token counts must come from MaaS endpoint usage fields",
        "source_anchors": SOURCE_ANCHORS,
        "record_counts": {
            "kb_articles": len(articles),
            "faq_questions": len(questions),
            "transcripts": len(transcripts),
            "account_lookup": len(accounts),
        },
        "uc1_category_counts": counts(articles, "category"),
        "faq_difficulty_counts": counts(questions, "difficulty"),
        "transcript_bucket_counts": counts(transcripts, "length_bucket"),
        "transcript_call_type_counts": counts(transcripts, "call_type"),
        "product_counts": counts(transcripts, "product"),
        "official_style_scope": [
            "CardX credit card",
            "CardX SPEEDY CASH",
            "CardX SPEEDY LOAN",
            "AutoX / Ngern Chaiyo title loan",
        ],
    }


def main() -> None:
    random.seed(SEED)
    articles, review_articles = generate_articles()
    questions, review_questions = generate_questions(articles, review_articles)
    accounts, review_accounts = generate_accounts()
    transcripts, review_transcripts = generate_transcripts(accounts, review_accounts)

    write_jsonl(DATA / "uc1" / "kb_articles.jsonl", articles)
    write_jsonl(DATA / "uc1" / "faq_questions.jsonl", questions)
    write_json(DATA / "uc1" / "vector_index_spec.json", vector_index_spec())
    write_jsonl(DATA / "uc2" / "transcripts.jsonl", transcripts)
    write_jsonl(DATA / "uc2" / "account_lookup.jsonl", accounts)
    write_json(DATA / "manifest.json", manifest(articles, questions, transcripts, accounts))
    write_json(
        REVIEW / "chinese_review_tables.json",
        {
            "说明": [
                {"项目": "用途", "说明": "本文件为同源中文审阅数据，用于导出中文Excel。正式benchmark使用JSONL中的泰英混合数据。"},
                {"项目": "范围", "说明": "仅覆盖CardX和AutoX：CardX信用卡、CardX SPEEDY CASH、CardX SPEEDY LOAN、AutoX/Ngern Chaiyo title loan，以及这些产品内的KYC、争议、催收和还款安排。"},
                {"项目": "安全", "说明": "全部客户、账户、金额、日期均为synthetic；不含真实PII。"},
            ],
            "覆盖统计": [
                {"类别": "KB文章数", "指标": "总数", "数值": len(articles), "说明": "目标约50-80篇"},
                {"类别": "FAQ问题数", "指标": "总数", "数值": len(questions), "说明": "目标约100个问题"},
                {"类别": "通话记录数", "指标": "总数", "数值": len(transcripts), "说明": "目标约100段"},
                {"类别": "账户lookup数", "指标": "总数", "数值": len(accounts), "说明": "每段通话一条mock account record"},
            ],
            "UC1_知识库": review_articles,
            "UC1_FAQ": review_questions,
            "UC2_通话": review_transcripts,
            "UC2_账户": review_accounts,
        },
    )
    print(json.dumps({"output": str(DATA), "counts": manifest(articles, questions, transcripts, accounts)["record_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
