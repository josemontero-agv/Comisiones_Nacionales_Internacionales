"use client";

import { useEffect, useState } from "react";

const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:5000"
).replace(/\/$/, "");

const LIMITE_FILAS = 80;

const CANALES = [
  { id: "nacional", etiqueta: "Nacional" },
  { id: "internacional", etiqueta: "Internacional" },
] as const;

type Canal = (typeof CANALES)[number]["id"];

type Salud = {
  status?: string;
  payable?: boolean;
  pilot?: boolean;
  backend?: string;
  database_ready?: boolean;
  message?: string;
};

type Totales = {
  currency?: string;
  expected?: string;
  calculated?: string;
  difference?: string;
};

type Resumen = {
  notice?: string;
  channel?: string;
  period_start?: string;
  period_end?: string;
  totals?: Totales;
  persona_puesto?: Fila[];
  detalle?: Fila[];
  excepciones?: Fila[];
  diferencias?: Fila[];
  counts?: Record<string, number>;
};

type Fila = Record<string, unknown>;

const COLUMNAS_PUESTO: Columna[] = [
  ["Puesto", "Puesto"],
  ["Línea comercial", "Línea comercial"],
  ["Nombre", "Nombre"],
  ["CONTADO", "Contado"],
  ["CREDITO", "Crédito"],
  ["LETRAS", "Letras"],
  ["Total", "Total"],
];

const COLUMNAS_DETALLE: Columna[] = [
  ["document", "Documento"],
  ["line", "Línea"],
  ["category", "Categoría"],
  ["commercial_line", "Línea comercial"],
  ["person", "Persona"],
  ["role", "Puesto"],
  ["currency", "Moneda"],
  ["commission_presented", "Comisión"],
  ["rule_id", "Regla"],
];

const COLUMNAS_EXCEPCION: Columna[] = [
  ["key", "Clave"],
  ["code", "Código"],
  ["blocking", "Bloquea"],
  ["detail", "Detalle"],
  ["amount", "Importe"],
];

const COLUMNAS_DIFERENCIA: Columna[] = [
  ["key", "Clave"],
  ["classification", "Clasificación"],
  ["expected", "Esperado"],
  ["actual", "Calculado"],
  ["delta", "Diferencia"],
  ["detail", "Detalle"],
];

type Columna = readonly [string, string];

