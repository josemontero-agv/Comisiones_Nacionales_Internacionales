"""Aggregate FILTRO rules, role payouts, and whether Subtotal x Linea is already the prorated base."""
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from pathlib import Path

NSM = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

def q(tag):
    return f"{{{NSM}}}{tag}"

CALC = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\calculo_vendedores\COMISIONES 2026 SETIEMBRE (1).xlsx")
FT = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\SEP\FACTURAS\REPORTE DE COMISIONES NACIONAL FT CONTADO Y CREDITO -SEP-26.xlsx")
LT = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\SEP\LETRAS\REPORTE DE COMISIONES NACIONAL LT -SEP-26.xlsx")


def shared(z):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join((t.text or "") for t in si.iter(q("t"))) for si in root.findall(q("si"))]


def sheets_map(z):
    NSR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    out = {}
    for sh in wb.find(q("sheets")):
        out[sh.attrib["name"]] = "xl/" + relmap[sh.attrib[f"{{{NSR}}}id"]]
    return out


def col_row(ref):
    col = "".join(ch for ch in ref if ch.isalpha())
    row = int("".join(ch for ch in ref if ch.isdigit()) or 0)
    return col, row


def num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_sheet(path, sheet_name, want_cols):
    with zipfile.ZipFile(path) as z:
        ss = shared(z)
        sm = sheets_map(z)
        root = ET.fromstring(z.read(sm[sheet_name]))
        rows = defaultdict(dict)
        for c in root.iter(q("c")):
            col, row = col_row(c.attrib.get("r", ""))
            if row <= 1 or col not in want_cols:
                continue
            t = c.attrib.get("t")
            v = c.find(q("v"))
            is_el = c.find(q("is"))
            if t == "s" and v is not None and v.text:
                val = ss[int(v.text)]
            elif t == "inlineStr" and is_el is not None:
                val = "".join(x.text or "" for x in is_el.iter(q("t")))
            elif v is not None:
                val = v.text
            else:
                val = None
            rows[row][col] = val
        return rows


