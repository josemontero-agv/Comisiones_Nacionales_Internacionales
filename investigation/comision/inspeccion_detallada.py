"""Deeper look: connections, tables, sample rows, pivot items, percentage table, source headers."""
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter, defaultdict

NSM = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NSR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

def q(tag):
    return f"{{{NSM}}}{tag}"

CALC = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\calculo_vendedores\COMISIONES 2026 SETIEMBRE (1).xlsx")
TABLA = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\Porcentajes\Tabla de Comisiones.xlsx")
SEP = Path(r"c:\Users\jmontero\Desktop\GitHub Proyectos_AGV\Comisiones_Nacional_Internacional\Proceso_Manual\nacional\SEP")


def shared(z):
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out = []
    for si in root.findall(q("si")):
        out.append("".join((t.text or "") for t in si.iter(q("t"))))
    return out


def sheets_map(z):
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    relmap = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
    out = {}
    for sh in wb.find(q("sheets")):
        name = sh.attrib["name"]
        rid = sh.attrib[f"{{{NSR}}}id"]
        out[name] = "xl/" + relmap[rid]
    return out


def cell_value(c, ss):
    t = c.attrib.get("t")
    f = c.find(q("f"))
    v = c.find(q("v"))
    is_el = c.find(q("is"))
    formula = f.text if f is not None else None
    if t == "s" and v is not None and v.text and v.text.isdigit():
        val = ss[int(v.text)]
    elif t == "inlineStr" and is_el is not None:
        val = "".join(x.text or "" for x in is_el.iter(q("t")))
    elif v is not None:
        val = v.text
    else:
        val = None
    return formula, val


def read_rows(z, sheet_path, ss, max_row, cols=None):
    root = ET.fromstring(z.read(sheet_path))
    rows = defaultdict(dict)
    for c in root.iter(q("c")):
        ref = c.attrib.get("r", "")
        col = "".join(ch for ch in ref if ch.isalpha())
        row = int("".join(ch for ch in ref if ch.isdigit()) or 0)
        if row == 0 or row > max_row:
            continue
        if cols and col not in cols:
            continue
        formula, val = cell_value(c, ss)
        rows[row][col] = (formula, val)
    return rows


def dump_sheet_sample(label, path, max_row=6, interesting=None):
    print("\n####", label)
    with zipfile.ZipFile(path) as z:
        # list sheets quickly
        if "xl/workbook.xml" not in z.namelist():
            print("not xlsx?")
            return
        sm = sheets_map(z)
        try:
            ss = shared(z)
        except KeyError:
            ss = []
        print("SHEETS:", list(sm))
        for name, sp in sm.items():
            root = ET.fromstring(z.read(sp))
            dim = root.find(q("dimension"))
            print(f"  {name} dim={dim.attrib.get('ref') if dim is not None else '?'}")
        # headers + a few rows of first visible-ish sheet or all small ones
        for name, sp in sm.items():
            rows = read_rows(z, sp, ss, max_row)
            if not rows:
                continue
            print(f"-- sample {name}")
            for r in sorted(rows)[:max_row]:
                items = []
                for col in sorted(rows[r], key=lambda c: (len(c), c)):
                    f, v = rows[r][col]
                    show = f if f else v
                    if show is None:
                        continue
                    items.append(f"{col}={str(show)[:80]}")
                print(f"  r{r}: " + " | ".join(items[:24]))


