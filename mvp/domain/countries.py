"""Resolución única de nombres configurados contra el catálogo ``res.country``."""

from __future__ import annotations

from dataclasses import dataclass

from mvp.domain.rules import normalize_key


@dataclass(frozen=True, slots=True)
class CountryReference:
    """Proyección mínima y persistible de un registro de ``res.country``."""

    country_id: int
    name: str
    code: str


@dataclass(frozen=True, slots=True)
class CountryResolution:
    country_id: int | None
    country_code: str | None
    matched_by: str | None
    blocking: bool
    reason: str


def resolve_country_name(
    configured_name: str, countries: tuple[CountryReference, ...]
) -> CountryResolution:
    """Resuelve por nombre exacto normalizado y usa ISO como fallback exacto.

    No aplica coincidencias parciales ni difusas. Un valor ausente, desconocido o ambiguo
    queda bloqueado para revisión; los cálculos posteriores comparan el ``country_id`` o el
    código ISO persistido, nunca vuelven a comparar el texto configurado.
    """

    wanted = normalize_key(configured_name)
    if not wanted:
        return CountryResolution(None, None, None, True, "MISSING_COUNTRY_NAME")

    by_name = [
        country for country in countries if normalize_key(country.name) == wanted
    ]
    if len(by_name) == 1:
        country = by_name[0]
        return CountryResolution(
            country.country_id,
            normalize_key(country.code),
            "name",
            False,
            "COUNTRY_RESOLVED",
        )
    if len(by_name) > 1:
        return CountryResolution(None, None, None, True, "AMBIGUOUS_COUNTRY_NAME")

    by_code = [
        country for country in countries if normalize_key(country.code) == wanted
    ]
    if len(by_code) == 1:
        country = by_code[0]
        return CountryResolution(
            country.country_id,
            normalize_key(country.code),
            "code",
            False,
            "COUNTRY_RESOLVED",
        )
    if len(by_code) > 1:
        return CountryResolution(None, None, None, True, "AMBIGUOUS_COUNTRY_CODE")
    return CountryResolution(None, None, None, True, "COUNTRY_NOT_FOUND")