def main():
    print("Loading CONTADO and LETRAS...")
    # CONTADO / LETRAS columns
    cols = {
        "A": "tipo", "C": "estado", "D": "valorlt", "E": "ltsinigv", "F": "cantlt",
        "G": "factura", "K": "dias", "O": "condicion", "V": "sublinea", "X": "subft",
        "Z": "pagado", "AA": "impuesto", "AB": "linea", "AC": "zona",
        "AD": "rep", "AE": "com_rep", "AF": "jtec", "AG": "com_jtec",
        "AH": "jcom", "AI": "com_jcom", "AJ": "ger", "AK": "com_ger", "AL": "filtro",
    }
    contado = load_sheet(CALC, "CONTADO - CREDITO", set(cols))
    letras = load_sheet(CALC, "LETRAS", set(cols))
    cons_cols = {"A": "tipo", "AD": "puesto", "AE": "nombre", "AF": "comision", "AG": "filtro", "AB": "linea"}
    cons = load_sheet(CALC, "CONSOLIDADO", set(cons_cols))

    def summarize(name, rows):
        print(f"\n== {name} rows {len(rows)}")
        filtro = Counter(r.get("AL") for r in rows.values())
        tipo = Counter((r.get("A"), r.get("AL")) for r in rows.values())
        print(" FILTRO", filtro)
        print(" TIPO x FILTRO", tipo)
        # no comisiona profile
        noc = [r for r in rows.values() if r.get("AL") == "NO COMISIONA"]
        print(" NO COMISIONA", len(noc))
        print("  impuesto", Counter(r.get("AA") for r in noc).most_common(8))
        print("  estado", Counter(str(r.get("C"))[:40] for r in noc).most_common(8))
        print("  linea", Counter(r.get("AB") for r in noc).most_common(10))
        print("  condicion", Counter(str(r.get("O"))[:50] for r in noc).most_common(8))
        # dias buckets
        def bucket(v):
            n = num(v)
            if n is None:
                return "blank"
            if n < 0:
                return "negativo (pago antes)"
            if n == 0:
                return "0"
            if n <= 30:
                return "1-30"
            if n <= 60:
                return "31-60"
            if n <= 90:
                return "61-90"
            return "91+"
        print("  dias NO", Counter(bucket(r.get("K")) for r in noc))
        com = [r for r in rows.values() if r.get("AL") == "COMISIONA"]
        print("  dias SI", Counter(bucket(r.get("K")) for r in com))
        print("  impuesto SI", Counter(r.get("AA") for r in com))
        print("  linea SI", Counter(r.get("AB") for r in com))
        # blank filtro
        blank = [r for r in rows.values() if not r.get("AL")]
        print(" BLANK filtro", len(blank), "lineas", Counter(r.get("AB") for r in blank).most_common(6))
        # sums of commissions where COMISIONA
        def s(key):
            return sum(num(r.get(key)) or 0 for r in com)
        print(f"  SUM comisiones COMISIONA rep={s('AE'):.2f} jtec={s('AG'):.2f} jcom={s('AI'):.2f} ger={s('AK'):.2f} total={s('AE')+s('AG')+s('AI')+s('AK'):.2f}")
        # name 0 / blank with money
        weird = []
        for r in com:
            for name_k, com_k, puesto in (("AD","AE","rep"), ("AF","AG","jtec"), ("AH","AI","jcom"), ("AJ","AK","ger")):
                nm = r.get(name_k)
                cv = num(r.get(com_k)) or 0
                if cv and (nm in (None, "", "0") or str(nm).strip() in ("0", "N/A", "OFICINA")):
                    weird.append((puesto, nm, cv, r.get("AB"), r.get("G")))
        print("  weird name with money", len(weird), "sum", round(sum(w[2] for w in weird), 2))
        print("  weird sample", weird[:8])
        # partial payment: pagado vs total, sublinea vs proportional
        partial = 0
        full = 0
        base_matches_raw = 0
        checked = 0
        examples = []
        for r in list(com)[:]:
            pag = num(r.get("Z"))
            # total ft not loaded as Y. skip
        return com

    summarize("CONTADO", contado)
    summarize("LETRAS", letras)

    print("\n== CONSOLIDADO", len(cons))
    print(" filtro", Counter(r.get("AG") for r in cons.values()))
    print(" puesto", Counter(r.get("AD") for r in cons.values()))
    # sum by puesto where COMISIONA
    sums = defaultdict(float)
    by_person = defaultdict(float)
    by_person_tipo = defaultdict(float)
    for r in cons.values():
        if r.get("AG") != "COMISIONA":
            continue
        cv = num(r.get("AF")) or 0
        sums[r.get("AD")] += cv
        key = (r.get("AD"), r.get("AE") or "(vacio)")
        by_person[key] += cv
        by_person_tipo[(r.get("AE") or "(vacio)", r.get("A"))] += cv
    print(" sum by puesto", {k: round(v, 2) for k, v in sums.items()})
    print(" TOTAL", round(sum(sums.values()), 2))
    print("\n TOP personas")
    for k, v in sorted(by_person.items(), key=lambda kv: -kv[1])[:40]:
        print(f"  {v:12.2f}  {k[0]} | {k[1]}")
    # name 0
    print("\n nombre 0 / vacio / OFICINA / N/A")
    for k, v in sorted(by_person.items(), key=lambda kv: -kv[1]):
        if k[1] in ("0", "(vacio)", "OFICINA", "N/A", "None") or str(k[1]).strip() in ("0", ""):
            print(f"  {v:12.2f}  {k}")

    # Compare bases: load FT report key columns
    print("\n== Compare FT report base vs CONTADO sublinea")
    ft_cols = {
        "D": "dias_f", "I": "numero", "L": "subprod", "N": "subgen", "P": "pagado",
        "R": "sinigv_f", "S": "base_f", "T": "motivo", "V": "codigo", "X": "linea",
    }
    # formulas are stored; cached values may be in <v>. Good.
    ft = load_sheet(FT, "Sheet1", set(ft_cols))
    print(" FT rows", len(ft), "motivo", Counter(r.get("T") for r in ft.values()).most_common(12))
    # index by numero + codigo
    ft_idx = {}
    for r in ft.values():
        ft_idx.setdefault((r.get("I"), r.get("V")), []).append(r)
    matched = 0
    base_eq = 0
    raw_eq = 0
    neither = 0
    samples_diff = []
    for r in contado.values():
        key = (r.get("G"), r.get("P") if False else None)
    # contado referencia interna is column P, not loaded. reload? I didn't include P.
    print(" (referencia not loaded, matching by factura+sublinea rough)")

    # Reload contado with P
    contado2 = load_sheet(CALC, "CONTADO - CREDITO", {"G", "P", "V", "X", "Z", "AL", "A", "K"})
    matched = raw_eq = base_eq = neither = 0
    partial_raw = partial_base = 0
    examples = []
    for r in contado2.values():
        cands = ft_idx.get((r.get("G"), r.get("P")))
        if not cands:
            continue
        matched += 1
        sub = num(r.get("V"))
        # pick candidate with closest subprod or base
        best = None
        for c in cands:
            raw = num(c.get("L"))
            base = num(c.get("S"))
            if raw is not None and sub is not None and abs(raw - sub) < 0.05:
                best = ("raw", c)
                break
            if base is not None and sub is not None and abs(base - sub) < 0.05:
                best = ("base", c)
                break
        if best is None and cands:
            c = cands[0]
            raw = num(c.get("L"))
            base = num(c.get("S"))
            if sub is not None and raw is not None and base is not None:
                if abs(sub - raw) <= abs(sub - base):
                    best = ("closer_raw", c)
                else:
                    best = ("closer_base", c)
        if not best:
            neither += 1
            continue
        kind, c = best
        if kind == "raw":
            raw_eq += 1
        elif kind == "base":
            base_eq += 1
        else:
            neither += 1
            if len(examples) < 6:
                examples.append((r.get("G"), r.get("P"), sub, num(c.get("L")), num(c.get("S")), c.get("T"), r.get("AL"), num(r.get("Z")), num(c.get("P"))))
        pag = num(c.get("P"))
        tot = None
        # partial if motivo not OK or base != raw
        raw = num(c.get("L"))
        base = num(c.get("S"))
        if raw and base and abs(raw - base) > 0.05:
            if kind == "raw":
                partial_raw += 1
            elif kind == "base":
                partial_base += 1
    print(f" matched {matched} sublinea==raw {raw_eq} sublinea==base {base_eq} neither {neither}")
    print(f" among partial (base!=raw): counted as raw {partial_raw} as base {partial_base}")
    print(" examples neither/closer", examples)

    # letras compare
    print("\n== Compare LT report vs LETRAS")
    lt_cols = {"I": "numero", "J": "pagadas", "K": "totales", "N": "subprod", "P": "subgen", "R": "pagado", "S": "sinigv", "T": "base", "V": "codigo"}
    lt = load_sheet(LT, "Sheet1", set(lt_cols))
    print(" LT rows", len(lt))
    lt_idx = {}
    for r in lt.values():
        lt_idx.setdefault((r.get("I"), r.get("V")), []).append(r)
    letras2 = load_sheet(CALC, "LETRAS", {"B", "F", "G", "P", "V", "D", "E", "AL", "Z"})
    m = raw_eq = base_eq = div_eq = 0
    samples = []
    cant_vs = Counter()
    for r in letras2.values():
        cands = lt_idx.get((r.get("G"), r.get("P")))
        if not cands:
            continue
        m += 1
        c = cands[0]
        sub = num(r.get("V"))
        raw = num(c.get("N"))
        base = num(c.get("T"))
        cant = num(r.get("F"))
        tot = num(c.get("K"))
        pagadas = num(c.get("J"))
        if cant is not None and tot is not None and abs(cant - tot) < 0.01:
            cant_vs["cant=letras_totales"] += 1
        elif cant is not None and pagadas is not None and abs(cant - pagadas) < 0.01:
            cant_vs["cant=letras_pagadas"] += 1
        else:
            cant_vs["cant=otro"] += 1
        if sub is not None and raw is not None and abs(sub - raw) < 0.05:
            raw_eq += 1
        elif sub is not None and base is not None and abs(sub - base) < 0.05:
            base_eq += 1
        elif sub is not None and raw is not None and cant and abs(sub - raw / cant) < 0.05:
            div_eq += 1
        elif len(samples) < 5:
            samples.append((r.get("G"), sub, raw, base, cant, tot, pagadas, r.get("B")))
    print(f" matched {m} sub==raw {raw_eq} sub==base {base_eq} sub==raw/cant {div_eq}")
    print(" cant vs reporte", cant_vs)
    print(" samples", samples)

    # How many letras rows per factura+product vs letras pagadas
    # estado distribution comisiona
    print("\n LETRAS estado x filtro")
    est = Counter((r.get("C"), r.get("AL")) for r in letras.values())
    for k, v in est.most_common(20):
        print(f"  {v:6} {k}")


if __name__ == "__main__":
    main()