export default function PaginaComisiones() {
  const [canal, setCanal] = useState<Canal>("nacional");
  const [oscuro, setOscuro] = useState(false);
  const [salud, setSalud] = useState<Salud | null>(null);
  const [errorSalud, setErrorSalud] = useState("");
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [avisoCanal, setAvisoCanal] = useState("");
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", oscuro);
  }, [oscuro]);

  useEffect(() => {
    const controlador = new AbortController();
    fetch(`${API_URL}/health`, { signal: controlador.signal })
      .then(async (respuesta) => {
        const cuerpo = (await respuesta.json()) as Salud;
        if (!respuesta.ok) {
          throw new Error(cuerpo.message || "La API no respondió bien.");
        }
        setSalud(cuerpo);
        setErrorSalud("");
      })
      .catch((error: unknown) => {
        if (controlador.signal.aborted) return;
        setSalud(null);
        setErrorSalud(
          error instanceof Error
            ? error.message
            : "No se pudo leer /health."
        );
      });
    return () => controlador.abort();
  }, []);

  useEffect(() => {
    const controlador = new AbortController();
    setCargando(true);
    setAvisoCanal("");
    setResumen(null);
    fetch(`${API_URL}/api/canales/${canal}/resumen`, {
      signal: controlador.signal,
    })
      .then(async (respuesta) => {
        const cuerpo = (await respuesta.json()) as Resumen & {
          message?: string;
          error?: string;
        };
        if (!respuesta.ok) {
          setResumen(null);
          setAvisoCanal(
            cuerpo.message ||
              "No hay un cierre Gold para este canal. La API no lo calcula."
          );
          return;
        }
        setResumen(cuerpo);
      })
      .catch((error: unknown) => {
        if (controlador.signal.aborted) return;
        setResumen(null);
        setAvisoCanal(
          error instanceof Error
            ? error.message
            : "No se pudo leer el resumen."
        );
      })
      .finally(() => {
        if (!controlador.signal.aborted) setCargando(false);
      });
    return () => controlador.abort();
  }, [canal]);

  const etiqueta =
    CANALES.find((item) => item.id === canal)?.etiqueta ?? canal;
  const totales = resumen?.totals;
  const detalle = recortar(resumen?.detalle);
  const puesto = recortar(resumen?.persona_puesto);
  const excepciones = recortar(resumen?.excepciones);
  const diferencias = recortar(resumen?.diferencias);
  const hayRecorte =
    detalle.ocultas + puesto.ocultas + excepciones.ocultas + diferencias.ocultas >
    0;

  return (
    <main className="page">
      <header className="header">
        <div>
          <h1>Comisiones {etiqueta}</h1>
          <p className="lead">
            Lectura de Gold ya calculado. Nacional e Internacional no se
            mezclan. Flask no calcula en esta pantalla.
          </p>
        </div>
        <button
          type="button"
          className="ghost"
          onClick={() => setOscuro((valor) => !valor)}
        >
          {oscuro ? "Modo claro" : "Modo oscuro"}
        </button>
      </header>

      <section className="banner" role="status">
        <strong>Septiembre 2026 no es pagable.</strong>
        Es un piloto. Faltan cierres adicionales por canal y esta vista no
        entrega a nómina. Ningún periodo nace aprobado.
      </section>

      <section className="card" aria-live="polite">
        <span>Salud de la API</span>
        {errorSalud ? (
          <p className="error" role="alert">
            {errorSalud} Arranque la API con python -m api y deje DATABASE_URL
            en el servidor.
          </p>
        ) : salud ? (
          <p>
            Estado{" "}
            <strong className={salud.status === "ok" ? "status-ok" : ""}>
              {salud.status}
            </strong>
            . Backend {salud.backend || "—"}. Base{" "}
            {salud.database_ready ? "lista" : "no lista"}. Pagable: no.
          </p>
        ) : (
          <p>Consultando /health…</p>
        )}
        {salud?.message ? <p className="note">{salud.message}</p> : null}
      </section>

      <div className="toolbar">
        <div>
          <p className="meta">Canal</p>
          <div className="channels" role="group" aria-label="Canal">
            {CANALES.map((item) => (
              <button
                key={item.id}
                type="button"
                className="channel"
                aria-pressed={canal === item.id}
                onClick={() => setCanal(item.id)}
              >
                {item.etiqueta}
              </button>
            ))}
          </div>
        </div>
        <a className="download" href={`${API_URL}/api/canales/${canal}/xlsx`}>
          Descargar Excel de {etiqueta}
        </a>
      </div>

      {resumen?.notice ? <p className="note">{resumen.notice}</p> : null}
      {resumen?.period_start ? (
        <p className="note">
          Periodo {resumen.period_start} a {resumen.period_end}. Los importes
          salen del manifiesto Gold; esta página no los recalcula.
        </p>
      ) : null}

      <section className="totals" aria-label="Totales">
        <article className="card">
          <span>Esperado</span>
          <strong>{monto(totales?.expected, totales?.currency)}</strong>
        </article>
        <article className="card">
          <span>Calculado</span>
          <strong>{monto(totales?.calculated, totales?.currency)}</strong>
        </article>
        <article className="card">
          <span>Diferencia</span>
          <strong>{monto(totales?.difference, totales?.currency)}</strong>
        </article>
      </section>

      {cargando ? (
        <p className="loading" role="status">
          Cargando el resumen de {etiqueta}…
        </p>
      ) : null}
      {avisoCanal ? (
        <section className="panel">
          <h2>Sin cierre para mostrar</h2>
          <p>{avisoCanal}</p>
          <p className="note">
            Un 404 sin Gold es el resultado esperado mientras las tablas
            estén vacías. La descarga del Excel responde igual hasta que
            exista el cierre de este canal.
          </p>
        </section>
      ) : null}

      {resumen ? (
        <div className="stack">
          {hayRecorte ? (
            <p className="limit-note">
              Se muestran como máximo {LIMITE_FILAS} filas por tabla. El
              Excel trae el libro completo.
            </p>
          ) : (
            <p className="note">
              Si el detalle supera {LIMITE_FILAS} filas, la pantalla recorta
              y el Excel trae el libro completo.
            </p>
          )}
          <Panel
            titulo="Resumen persona × puesto"
            cuenta={resumen.counts?.persona_puesto}
            columnas={COLUMNAS_PUESTO}
            filas={puesto.visibles}
          />
          <Panel
            titulo="Detalle"
            cuenta={resumen.counts?.detalle}
            columnas={COLUMNAS_DETALLE}
            filas={detalle.visibles}
          />
          <Panel
            titulo="Excepciones"
            cuenta={resumen.counts?.excepciones}
            columnas={COLUMNAS_EXCEPCION}
            filas={excepciones.visibles}
          />
          <Panel
            titulo="Diferencias"
            cuenta={resumen.counts?.diferencias}
            columnas={COLUMNAS_DIFERENCIA}
            filas={diferencias.visibles}
          />
        </div>
      ) : null}
    </main>
  );
}

function Panel({
  titulo,
  cuenta,
  columnas,
  filas,
}: {
  titulo: string;
  cuenta?: number;
  columnas: Columna[];
  filas: Fila[];
}) {
  return (
    <section className="panel">
      <h2>
        {titulo}
        {typeof cuenta === "number" ? ` (${cuenta})` : ""}
      </h2>
      {filas.length === 0 ? (
        <p className="empty">Sin filas en este corte.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {columnas.map(([clave, etiqueta]) => (
                  <th key={clave}>{etiqueta}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, indice) => (
                <tr key={String(fila.key ?? indice)}>
                  {columnas.map(([clave]) => (
                    <td key={clave}>{textoCelda(fila[clave])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function recortar(filas: Fila[] | undefined): { visibles: Fila[]; ocultas: number } {
  const todas = filas ?? [];
  return {
    visibles: todas.slice(0, LIMITE_FILAS),
    ocultas: Math.max(0, todas.length - LIMITE_FILAS),
  };
}

function monto(valor: string | undefined, moneda: string | undefined): string {
  if (!valor) return "—";
  return moneda ? `${moneda} ${valor}` : valor;
}

function textoCelda(valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  if (typeof valor === "boolean") return valor ? "Sí" : "No";
  if (typeof valor === "object") return JSON.stringify(valor);
  return String(valor);
}
