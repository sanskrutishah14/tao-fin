"""Table-specific caption and unit scale.

Run from the backend directory:

    python tests/test_table_parser.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.financial_lookup import format_amount, resolve_table_question
from app.services.table_parser import extract_table_chunks


RESULTS = []
SEC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "sec",
)
COMPANIES = {
    "AAPL": "Apple Inc.",
    "VENU": "Venu Holding Corporation",
}


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail else ""))


def _line(chunks, needle):
    return next(item for item in chunks if needle in item["text"])


def _ask(question, chunks):
    return resolve_table_question(question, chunks, COMPANIES)


SYNTHETIC = """
<html><body>
<p>CONSOLIDATED STATEMENTS OF OPERATIONS (In millions, except number of shares, which are reflected in thousands, and per-share amounts)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Net sales</td><td>416161</td><td>391035</td></tr>
<tr><td>Earnings per share - Basic</td><td>7.49</td><td>6.11</td></tr>
</table>
<p>(in thousands)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Regional headcount</td><td>120045</td><td>110045</td></tr>
</table>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Uncaptioned obligation</td><td>999991</td><td>888881</td></tr>
</table>
<p>(in square feet)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Floor space</td><td>440001</td><td>430001</td></tr>
</table>
<p>(in percent)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Effective tax rate</td><td>24.1</td><td>24.0</td></tr>
</table>
<table>
<tr><td>Instrument</td><td>2025 Amount (in millions)</td><td>2024</td></tr>
<tr><td>Standalone debt principal</td><td>912810</td><td>973410</td></tr>
</table>
<p>(in millions and in thousands)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Mixed caption line</td><td>151515</td><td>141414</td></tr>
</table>
<p>(in thousands)</p>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Conflicting fact</td><td><ix:nonFraction scale="6" unitRef="USD">180180</ix:nonFraction></td><td><ix:nonFraction scale="6" unitRef="USD">170170</ix:nonFraction></td></tr>
</table>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Cash on hand</td><td><ix:nonFraction scale="0" unitRef="USD">41306358</ix:nonFraction></td><td><ix:nonFraction scale="0" unitRef="USD">37969454</ix:nonFraction></td></tr>
</table>
<p>(in billions)</p>
<div>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Wrapped assets</td><td>359241</td><td>364980</td></tr>
</table>
<table>
<tr><td></td><td>2025</td><td>2024</td></tr>
<tr><td>Wrapped neighbor</td><td>285508</td><td>308030</td></tr>
</table>
</div>
</body></html>
"""


def test_synthetic_captions():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "captions.html")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(SYNTHETIC)
        chunks = extract_table_chunks(
            path,
            metadata={"company": "AAPL", "form": "10-K", "filing": "captions.html", "source": "SEC"},
        )

    sales = _line(chunks, "Net sales: 2025=416161")
    record(
        "operations caption is millions and marks per-share",
        sales["metadata"].get("statement_scale") == "million"
        and sales["metadata"].get("per_share_in_caption") is True,
        str(sales["metadata"].get("statement_scale")),
    )
    headcount = _line(chunks, "Regional headcount")
    record(
        "following table keeps its own thousands caption",
        headcount["metadata"].get("statement_scale") == "thousand",
        str(headcount["metadata"].get("statement_scale")),
    )
    bare = _line(chunks, "Uncaptioned obligation")
    record(
        "table with no usable caption stays unscaled",
        bare["metadata"].get("statement_scale") is None,
        str(bare["metadata"].get("statement_scale")),
    )
    floor = _line(chunks, "Floor space")
    record(
        "square-feet caption is not a money scale",
        floor["metadata"].get("statement_scale") is None,
        str(floor["metadata"].get("statement_scale")),
    )
    tax = _line(chunks, "Effective tax rate")
    record(
        "explicit percent caption is percent",
        tax["metadata"].get("statement_scale") == "percent",
        str(tax["metadata"].get("statement_scale")),
    )
    debt = _line(chunks, "Standalone debt principal")
    record(
        "unit inside this table's header is used",
        debt["metadata"].get("statement_scale") == "million",
        str(debt["metadata"].get("statement_scale")),
    )
    mixed = _line(chunks, "Mixed caption line")
    record(
        "two money units in one caption stay unknown",
        mixed["metadata"].get("statement_scale") is None,
        str(mixed["metadata"].get("statement_scale")),
    )
    conflict = _line(chunks, "Conflicting fact")
    record(
        "caption and XBRL that disagree stay unknown",
        conflict["metadata"].get("statement_scale") is None,
        str(conflict["metadata"].get("statement_scale")),
    )
    cash = _line(chunks, "Cash on hand")
    record(
        "unique USD scale of 0 is dollars",
        cash["metadata"].get("statement_scale") == "dollar",
        str(cash["metadata"].get("statement_scale")),
    )
    wrapped = _line(chunks, "Wrapped assets")
    neighbor = _line(chunks, "Wrapped neighbor")
    record(
        "a wrapper caption does not leak into the next table",
        wrapped["metadata"].get("statement_scale") == "billion"
        and neighbor["metadata"].get("statement_scale") is None,
        f"{wrapped['metadata'].get('statement_scale')} / {neighbor['metadata'].get('statement_scale')}",
    )

    eps = _ask("What was Apple's basic earnings per share for fiscal year 2025?", chunks)
    record(
        "per-share value is not scaled by the millions caption",
        eps and eps["status"] == "answered" and eps["value"] == 7.49 and eps["unit"] == "usd_per_share",
        str(eps and (eps.get("status"), eps.get("value"), eps.get("unit"), eps.get("reason"))),
    )
    eps_millions = _ask(
        "What was Apple's basic earnings per share for fiscal year 2025, in USD millions?",
        chunks,
    )
    record(
        "asking for EPS in millions is insufficient",
        eps_millions and eps_millions["status"] == "insufficient",
        str(eps_millions and (eps_millions.get("status"), eps_millions.get("value"), eps_millions.get("reason"))),
    )
    billions = _ask(
        "What was Apple's wrapped assets for fiscal year 2025, in USD billions?",
        chunks,
    )
    record(
        "millions are not involved; billions caption converts once",
        billions and billions["status"] == "answered" and billions["value"] == 359241 and billions["unit"] == "billion",
        str(billions and (billions.get("status"), billions.get("value"), billions.get("unit"), billions.get("reason"))),
    )
    sales_billions = _ask(
        "What was Apple's net sales for fiscal year 2025, in USD billions?",
        chunks,
    )
    record(
        "millions convert to billions once",
        sales_billions
        and sales_billions["status"] == "answered"
        and sales_billions["value"] == 416.161
        and sales_billions["unit"] == "billion",
        str(sales_billions and (sales_billions.get("status"), sales_billions.get("value"), sales_billions.get("unit"))),
    )
    bare_ask = _ask(
        "What was Apple's uncaptioned obligation for fiscal year 2025, in USD millions?",
        chunks,
    )
    record(
        "an unscaled large number is not treated as millions",
        bare_ask and bare_ask["status"] == "insufficient",
        str(bare_ask and (bare_ask.get("status"), bare_ask.get("reason"))),
    )
    dollars = _ask(
        "What was Apple's cash on hand for fiscal year 2025, in USD millions?",
        chunks,
    )
    record(
        "explicit dollars convert to millions once",
        dollars and dollars["status"] == "answered" and dollars["value"] == 41.306358 and dollars["unit"] == "million",
        str(dollars and (dollars.get("status"), dollars.get("value"), dollars.get("unit"), dollars.get("reason"))),
    )
    percent = _ask(
        "What was Apple's effective tax rate for fiscal year 2025, in percent?",
        chunks,
    )
    record(
        "a percent caption is returned as a percent",
        percent and percent["status"] == "answered" and percent["value"] == 24.1 and percent["unit"] == "percent",
        str(percent and (percent.get("status"), percent.get("value"), percent.get("unit"), percent.get("reason"))),
    )
    percent_as_money = _ask(
        "What was Apple's effective tax rate for fiscal year 2025, in USD millions?",
        chunks,
    )
    record(
        "a percent table is not converted into millions",
        percent_as_money and percent_as_money["status"] == "insufficient",
        str(percent_as_money and percent_as_money.get("reason")),
    )


def test_real_filings():
    apple = extract_table_chunks(
        os.path.join(SEC, "AAPL_10-K_000032019325000079.html"),
        metadata={"company": "AAPL", "form": "10-K", "filing": "AAPL_10-K.html", "source": "SEC"},
    )
    venu = extract_table_chunks(
        os.path.join(SEC, "VENU_10-K_000149315226014137.html"),
        metadata={"company": "VENU", "form": "10-K", "filing": "VENU_10-K.html", "source": "SEC"},
    )
    services = _line(apple, "Net sales - Services: 2025=109158")
    record(
        "Apple services statement uses its millions caption",
        services["metadata"].get("statement_scale") == "million"
        and services["metadata"].get("per_share_in_caption") is True
        and "Net sales - Services: 2025=109158, 2024=96169, 2023=85200" in services["text"],
        str(services["metadata"].get("statement_scale")),
    )
    debt = _line(apple, "Total term debt principal: 2025=91281")
    record(
        "Apple debt table keeps the millions unit in its own header",
        debt["metadata"].get("statement_scale") == "million",
        str(debt["metadata"].get("statement_scale")),
    )
    assets = _ask(
        "What was Apple's total assets at the end of fiscal year 2025, in USD billions?",
        apple,
    )
    record(
        "Apple total assets convert from millions to billions once",
        assets and assets["status"] == "answered" and assets["value"] == 359.241 and assets["unit"] == "billion",
        str(assets and (assets.get("status"), assets.get("value"), assets.get("unit"), assets.get("reason"))),
    )
    eps = _ask("What was Apple's basic earnings per share for fiscal year 2025?", apple)
    record(
        "Apple basic EPS stays 7.49 per share",
        eps and eps["status"] == "answered" and eps["value"] == 7.49 and eps["unit"] == "usd_per_share",
        str(eps and (eps.get("status"), eps.get("value"), eps.get("unit"), eps.get("reason"))),
    )
    revenue = _line(venu, "Total revenues, net: 2025=17897046")
    cash = _line(venu, "Cash and cash equivalents: 2025=41306358")
    venu_assets = _line(venu, "Total assets: 2025=370555035")
    venu_liabilities = _line(venu, "Total liabilities: 2025=171703684")
    dollar_rows = [
        item for item in venu if item["metadata"].get("statement_scale") == "dollar"
    ]
    record(
        "Venu statement tables without a stated scale stay unscaled",
        revenue["metadata"].get("statement_scale") is None
        and cash["metadata"].get("statement_scale") is None
        and venu_assets["metadata"].get("statement_scale") is None
        and venu_liabilities["metadata"].get("statement_scale") is None,
        " ".join(
            f"{name}={chunk['metadata'].get('statement_scale')}"
            for name, chunk in (
                ("revenue", revenue),
                ("assets", venu_assets),
                ("cash", cash),
                ("liabilities", venu_liabilities),
            )
        ),
    )
    record(
        "Venu uses dollar only on a table that states it",
        len(dollar_rows) >= 1
        and revenue["metadata"].get("statement_scale") is None
        and cash["metadata"].get("statement_scale") is None,
        f"dollar_chunks={len(dollar_rows)}",
    )
    record(
        "a dollar-to-million conversion keeps six decimal places",
        format_amount(50.781223) == "50.781223" and format_amount(359.241) == "359.241",
        format_amount(50.781223),
    )
    venu_loss = _ask(
        "What was VENU's net loss for fiscal year 2025, in USD millions?",
        venu,
    )
    record(
        "Venu net loss converts from explicit dollars once",
        venu_loss
        and venu_loss["status"] == "answered"
        and venu_loss["value"] == 50.781223
        and venu_loss["unit"] == "million",
        str(venu_loss and (venu_loss.get("status"), venu_loss.get("value"), venu_loss.get("unit"), venu_loss.get("reason"))),
    )
    for question in (
        "What was VENU's total revenues, net for fiscal year 2025, in USD millions?",
        "What was VENU's total assets at the end of fiscal year 2025, in USD millions?",
        "What was VENU's cash and cash equivalents at the end of fiscal year 2025, in USD millions?",
        "What was VENU's total liabilities at the end of fiscal year 2025, in USD millions?",
    ):
        found = _ask(question, venu)
        record(
            f"Venu without a scale abstains: {question[:42]}",
            found and found["status"] == "insufficient",
            str(found and (found.get("status"), found.get("reason"))),
        )
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "usd-no-scale.html")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "<html><body><table><tr><td></td><td>2025</td><td>2024</td></tr>"
                "<tr><td>Total assets</td>"
                "<td><ix:nonFraction unitRef=\"USD\" decimals=\"0\">370555035</ix:nonFraction></td>"
                "<td><ix:nonFraction unitRef=\"USD\" decimals=\"0\">178417515</ix:nonFraction></td>"
                "</tr></table></body></html>"
            )
        no_scale = extract_table_chunks(
            path,
            metadata={"company": "VENU", "form": "10-K", "filing": "usd-no-scale.html", "source": "SEC"},
        )
    bare_assets = _line(no_scale, "Total assets: 2025=370555035")
    record(
        "USD with decimals 0 and no scale attribute is not a scale",
        bare_assets["metadata"].get("statement_scale") is None,
        str(bare_assets["metadata"].get("statement_scale")),
    )
    venu_revenue = _ask(
        "What was VENU's total revenues, net for fiscal year 2025, in USD millions?",
        venu,
    )
    record(
        "Venu revenue without a unit is insufficient",
        venu_revenue and venu_revenue["status"] == "insufficient",
        str(venu_revenue and (venu_revenue.get("status"), venu_revenue.get("reason"))),
    )


WALMART_CAPTION = """
<html><body>
<table>
<tr><td>Walmart Inc. selected comparative schedule for retail operations and membership clubs across formats</td></tr>
<tr><td>Supplemental balance sheet rollforward prepared for the annual filing cover page</td></tr>
<tr><td>Columns below repeat the date heading before the unit caption</td></tr>
<tr><td>This preamble is long enough that a short prefix cannot see the unit</td></tr>
<tr><td>The unit caption belongs to this table and not to the next one</td></tr>
<tr><td>(Amounts in millions)</td></tr>
<tr><td></td><td>2026</td><td>2025</td></tr>
<tr><td>Total assets</td><td>284668</td><td>260823</td></tr>
<tr><td>Accounts payable</td><td>63061</td><td>58666</td></tr>
</table>
<table>
<tr><td></td><td>2026</td><td>2025</td></tr>
<tr><td>Total assets</td><td>10</td><td>9</td></tr>
<tr><td>Accounts payable</td><td>1611</td><td>3228</td></tr>
</table>
<table>
<tr><td>Uncaptioned obligation schedule with a long header so a later note is outside the header window and outside the first caption prefix</td><td>2026</td><td>2025</td></tr>
<tr><td>Uncaptioned obligation</td><td>111</td><td>222</td></tr>
<tr><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td></tr>
<tr><td></td><td></td><td></td></tr>
<tr><td>See the other schedule (Amounts in millions) for a different presentation</td><td></td><td></td></tr>
</table>
</body></html>
"""


def test_walmart_caption_stays_on_its_table():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "walmart-caption.html")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(WALMART_CAPTION)
        chunks = extract_table_chunks(
            path,
            metadata={"company": "WMT", "form": "10-K", "filing": "walmart-caption.html", "source": "SEC"},
        )
    face = _line(chunks, "Accounts payable: 2026=63061")
    neighbor = _line(chunks, "Accounts payable: 2026=1611")
    noted = _line(chunks, "Uncaptioned obligation: 2026=111")
    record(
        "Amounts in millions attaches to the table whose header states it",
        face["metadata"].get("statement_scale") == "million",
        str(face["metadata"].get("statement_scale")),
    )
    record(
        "the next table does not inherit Amounts in millions",
        neighbor["metadata"].get("statement_scale") is None,
        str(neighbor["metadata"].get("statement_scale")),
    )
    record(
        "a note below the header is not this table's scale",
        noted["metadata"].get("statement_scale") is None,
        str(noted["metadata"].get("statement_scale")),
    )


if __name__ == "__main__":
    test_synthetic_captions()
    test_walmart_caption_stays_on_its_table()
    test_real_filings()
    failed = [item for item in RESULTS if not item[1]]
    print(f"passed={len(RESULTS) - len(failed)} failed={len(failed)}")
    raise SystemExit(1 if failed else 0)
