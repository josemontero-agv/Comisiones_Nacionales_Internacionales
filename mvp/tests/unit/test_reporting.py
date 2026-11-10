from decimal import Decimal

import pytest

from mvp.application.reporting import build_commission_pivot


def _payload(channel: str, person: str = "Persona") -> dict:
    return {
        "manifest": {"channel": channel},
        "rows": [
            {
                "category": "CONTADO",
                "commission_presented": "10.25",
                "role": "Gerente",
                "commercial_line": "AGROVET",
                "person": person,
                "currency": "PEN",
            },
            {
                "category": "LETRAS",
                "commission_presented": "2.75",
                "role": "Gerente",
                "commercial_line": "AGROVET",
                "person": person,
                "currency": "PEN",
            },
        ],
    }


def test_pivot_has_required_shape_and_hierarchy() -> None:
    rows = build_commission_pivot([_payload("nacional")])
    assert rows == [
        {
            "Puesto": "Gerente",
            "Línea comercial": "AGROVET",
            "Nombre": "Persona",
            "CONTADO": Decimal("10.25"),
            "CREDITO": Decimal(0),
            "LETRAS": Decimal("2.75"),
            "Total": Decimal("13.00"),
        }
    ]


def test_pivot_rejects_mixed_channels() -> None:
    with pytest.raises(ValueError, match="mezclar canales"):
        build_commission_pivot(
            [_payload("nacional"), _payload("internacional", "Otra persona")]
        )
