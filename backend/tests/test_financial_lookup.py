"""Line selection, fiscal year, units, ratios, ambiguity, and missing rows.

Run from the backend directory:

    python tests/test_financial_lookup.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import metrics_resolver
from app.services.financial_lookup import resolve_table_question
from app.services.table_parser import extract_table_chunks
from app.services.tao_pipeline import TAOPipeline


COMPANIES = {
    "MSFT": "Microsoft Corporation",
    "AAPL": "Apple Inc.",
}

results = []


def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


def chunk(text, company="MSFT", form="10-K", scale="million", filing="msft-10k.html"):
    return {
        "text": text,
        "metadata": {
            "type": "table",
            "company": company,
            "form": form,
            "filing": filing,
            "source": "SEC EDGAR",
            "statement_scale": scale,
        },
    }


def answer(question, chunks, companies=None):
    return resolve_table_question(question, chunks, companies if companies is not None else COMPANIES)


CONSOLIDATED = chunk(
    "\n".join([
        "Total revenue: 2026=331839, 2025=281724, 2024=245122",
        "Total cost of revenue: 2026=106374, 2025=87831, 2024=74114",
        "Cost of revenue: 2026=25017, 2025=22422",
        "Research and development: 2026=35562, 2025=32488, 2024=29510",
        "Operating income: 2026=155237, 2025=128528, 2024=109433",
        "Net income: 2026=133749, 2025=101832, 2024=88136",
        "Adjusted net income (non-GAAP): 2026=128786, 2025=105452",
        "Earnings per share - Diluted: 2026=17.95, 2025=13.64, 2024=11.8",
        "Adjusted diluted earnings per share (non-GAAP): 2026=17.28, 2025=14.13",
    ])
)
SEGMENT = chunk(
    "\n".join([
        "Cost of revenue: 2026=57876, 2025=40171",
        "Operating income: 2026=56972, 2025=44589",
    ]),
    filing="msft-segment.html",
)
BALANCE = chunk(
    "\n".join([
        "Total assets: 2026=758376, 2025=619003",
        "Short-term unearned revenue: 2026=72965, 2025=64555",
        "Unearned revenue: 2026=9361, 2025=5438",
    ]),
    filing="msft-balance.html",
)
QUARTER = chunk(
    "Total revenue: 2026=90000, 2025=80000",
    form="10-Q",
    filing="msft-10q.html",
)
APPLE = chunk(
    "\n".join([
        "Total net sales: 2025=416161, 2024=6, 2023=391035",
        "Total net sales: 2025=416161, 2024=391035, 2023=383285",
        "Net income: 2025=112010, 2024=93736",
    ]),
    company="AAPL",
    filing="aapl-10k.html",
)
CHUNKS = [CONSOLIDATED, SEGMENT, BALANCE, QUARTER, APPLE]


def test_selection_and_units():
    revenue = answer(
        "What was Microsoft's total revenue for fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "total revenue uses the 10-K line, not the 10-Q",
        revenue and revenue["status"] == "answered" and revenue["value"] == 331839 and revenue["unit"] == "million",
        str(revenue and (revenue.get("status"), revenue.get("value"), revenue.get("unit"), revenue.get("form"))),
    )

    cost = answer(
        "What was Microsoft's total cost of revenue for fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "total cost of revenue does not use a segment cost of revenue row",
        cost and cost["value"] == 106374,
        str(cost and cost.get("value")),
    )

    operating = answer(
        "What was Microsoft's operating income for fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "operating income uses the consolidated statement when segment rows disagree",
        operating and operating["value"] == 155237,
        str(operating and (operating.get("status"), operating.get("value"), operating.get("reason"))),
    )

    adjusted = answer(
        "What was Microsoft's net income for fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "net income does not use the non-GAAP row",
        adjusted and adjusted["value"] == 133749,
        str(adjusted and adjusted.get("value")),
    )

    eps = answer(
        "What was Microsoft's diluted earnings per share for fiscal year 2026?",
        CHUNKS,
    )
    record(
        "diluted EPS stays per share inside a millions table",
        eps and eps["value"] == 17.95 and eps["unit"] == "usd_per_share",
        str(eps and (eps.get("value"), eps.get("unit"))),
    )

    scaled = answer(
        "What was Microsoft's total revenue for fiscal year 2026, in USD billions?",
        CHUNKS,
    )
    record(
        "millions convert to billions",
        scaled and scaled["value"] == 331.839 and scaled["unit"] == "billion",
        str(scaled and (scaled.get("value"), scaled.get("unit"))),
    )

    assets = answer(
        "What was Microsoft's total assets at the end of fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "fiscal year selects total assets",
        assets and assets["value"] == 758376 and assets["year"] == 2026,
        str(assets and (assets.get("value"), assets.get("year"))),
    )

    short_term = answer(
        "What was Microsoft's short-term unearned revenue at the end of fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record(
        "short-term unearned revenue is not the unearned revenue row",
        short_term and short_term["value"] == 72965,
        str(short_term and short_term.get("value")),
    )


def test_growth_ratio_and_refusals():
    growth = answer(
        "What was the growth rate in Microsoft's total revenue from fiscal year 2025 to fiscal year 2026, in percent?",
        CHUNKS,
    )
    record(
        "same-row revenue growth is 17.79 percent",
        growth and growth["status"] == "answered" and growth["value"] == 17.79 and growth["unit"] == "percent",
        str(growth and (growth.get("status"), growth.get("value"))),
    )

    margin = metrics_resolver.resolve(
        "What was Apple's net margin for fiscal year 2025?",
        ["2025"],
        [APPLE],
    )
    record(
        "Apple net margin stays on the ratio resolver",
        margin is not None and margin["computed_value_pct"] == 26.92,
        str(margin and margin.get("computed_value_pct")),
    )
    lookup_margin = answer(
        "What was Apple's net margin for fiscal year 2025?",
        CHUNKS,
    )
    record(
        "a margin question is not answered as a statement line",
        lookup_margin is None,
        str(lookup_margin),
    )

    microsoft_margin = metrics_resolver.resolve(
        "What was Microsoft's net margin for fiscal year 2026?",
        ["2026"],
        [CONSOLIDATED],
    )
    record(
        "net margin can use total revenue as the denominator",
        microsoft_margin is not None and microsoft_margin["computed_value_pct"] == 40.31,
        str(microsoft_margin and microsoft_margin.get("computed_value_pct")),
    )

    missing = answer(
        "What was Microsoft's inventory for fiscal year 2026, in USD millions?",
        CHUNKS,
    )
    record("a missing line is not invented", missing is None, str(missing))

    cloud = answer(
        "What was Microsoft Cloud revenue for fiscal year 2026, in USD billions?",
        CHUNKS,
    )
    record(
        "Microsoft Cloud revenue is not replaced by total revenue",
        cloud is None,
        str(cloud),
    )

    cash = answer(
        "What was Microsoft's cash from operations for fiscal year 2026, in USD billions?",
        [chunk("Net cash from operations: 2026=182935, 2025=136162")],
    )
    record(
        "cash from operations is not replaced by net cash from operations",
        cash is None,
        str(cash),
    )

    apple_2025 = answer(
        "What was Apple's total net sales for fiscal year 2025, in USD millions?",
        [APPLE],
    )
    record(
        "agreeing 2025 rows survive a bad 2024 duplicate",
        apple_2025 and apple_2025["value"] == 416161,
        str(apple_2025 and apple_2025.get("value")),
    )
    apple_2024 = answer(
        "What was Apple's total net sales for fiscal year 2024, in USD millions?",
        [APPLE],
    )
    record(
        "disagreeing values for the same line are not guessed",
        apple_2024 and apple_2024["status"] == "insufficient",
        str(apple_2024 and apple_2024.get("status")),
    )

    only_quarter = answer(
        "What was Microsoft's total revenue for fiscal year 2026, in USD millions?",
        [QUARTER],
    )
    record(
        "a fiscal-year question does not use a 10-Q row",
        only_quarter and only_quarter["status"] == "insufficient",
        str(only_quarter and only_quarter.get("reason")),
    )

    euros = answer(
        "What was Microsoft's total revenue for fiscal year 2026, in EUR millions?",
        CHUNKS,
    )
    record(
        "a foreign currency is not converted without a rate",
        euros and euros["status"] == "insufficient",
        str(euros and euros.get("reason")),
    )

    no_scale = answer(
        "What was Microsoft's total revenue for fiscal year 2026, in USD millions?",
        [chunk("Total revenue: 2026=331839", scale=None)],
    )
    record(
        "a missing caption scale is not assumed to be millions",
        no_scale and no_scale["status"] == "insufficient",
        str(no_scale and no_scale.get("reason")),
    )


def test_real_filings():
    root = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "sec",
    )
    msft = extract_table_chunks(
        os.path.join(root, "MSFT_10-K_000119312526323660.html"),
        metadata={"company": "MSFT", "form": "10-K", "filing": "MSFT_10-K.html", "source": "SEC EDGAR"},
    )
    aapl = extract_table_chunks(
        os.path.join(root, "AAPL_10-K_000032019325000079.html"),
        metadata={"company": "AAPL", "form": "10-K", "filing": "AAPL_10-K.html", "source": "SEC EDGAR"},
    )
    filings = msft + aapl
    expected = [
        ("What was Microsoft's total revenue for fiscal year 2026, in USD millions?", 331839, "million"),
        ("What was Microsoft's net income for fiscal year 2026, in USD millions?", 133749, "million"),
        ("What was Microsoft's research and development expense for fiscal year 2026, in USD millions?", 35562, "million"),
        ("What was Microsoft's total assets at the end of fiscal year 2026, in USD millions?", 758376, "million"),
        ("What was Microsoft's diluted earnings per share for fiscal year 2026?", 17.95, "usd_per_share"),
        ("What was Microsoft's total cost of revenue for fiscal year 2026, in USD millions?", 106374, "million"),
        ("What was Microsoft's short-term unearned revenue at the end of fiscal year 2026, in USD millions?", 72965, "million"),
        ("What was Microsoft's operating income for fiscal year 2026, in USD millions?", 155237, "million"),
        ("What was the growth rate in Microsoft's total revenue from fiscal year 2025 to fiscal year 2026, in percent?", 17.79, "percent"),
    ]
    for question, value, unit in expected:
        found = answer(question, filings)
        record(
            f"filing row: {question[:48]}",
            found and found["status"] == "answered" and found["value"] == value and found["unit"] == unit,
            str(found and (found.get("status"), found.get("value"), found.get("unit"), found.get("reason"))),
        )
    named_changes = [
        (
            "What was Apple's change in fair value of derivative instruments for fiscal year 2025, in USD millions?",
            849,
        ),
        (
            "What was Apple's change in fair value of marketable debt securities for fiscal year 2025, in USD millions?",
            817,
        ),
        (
            "What was Apple's change in foreign currency translation net of tax for fiscal year 2024, in USD millions?",
            395,
        ),
        (
            "What was Apple's change in valuation allowance for fiscal year 2025, in USD millions?",
            2091,
        ),
    ]
    for question, value in named_changes:
        found = answer(question, filings)
        record(
            f"named change line: {question[16:64]}",
            found and found["status"] == "answered" and found["value"] == value and found["unit"] == "million",
            str(found and (found.get("status"), found.get("value"), found.get("unit"), found.get("reason"))),
        )

    revenue_chunk = next(
        item for item in msft if "Total revenue: 2026=331839" in item["text"]
    )
    record(
        "caption scale is stored without changing the row text",
        revenue_chunk["metadata"].get("statement_scale") == "million"
        and "Total revenue: 2026=331839" in revenue_chunk["text"],
    )


class _Retriever:
    def __init__(self, chunks):
        self.chunks = chunks
        self.retrieve_called = False

    def get_table_chunks(self):
        return self.chunks

    def retrieve(self, question, top_k=5):
        self.retrieve_called = True
        return []


class _RAG:
    def __init__(self, chunks):
        self.retriever = _Retriever(chunks)

    def retrieve(self, question, top_k=5):
        return self.retriever.retrieve(question, top_k=top_k)


def test_batch1_safeguards():
    companies = {
        "MSFT": "Microsoft Corporation",
        "AAPL": "Apple Inc.",
        "TROW": "T. Rowe Price Group, Inc.",
        "VENU": "Venu Holding Corporation",
    }
    rag = _RAG(CHUNKS)
    pipeline = TAOPipeline(rag, company_index=companies, allow_external_fallback=False)
    record(
        "TROW's names TROW",
        pipeline._guess_ticker("What was TROW's net margin for fiscal year 2025?") == "TROW",
    )
    record(
        "Apple's names Apple",
        pipeline._guess_ticker("What was Apple's net margin for fiscal year 2025?") == "AAPL",
    )
    record(
        "revenues does not name VENU",
        pipeline._guess_ticker("By how many USD millions did net revenues change from fiscal year 2024 to fiscal year 2025?") is None,
    )

    trow = chunk(
        "\n".join([
            "Net income: 2025=2208.3, 2024=2135.8",
            "Net revenues: 2025=7314.8, 2024=7093.6",
        ]),
        company="TROW",
        filing="trow-10k.html",
    )
    mixed = _RAG([CONSOLIDATED, trow])
    mixed_pipeline = TAOPipeline(mixed, company_index=companies, allow_external_fallback=False)
    trow_margin = mixed_pipeline.run("What was TROW's net margin for fiscal year 2025?")
    record(
        "TROW margin uses its net revenues and not Microsoft",
        "30.19%" in trow_margin["answer"]
        and "2,208.3" in trow_margin["answer"]
        and "7,314.8" in trow_margin["answer"]
        and "101,832" not in trow_margin["answer"]
        and "331,839" not in trow_margin["answer"]
        and "36.15" not in trow_margin["answer"]
        and mixed.retriever.retrieve_called is False,
        trow_margin["answer"],
    )
    microsoft_only = TAOPipeline(
        _RAG([CONSOLIDATED]),
        company_index=companies,
        allow_external_fallback=False,
    )
    missing_trow = microsoft_only.run("What was TROW's net margin for fiscal year 2025?")
    record(
        "TROW margin abstains when TROW has no revenue line",
        missing_trow["answer"] == "Insufficient evidence."
        and "40.31" not in missing_trow["answer"]
        and "36.15" not in missing_trow["answer"],
        missing_trow["answer"],
    )
    conflict_trow = chunk(
        "\n".join([
            "Net income: 2025=2208.3",
            "Net revenues: 2025=7314.8",
            "Total revenue: 2025=9999",
        ]),
        company="TROW",
        filing="trow-conflict.html",
    )
    conflict_pipeline = TAOPipeline(
        _RAG([CONSOLIDATED, conflict_trow]),
        company_index=companies,
        allow_external_fallback=False,
    )
    conflict_margin = conflict_pipeline.run("What was TROW's net margin for fiscal year 2025?")
    record(
        "conflicting TROW denominators abstain",
        conflict_margin["answer"] == "Insufficient evidence."
        and "30.19" not in conflict_margin["answer"]
        and "40.31" not in conflict_margin["answer"],
        conflict_margin["answer"],
    )

    tied = metrics_resolver.resolve(
        "What was Apple's net margin for fiscal year 2024?",
        ["2024"],
        [APPLE],
    )
    record(
        "a tied denominator is not chosen",
        tied is not None and tied.get("unavailable") == "conflict" and "computed_value_pct" not in tied,
        str(tied),
    )

    majority_rows = chunk(
        "\n".join([
            "Total net sales: 2025=416161, 2024=6, 2023=391035",
            "Total net sales: 2025=416161, 2024=391035, 2023=383285",
            "Total net sales: 2025=416161, 2024=391035, 2023=383285",
            "Net income: 2025=112010, 2024=93736",
            "Operating income: 2025=133050, 2024=123216",
        ]),
        company="AAPL",
        filing="aapl-majority.html",
    )
    majority = metrics_resolver.resolve(
        "What was Apple's net margin for fiscal year 2024?",
        ["2024"],
        [majority_rows],
    )
    record(
        "the repeated total-net-sales value is the FY2024 denominator",
        majority is not None
        and majority.get("denominator_value") == 391035
        and majority.get("computed_value_pct") == 23.97,
        str(majority and (majority.get("denominator_value"), majority.get("computed_value_pct"))),
    )
    operating = metrics_resolver.resolve(
        "What was Apple's operating margin for fiscal year 2024?",
        ["2024"],
        [majority_rows],
    )
    record(
        "FY2024 operating margin uses the repeated denominator",
        operating is not None and operating.get("computed_value_pct") == 31.51,
        str(operating and operating.get("computed_value_pct")),
    )
    still_2025 = metrics_resolver.resolve(
        "What was Apple's net margin for fiscal year 2025?",
        ["2025"],
        [majority_rows],
    )
    record(
        "Apple FY2025 net margin stays 26.92",
        still_2025 is not None and still_2025.get("computed_value_pct") == 26.92,
        str(still_2025 and still_2025.get("computed_value_pct")),
    )

    goodwill = [
        chunk("Goodwill: 2026=119651, 2025=119509", company="MSFT", filing="msft-goodwill.html"),
        chunk("Goodwill: 2025=2642.8", company="TROW", filing="trow-goodwill.html"),
    ]
    microsoft_goodwill = answer(
        "What was Microsoft's goodwill at the end of fiscal year 2026, in USD millions?",
        goodwill,
        companies,
    )
    record(
        "Microsoft goodwill is 119651 million, not TROW's 2642.8",
        microsoft_goodwill
        and microsoft_goodwill.get("status") == "answered"
        and microsoft_goodwill.get("value") == 119651
        and microsoft_goodwill.get("unit") == "million",
        str(microsoft_goodwill and (microsoft_goodwill.get("status"), microsoft_goodwill.get("value"), microsoft_goodwill.get("reason"))),
    )
    goodwill_growth = answer(
        "What was the growth rate in Microsoft's goodwill from fiscal year 2025 to fiscal year 2026, in percent?",
        goodwill,
        companies,
    )
    record(
        "Microsoft goodwill growth is 0.12 percent",
        goodwill_growth
        and goodwill_growth.get("status") == "answered"
        and goodwill_growth.get("value") == 0.12,
        str(goodwill_growth and (goodwill_growth.get("status"), goodwill_growth.get("value"), goodwill_growth.get("reason"))),
    )
    unnamed = answer(
        "What was goodwill for fiscal year 2026, in USD millions?",
        goodwill,
        companies,
    )
    record(
        "goodwill without one company is not guessed",
        unnamed is None,
        str(unnamed),
    )

    eps_rows = chunk(
        "\n".join([
            "Earnings per share - Basic: 2025=7.49, 2024=6.11, 2023=6.16",
            "Shares used in computing earnings per share - Basic: 2025=14948500, 2024=15343783, 2023=15744231",
        ]),
        company="AAPL",
        filing="aapl-eps.html",
        scale=None,
    )
    basic_eps = answer(
        "What was Apple's basic earnings per share for fiscal year 2025?",
        [eps_rows],
        companies,
    )
    record(
        "basic EPS does not collide with the share-count row",
        basic_eps
        and basic_eps.get("status") == "answered"
        and basic_eps.get("value") == 7.49
        and basic_eps.get("unit") == "usd_per_share",
        str(basic_eps and (basic_eps.get("status"), basic_eps.get("value"), basic_eps.get("unit"), basic_eps.get("reason"))),
    )


def test_pipeline_skips_llm_for_a_unique_row():
    rag = _RAG(CHUNKS)
    pipeline = TAOPipeline(rag, company_index=COMPANIES, allow_external_fallback=True)
    output = pipeline.run(
        "What was Microsoft's total revenue for fiscal year 2026, in USD millions?"
    )
    record(
        "pipeline answers a unique row without retrieval",
        output["answer"].endswith("331,839 million.") and rag.retriever.retrieve_called is False,
        output["answer"],
    )
    record(
        "pipeline keeps the live verification fields",
        set(output["verification"]["checks"]) == {
            "numerical",
            "evidence",
            "logical",
            "financial_consistency",
        }
        and output["verification"]["confidence"] == 1.0
        and "query_analysis" in output
        and "tao" in output
        and "latency_seconds" in output,
    )

    margin = pipeline.run("What was Apple's net margin for fiscal year 2025?")
    record(
        "Apple net margin ignores Microsoft total revenue",
        "26.92%" in margin["answer"] and rag.retriever.retrieve_called is False,
        margin["answer"],
    )

    narrative = pipeline.run(
        "What was Microsoft Cloud revenue for fiscal year 2026, in USD billions?"
    )
    record(
        "an unmatched narrative question still reaches retrieval",
        rag.retriever.retrieve_called is True and narrative["answer"] == "Insufficient evidence.",
        narrative["answer"],
    )


def test_absolute_change():
    marketing = chunk(
        "Sales and marketing: 2026=26710, 2025=25654, 2024=24456",
        company="MSFT",
        filing="msft-10k.html",
    )
    other = chunk(
        "Sales and marketing: 2026=1, 2025=1",
        company="MSFT",
        filing="msft-other.html",
    )
    bare = chunk(
        "Sales and marketing: 2026=26710, 2025=25654",
        company="MSFT",
        filing="msft-bare.html",
        scale=None,
    )
    trow = chunk(
        "Net revenues: 2025=7314.8, 2024=7093.6, 2023=6460.5",
        company="TROW",
        filing="trow-10k.html",
    )
    companies = {**COMPANIES, "TROW": "T. Rowe Price Group, Inc."}
    change = answer(
        "By how many USD millions did Microsoft's sales and marketing expense change from fiscal year 2025 to fiscal year 2026?",
        [marketing],
    )
    record(
        "sales and marketing change is later minus earlier",
        change and change["status"] == "answered" and change["value"] == 1056 and change["unit"] == "million",
        str(change and (change.get("status"), change.get("value"), change.get("unit"), change.get("reason"))),
    )
    growth = answer(
        "What was the growth rate in Microsoft's sales and marketing expense from fiscal year 2025 to fiscal year 2026, in percent?",
        [marketing],
    )
    record(
        "the same row's growth rate stays a percent",
        growth and growth["status"] == "answered" and growth["value"] == 4.12 and growth["unit"] == "percent",
        str(growth and (growth.get("status"), growth.get("value"), growth.get("unit"))),
    )
    revenues = resolve_table_question(
        "By how many USD millions did TROW's net revenues change from fiscal year 2024 to fiscal year 2025?",
        [trow, marketing],
        companies,
    )
    record(
        "TROW net-revenue change does not use Microsoft",
        revenues and revenues["status"] == "answered" and revenues["value"] == 221.2 and revenues["unit"] == "million",
        str(revenues and (revenues.get("status"), revenues.get("value"), revenues.get("unit"), revenues.get("filing"))),
    )
    missing = answer(
        "By how many USD millions did Microsoft's goodwill change from fiscal year 2025 to fiscal year 2026?",
        [marketing],
    )
    record(
        "a missing change row abstains",
        missing and missing["status"] == "insufficient",
        str(missing and missing.get("reason")),
    )
    ambiguous = answer(
        "By how many USD millions did Microsoft's sales and marketing expense change in fiscal year 2026?",
        [marketing],
    )
    record(
        "one named year is not an absolute change",
        ambiguous and ambiguous["status"] == "insufficient" and ambiguous.get("value") is None,
        str(ambiguous and (ambiguous.get("status"), ambiguous.get("value"), ambiguous.get("reason"))),
    )
    conflict = answer(
        "By how many USD millions did Microsoft's sales and marketing expense change from fiscal year 2025 to fiscal year 2026?",
        [marketing, other],
    )
    record(
        "conflicting change rows abstain",
        conflict and conflict["status"] == "insufficient",
        str(conflict and conflict.get("reason")),
    )
    unscaled = answer(
        "By how many USD millions did Microsoft's sales and marketing expense change from fiscal year 2025 to fiscal year 2026?",
        [bare],
    )
    record(
        "a change without a caption scale abstains",
        unscaled and unscaled["status"] == "insufficient",
        str(unscaled and unscaled.get("reason")),
    )


def test_incidental_labels():
    companies = {
        **COMPANIES,
        "TROW": "T. Rowe Price Group, Inc.",
        "VENU": "Venu Holding Corporation",
    }
    rows = [
        chunk("Fourth Quarter: 2026=9, 2025=3400, 2024=8", company="MSFT", filing="quarter.html"),
        chunk("27: 2026=58.7, 2025=85.7", company="TROW", filing="day.html", form="10-Q"),
        chunk("Investments: 2025=344.3, 2024=1541.2", company="TROW", filing="investments.html"),
        chunk("Issued: 2025=10", company="VENU", filing="issued.html"),
        chunk("Acquired investments: 2025=71.7, 2024=66.4", company="TROW", filing="acquired.html"),
        chunk("Common stock issued: 2025=1498, 2024=1423", company="AAPL", filing="issued-stock.html"),
        chunk(
            "Change in fair value of derivative instruments: 2025=849, 2024=(832)",
            company="AAPL",
            filing="oci.html",
        ),
    ]
    shareholder = answer(
        "How many USD billions did Microsoft return to shareholders through share repurchases and dividends in the fourth quarter of fiscal year 2026?",
        rows,
        companies,
    )
    record(
        "a quarter heading is not the shareholder-return metric",
        shareholder is None,
        str(shareholder and (shareholder.get("status"), shareholder.get("value"), shareholder.get("reason"))),
    )
    dated = answer(
        "As of September 27, 2025, how many USD millions of Apple's May 2025 share repurchase program had been utilized?",
        rows,
        companies,
    )
    record(
        "a calendar day is not a statement line",
        dated is None,
        str(dated and (dated.get("status"), dated.get("reason"))),
    )
    seed = answer(
        "At December 31, 2025, how many USD billions of seed capital investments in its products did TROW have?",
        rows,
        companies,
    )
    record(
        "generic investments does not answer seed capital",
        seed is None,
        str(seed and (seed.get("status"), seed.get("value"), seed.get("reason"))),
    )
    issued = answer(
        "What was the aggregate purchase amount of Venu's Series B preferred stock issued to Aramark on June 16, 2025, in USD millions?",
        rows,
        companies,
    )
    record(
        "generic issued does not answer a purchase amount",
        issued is None,
        str(issued and (issued.get("status"), issued.get("reason"))),
    )
    acquired = answer(
        "What was TROW's acquired investments for fiscal year 2025, in USD millions?",
        rows,
        companies,
    )
    record(
        "acquired investments still resolves",
        acquired and acquired["status"] == "answered" and acquired["value"] == 71.7,
        str(acquired and (acquired.get("status"), acquired.get("value"), acquired.get("reason"))),
    )
    stock = answer(
        "What was Apple's common stock issued for fiscal year 2025, in USD millions?",
        rows,
        companies,
    )
    record(
        "common stock issued still resolves",
        stock and stock["status"] == "answered" and stock["value"] == 1498,
        str(stock and (stock.get("status"), stock.get("value"), stock.get("reason"))),
    )
    named = answer(
        "What was Apple's change in fair value of derivative instruments for fiscal year 2025, in USD millions?",
        rows,
        companies,
    )
    record(
        "a line named change is the fiscal-year amount",
        named and named["status"] == "answered" and named["value"] == 849 and named["unit"] == "million",
        str(named and (named.get("status"), named.get("value"), named.get("reason"))),
    )


def test_balance_sheet_context_and_footnotes():
    companies = {
        "KO": "Coca-Cola Company",
        "WMT": "Walmart Inc.",
        "JPM": "JPMorgan Chase & Co.",
        "CAT": "Caterpillar Inc.",
        "NEE": "NextEra Energy, Inc.",
    }

    def assets(body, company, scale="million", filing="face.html"):
        return chunk(
            "Total assets: 2026=1, 2025=1, 2024=1, 2021=1, 2020=1\n" + body,
            company=company,
            scale=scale,
            filing=filing,
        )

    def aside(body, company, scale="million", filing="other.html"):
        return chunk(body, company=company, scale=scale, filing=filing)

    cases = [
        (
            "hold-024 balance-sheet accounts payable is the only scaled candidate",
            "What was Coca-Cola's accounts payable and accrued for fiscal year 2021, in USD millions?",
            [
                assets("Accounts payable and accrued expenses: 2021=14619, 2020=11145", "KO", filing="ko-face.html"),
                aside("Accounts payable and accrued expenses: 2021=(18), 2020=(19)", "KO"),
            ],
            14619,
        ),
        (
            "hold-032 uses the same balance-sheet row for the prior year",
            "What was Coca-Cola's accounts payable and accrued for fiscal year 2020, in USD millions?",
            [
                assets("Accounts payable and accrued expenses: 2021=14619, 2020=11145", "KO", filing="ko-face.html"),
                aside("Accounts payable and accrued expenses: 2021=(18), 2020=(19)", "KO"),
            ],
            11145,
        ),
        (
            "hold-050 keeps the balance-sheet payable when other tables disagree",
            "What was Coca-Cola's accounts payable and accrued for fiscal year 2025, in USD millions?",
            [
                assets("Accounts payable and accrued expenses: 2025=14813, 2024=21712", "KO", filing="ko-face.html"),
                aside("Accounts payable and accrued expenses: 2025=816, 2024=2", "KO", filing="ko-a.html"),
                aside("Accounts payable and accrued expenses: 2025=(8), 2024=(6)", "KO", filing="ko-b.html"),
            ],
            14813,
        ),
        (
            "hold-064 accrued income taxes stays on the balance sheet",
            "What was Coca-Cola's accrued income taxes for fiscal year 2025, in USD millions?",
            [
                assets("Accrued income taxes: 2025=525, 2024=400", "KO"),
                aside("Accrued income taxes: 2025=5, 2024=1", "KO"),
            ],
            525,
        ),
        (
            "hold-036 Walmart accrued income taxes uses the balance-sheet table",
            "What was Walmart's accrued income taxes for fiscal year 2021, in USD millions?",
            [
                assets("Accrued income taxes: 2021=242, 2020=280", "WMT"),
                aside("Accrued income taxes: 2021=(136), 2020=100", "WMT"),
            ],
            242,
        ),
        (
            "hold-053 Walmart accrued income taxes fiscal 2026",
            "What was Walmart's accrued income taxes for fiscal year 2026, in USD millions?",
            [
                assets("Accrued income taxes: 2026=596, 2025=608", "WMT"),
                aside("Accrued income taxes: 2026=113, 2025=435", "WMT"),
            ],
            596,
        ),
        (
            "hold-144 Walmart accrued income taxes fiscal 2025",
            "What was Walmart's accrued income taxes for fiscal year 2025, in USD millions?",
            [
                assets("Accrued income taxes: 2026=596, 2025=608", "WMT"),
                aside("Accrued income taxes: 2026=113, 2025=435", "WMT"),
            ],
            608,
        ),
        (
            "hold-042 receivable on the balance sheet is not the other table",
            "What was JPMorgan's accrued interest and accounts receivable for fiscal year 2021, in USD millions?",
            [
                assets("Accrued interest and accounts receivable: 2021=102570, 2020=90000", "JPM"),
                aside("Accrued interest and accounts receivable: 2021=(12401), 2020=1", "JPM", filing="jpm-a.html"),
                aside(
                    "Accrued interest and accounts receivable: 2021=102.1, 2020=90",
                    "JPM",
                    scale="billion",
                    filing="jpm-b.html",
                ),
            ],
            102570,
        ),
        (
            "hold-059 receivable fiscal 2025",
            "What was JPMorgan's accrued interest and accounts receivable for fiscal year 2025, in USD millions?",
            [
                assets("Accrued interest and accounts receivable: 2025=111599, 2024=101223", "JPM"),
                aside("Accrued interest and accounts receivable: 2025=(11514)", "JPM", filing="jpm-a.html"),
                aside("Accrued interest and accounts receivable: 2025=111.1", "JPM", scale="billion", filing="jpm-b.html"),
            ],
            111599,
        ),
        (
            "hold-142 receivable fiscal 2024",
            "What was JPMorgan's accrued interest and accounts receivable for fiscal year 2024, in USD millions?",
            [
                assets("Accrued interest and accounts receivable: 2025=111599, 2024=101223", "JPM"),
                aside("Accrued interest and accounts receivable: 2024=5735", "JPM", filing="jpm-a.html"),
                aside("Accrued interest and accounts receivable: 2024=111.0", "JPM", scale="billion", filing="jpm-b.html"),
            ],
            101223,
        ),
        (
            "hold-102 balance-sheet payable converts to billions",
            "What was Coca-Cola's accounts payable and accrued for fiscal year 2024, in USD billions?",
            [
                assets("Accounts payable and accrued expenses: 2025=14813, 2024=21712", "KO"),
                aside("Accounts payable and accrued expenses: 2024=2", "KO", filing="ko-a.html"),
                aside("Accounts payable and accrued expenses: 2024=(6)", "KO", filing="ko-b.html"),
            ],
            21.712,
        ),
    ]
    for name, question, rows, expected in cases:
        found = answer(question, rows, companies)
        record(
            name,
            found and found["status"] == "answered" and found["value"] == expected,
            str(found and (found.get("status"), found.get("value"), found.get("unit"), found.get("reason"))),
        )

    change_rows = [
        assets("Accounts payable and accrued expenses: 2021=14619, 2020=11145", "KO", filing="ko-face.html"),
        aside("Accounts payable and accrued expenses: 2021=(18), 2020=(19)", "KO"),
    ]
    change = answer(
        "By how many USD millions did Coca-Cola's accounts payable and accrued change from fiscal year 2020 to fiscal year 2021?",
        change_rows,
        companies,
    )
    record(
        "hold-118 balance-sheet change is 14619 minus 11145",
        change and change["status"] == "answered" and change["value"] == 3474 and change["unit"] == "million",
        str(change and (change.get("status"), change.get("value"), change.get("unit"), change.get("reason"))),
    )

    ambiguous = [
        (
            "hold-009 two balance-sheet payable values stay unresolved",
            "What was Caterpillar's accounts payable for fiscal year 2021, in USD millions?",
            [
                assets("Accounts payable: 2021=8154, 2020=6128", "CAT", filing="cat-face.html"),
                assets("Accounts payable: 2021=(167), 2020=7", "CAT", scale=None, filing="cat-note.html"),
                aside("Accounts payable: 2021=2041", "CAT"),
            ],
        ),
        (
            "hold-047 a descriptive payable note does not select the other row",
            "What was NextEra's accounts payable for fiscal year 2025, in USD millions?",
            [
                assets("Accounts payable: 2025=1084, 2024=996", "NEE", filing="nee-face.html"),
                assets(
                    "Accounts payable ($502 and $631 related to VIEs, respectively): 2025=7583, 2024=6982",
                    "NEE",
                    scale=None,
                    filing="nee-vie.html",
                ),
            ],
        ),
        (
            "hold-054 two accrued construction rows stay unresolved",
            "What was NextEra's accrued construction-related expenditures for fiscal year 2025, in USD millions?",
            [
                assets("Accrued construction-related expenditures: 2025=1153", "NEE", filing="nee-a.html"),
                assets("Accrued construction-related expenditures: 2025=2966", "NEE", scale=None, filing="nee-b.html"),
            ],
        ),
        (
            "hold-061 two accrued interest rows stay unresolved",
            "What was NextEra's accrued interest and taxes for fiscal year 2025, in USD millions?",
            [
                assets("Accrued interest and taxes: 2025=470", "NEE", filing="nee-a.html"),
                assets("Accrued interest and taxes: 2025=1185", "NEE", scale=None, filing="nee-b.html"),
            ],
        ),
        (
            "hold-089 two paid-in capital rows stay unresolved",
            "What was NextEra's additional paid-in capital for fiscal year 2025, in USD millions?",
            [
                assets("Additional paid-in capital: 2025=26866", "NEE", filing="nee-a.html"),
                assets("Additional paid-in capital: 2025=19494", "NEE", scale=None, filing="nee-b.html"),
            ],
        ),
        (
            "an unscaled balance-sheet copy does not adopt another table's amount",
            "What was Walmart's accounts payable for fiscal year 2019, in USD millions?",
            [
                assets("Accounts payable: 2021=49141, 2020=46973, 2019=47060", "WMT", scale=None, filing="wmt-supp.html"),
                aside("Accounts payable: 2021=6966, 2020=(274), 2019=1831", "WMT"),
            ],
        ),
    ]
    for name, question, rows in ambiguous:
        found = answer(question, rows, companies)
        record(
            name,
            found and found["status"] == "insufficient" and found.get("value") is None,
            str(found and (found.get("status"), found.get("value"), found.get("reason"))),
        )

    shared = answer(
        "What was Walmart's accounts payable for fiscal year 2021, in USD millions?",
        [
            assets("Accounts payable: 2021=49141, 2020=46973", "WMT", filing="wmt-face.html"),
            assets(
                "Accounts payable: 2021=49141, 2020=46973, 2019=47060",
                "WMT",
                scale=None,
                filing="wmt-supp.html",
            ),
            aside("Accounts payable: 2021=6966, 2020=(274), 2019=1831", "WMT"),
        ],
        companies,
    )
    record(
        "the same balance-sheet amount keeps the caption stated for that amount",
        shared and shared["status"] == "answered" and shared["value"] == 49141 and shared["unit"] == "million",
        str(shared and (shared.get("status"), shared.get("value"), shared.get("unit"), shared.get("reason"))),
    )

    footnotes = [
        chunk("Accrued asset removal costs(b): 2021=489, 2020=1179", company="NEE", scale=None, filing="nee-b.html"),
        chunk("Accrued asset removal costs(c): 2021=263, 2020=263", company="NEE", filing="nee-c.html"),
        chunk(
            "Accrued asset removal costs(c): 2021=752, 2020=1179",
            company="NEE",
            filing="nee-c2.html",
        ),
    ]
    for name, question in (
        (
            "hold-013 omitted footnote marker stays unresolved",
            "What was NextEra's accrued asset removal costs for fiscal year 2021, in USD millions?",
        ),
        (
            "hold-021 omitted footnote marker stays unresolved",
            "What was NextEra's accrued asset removal costs for fiscal year 2020, in USD millions?",
        ),
        (
            "hold-123 omitted footnote marker does not produce a change",
            "By how many USD millions did NextEra's accrued asset removal costs change from fiscal year 2020 to fiscal year 2021?",
        ),
    ):
        found = answer(question, footnotes, companies)
        record(
            name,
            found and found["status"] == "insufficient" and found.get("value") is None,
            str(found and (found.get("status"), found.get("value"), found.get("reason"))),
        )

    marked = [
        chunk("Maintenance revenue(b): 2025=40, 2024=30", company="NEE", filing="mark-b.html"),
        chunk("Maintenance revenue(c): 2025=10, 2024=9", company="NEE", filing="mark-c.html"),
    ]
    named = answer(
        "What was NextEra's maintenance revenue (c) for fiscal year 2025, in USD millions?",
        marked,
        companies,
    )
    record(
        "a question that names footnote (c) does not use (b)",
        named and named["status"] == "answered" and named["value"] == 10,
        str(named and (named.get("status"), named.get("value"), named.get("reason"))),
    )
    omitted = answer(
        "What was NextEra's maintenance revenue for fiscal year 2025, in USD millions?",
        marked,
        companies,
    )
    record(
        "omitting the marker abstains while (b) and (c) disagree",
        omitted and omitted["status"] == "insufficient" and omitted.get("value") is None,
        str(omitted and (omitted.get("status"), omitted.get("value"), omitted.get("reason"))),
    )
    only_c = answer(
        "What was NextEra's maintenance revenue for fiscal year 2025, in USD millions?",
        [marked[1]],
        companies,
    )
    record(
        "one footnote variant is the line when no other value exists",
        only_c and only_c["status"] == "answered" and only_c["value"] == 10,
        str(only_c and (only_c.get("status"), only_c.get("value"), only_c.get("reason"))),
    )
    described = answer(
        "What was NextEra's accounts payable ($502 and $631 related to VIEs, respectively) for fiscal year 2025, in USD millions?",
        [
            assets("Accounts payable: 2025=1084, 2024=996", "NEE", filing="nee-face.html"),
            assets(
                "Accounts payable ($502 and $631 related to VIEs, respectively): 2025=7583, 2024=6982",
                "NEE",
                filing="nee-vie.html",
            ),
        ],
        companies,
    )
    record(
        "a question that repeats a descriptive parenthesis uses that line",
        described and described["status"] == "answered" and described["value"] == 7583,
        str(described and (described.get("status"), described.get("value"), described.get("unit"), described.get("reason"))),
    )
    restored = answer(
        "What was Caterpillar's accrued wages salaries and employee benefits for fiscal year 2023, in USD millions?",
        [
            assets(
                "Accrued wages, salaries and employee benefits: 2025=187, 2024=(363)",
                "CAT",
                filing="cat-face.html",
            ),
            aside(
                "Accrued wages, salaries and employee benefits: 2025=10, 2024=11, 2023=486",
                "CAT",
                filing="cat-note.html",
            ),
        ],
        companies,
    )
    record(
        "a balance-sheet table without the requested year does not hide the only dated row",
        restored and restored["status"] == "answered" and restored["value"] == 486,
        str(restored and (restored.get("status"), restored.get("value"), restored.get("reason"))),
    )
    euros = answer(
        "What was Coca-Cola's accounts payable and accrued for fiscal year 2021, in euros?",
        [
            assets("Accounts payable and accrued expenses: 2021=14619, 2020=11145", "KO"),
        ],
        companies,
    )
    record(
        "euro conversion still abstains without an exchange rate",
        euros
        and euros["status"] == "insufficient"
        and euros.get("value") is None
        and "exchange rate" in (euros.get("reason") or ""),
        str(euros and (euros.get("status"), euros.get("value"), euros.get("reason"))),
    )


if __name__ == "__main__":
    test_selection_and_units()
    test_growth_ratio_and_refusals()
    test_batch1_safeguards()
    test_pipeline_skips_llm_for_a_unique_row()
    test_absolute_change()
    test_incidental_labels()
    test_balance_sheet_context_and_footnotes()
    test_real_filings()
    failed = [name for name, passed, _detail in results if not passed]
    print(f"\npassed={sum(1 for _n, ok, _d in results if ok)} failed={len(failed)}")
    if failed:
        sys.exit(1)
