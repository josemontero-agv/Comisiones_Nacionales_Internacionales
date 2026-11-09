"""Ruleset versionado: catálogos, matriz Nacional, beneficiarios Internacional y precedencia.

El ruleset es un dato auditable (JSON versionado); este módulo solo lo interpreta. La
precedencia determinista es factura > producto > línea > cliente > país > TODOS; a igual
alcance gana mayor prioridad y luego la versión vigente más reciente; una exclusión gana a
una inclusión empatada y un empate no resoluble se informa como conflicto.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from mvp.domain.money import to_decimal
from mvp.domain.periods import parse_date

SCOPE_RANK = {
    "factura": 6,
    "producto": 5,
    "linea": 4,
    "cliente": 3,
    "pais": 2,
    "todos": 1,
}

ROLE_ORDER = ("Representante de Ventas", "Jefe Tecnico", "Jefe Comercial", "Gerente")

_SPACES = re.compile(r"\s+")


def normalize_key(value: str | None) -> str:
    """Normaliza claves de catálogo: mayúsculas, sin espacios duplicados ni NBSP."""
    if value is None:
        return ""
    return _SPACES.sub(" ", str(value).replace("\xa0", " ")).strip().upper()


@dataclass(frozen=True, slots=True)
class Catalog:
    catalog_id: str
    approved: bool
    values: tuple[str, ...]
    evidence: str = ""

    def contains(self, value: str | None) -> bool:
        return normalize_key(value) in {normalize_key(v) for v in self.values}


@dataclass(frozen=True, slots=True)
class RoleAssignment:
    role: str
    person: str | None
    rate: Decimal | None


@dataclass(frozen=True, slots=True)
class NacionalRule:
    rule_key: str
    commercial_line: str
    roles: tuple[RoleAssignment, ...]

    @property
    def rule_id(self) -> str:
        return f"NAC:{normalize_key(self.rule_key)}"


@dataclass(frozen=True, slots=True)
class ZoneVariant:
    variant_id: str
    zone_prefix: str
    suffix: str
    product_family: str | None = None
    line_category_prefix: str | None = None


@dataclass(frozen=True, slots=True)
class ScopedRule:
    rule_id: str
    beneficiary: str
    scope_type: str
    scope_values: tuple[str, ...]
    rates: tuple[tuple[str, Decimal], ...]
    lines: tuple[str, ...] = ()
    priority: int = 0
    effect: str = "include"
    version: int = 1
    valid_from: date | None = None
    valid_to: date | None = None
    approved: bool = True
    country_group: str | None = None
    evidence: str = ""

    def rate_for(self, commercial_line: str | None) -> Decimal | None:
        key = normalize_key(commercial_line)
        for line, rate in self.rates:
            if normalize_key(line) == key:
                return rate
        return None

    def is_valid_on(self, day: date) -> bool:
        if self.valid_from and day < self.valid_from:
            return False
        return not (self.valid_to and day > self.valid_to)


@dataclass(frozen=True, slots=True)
class ProductOverride:
    rule_id: str
    product_code: str
    commercial_line: str
    approved: bool
    evidence: str


@dataclass(frozen=True, slots=True)
class LineContext:
    """Atributos de una línea que pueden activar el alcance de una regla."""

    doc_key: str
    product_code: str | None
    commercial_line: str | None
    partner_ref: str | None
    country_code: str | None
    payment_date: date


@dataclass(frozen=True, slots=True)
class Resolution:
    beneficiary: str
    rule: ScopedRule | None
    rate: Decimal | None
    excluded: bool
    conflict: bool
    reason: str


@dataclass(frozen=True, slots=True)
class Ruleset:
    version: str
    sha256: str
    catalogs: dict[str, Catalog]
    category_by_term: dict[str, dict[str, str]]
    letter_eligible_status: tuple[str, ...]
    letter_excluded_status: tuple[str, ...]
    product_overrides: tuple[ProductOverride, ...]
    nacional_rules: tuple[NacionalRule, ...]
    zone_variants: tuple[ZoneVariant, ...]
    product_families: dict[str, Catalog]
    country_groups: dict[str, Catalog]
    intl_rules: tuple[ScopedRule, ...]
    raw: dict

    def catalog(self, catalog_id: str) -> Catalog:
        return self.catalogs[catalog_id]

    def nacional_rule(self, rule_key: str) -> NacionalRule | None:
        wanted = normalize_key(rule_key)
        for rule in self.nacional_rules:
            if normalize_key(rule.rule_key) == wanted:
                return rule
        return None

    def override_for(self, product_code: str | None) -> ProductOverride | None:
        wanted = normalize_key(product_code)
        for override in self.product_overrides:
            if normalize_key(override.product_code) == wanted:
                return override
        return None

    def in_product_family(self, family: str, product_code: str | None) -> bool:
        catalog = self.product_families.get(family)
        if catalog is None or not product_code:
            return False
        code = normalize_key(product_code)
        return any(code.startswith(normalize_key(prefix)) for prefix in catalog.values)

    def provisional_items(self) -> list[tuple[str, str]]:
        items = [
            (c.catalog_id, c.evidence) for c in self.catalogs.values() if not c.approved
        ]
        items += [
            (c.catalog_id, c.evidence)
            for c in self.product_families.values()
            if not c.approved
        ]
        items += [
            (c.catalog_id, c.evidence)
            for c in self.country_groups.values()
            if not c.approved
        ]
        items += [(r.rule_id, r.evidence) for r in self.intl_rules if not r.approved]
        items += [
            (o.rule_id, o.evidence) for o in self.product_overrides if not o.approved
        ]
        return sorted(items)


def canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _catalog(catalog_id: str, data: dict) -> Catalog:
    return Catalog(
        catalog_id=catalog_id,
        approved=bool(data.get("approved", False)),
        values=tuple(str(v) for v in data.get("values", [])),
        evidence=str(data.get("evidence", "")),
    )


def _rate(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return to_decimal(str(value))


def load_ruleset(data: dict) -> Ruleset:
    catalogs = {cid: _catalog(cid, c) for cid, c in data["catalogs"].items()}
    families = {
        fid: _catalog(fid, c) for fid, c in data.get("product_families", {}).items()
    }
    groups = {
        gid: _catalog(gid, c) for gid, c in data.get("country_groups", {}).items()
    }
    nacional = data.get("nacional", {})
    nac_rules = tuple(
        NacionalRule(
            rule_key=row["rule_key"],
            commercial_line=row.get("commercial_line", ""),
            roles=tuple(
                RoleAssignment(
                    role=r["role"], person=r.get("person"), rate=_rate(r.get("rate"))
                )
                for r in row["roles"]
            ),
        )
        for row in nacional.get("matrix", [])
    )
    variants = tuple(
        ZoneVariant(
            variant_id=v["variant_id"],
            zone_prefix=v["zone_prefix"],
            suffix=v["suffix"],
            product_family=v.get("product_family"),
            line_category_prefix=v.get("line_category_prefix"),
        )
        for v in nacional.get("zone_variants", [])
    )
    intl_rules = tuple(
        ScopedRule(
            rule_id=r["rule_id"],
            beneficiary=r["beneficiary"],
            scope_type=r["scope"]["type"],
            scope_values=tuple(r["scope"].get("values", [])),
            rates=tuple((k, to_decimal(str(v))) for k, v in sorted(r["rates"].items())),
            lines=tuple(r.get("lines", [])),
            priority=int(r.get("priority", 0)),
            effect=r.get("effect", "include"),
            version=int(r.get("version", 1)),
            valid_from=parse_date(r.get("valid_from")),
            valid_to=parse_date(r.get("valid_to")),
            approved=bool(r.get("approved", False)),
            country_group=r["scope"].get("country_group"),
            evidence=str(r.get("evidence", "")),
        )
        for r in data.get("internacional", {}).get("rules", [])
    )
    for rule in intl_rules:
        if rule.scope_type not in SCOPE_RANK:
            raise ValueError(
                f"unknown scope type {rule.scope_type!r} in {rule.rule_id}"
            )
        if rule.effect not in ("include", "exclude"):
            raise ValueError(f"unknown effect {rule.effect!r} in {rule.rule_id}")
    overrides = tuple(
        ProductOverride(
            rule_id=o["rule_id"],
            product_code=o["product_code"],
            commercial_line=o["commercial_line"],
            approved=bool(o.get("approved", False)),
            evidence=str(o.get("evidence", "")),
        )
        for o in data.get("product_overrides", [])
    )
    letters = data.get("letters", {})
    return Ruleset(
        version=data["ruleset_version"],
        sha256=hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest(),
        catalogs=catalogs,
        category_by_term={
            channel: {normalize_key(k): v for k, v in terms.items()}
            for channel, terms in data.get("payment_term_category", {}).items()
        },
        letter_eligible_status=tuple(
            normalize_key(s) for s in letters.get("eligible_status", [])
        ),
        letter_excluded_status=tuple(
            normalize_key(s) for s in letters.get("excluded_status", [])
        ),
        product_overrides=overrides,
        nacional_rules=nac_rules,
        zone_variants=variants,
        product_families=families,
        country_groups=groups,
        intl_rules=intl_rules,
        raw=data,
    )


def load_ruleset_file(path: Path) -> Ruleset:
    return load_ruleset(json.loads(path.read_text(encoding="utf-8")))


def _scope_matches(
    rule: ScopedRule, ctx: LineContext, groups: dict[str, Catalog]
) -> bool:
    if rule.lines and normalize_key(ctx.commercial_line) not in {
        normalize_key(x) for x in rule.lines
    }:
        return False
    values = {normalize_key(v) for v in rule.scope_values}
    if rule.scope_type == "todos":
        return True
    if rule.scope_type == "factura":
        return normalize_key(ctx.doc_key) in values
    if rule.scope_type == "producto":
        return normalize_key(ctx.product_code) in values
    if rule.scope_type == "linea":
        return normalize_key(ctx.commercial_line) in values
    if rule.scope_type == "cliente":
        return normalize_key(ctx.partner_ref) in values
    if rule.scope_type == "pais":
        if ctx.country_code is None:
            return False
        if rule.country_group:
            group = groups.get(rule.country_group)
            return bool(group and group.contains(ctx.country_code))
        return normalize_key(ctx.country_code) in values
    return False


def resolve_beneficiary(
    beneficiary: str,
    rules: tuple[ScopedRule, ...],
    ctx: LineContext,
    groups: dict[str, Catalog],
) -> Resolution:
    candidates = [
        r
        for r in rules
        if r.beneficiary == beneficiary
        and r.is_valid_on(ctx.payment_date)
        and _scope_matches(r, ctx, groups)
    ]
    if not candidates:
        return Resolution(beneficiary, None, None, False, False, "NO_RULE_IN_SCOPE")
    top_rank = max(SCOPE_RANK[r.scope_type] for r in candidates)
    tier = [r for r in candidates if SCOPE_RANK[r.scope_type] == top_rank]
    top_priority = max(r.priority for r in tier)
    tier = [r for r in tier if r.priority == top_priority]
    exclusions = [r for r in tier if r.effect == "exclude"]
    if exclusions:
        chosen = max(exclusions, key=lambda r: (r.version, r.rule_id))
        return Resolution(beneficiary, chosen, None, True, False, "EXCLUDED_BY_RULE")
    top_version = max(r.version for r in tier)
    tier = [r for r in tier if r.version == top_version]
    rates = {r.rate_for(ctx.commercial_line) for r in tier}
    if len(tier) > 1 and len(rates) > 1:
        return Resolution(beneficiary, None, None, False, True, "RULE_CONFLICT")
    chosen = min(tier, key=lambda r: r.rule_id)
    rate = chosen.rate_for(ctx.commercial_line)
    if rate is None:
        return Resolution(beneficiary, chosen, None, False, False, "NO_RATE_FOR_LINE")
    return Resolution(beneficiary, chosen, rate, False, False, "RULE_APPLIED")


def intl_beneficiaries(rules: tuple[ScopedRule, ...]) -> tuple[str, ...]:
    return tuple(sorted({r.beneficiary for r in rules}))
