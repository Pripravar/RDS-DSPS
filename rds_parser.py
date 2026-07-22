#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Naparsuje ručně vyplňovaný vzor "Tabulka_terminu_a_predavani_RDS_Martinovice.xlsx"
do rds_data.json ve tvaru, který čte webová appka (index.html).

Spouštěj JEN pro první naplnění. Po nasazení je hlavní zdroj dat Firebase.
"""
import openpyxl, datetime, json, sys, os, re

SRC = os.environ.get("RDS_SRC",
    "../vzor, vyplnovaný ručně/Tabulka_terminu_a_predavani_RDS_Martinovice.xlsx")
OUT = "rds_data.json"

# mapa: klíč milníku -> index sloupce (0-based) v Martinovice šabloně
COLS = {
    "sod":        6,   # termín odevzdání předkonceptu dle SOD (deadline)
    "m1":         8,   # 1. předkoncept od projektanta (Projektant -> M-SILNICE)
    "m2":         9,   # 2. připomínky od M-SILNICE (M-SILNICE -> Projektant)
    "vv_predpoklad": 10,  # předpokládaný termín předložení pro VV (deadline)
    "m3":        12,   # 3. předkoncept k VV od projektanta
    "m4":        13,   # 4. koncept po zapracování připomínek z VV
    "m5":        14,   # 5. připomínky od TDS ke konceptu
    "m6":        15,   # 6. čistopis od projektanta
    "m7":        16,   # 7. odsouhlasení čistopisu TDS
    "m8":        17,   # podepsáno na ASPE HUB
    "m9":        18,   # pokyn k tisku RDS
    "m10":       19,   # předání výtisků RDS
    "vv_cislo":  20,
    "vv_termin": 21,
    "vv_zapis":  22,
    "zmena":     23,
    "pozn_zmeny":24,
    "zmena15":   25,
    "oznameni1": 26,
    "oznameni2": 27,
}
MILNIKY = ["m1","m2","m3","m4","m5","m6","m7","m8","m9","m10"]

def cell(v):
    """Vrátí (date_iso|None, text|None) pro buňku."""
    if v is None:
        return None, None
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d"), None
    s = str(v).strip()
    if not s:
        return None, None
    # zkus najít datum na začátku textu typu "5.8.2025\npoznámka"
    m = re.match(r"^\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})", s)
    d = None
    if m:
        try:
            dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d = datetime.date(yy, mm, dd).strftime("%Y-%m-%d")
        except ValueError:
            d = None
    return d, s

def main():
    wb = openpyxl.load_workbook(SRC, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    objekty = []
    cur_parent = None
    for i, row in enumerate(rows):
        if i < 5:  # hlavičky
            continue
        a  = row[0]
        b  = row[1]
        popis = row[2]
        if not popis:
            continue
        popis = str(popis).strip()
        is_parent = (b is not None) or popis.upper().startswith("SO ")

        # identita
        so_label = None
        popis_clean = popis
        m = re.match(r"^(SO\s*[\d\.\w]+)\s*[-–]\s*(.*)$", popis)
        if m:
            so_label = m.group(1).replace("SO", "SO ").replace("  ", " ").strip()
            popis_clean = m.group(2).strip()

        if is_parent:
            cur_parent = so_label or (("SO " + str(a)) if a is not None else popis)
            cast = None
        else:
            cast = popis          # část (sanace, zemní těleso, NK, ...)
            popis_clean = ""

        pozn = row[3]
        sub  = row[4]
        proj = row[5]

        ms = {}
        for key, col in COLS.items():
            if col >= len(row):
                continue
            d, t = cell(row[col])
            if d or t:
                ms[key] = {"d": d, "t": t}

        objekty.append({
            "so": cur_parent or popis,
            "popis": popis_clean if is_parent else "",
            "cast": cast,
            "projektant": str(proj).strip() if proj else "",
            "sub": str(sub).strip() if sub else "",
            "pozn": str(pozn).strip() if pozn else "",
            "sod": ms.get("sod", {}).get("d") or (ms.get("sod", {}).get("t") if "sod" in ms else None),
            "vv_predpoklad": (ms.get("vv_predpoklad", {}).get("d")
                              or (ms.get("vv_predpoklad", {}).get("t") if "vv_predpoklad" in ms else None)),
            "vv_cislo": ms.get("vv_cislo", {}).get("t"),
            "vv_termin": ms.get("vv_termin", {}).get("d"),
            "vv_zapis": ms.get("vv_zapis", {}).get("t"),
            "zmena": ms.get("zmena", {}).get("t"),
            "pozn_zmeny": ms.get("pozn_zmeny", {}).get("t"),
            "zmena15": ms.get("zmena15", {}).get("t"),
            "oznameni1": ms.get("oznameni1", {}).get("t"),
            "oznameni2": ms.get("oznameni2", {}).get("t"),
            "milniky": {k: ms[k] for k in MILNIKY if k in ms},
        })

    data = {
        "verze": 1,
        "stavby": {
            "i16-martinovice-rds": {
                "nazev": "I/16 Mladá Boleslav – Martinovice",
                "typ": "RDS",
                "objekty": objekty,
            }
        }
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"IMPORT OK: {len(objekty)} řádků SO/částí -> {OUT}")
    # rychlý přehled kolik má vyplněné milníky
    vypln = sum(1 for o in objekty if o["milniky"])
    print(f"  z toho {vypln} má aspoň jeden vyplněný milník, {len(objekty)-vypln} zatím prázdných")

if __name__ == "__main__":
    main()
