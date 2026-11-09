from datetime import date
from decimal import Decimal
from pathlib import Path

from mvp.domain.eligibility import evaluate
from mvp.domain.models import Document, DocumentLine, PaymentAllocation
from mvp.domain.rules import (
    LineContext,
    ScopedRule,
    load_ruleset_file,
    resolve_beneficiary,
)

RULESET = Path(__file__).resolve().parents[2] / "rulesets/2026-09.v1.json"


def test_exclusions_are_explicit_and_unknown_account_blocks() -> None:
    ruleset = load_ruleset_file(RULESET)
    line = DocumentLine(
        doc_key="F1",
        line_key="L1",
        price_subtotal=Decimal(100),
        price_total=Decimal(118),
        product_code="P1",
        account_code="999",
    )
    payment = PaymentAllocation("F1", "P1", date(2026, 9, 1), Decimal(118))
    boleta = Document(
        "F1", "nacional", "PEN", Decimal(118), Decimal(100), doc_type_code="03"
    )
    assert evaluate(boleta, line, payment, ruleset).code == "DOCUMENT_TYPE_EXCLUDED"
    invoice = Document("F1", "nacional", "PEN", Decimal(118), Decimal(100))
    decision = evaluate(invoice, line, payment, ruleset)
    assert decision.code == "UNKNOWN_ACCOUNT"
    assert decision.blocking


def test_scope_precedence_and_conflict() -> None:
    day = date(2026, 9, 1)
    context = LineContext("F1", "P1", "PETMEDICA", "C1", "PE", day)
    rules = (
        ScopedRule("all", "Ana", "todos", (), (("PETMEDICA", Decimal("0.01")),)),
        ScopedRule(
            "product", "Ana", "producto", ("P1",), (("PETMEDICA", Decimal("0.02")),)
        ),
    )
    resolution = resolve_beneficiary("Ana", rules, context, {})
    assert resolution.rule and resolution.rule.rule_id == "product"
    assert resolution.rate == Decimal("0.02")

    conflict = rules + (
        ScopedRule(
            "product-2", "Ana", "producto", ("P1",), (("PETMEDICA", Decimal("0.03")),)
        ),
    )
    assert resolve_beneficiary("Ana", conflict, context, {}).conflict
