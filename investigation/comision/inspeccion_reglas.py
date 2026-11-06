"""Explain FILTRO, reconcile pivot total, and locate hidden pivot filters."""
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict, Counter
from pathlib import Path

NSM = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NSR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def q(tag):
    return f"{{{NSM}}}{tag}"

CALC = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\calculo_vendedores\COMISIONES 2026 SETIEMBRE (1).xlsx")
FT = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\SEP\FACTURAS\REPORTE DE COMISIONES NACIONAL FT CONTADO Y CREDITO -SEP-26.xlsx")


def shared(z):
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    return ["".join((t.text or "") for t in si.iter(q("t"))) for si in root.findall(q("si"))]


def sheets_map(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    return {sh.attrib["name"]: "xl/" + relmap[sh.attrib[f"{{{NSR}}}id"]] for sh in wb.find(q("sheets"))}


def col_row(ref):
    col = "".join(ch for ch in ref if ch.isalpha())
    row = int("".join(ch for ch in ref if ch.isdigit()) or 0)
    return col, row


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_sheet(path, sheet_name, want):
    with zipfile.ZipFile(path) as z:
        ss = shared(z)
        sm = sheets_map(z)
        root = ET.fromstring(z.read(sm[sheet_name]))
        rows = defaultdict(dict)
        for c in root.iter(q("c")):
            col, row = col_row(c.attrib.get("r", ""))
            if row <= 1 or col not in want:
                continue
            t = c.attrib.get("t")
            v = c.find(q("v"))
            if t == "s" and v is not None and v.text:
                val = ss[int(v.text)]
            elif v is not None:
                val = v.text
            else:
                val = None
            rows[row][col] = val
        return rows


def main():
    print("=== PIVOT XML filters ===")
    with zipfile.ZipFile(CALC) as z:
        xml = z.read("xl/pivotTables/pivotTable1.xml").decode("utf-8")
        # print filter-related slices
        root = ET.fromstring(z.read("xl/pivotTables/pivotTable1.xml"))
        print("attribs", root.attrib)
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag.lower() in ("pivotfilter", "filter", "autofilter", "item", "pagefield") or "filter" in tag.lower() or tag in ("pivotField",):
                pass
        # pivotFields compact: which are axis and hidden items
        pfs = root.find(q("pivotFields"))
        for i, pf in enumerate(pfs.findall(q("pivotField"))):
            axis = pf.attrib.get("axis")
            items = pf.find(q("items"))
            hidden = []
            shown = 0
            if items is not None:
                for it in items.findall(q("item")):
                    if it.attrib.get("h") == "1":
                        hidden.append(it.attrib.get("x"))
                    else:
                        shown += 1
            if axis or hidden or pf.attrib.get("numFmtId"):
                print(f" field[{i}] axis={axis} attrs={dict(pf.attrib)} hidden_count={len(hidden)} shown={shown} hidden_x={hidden[:20]}")
        # data fields and row fields already known
        loc = root.find(q("location"))
        print("location", loc.attrib if loc is not None else None)
        pf = root.find(q("pageFields"))
        print("pageFields raw", ET.tostring(pf, encoding="unicode")[:1500] if pf is not None else None)

    cons = load_sheet(CALC, "CONSOLIDADO", {"A", "AB", "AD", "AE", "AF", "AG", "C"})
    # reconcile
    def amt(r):
        return num(r.get("AF")) or 0

    total = sum(amt(r) for r in cons.values() if r.get("AG") == "COMISIONA")
    no0 = sum(amt(r) for r in cons.values() if r.get("AG") == "COMISIONA" and str(r.get("AE")) not in ("0", "N/A", "OFICINA"))
    print(f"\nconsolidado COMISIONA {total:.4f}")
    print(f"excluding nombre 0/N/A/OFICINA {no0:.4f}")

    # by linea of name 0
    by = defaultdict(float)
    for r in cons.values():
        if r.get("AG") == "COMISIONA" and str(r.get("AE")) == "0":
            by[(r.get("AD"), r.get("AB"))] += amt(r)
    print("nombre 0 by puesto/linea", {k: round(v, 2) for k, v in by.items()})

    # which lineas are in pivot (from earlier visual): exclude EQUESTRIA?
    pivot_lineas = {"AGROVET & OTROS", "PETMEDICA", "INTERPET", "AVIVET & AGV", "PET NUTRISCIENCE"}
    sub = sum(amt(r) for r in cons.values() if r.get("AG") == "COMISIONA" and r.get("AB") in pivot_lineas and str(r.get("AE")) not in ("0",))
    print(f"only pivot lineas exclude name 0: {sub:.4f}")
    sub2 = sum(amt(r) for r in cons.values() if r.get("AG") == "COMISIONA" and r.get("AB") in pivot_lineas)
    print(f"only pivot lineas keep name 0: {sub2:.4f}")

    bylinea = defaultdict(float)
    for r in cons.values():
        if r.get("AG") == "COMISIONA":
            bylinea[r.get("AB")] += amt(r)
    print("comisiona by linea")
    for k, v in sorted(bylinea.items(), key=lambda kv: -kv[1]):
        print(f"  {v:12.2f} {k}")

    # FILTRO rules on CONTADO using impuesto, linea, dias
    print("\n=== FILTRO rules CONTADO ===")
    cont = load_sheet(CALC, "CONTADO - CREDITO", {"A", "K", "O", "V", "X", "Z", "Y", "AA", "AB", "AC", "AL", "G", "P"})
    def bucket_dias(v):
        n = num(v)
        if n is None:
            return "blank"
        if n > 30:
            return ">30"
        return "<=30"

    ct = Counter((r.get("AA"), r.get("AB"), bucket_dias(r.get("K")), r.get("AL")) for r in cont.values())
    # collapse: predict NO if TTG or linea in GENVET/OTROS or dias>30 or linea blank
    pred_ok = pred_bad = 0
    bad_samples = []
    for r in cont.values():
        reasons = []
        if r.get("AA") == "TTG_BONIFICACION":
            reasons.append("TTG")
        if r.get("AB") in ("GENVET", "OTROS", "OFICINA", None, "0"):
            reasons.append("linea_excluida")
        if (num(r.get("K")) or 0) > 30:
            reasons.append("dias>30")
        pred = "NO COMISIONA" if reasons else "COMISIONA"
        if pred == r.get("AL"):
            pred_ok += 1
        else:
            pred_bad += 1
            if len(bad_samples) < 15:
                bad_samples.append((r.get("AL"), pred, reasons, r.get("AA"), r.get("AB"), r.get("K"), r.get("A"), r.get("G"), r.get("O")))
    print(f"rule TTG|linea GENVET/OTROS/vacia|dias>30 -> NO. ok={pred_ok} bad={pred_bad}")
    for s in bad_samples:
        print(" ", s)

    # partial payments vs filtro
    ft = load_sheet(FT, "Sheet1", {"I", "L", "N", "P", "S", "T", "V"})
    ft_idx = {}
    for r in ft.values():
        ft_idx.setdefault((r.get("I"), r.get("V")), r)
    partial_filtro = Counter()
    motivo_filtro = Counter()
    for r in cont.values():
        src = ft_idx.get((r.get("G"), r.get("P")))
        if not src:
            continue
        raw = num(src.get("L"))
        base = num(src.get("S"))
        if raw is not None and base is not None and abs(raw - base) > 0.5:
            partial_filtro[r.get("AL")] += 1
        motivo_filtro[(src.get("T"), r.get("AL"))] += 1
    print("partial base!=raw by filtro", partial_filtro)
    print("motivo x filtro")
    for k, v in motivo_filtro.most_common():
        print(f"  {v:5} {k}")

    print("\n=== FILTRO rules LETRAS ===")
    let = load_sheet(CALC, "LETRAS", {"C", "K", "AA", "AB", "AL", "F"})
    pred_ok = pred_bad = 0
    bad_samples = []
    for r in let.values():
        reasons = []
        if r.get("AA") == "TTG_BONIFICACION":
            reasons.append("TTG")
        if r.get("C") == "Protestado":
            reasons.append("protestado")
        if r.get("AB") in ("GENVET", "OTROS", "OFICINA", "AVIVET", None, "0"):
            reasons.append("linea")
        if (num(r.get("K")) or 0) > 30:
            reasons.append("dias>30")
        pred = "NO COMISIONA" if reasons else "COMISIONA"
        if pred == r.get("AL"):
            pred_ok += 1
        else:
            pred_bad += 1
            if len(bad_samples) < 12:
                bad_samples.append((r.get("AL"), pred, reasons, r.get("C"), r.get("AA"), r.get("AB"), r.get("K")))
    print(f"rule TTG|protestado|linea AVIVET/GENVET/OTROS/vacia|dias>30 -> NO. ok={pred_ok} bad={pred_bad} of {len(let)}")
    for s in bad_samples:
        print(" ", s)

    # estado x impuesto x filtro for letras mismatches only summary
    print("letras NO that are IGV and not protestado and dias<=30")
    c = Counter()
    for r in let.values():
        if r.get("AL") == "NO COMISIONA" and r.get("AA") != "TTG_BONIFICACION" and r.get("C") != "Protestado" and (num(r.get("K")) or 0) <= 30:
            c[(r.get("C"), r.get("AB"))] += 1
    print(c.most_common(15))


if __name__ == "__main__":
    main()
