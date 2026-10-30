"""Build the independent 50-question set from filings already on disk.

Gold values are read from parsed table lines or from a sentence in the
filing text. A missing line stops the build. Nothing here calls the
answering pipeline.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
QUESTIONS_PATH = PROJECT_ROOT / "evaluation" / "validation_50_questions.json"
SEC_DIR = BACKEND_DIR / "data" / "sec"

for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from app.services.calculator import growth_rate, margin  # noqa: E402
from app.services.financial_lookup import (  # noqa: E402
    _extract_year_values,
    canonical_label,
)
from app.services.table_parser import extract_table_chunks  # noqa: E402
from evaluation.scoring import answer_correct  # noqa: E402


LABEL = (
    "50-question independent evaluation. Separate from the 8-question "
    "smoke test and the 12-question validation set. Not an estimate of "
    "overall financial accuracy."
)

FILINGS = {
    "AAPL": {
        "company": "Apple Inc.",
        "cik": "0000320193",
        "form": "10-K",
        "fiscal_year": 2025,
        "accession": "0000320193-25-000079",
        "report_date": "2025-09-27",
        "html": "AAPL_10-K_000032019325000079.html",
        "text": "AAPL_10-K_000032019325000079.txt",
    },
    "MSFT": {
        "company": "Microsoft Corporation",
        "cik": "0000789019",
        "form": "10-K",
        "fiscal_year": 2026,
        "accession": "0001193125-26-323660",
        "report_date": "2026-06-30",
        "html": "MSFT_10-K_000119312526323660.html",
        "text": "MSFT_10-K_000119312526323660.txt",
    },
    "TROW": {
        "company": "T. Rowe Price Group, Inc.",
        "cik": "0001113169",
        "form": "10-K",
        "fiscal_year": 2025,
        "accession": "0001628280-26-008002",
        "report_date": "2025-12-31",
        "html": "TROW_10-K_000162828026008002.html",
        "text": "TROW_10-K_000162828026008002.txt",
    },
    "VENU": {
        "company": "Venu Holding Corporation",
        "cik": "0001770501",
        "form": "10-K",
        "fiscal_year": 2025,
        "accession": "0001493152-26-014137",
        "report_date": "2025-12-31",
        "html": "VENU_10-K_000149315226014137.html",
        "text": "VENU_10-K_000149315226014137.txt",
    },
}


def _chunks(ticker: str) -> List[Dict[str, Any]]:
    meta = FILINGS[ticker]
    path = SEC_DIR / meta["html"]
    return extract_table_chunks(
        str(path),
        metadata={
            "company": ticker,
            "form": meta["form"],
            "filing": meta["html"],
            "source": "SEC EDGAR",
        },
    )


def _rows(chunks: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    found = []
    for chunk in chunks:
        for line in chunk.get("text", "").splitlines():
            if ":" not in line:
                continue
            raw_label = line.split(":", 1)[0].strip()
            if canonical_label(raw_label) != label:
                continue
            values = _extract_year_values(line.split(":", 1)[1])
            found.append({"line": line.strip(), "values": values, "label": raw_label})
    return found


def _unique_value(
    rows: List[Dict[str, Any]],
    year: int,
    line_contains: Optional[str] = None,
) -> float:
    present = [row for row in rows if year in row["values"]]
    if line_contains:
        present = [row for row in present if line_contains in row["line"]]
    if not present:
        raise RuntimeError(f"no row contains {year}")
    keys = {round(row["values"][year], 6) for row in present}
    if len(keys) != 1:
        raise RuntimeError(f"conflicting values for {year}: {keys}")
    return present[0]["values"][year]


def _quote_for_number(path: Path, value: float) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    collapsed = re.sub(r"\s+", " ", text)
    candidates = []
    if abs(value - round(value)) < 1e-6:
        whole = int(round(value))
        candidates.append(f"{whole:,}")
        candidates.append(str(whole))
    else:
        plain = f"{value:.4f}".rstrip("0").rstrip(".")
        candidates.append(plain)
        if "." in plain:
            whole, frac = plain.split(".")
            candidates.append(f"{int(whole):,}.{frac}")
    for candidate in candidates:
        if candidate in collapsed:
            return candidate
    raise RuntimeError(f"{path.name} does not contain a printed form of {value}")


def _filing_fields(ticker: str, statement: str) -> Dict[str, Any]:
    meta = FILINGS[ticker]
    return {
        "ticker": ticker,
        "cik": meta["cik"],
        "company": meta["company"],
        "form": meta["form"],
        "fiscal_year": meta["fiscal_year"],
        "accession": meta["accession"],
        "report_date": meta["report_date"],
        "statement": statement,
        "source_file": f"backend/data/sec/{meta['html']}",
    }


def _lookup(
    ticker: str,
    chunks: List[Dict[str, Any]],
    *,
    label: str,
    year: int,
    question: str,
    unit: str,
    statement: str,
    category: str,
    display_value: Optional[float] = None,
    allow_scale: bool = True,
    line_contains: Optional[str] = None,
) -> Dict[str, Any]:
    rows = _rows(chunks, label)
    raw = _unique_value(rows, year, line_contains)
    gold = raw if display_value is None else display_value
    line = next(
        row["line"]
        for row in rows
        if year in row["values"]
        and (line_contains is None or line_contains in row["line"])
        and round(row["values"][year], 6) == round(raw, 6)
    )
    record = _filing_fields(ticker, statement)
    record.update(
        {
            "question": question,
            "line_item": rows[0]["label"],
            "source_quote": _quote_for_number(SEC_DIR / FILINGS[ticker]["html"], raw),
            "source_line": line,
            "gold_value": gold,
            "gold_unit": unit,
            "allow_scale_conversion": allow_scale,
            "tolerance_mode": "exact",
            "tolerance_abs": 0,
            "category": category,
            "expected_path": "not used for scoring",
            "answer_mode": "numeric",
        }
    )
    return record


def _ratio(
    ticker: str,
    chunks: List[Dict[str, Any]],
    *,
    numerator: str,
    denominator: str,
    year: int,
    question: str,
    numerator_contains: Optional[str] = None,
    denominator_contains: Optional[str] = None,
) -> Dict[str, Any]:
    num_rows = _rows(chunks, numerator)
    den_rows = _rows(chunks, denominator)
    num = _unique_value(num_rows, year, numerator_contains)
    den = _unique_value(den_rows, year, denominator_contains)
    gold = round(margin(num, den), 2)
    record = _filing_fields(ticker, "Income statement")
    record.update(
        {
            "question": question,
            "line_item": f"{num_rows[0]['label']} / {den_rows[0]['label']}",
            "source_quote": _quote_for_number(SEC_DIR / FILINGS[ticker]["html"], num),
            "source_line": next(
                row["line"]
                for row in num_rows
                if year in row["values"] and round(row["values"][year], 6) == round(num, 6)
            ),
            "source_line_extra": next(
                row["line"]
                for row in den_rows
                if year in row["values"] and round(row["values"][year], 6) == round(den, 6)
            ),
            "inputs": {
                "numerator": num,
                "denominator": den,
                "formula": f"round({num} / {den} * 100, 2)",
            },
            "gold_value": gold,
            "gold_unit": "percent",
            "allow_scale_conversion": False,
            "tolerance_mode": "absolute",
            "tolerance_abs": 0.01,
            "category": "ratio",
            "expected_path": "not used for scoring",
            "answer_mode": "numeric",
        }
    )
    return record


def _growth(
    ticker: str,
    chunks: List[Dict[str, Any]],
    *,
    label: str,
    start: int,
    end: int,
    question: str,
) -> Dict[str, Any]:
    rows = _rows(chunks, label)
    usable = [row for row in rows if start in row["values"] and end in row["values"]]
    if not usable:
        raise RuntimeError(f"{label} lacks {start} and {end}")
    pairs = {
        (round(row["values"][start], 6), round(row["values"][end], 6)) for row in usable
    }
    if len(pairs) != 1:
        raise RuntimeError(f"conflicting growth inputs for {label}: {pairs}")
    old = usable[0]["values"][start]
    new = usable[0]["values"][end]
    record = _filing_fields(ticker, "Income statement")
    record.update(
        {
            "question": question,
            "line_item": usable[0]["label"],
            "source_quote": _quote_for_number(SEC_DIR / FILINGS[ticker]["html"], new),
            "source_line": usable[0]["line"],
            "inputs": {
                "start_year": start,
                "end_year": end,
                "start_value": old,
                "end_value": new,
                "formula": f"round(({new} - {old}) / {old} * 100, 2)",
            },
            "gold_value": round(growth_rate(old, new), 2),
            "gold_unit": "percent",
            "allow_scale_conversion": False,
            "tolerance_mode": "absolute",
            "tolerance_abs": 0.01,
            "category": "growth",
            "expected_path": "not used for scoring",
            "answer_mode": "numeric",
        }
    )
    return record


def _narrative(ticker: str, needle: str, question: str, gold: float, unit: str) -> Dict[str, Any]:
    path = SEC_DIR / FILINGS[ticker]["text"]
    collapsed = re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace"))
    needle = re.sub(r"\s+", " ", needle)
    if needle not in collapsed:
        raise RuntimeError(f"narrative quote not in {path.name}: {needle}")
    record = _filing_fields(ticker, "Narrative")
    record["source_file"] = f"backend/data/sec/{FILINGS[ticker]['text']}"
    record.update(
        {
            "question": question,
            "line_item": needle,
            "source_quote": needle,
            "gold_value": gold,
            "gold_unit": unit,
            "allow_scale_conversion": True,
            "tolerance_mode": "exact",
            "tolerance_abs": 0,
            "category": "narrative",
            "expected_path": "not used for scoring",
            "answer_mode": "numeric",
        }
    )
    return record


def _sample_answer(record: Dict[str, Any]) -> str:
    value = record["gold_value"]
    unit = record["gold_unit"]
    if unit == "percent":
        return f"{value}%"
    if unit == "usd_per_share":
        return str(value)
    if isinstance(value, float) and abs(value - round(value)) > 1e-6:
        text = f"{value:.6f}".rstrip("0").rstrip(".")
    else:
        text = f"{int(round(value)):,}"
    if unit == "billion":
        return f"{text} billion"
    if unit == "million":
        return f"{text} million"
    return text


def build_questions() -> List[Dict[str, Any]]:
    chunks = {ticker: _chunks(ticker) for ticker in FILINGS}
    aapl, msft, trow, venu = chunks["AAPL"], chunks["MSFT"], chunks["TROW"], chunks["VENU"]
    questions: List[Dict[str, Any]] = []

    def add(record: Dict[str, Any]) -> None:
        questions.append(record)

    add(_lookup("MSFT", msft, label="sales and marketing", year=2026,
                question="What was Microsoft's sales and marketing expense for fiscal year 2026, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("AAPL", aapl, label="earnings per share basic", year=2025,
                question="What was Apple's basic earnings per share for fiscal year 2025?",
                unit="usd_per_share", statement="Income statement", category="lookup",
                allow_scale=False, line_contains="2025=7.49"))
    add(_ratio("MSFT", msft, numerator="net income", denominator="total revenue", year=2026,
               question="What was Microsoft's net margin for fiscal year 2026?"))
    add(_growth("TROW", trow, label="net revenues", start=2024, end=2025,
                question="What was the growth rate in TROW's net revenues from fiscal year 2024 to fiscal year 2025, in percent?"))
    add(_narrative(
        "AAPL",
        "which totaled $132.4 billion as of September 27, 2025",
        "As of September 27, 2025, what was the total of Apple's cash, cash equivalents, and marketable securities, in USD billions?",
        132.4,
        "billion",
    ))

    add(_lookup("MSFT", msft, label="goodwill", year=2026,
                question="What was Microsoft's goodwill at the end of fiscal year 2026, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("MSFT", msft, label="cash and cash equivalents", year=2026,
                question="What was Microsoft's cash and cash equivalents at the end of fiscal year 2026, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("MSFT", msft, label="total current assets", year=2026,
                question="What was Microsoft's total current assets at the end of fiscal year 2026, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("MSFT", msft, label="total liabilities", year=2026,
                question="What was Microsoft's total liabilities at the end of fiscal year 2026, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("MSFT", msft, label="total stockholders equity", year=2026,
                question="What was Microsoft's total stockholders' equity at the end of fiscal year 2026, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("MSFT", msft, label="sales and marketing", year=2024,
                question="What was Microsoft's sales and marketing expense for fiscal year 2024, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("MSFT", msft, label="goodwill", year=2025,
                question="What was Microsoft's goodwill at the end of fiscal year 2025, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))

    add(_lookup("AAPL", aapl, label="net sales products", year=2025,
                question="What was Apple's net sales - products for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("AAPL", aapl, label="net sales services", year=2025,
                question="What was Apple's net sales - services for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("AAPL", aapl, label="total assets", year=2025,
                question="What was Apple's total assets at the end of fiscal year 2025, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("AAPL", aapl, label="cash and cash equivalents", year=2025,
                question="What was Apple's cash and cash equivalents at the end of fiscal year 2025, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("AAPL", aapl, label="total liabilities", year=2025,
                question="What was Apple's total liabilities at the end of fiscal year 2025, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("AAPL", aapl, label="total current assets", year=2025,
                question="What was Apple's total current assets at the end of fiscal year 2025, in USD millions?",
                unit="million", statement="Balance sheet", category="lookup"))
    add(_lookup("AAPL", aapl, label="cost of sales products", year=2025,
                question="What was Apple's cost of sales - products for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("AAPL", aapl, label="research and development", year=2025,
                question="What was Apple's research and development expense for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))

    add(_lookup("TROW", trow, label="net revenues", year=2025,
                question="What was TROW's net revenues for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("TROW", trow, label="investment advisory fees", year=2025,
                question="What was TROW's investment advisory fees for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("TROW", trow, label="compensation benefits and related costs", year=2025,
                question="What was TROW's compensation, benefits, and related costs for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))
    add(_lookup("TROW", trow, label="total compensation and related costs", year=2025,
                question="What was TROW's total compensation and related costs for fiscal year 2025, in USD millions?",
                unit="million", statement="Income statement", category="lookup"))

    venu_revenue = _unique_value(_rows(venu, "total revenues net"), 2025)
    venu_assets = _unique_value(_rows(venu, "total assets"), 2025)
    venu_cash = _unique_value(_rows(venu, "cash and cash equivalents"), 2025)
    venu_liabilities = _unique_value(_rows(venu, "total liabilities"), 2025)
    venu_loss_rows = _rows(venu, "net loss")
    venu_loss_line = next(row["line"] for row in venu_loss_rows if 2025 in row["values"])
    if "(50,781,223" not in venu_loss_line and "(50781223" not in venu_loss_line.replace(",", ""):
        raise RuntimeError(f"Venu net loss line is not the parenthetical loss: {venu_loss_line}")
    venu_loss = 50781223.0
    for label, raw, gold in (
        ("total revenues net", venu_revenue, venu_revenue / 1_000_000),
        ("total assets", venu_assets, venu_assets / 1_000_000),
        ("cash and cash equivalents", venu_cash, venu_cash / 1_000_000),
        ("total liabilities", venu_liabilities, venu_liabilities / 1_000_000),
    ):
        record = _lookup(
            "VENU", venu, label=label, year=2025,
            question="",
            unit="million", statement="Financial statements", category="unit_conversion",
            display_value=gold,
        )
        questions.append(record)
    questions[-4]["question"] = "What was Venu's total revenues, net for fiscal year 2025, in USD millions?"
    questions[-3]["question"] = "What was Venu's total assets at the end of fiscal year 2025, in USD millions?"
    questions[-2]["question"] = "What was Venu's cash and cash equivalents at the end of fiscal year 2025, in USD millions?"
    questions[-1]["question"] = "What was Venu's total liabilities at the end of fiscal year 2025, in USD millions?"
    loss = _lookup(
        "VENU", venu, label="net loss", year=2025,
        question="What was Venu's net loss for fiscal year 2025, in USD millions?",
        unit="million", statement="Income statement", category="lookup",
        display_value=venu_loss / 1_000_000,
    )
    loss["source_note"] = (
        "The filing prints this loss in parentheses. Gold is the absolute "
        "amount because scoring reads an unsigned number."
    )
    add(loss)

    add(_ratio("MSFT", msft, numerator="gross margin", denominator="total revenue", year=2026,
               question="What was Microsoft's gross margin for fiscal year 2026?"))
    add(_ratio(
        "MSFT", msft, numerator="operating income", denominator="total revenue", year=2026,
        question="What was Microsoft's operating margin for fiscal year 2026?",
        numerator_contains="2024=109433",
    ))
    add(_ratio(
        "AAPL", aapl, numerator="net income", denominator="total net sales", year=2024,
        question="What was Apple's net margin for fiscal year 2024?",
        denominator_contains="2024=391035",
    ))
    add(_ratio(
        "AAPL", aapl, numerator="operating income", denominator="total net sales", year=2024,
        question="What was Apple's operating margin for fiscal year 2024?",
        denominator_contains="2024=391035",
    ))
    add(_ratio("TROW", trow, numerator="net income", denominator="net revenues", year=2025,
               question="What was TROW's net margin for fiscal year 2025?"))

    add(_growth("MSFT", msft, label="sales and marketing", start=2025, end=2026,
                question="What was the growth rate in Microsoft's sales and marketing expense from fiscal year 2025 to fiscal year 2026, in percent?"))
    add(_growth("MSFT", msft, label="goodwill", start=2025, end=2026,
                question="What was the growth rate in Microsoft's goodwill from fiscal year 2025 to fiscal year 2026, in percent?"))
    add(_growth("TROW", trow, label="investment advisory fees", start=2024, end=2025,
                question="What was the growth rate in TROW's investment advisory fees from fiscal year 2024 to fiscal year 2025, in percent?"))
    add(_growth("AAPL", aapl, label="net sales products", start=2024, end=2025,
                question="What was the growth rate in Apple's net sales - products from fiscal year 2024 to fiscal year 2025, in percent?"))
    add(_growth("MSFT", msft, label="total liabilities", start=2025, end=2026,
                question="What was the growth rate in Microsoft's total liabilities from fiscal year 2025 to fiscal year 2026, in percent?"))

    goodwill = _lookup("MSFT", msft, label="goodwill", year=2026,
                       question="What was Microsoft's goodwill at the end of fiscal year 2026, in USD billions?",
                       unit="billion", statement="Balance sheet", category="unit_conversion",
                       display_value=119651 / 1000)
    current_assets = _lookup("MSFT", msft, label="total current assets", year=2026,
                             question="What was Microsoft's total current assets at the end of fiscal year 2026, in USD billions?",
                             unit="billion", statement="Balance sheet", category="unit_conversion",
                             display_value=207710 / 1000)
    trow_revenue_b = _lookup("TROW", trow, label="net revenues", year=2025,
                             question="What was TROW's net revenues for fiscal year 2025, in USD billions?",
                             unit="billion", statement="Income statement", category="unit_conversion",
                             display_value=7314.8 / 1000)
    aapl_assets_b = _lookup("AAPL", aapl, label="total assets", year=2025,
                            question="What was Apple's total assets at the end of fiscal year 2025, in USD billions?",
                            unit="billion", statement="Balance sheet", category="unit_conversion",
                            display_value=359241 / 1000)
    add(goodwill)
    add(current_assets)
    add(trow_revenue_b)
    add(aapl_assets_b)

    sales_change = _lookup(
        "MSFT", msft, label="sales and marketing", year=2026,
        question="By how many USD millions did Microsoft's sales and marketing expense change from fiscal year 2025 to fiscal year 2026?",
        unit="million", statement="Income statement", category="comparison",
        display_value=26710 - 25654,
    )
    sales_change["inputs"] = {"year_2026": 26710, "year_2025": 25654, "formula": "26710 - 25654"}
    revenue_change = _lookup(
        "TROW", trow, label="net revenues", year=2025,
        question="By how many USD millions did TROW's net revenues change from fiscal year 2024 to fiscal year 2025?",
        unit="million", statement="Income statement", category="comparison",
        display_value=7314.8 - 7093.6,
    )
    revenue_change["gold_value"] = round(7314.8 - 7093.6, 1)
    revenue_change["tolerance_mode"] = "absolute"
    revenue_change["tolerance_abs"] = 0.01
    revenue_change["inputs"] = {"year_2025": 7314.8, "year_2024": 7093.6, "formula": "7314.8 - 7093.6"}
    add(sales_change)
    add(revenue_change)

    add(_narrative(
        "AAPL",
        "aggregate principal amount of $91.3 billion",
        "What was the aggregate principal amount of Apple's fixed-rate notes, in USD billions, as disclosed in the fiscal year 2025 Form 10-K?",
        91.3,
        "billion",
    ))
    add(_narrative(
        "AAPL",
        "announced an additional program to repurchase up to $100 billion",
        "On May 1, 2025, how large a share repurchase program did Apple announce, in USD billions?",
        100,
        "billion",
    ))
    add(_narrative(
        "MSFT",
        "additional tax payment of $28.9 billion",
        "In Microsoft's fiscal year 2026 Form 10-K, what additional tax payment is the IRS seeking in the NOPAs, in USD billions?",
        28.9,
        "billion",
    ))
    add(_narrative(
        "MSFT",
        "increased 84% to $678 billion",
        "What was Microsoft's commercial remaining performance obligation, in USD billions, in the fiscal year 2026 Form 10-K?",
        678,
        "billion",
    ))
    add(_narrative(
        "TROW",
        "$1,775.6 billion in assets under management",
        "At December 31, 2025, how many USD billions of assets under management did TROW report in its Form 10-K narrative?",
        1775.6,
        "billion",
    ))

    if len(questions) != 50:
        raise RuntimeError(f"expected 50 questions, built {len(questions)}")

    forbidden = set()
    for name in ("smoke_questions.json", "validation_questions.json"):
        prior = json.loads((PROJECT_ROOT / "evaluation" / name).read_text(encoding="utf-8"))
        forbidden.update(item["question"] for item in prior)
    for index, record in enumerate(questions, start=1):
        record["id"] = f"ind-{index:02d}"
        if record["question"] in forbidden:
            raise RuntimeError(f"copied an existing question: {record['question']}")
        if not answer_correct(_sample_answer(record), record):
            raise RuntimeError(
                f"{record['id']} sample answer does not score correct: "
                f"{_sample_answer(record)} gold={record['gold_value']} {record['gold_unit']}"
            )
    return questions


def write_questions(questions: List[Dict[str, Any]]) -> None:
    QUESTIONS_PATH.write_text(json.dumps(questions, indent=2), encoding="utf-8")
