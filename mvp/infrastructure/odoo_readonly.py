"""Cliente XML-RPC de Odoo estrictamente de solo lectura.

Solo se permiten `fields_get`, `search_count`, `search_read` y `read`. Toda lectura declara
campos explícitos, pagina por `id` ascendente (sin offsets) y resuelve relaciones en lotes.
"""

from __future__ import annotations

import os
import xmlrpc.client
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

ALLOWED_METHODS = frozenset({"fields_get", "search_count", "search_read", "read"})
DEFAULT_PAGE_SIZE = 300


class ReadOnlyViolation(RuntimeError):
    """Se intentó invocar un método que no es de lectura."""


class OdooTransport(Protocol):
    def execute_kw(self, model: str, method: str, args: list, kwargs: dict) -> Any: ...


@dataclass(frozen=True, slots=True)
class OdooCredentials:
    url: str
    db: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> OdooCredentials:
        """Lee credenciales de variables de entorno (cargadas desde `.env` por el CLI)."""
        missing = [
            k
            for k in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_PASSWORD")
            if not os.getenv(k)
        ]
        if missing:
            raise RuntimeError(
                f"missing Odoo environment variables: {', '.join(missing)}"
            )
        return cls(
            url=os.environ["ODOO_URL"].rstrip("/"),
            db=os.environ["ODOO_DB"],
            user=os.environ["ODOO_USER"],
            password=os.environ["ODOO_PASSWORD"],
        )

    def __repr__(self) -> str:
        return (
            f"OdooCredentials(url={self.url!r}, db={self.db!r}, user=***, password=***)"
        )


class XmlRpcTransport:
    def __init__(
        self, credentials: OdooCredentials, timeout_seconds: int = 120
    ) -> None:
        self._credentials = credentials
        common = xmlrpc.client.ServerProxy(f"{credentials.url}/xmlrpc/2/common")
        uid = common.authenticate(
            credentials.db, credentials.user, credentials.password, {}
        )
        if not uid:
            raise RuntimeError("Odoo authentication failed")
        self._uid = uid
        self._models = xmlrpc.client.ServerProxy(
            f"{credentials.url}/xmlrpc/2/object", allow_none=True
        )
        self.server_version = str(common.version().get("server_version", ""))

    def execute_kw(self, model: str, method: str, args: list, kwargs: dict) -> Any:
        c = self._credentials
        return self._models.execute_kw(
            c.db, self._uid, c.password, model, method, args, kwargs
        )


class OdooReadOnlyClient:
    def __init__(
        self, transport: OdooTransport, page_size: int = DEFAULT_PAGE_SIZE
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        self._transport = transport
        self.page_size = page_size
        self.calls: list[tuple[str, str]] = []

    def _call(self, model: str, method: str, args: list, kwargs: dict) -> Any:
        if method not in ALLOWED_METHODS:
            raise ReadOnlyViolation(
                f"method {method!r} is not allowed (read-only client)"
            )
        self.calls.append((model, method))
        return self._transport.execute_kw(model, method, args, kwargs)

    def execute(self, model: str, method: str, *args: Any, **kwargs: Any) -> Any:
        """Punto único de salida; rechaza cualquier método fuera de la lista blanca."""
        return self._call(model, method, list(args), kwargs)

    def fields_get(self, model: str) -> dict[str, dict]:
        return self._call(
            model, "fields_get", [], {"attributes": ["type", "relation", "string"]}
        )

    def search_count(self, model: str, domain: list) -> int:
        return int(self._call(model, "search_count", [domain], {}))

    def search_read_paged(
        self, model: str, domain: list, fields: Sequence[str]
    ) -> Iterator[dict]:
        if not fields:
            raise ValueError("explicit fields are required")
        last_id = 0
        while True:
            batch = self._call(
                model,
                "search_read",
                [list(domain) + [("id", ">", last_id)]],
                {"fields": list(fields), "order": "id asc", "limit": self.page_size},
            )
            if not batch:
                return
            yield from batch
            last_id = batch[-1]["id"]
            if len(batch) < self.page_size:
                return

    def read_by_ids(
        self, model: str, ids: Iterable[int], fields: Sequence[str]
    ) -> list[dict]:
        unique = sorted({int(i) for i in ids if i})
        rows: list[dict] = []
        for start in range(0, len(unique), self.page_size):
            chunk = unique[start : start + self.page_size]
            rows.extend(self.search_read_paged(model, [("id", "in", chunk)], fields))
        return sorted(rows, key=lambda r: r["id"])

    def search_by_values(
        self,
        model: str,
        field: str,
        values: Iterable[str],
        fields: Sequence[str],
        extra_domain: list | None = None,
    ) -> list[dict]:
        unique = sorted({v for v in values if v})
        rows: list[dict] = []
        for start in range(0, len(unique), self.page_size):
            chunk = unique[start : start + self.page_size]
            domain = [(field, "in", chunk)] + list(extra_domain or [])
            rows.extend(self.search_read_paged(model, domain, fields))
        return sorted(rows, key=lambda r: r["id"])
