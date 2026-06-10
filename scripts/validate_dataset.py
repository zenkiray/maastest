#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "benchmark_data"

EXPECTED_COUNTS = {
    "kb_articles": 60,
    "faq_questions": 100,
    "transcripts": 100,
    "account_lookup": 100,
}

EXPECTED_FAQ = {"simple": 60, "multi_fact": 30, "ambiguous_edge": 10}
EXPECTED_BUCKETS = {"short": 34, "medium": 33, "long": 33}
EXPECTED_CALL_TYPES = {"inbound_inquiry_dispute": 34, "inbound_collection": 33, "outbound_collection": 33}
REQUIRED_CATEGORIES = {
    "credit_cards",
    "personal_loans",
    "auto_title_loans",
    "kyc_onboarding",
    "disputes_chargebacks",
}
ALLOWED_PRODUCTS = {
    "CardX credit card",
    "CardX SPEEDY CASH",
    "CardX SPEEDY LOAN",
    "AutoX / Ngern Chaiyo title loan",
}
FORBIDDEN_TERMS = {
    "HomeX",
    "SaveX",
    "PayX",
    "home loan",
    "savings/current/deposit account",
    "digital transfer/payment",
    "digital banking",
    "home loan",
    "deposit account",
}


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def count_by(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[str(row[key])] = out.get(str(row[key]), 0) + 1
    return out


def thai_ratio(text: str) -> float:
    thai = len(re.findall(r"[\u0E00-\u0E7F]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = thai + latin
    return 0.0 if total == 0 else thai / total


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def validate() -> None:
    manifest = read_json(DATA / "manifest.json")
    articles = read_jsonl(DATA / "uc1" / "kb_articles.jsonl")
    questions = read_jsonl(DATA / "uc1" / "faq_questions.jsonl")
    transcripts = read_jsonl(DATA / "uc2" / "transcripts.jsonl")
    accounts = read_jsonl(DATA / "uc2" / "account_lookup.jsonl")

    assert_true(manifest["record_counts"] == EXPECTED_COUNTS, f"manifest counts mismatch: {manifest['record_counts']}")
    assert_true(len(articles) == 60, "expected 60 articles")
    assert_true(len(questions) == 100, "expected 100 FAQ questions")
    assert_true(len(transcripts) == 100, "expected 100 transcripts")
    assert_true(len(accounts) == 100, "expected 100 account records")

    all_text = "\n".join(json.dumps(row, ensure_ascii=False) for row in articles + questions + transcripts + accounts)
    for term in FORBIDDEN_TERMS:
        assert_true(term not in all_text, f"forbidden out-of-scope product label found: {term}")

    article_ids = set()
    categories = set()
    for row in articles:
        for key in ["article_id", "product", "category", "topic_id", "title", "body", "source_ids", "synthetic_only"]:
            assert_true(key in row, f"article missing {key}: {row}")
        assert_true(row["synthetic_only"] is True, f"article not synthetic: {row['article_id']}")
        assert_true(row["product"] in ALLOWED_PRODUCTS, f"article product out of scope: {row['product']}")
        assert_true(row["article_id"] not in article_ids, f"duplicate article_id: {row['article_id']}")
        article_ids.add(row["article_id"])
        categories.add(row["category"])
        assert_true(0.70 <= thai_ratio(row["body"]) <= 0.98, f"article Thai ratio out of expected range: {row['article_id']}")
        assert_true(row["source_ids"], f"article has no source anchors: {row['article_id']}")
    assert_true(REQUIRED_CATEGORIES.issubset(categories), f"missing categories: {REQUIRED_CATEGORIES - categories}")

    faq_counts = count_by(questions, "difficulty")
    assert_true(faq_counts == EXPECTED_FAQ, f"FAQ difficulty mismatch: {faq_counts}")
    for row in questions:
        for key in ["question_id", "product", "category", "difficulty", "question", "expected_article_ids", "synthetic_only"]:
            assert_true(key in row, f"FAQ missing {key}: {row}")
        assert_true(row["product"] in ALLOWED_PRODUCTS, f"FAQ product out of scope: {row['product']}")
        for article_id in row["expected_article_ids"]:
            assert_true(article_id in article_ids, f"FAQ references missing KB {article_id}: {row['question_id']}")
        if row["difficulty"] != "simple":
            assert_true(len(set(row["expected_article_ids"])) >= 2, f"non-simple FAQ needs 2+ refs: {row['question_id']}")

    account_by_customer = {row["customer_id"]: row for row in accounts}
    assert_true(len(account_by_customer) == 100, "duplicate customer_id in account lookup")
    for row in accounts:
        for key in ["customer_id", "account_id", "product", "status", "days_overdue", "outstanding_balance_thb", "synthetic_only"]:
            assert_true(key in row, f"account missing {key}: {row}")
        assert_true(row["product"] in ALLOWED_PRODUCTS, f"account product out of scope: {row['product']}")
        if row["status"] == "overdue":
            assert_true(row["days_overdue"] > 0 and row["minimum_due_thb"] > 0, f"overdue account has invalid due values: {row['customer_id']}")

    assert_true(count_by(transcripts, "length_bucket") == EXPECTED_BUCKETS, f"bucket mismatch: {count_by(transcripts, 'length_bucket')}")
    assert_true(count_by(transcripts, "call_type") == EXPECTED_CALL_TYPES, f"call type mismatch: {count_by(transcripts, 'call_type')}")
    for row in transcripts:
        for key in ["transcript_id", "product", "length_bucket", "call_type", "customer_id", "account_id", "dialogue", "expected_tool_call"]:
            assert_true(key in row, f"transcript missing {key}: {row}")
        assert_true(row["product"] in ALLOWED_PRODUCTS, f"transcript product out of scope: {row['product']}")
        account = account_by_customer.get(row["customer_id"])
        assert_true(account is not None, f"transcript missing account lookup: {row['transcript_id']}")
        assert_true(account["account_id"] == row["account_id"], f"account_id mismatch: {row['transcript_id']}")
        assert_true(account["product"] == row["product"], f"product mismatch: {row['transcript_id']}")
        assert_true("Agent:" in row["dialogue"] and "Customer:" in row["dialogue"], f"speaker labels missing: {row['transcript_id']}")
        if "collection" in row["call_type"]:
            assert_true(account["status"] == "overdue", f"collection transcript must use overdue account: {row['transcript_id']}")
            assert_true("วัตถุประสงค์" in row["dialogue"], f"collection disclosure missing: {row['transcript_id']}")
        tool = row["expected_tool_call"]
        assert_true(tool["name"] == "get_account_summary", f"unexpected tool: {row['transcript_id']}")
        assert_true(tool["arguments"]["customer_id"] == row["customer_id"], f"tool customer mismatch: {row['transcript_id']}")
        assert_true(0.70 <= thai_ratio(row["dialogue"]) <= 0.98, f"transcript Thai ratio out of range: {row['transcript_id']}")


def main() -> int:
    try:
        validate()
    except AssertionError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