def main():
    print("===== CONNECTIONS / TABLES / PIVOT FIELDS =====")
    with zipfile.ZipFile(CALC) as z:
        ss = shared(z)
        sm = sheets_map(z)
        if "xl/connections.xml" in z.namelist():
            txt = z.read("xl/connections.xml").decode("utf-8", errors="replace")
            print("CONNECTIONS XML length", len(txt))
            print(txt[:8000])
        print("\nTABLES:")
        for n in sorted(x for x in z.namelist() if x.startswith("xl/tables/table") and x.endswith(".xml")):
            root = ET.fromstring(z.read(n))
            print(f"  {n} name={root.attrib.get('name')} display={root.attrib.get('displayName')} ref={root.attrib.get('ref')} cols:")
            cols = root.find(q("tableColumns"))
            if cols is not None:
                for col in cols.findall(q("tableColumn")):
                    print(f"    id={col.attrib.get('id')} name={col.attrib.get('name')}")

        print("\nPIVOT CACHE FIELDS + shared items (short)")
        root = ET.fromstring(z.read("xl/pivotCache/pivotCacheDefinition1.xml"))
        cf = root.find(q("cacheFields"))
        for i, f in enumerate(cf.findall(q("cacheField"))):
            fname = f.attrib.get("name")
            si = f.find(q("sharedItems"))
            items = []
            if si is not None:
                for child in list(si)[:25]:
                    if child.attrib.get("v") is not None:
                        items.append(child.attrib.get("v"))
                    elif child.tag == q("m"):
                        items.append("(blank)")
                    elif child.tag == q("n"):
                        items.append(child.attrib.get("v"))
                    elif child.tag == q("s"):
                        items.append(child.attrib.get("v"))
                    elif child.tag == q("d"):
                        items.append("date:" + (child.attrib.get("v") or ""))
                    else:
                        items.append(child.tag.split("}")[-1] + ":" + str(child.attrib)[:60])
                count = si.attrib.get("count")
            else:
                count = "0"
            if fname in ("Puesto", "Nombre", "FILTRO", "TIPO", "Linea Comercial", "Estado Letra2", "Linea Comercial Zona") or (items and len(items) <= 30 and fname in ("Puesto", "FILTRO", "TIPO")):
                print(f"  [{i}] {fname} sharedCount={count} sample={items[:30]}")
            else:
                print(f"  [{i}] {fname} sharedCount={count}")

        print("\nRESUMEN sheet full cells")
        rows = read_rows(z, sm["RESUMEN COMISIONES"], ss, 60)
        for r in sorted(rows):
            items = []
            for col in sorted(rows[r], key=lambda c: (len(c), c)):
                f, v = rows[r][col]
                items.append(f"{col}={v if v is not None else f}")
            print(f"  r{r}: " + " | ".join(items))

        print("\nTABLA COMISIONES full")
        rows = read_rows(z, sm["Tabla Comisiones"], ss, 30)
        for r in sorted(rows):
            items = []
            for col in ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K"]:
                if col in rows[r]:
                    f, v = rows[r][col]
                    items.append(f"{col}={f if f else v}")
            print(f"  r{r}: " + " | ".join(items))

        print("\nCONTADO formulas row 2 all formula cols + values row 2 key cols")
        rows = read_rows(z, sm["CONTADO - CREDITO"], ss, 4)
        for r in (1, 2, 3):
            print(" ROW", r)
            for col in sorted(rows[r], key=lambda c: (len(c), c)):
                f, v = rows[r][col]
                if f or col in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") or col in ("AA","AB","AC","AD","AE","AF","AG","AH","AI","AJ","AK","AL","AM","AN"):
                    if r == 1 or f or col in ("A","Z","AA","AB","AC","V","X","AD","AE","AL","AM","AN"):
                        print(f"   {col}: val={v} formula={f}")

        print("\nLETRAS row 2 key")
        rows = read_rows(z, sm["LETRAS"], ss, 3)
        for r in (1, 2):
            print(" ROW", r)
            for col in sorted(rows[r], key=lambda c: (len(c), c)):
                f, v = rows[r][col]
                if r == 1 or f or col in ("A","B","C","D","E","F","G","V","X","Z","AB","AC","AD","AE","AL","AM"):
                    print(f"   {col}: val={str(v)[:80]} formula={f}")

        print("\nCONSOLIDADO rows 1-6 all")
        rows = read_rows(z, sm["CONSOLIDADO"], ss, 6)
        for r in sorted(rows):
            items = []
            for col in sorted(rows[r], key=lambda c: (len(c), c)):
                f, v = rows[r][col]
                items.append(f"{col}={str(v)[:40]}")
            print(f"  r{r}: " + " | ".join(items))

        print("\nDETALLE1 rows 1-5 first 15 cols")
        rows = read_rows(z, sm["Detalle1"], ss, 5)
        for r in sorted(rows):
            items = []
            for col in sorted(rows[r], key=lambda c: (len(c), c))[:18]:
                f, v = rows[r][col]
                items.append(f"{col}={str(v)[:40]}")
            print(f"  r{r}: " + " | ".join(items))

    print("\n\n===== SOURCE TABLA =====")
    dump_sheet_sample("TABLA PORCENTAJES", TABLA, 30)

    print("\n\n===== SEP FILES headers =====")
    for p in sorted(SEP.rglob("*.xlsx")):
        if p.name.startswith("~$"):
            continue
        dump_sheet_sample(p.name, p, 2)


if __name__ == "__main__":
    main()
