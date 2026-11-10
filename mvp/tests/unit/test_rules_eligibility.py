from datetime import date
from decimal import Decimal
from pathlib import Path

from mvp.domain.countries import CountryReference, resolve_country_name
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


def test_account_catalog_excludes_no_va_causes_without_using_free_text() -> None:
    ruleset = load_ruleset_file(RULESET)
    payment = PaymentAllocation(
        "F1",
        "P1",
        date(2026, 9, 1),
        Decimal(118),
        review_flag="NO VA",
    )
    document = Document("F1", "internacional", "USD", Decimal(118), Decimal(100))

    for account in ("7011001", "7599001", "7599006", "7599007", "7599009"):
        line = DocumentLine(
            "F1",
            "L1",
            Decimal(100),
            Decimal(118),
            product_code="P1",
            account_code=account,
        )
        decision = evaluate(document, line, payment, ruleset)
        assert decision.code == "ACCOUNT_EXCLUDED"
        assert not decision.blocking

    sale_line = DocumentLine(
        "F1",
        "L2",
        Decimal(100),
        Decimal(118),
        product_code="P1",
        account_code="7022101",
    )
    assert evaluate(document, sale_line, payment, ruleset).code == "ELIGIBLE"


def test_digital_remains_outside_automatic_pilot() -> None:
    ruleset = load_ruleset_file(RULESET)
    document = Document("F1", "digital", "PEN", Decimal(118), Decimal(100))
    line = DocumentLine(
        "F1",
        "L1",
        Decimal(100),
        Decimal(118),
        product_code="P1",
        account_code="7022101",
    )
    payment = PaymentAllocation("F1", "P1", date(2026, 9, 1), Decimal(118))
    assert evaluate(document, line, payment, ruleset).code == "DIGITAL_OUT_OF_PILOT"


def test_country_name_is_resolved_once_to_persistable_identity() -> None:
    countries = (
        CountryReference(173, "Perú", "PE"),
        CountryReference(49, "Costa Rica", "CR"),
    )
    by_name = resolve_country_name("Costa Rica", countries)
    assert (by_name.country_id, by_name.country_code, by_name.matched_by) == (
        49,
        "CR",
        "name",
    )
    assert not by_name.blocking

    by_code = resolve_country_name("pe", countries)
    assert (by_code.country_id, by_code.country_code, by_code.matched_by) == (
        173,
        "PE",
        "code",
    )
    assert resolve_country_name("América", countries).reason == "COUNTRY_NOT_FOUND"


def test_ivonne_override_and_international_country_rules_are_structured() -> None:
    ruleset = load_ruleset_file(RULESET)
    override = next(
        item
        for item in ruleset.period_overrides
        if item.rule_id == "OVR-IVONNE-F522-ATREVIA-2026-09"
    )
    assert override.proposer == "Sandra"
    assert override.applied_by == "José Montero"
    assert override.matches(
        day=date(2026, 9, 28),
        invoice_ref="F F15-00000522",
        product_code="31392PER00007",
        product_name="ATREVIA TRIO CATS SPOT ON MEDIUM (X 5 PIP, STD)",
    )
    assert not override.matches(
        day=date(2026, 9, 28),
        invoice_ref="F F15-00000522",
        product_code="OTRO",
        product_name="ATREVIA TRIO CATS SPOT ON MEDIUM (X 5 PIP, STD)",
    )

    mayumi = next(
        rule
        for rule in ruleset.intl_rules
        if rule.rule_id == "INTL-MAYUMI-AVIVET-LATAM-V1"
    )
    luis = next(
        rule
        for rule in ruleset.intl_rules
        if rule.rule_id == "INTL-LUIS-PETMEDICA-AMERICA-V1"
    )
    assert mayumi.role == "Jefe Tecnico Comercial Latinoamerica Avivet"
    assert mayumi.rate_for("AVIVET") == Decimal("0.005")
    assert luis.rate_for("PETMEDICA") == Decimal("0.005")
    assert mayumi.country_group == luis.country_group == "america_latam"

    country_catalog = ruleset.country_groups["america_latam"]
    assert country_catalog.approved
    assert country_catalog.values == (
        "MX",
        "GT",
        "BZ",
        "SV",
        "HN",
        "NI",
        "CR",
        "PA",
        "CO",
        "VE",
        "EC",
        "PE",
        "BO",
        "BR",
        "PY",
        "UY",
        "AR",
        "CL",
        "GY",
        "SR",
        "GF",
    )

    for beneficiary, line in (
        ("Luis Chávez", "PETMEDICA"),
        ("Mayumi Garcilazo", "AVIVET"),
    ):
        included = resolve_beneficiary(
            beneficiary,
            ruleset.intl_rules,
            LineContext("F1", "P1", line, "C1", "PE", date(2026, 9, 1)),
            ruleset.country_groups,
        )
        assert included.reason == "RULE_APPLIED"
        assert included.rate == Decimal("0.005")
        for excluded_code in ("US", "CA", "DO", "Perú"):
            excluded = resolve_beneficiary(
                beneficiary,
                ruleset.intl_rules,
                LineContext(
                    "F1",
                    "P1",
                    line,
                    "C1",
                    excluded_code,
                    date(2026, 9, 1),
                ),
                ruleset.country_groups,
            )
            assert excluded.reason == "NO_RULE_IN_SCOPE"
