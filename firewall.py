"""
firewall.py — Investment quality and ethics pre-screening gate.

Runs before any Buffett analysis. Returns a FirewallResult that tells the
app whether to PASS (full analysis), WARN (show analysis + banner), or
BLOCK (halt with explanation).

Why this exists:
  Buffett's methodology only works on businesses with real, measurable
  economics. Applying it to shell companies, leveraged ETFs, or penny stocks
  produces meaningless scores. The firewall prevents misleading output.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, List
import metrics


# Sectors/industries flagged for ethical transparency.
# These are not automatically blocked — Buffett himself owns some of these —
# but the user deserves to know what they are analyzing.
ETHICS_FLAGGED_INDUSTRIES = {
    "tobacco", "cigarette", "alcohol", "beverage—brewers", "gambling",
    "casinos", "defense", "aerospace & defense", "weapons", "arms",
    "adult entertainment", "pornography",
}

# Sectors that yfinance returns which indicate non-equity instruments.
NON_EQUITY_TYPES = {
    "etf", "mutualfund", "index", "fund", "bond", "currency",
    "cryptocurrency", "futures", "option",
}

# Known inverse/leveraged ETF keyword signals in the short name
LEVERAGED_ETF_KEYWORDS = {"ultrashort", "ultra pro", "2x", "3x", "-2x", "-3x",
                           "inverse", "bear", "short", "direxion", "proshares ultra"}


@dataclass
class FirewallIssue:
    level: Literal["block", "warn"]
    code: str
    message: str
    detail: str


@dataclass
class FirewallResult:
    status: Literal["PASS", "WARN", "BLOCK"]
    issues: List[FirewallIssue] = field(default_factory=list)

    @property
    def block_issues(self) -> List[FirewallIssue]:
        return [i for i in self.issues if i.level == "block"]

    @property
    def warn_issues(self) -> List[FirewallIssue]:
        return [i for i in self.issues if i.level == "warn"]


def run(symbol: str) -> FirewallResult:
    """
    Run all firewall checks for the given ticker symbol.
    Returns a FirewallResult with status and a list of issues.
    """
    info = metrics.get_info(symbol)
    issues: List[FirewallIssue] = []

    # --- Check 1: Ticker must exist and return real data ---
    if not info:
        issues.append(FirewallIssue(
            level="block",
            code="INVALID_TICKER",
            message="Ticker not found",
            detail=(
                f"'{symbol}' did not return valid data from Yahoo Finance. "
                "Verify that the ticker is correct (e.g. AAPL, KO, MSFT)."
            ),
        ))
        return FirewallResult(status="BLOCK", issues=issues)

    quote_type = str(info.get("quoteType", "")).lower()
    short_name = str(info.get("shortName") or info.get("longName") or "").lower()

    # --- Check 2: Must be an equity (stock), not a fund/ETF/crypto ---
    if quote_type in NON_EQUITY_TYPES:
        issues.append(FirewallIssue(
            level="block",
            code="NOT_AN_EQUITY",
            message=f"Non-analyzable instrument: {quote_type.upper()}",
            detail=(
                "Buffett analysis requires a company with real financial statements. "
                f"'{symbol}' is a {quote_type.upper()}, not an individual stock. "
                "Look for companies like KO, AAPL, JNJ."
            ),
        ))

    # --- Check 3: Detect leveraged/inverse ETFs by name ---
    if any(kw in short_name for kw in LEVERAGED_ETF_KEYWORDS):
        issues.append(FirewallIssue(
            level="block",
            code="LEVERAGED_ETF",
            message="Leveraged or inverse ETF detected",
            detail=(
                "Leveraged/inverse ETFs have no business fundamentals. "
                "They are speculative instruments incompatible with value analysis."
            ),
        ))

    # --- Check 4: Market cap must be >= $300M ---
    market_cap = info.get("marketCap")
    if market_cap is not None and market_cap < 300_000_000:
        cap_m = market_cap / 1_000_000
        issues.append(FirewallIssue(
            level="block",
            code="MICRO_CAP",
            message=f"Very low market cap: ${cap_m:.0f}M",
            detail=(
                f"With a market cap of ${cap_m:.0f}M, this company is micro/nano-cap. "
                "Financial data is often incomplete or unreliable at this scale. "
                "Buffett invests in companies with durable competitive advantages, "
                "which generally requires significant scale."
            ),
        ))

    # --- Check 5: Must have at least 3 years of income data ---
    income = metrics.get_income_statement(symbol)
    years_of_data = income.shape[1] if not income.empty else 0
    if years_of_data < 3:
        issues.append(FirewallIssue(
            level="block",
            code="INSUFFICIENT_HISTORY",
            message=f"Insufficient financial history: {years_of_data} year(s)",
            detail=(
                "At least 3 years of annual financial statements are required "
                "to assess consistency and trends. "
                f"Only {years_of_data} period(s) were found for '{symbol}'."
            ),
        ))

    # --- Check 6: Negative book value (equity) ---
    book_value = info.get("bookValue")
    if book_value is not None and book_value < 0:
        issues.append(FirewallIssue(
            level="block",
            code="NEGATIVE_EQUITY",
            message="Negative equity",
            detail=(
                f"Book value per share is ${book_value:.2f} (negative). "
                "This invalidates P/B and ROE calculations. May indicate excessive debt "
                "or accumulated losses. Buffett avoids companies with negative equity."
            ),
        ))

    # --- Check 7: Zero or missing revenue ---
    revenue_hist = metrics.get_revenue_history(symbol)
    if not revenue_hist["values"] or all(v == 0 for v in revenue_hist["values"]):
        issues.append(FirewallIssue(
            level="block",
            code="NO_REVENUE",
            message="No reported revenue",
            detail=(
                "No revenue found in financial statements. "
                "Could be a pre-operational company, shell company, or a "
                "data issue with Yahoo Finance."
            ),
        ))

    # --- Check 8: High beta (warn only, not block) ---
    beta = info.get("beta")
    if beta is not None and beta > 4:
        issues.append(FirewallIssue(
            level="warn",
            code="HIGH_VOLATILITY",
            message=f"Extreme volatility: Beta = {beta:.2f}",
            detail=(
                f"Beta of {beta:.2f} indicates volatility far above the market. "
                "Buffett seeks predictable businesses ('within his circle of competence'). "
                "Such high beta suggests speculation or elevated sector risk. "
                "The analysis is shown, but with this warning."
            ),
        ))

    # --- Check 9: Ethics / sector transparency flag ---
    industry = str(info.get("industry") or "").lower()
    sector = str(info.get("sector") or "").lower()
    combined = industry + " " + sector

    # Use word-boundary matching to avoid "alcohol" matching "non-alcoholic"
    import re
    flagged_terms = [
        term for term in ETHICS_FLAGGED_INDUSTRIES
        if re.search(r'\b' + re.escape(term) + r'\b', combined)
    ]
    if flagged_terms:
        issues.append(FirewallIssue(
            level="warn",
            code="ETHICS_FLAG",
            message=f"Sector with ethical considerations: {info.get('industry', 'N/A')}",
            detail=(
                f"This company operates in '{info.get('industry', sector)}', "
                "a sector that some investors exclude for ethical or value reasons. "
                "Financial analysis is applied normally, but consider whether this "
                "type of business aligns with your investment principles."
            ),
        ))

    # --- Check 10: No price data ---
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        issues.append(FirewallIssue(
            level="warn",
            code="NO_PRICE",
            message="Current price not available",
            detail=(
                "Could not obtain the current market price. "
                "Valuation calculations (P/E, P/B) may be inaccurate. "
                "Verify that the market is open or that the ticker is active."
            ),
        ))

    # --- Determine final status ---
    if any(i.level == "block" for i in issues):
        status = "BLOCK"
    elif any(i.level == "warn" for i in issues):
        status = "WARN"
    else:
        status = "PASS"

    return FirewallResult(status=status, issues=issues)
