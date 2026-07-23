#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_rds.py — zápis do RDS/DSPS appky (Firebase) pro denní plnič z mailů.

AUTO režim (přál si uživatel): jasné milníky se zapisují ROVNOU do tabulky
(objekty/<stavba>/<RDS|DSPS>/<objId>/milniky/<mID>). Nejisté jdou do /inbox (Schránka),
kde je uživatel v appce potvrdí. Každý přímý zápis se loguje do /log.

Použití:
  python3 push_rds.py --get-context          # JSON staveb + objektů (pro párování)
  python3 push_rds.py updates.json           # aplikuje seznam změn (viz formát níže)
  python3 push_rds.py --backup               # snapshot DB -> backups/rds-RRRR-MM-DD.json (drží 30)
  python3 push_rds.py --prune [--days=45]    # úklid /inbox (aplikované/zahozené starší než N dní)

updates.json = pole objektů. Každý:
{
  "vlaknoId": "<gmail thread id>#<odlišovač>",   # dedup (u více změn z 1 mailu přidej #cast)
  "predmet": "...", "datum": "19.6.2026", "zdroj": "mail: <předmět>",
  "jistota": "vysoká" | "nízká",
  "akce": {
     "stavbaId": "i16-martinovice-rds" | "?" | "new",
     "nazevNew": "<přesný název z feedu>",         # jen když stavbaId=new
     "meta": { "cislo":"", "pripravar":"", "sv":"", "start":"", "finish":"", "zdroj":"feed" },
     "typ": "RDS" | "DSPS" | "VTD" | "SUB",
     "objId": "o012" | "new",
     "so": "SO 201", "cast": "NK/Hrncová ložiska/…", "popis": "",   # když objId=new
     # --- RDS/DSPS/VTD (režim milníků) ---
     "milnik": "m3" | null,                          # id milníku dle CHAIN v index.html (VTD m1..m5)
     "d": "2026-06-19", "t": "Svoboda > Líbal (mail)",
     "chybi": "", "pozn": "",                        # volitelné (co chybí / poznámka s datem)
     # --- SUB (režim log verzí – co jsem poslal subdodavateli) ---
     "sub": "Kunst s.r.o.",                          # subdodavatel (doplní se když prázdný)
     "odeslani": { "verze":"3", "d":"2026-07-01", "pozn":"čistopis" },
     "kontakt": { "jmeno":"", "mail":"", "tel":"", "role":"projektant|SUB" }
  }
}
Pravidlo AUTO (milníky RDS/DSPS/VTD): zapíše se PŘÍMO jen když jistota=vysoká a stavbaId≠"?" a
objId≠null a milnik≠null a milník je JEŠTĚ PRÁZDNÝ. Jinak → /inbox.
Pravidlo AUTO (SUB): přidá odeslanou verzi do logu když jistota=vysoká a stavbaId≠"?" (objekt SO
se najde podle so+cast nebo založí). Duplicitní verze+datum se přeskočí. Nejisté → /inbox.
"""
import json, os, sys, time, urllib.request, urllib.error, datetime, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))

def cfg():
    p = os.path.join(HERE, "firebase.local.json")
    if not os.path.exists(p):
        print("CHYBA: chybí firebase.local.json"); sys.exit(1)
    c = json.load(open(p, encoding="utf-8"))
    return c["apiKey"], c["dbUrl"].rstrip("/"), c["email"], c["password"]

def signin(api, email, pw):
    b = json.dumps({"email": email, "password": pw, "returnSecureToken": True}).encode()
    r = urllib.request.Request("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=" + api,
                               data=b, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=30))["idToken"]

def get(db, path, tok):
    try:
        return json.load(urllib.request.urlopen(db + "/" + path + ".json?auth=" + tok, timeout=60))
    except urllib.error.HTTPError:
        return None

def put(db, path, tok, obj):
    r = urllib.request.Request(db + "/" + path + ".json?auth=" + tok,
                               data=json.dumps(obj, ensure_ascii=False).encode(),
                               headers={"Content-Type": "application/json"}, method="PUT")
    return urllib.request.urlopen(r, timeout=30).getcode()

def patch(db, path, tok, obj):
    r = urllib.request.Request(db + "/" + path + ".json?auth=" + tok,
                               data=json.dumps(obj, ensure_ascii=False).encode(),
                               headers={"Content-Type": "application/json"}, method="PATCH")
    return urllib.request.urlopen(r, timeout=30).getcode()

def post(db, path, tok, obj):
    r = urllib.request.Request(db + "/" + path + ".json?auth=" + tok,
                               data=json.dumps(obj, ensure_ascii=False).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(r, timeout=30))

def slug(s):
    s = str(s or "")
    # odstraň diakritiku -> ASCII (jinak neplatná/nekódovatelná Firebase cesta)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[.$#\[\]/\x00-\x1f]+", "_", s)
    return re.sub(r"\s+", "_", s).strip("_")[:180] or "x"

def d_iso(s):
    """'19.6.2026' | '2026-06-19' -> 'YYYY-MM-DD' nebo None"""
    if not s: return None
    s = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m: return s[:10]
    m = re.match(r"^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", s)
    if m:
        try: return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError: return None
    return None

# ---------- kontext ----------
def get_context(db, tok):
    stavby = get(db, "stavby", tok) or {}
    objekty = get(db, "objekty", tok) or {}
    out = {"stavby": [],
           "milniky": {"RDS": ["m1..m10"], "DSPS": ["m1..m9"],
                       "VTD": ["m1 koncept odeslán", "m2 vrácení/připomínky", "m3 odsouhlaseno TDI",
                               "m4 čistopis zhotovitel->TDI", "m5 čistopis TDI->zhotovitel"]},
           "SUB": "režim log verzí: objekt má sub (subdodavatel) + odeslani[{verze,d,pozn}]"}
    for sid, s in stavby.items():
        entry = {"stavbaId": sid, "nazev": s.get("nazev", ""), "meta": s.get("meta"), "typy": {}}
        for typ in ("RDS", "DSPS", "VTD"):
            m = (objekty.get(sid, {}) or {}).get(typ, {}) or {}
            entry["typy"][typ] = [
                {"objId": k, "so": v.get("so"), "cast": v.get("cast") or v.get("popis"),
                 "vyplneno": sorted((v.get("milniky") or {}).keys())}
                for k, v in sorted(m.items())
            ]
        sub = (objekty.get(sid, {}) or {}).get("SUB", {}) or {}
        entry["typy"]["SUB"] = [
            {"objId": k, "so": v.get("so"), "cast": v.get("cast") or v.get("popis"),
             "sub": v.get("sub", ""),
             "verze": [x.get("verze") for x in (v.get("odeslani") or [])]}
            for k, v in sorted(sub.items())
        ]
        out["stavby"].append(entry)
    print(json.dumps(out, ensure_ascii=False, indent=1))

# ---------- aplikace změn ----------
def apply_updates(db, tok, updates):
    objekty = get(db, "objekty", tok) or {}
    seen_inbox = get(db, "inbox", tok) or {}
    seen_vlakna = {v.get("vlaknoId") for v in seen_inbox.values() if isinstance(v, dict)}
    direct, inbox_n, skip = 0, 0, 0
    for u in updates:
        a = u.get("akce", {}) or {}
        vid = u.get("vlaknoId")
        jist = (u.get("jistota") or "").lower()
        sid = a.get("stavbaId"); typ = a.get("typ") or "RDS"; oid = a.get("objId")
        mil = a.get("milnik"); d = d_iso(a.get("d")); t = a.get("t")

        # nová stavba z feedu
        if sid == "new" and a.get("nazevNew"):
            nsid = slug(a["nazevNew"].lower())
            rec = {"nazev": a["nazevNew"], "poradi": int(time.time())}
            if a.get("meta"): rec["meta"] = a["meta"]
            put(db, "stavby/" + nsid, tok, rec)
            put(db, "objekty/" + nsid, tok, {"RDS": {}, "DSPS": {}, "VTD": {}, "SUB": {}})
            sid = nsid
            objekty.setdefault(sid, {"RDS": {}, "DSPS": {}, "VTD": {}, "SUB": {}})

        # kontakt do adresáře
        k = a.get("kontakt")
        if k and k.get("jmeno"):
            patch(db, "kontakty/" + slug(k["jmeno"].lower()), tok,
                  {"jmeno": k.get("jmeno"), "mail": k.get("mail", ""), "tel": k.get("tel", ""),
                   "role": k.get("role", ""), "akce": sid, "so": a.get("so", "")})

        # ---- SUB: přidání odeslané verze do logu (co jsem poslal subdodavateli) ----
        if typ == "SUB" and a.get("odeslani"):
            snd = a["odeslani"]
            sd = d_iso(snd.get("d")); sv = str(snd.get("verze") or "").strip(); sp = snd.get("pozn", "")
            sub_ok = (jist == "vysoká" and sid and sid != "?" and (sd or sp))
            if sub_ok:
                # najdi/založ objekt SO v sekci SUB
                subm = (objekty.get(sid, {}) or {}).get("SUB", {}) or {}
                if oid and oid != "new" and oid in subm:
                    tgt = oid; cur = subm[oid]
                else:
                    # zkus najít podle SO+cast, jinak založ nový
                    tgt = next((kk for kk, vv in subm.items()
                                if vv.get("so") == a.get("so") and (vv.get("cast") or "") == (a.get("cast") or "")), None)
                    cur = subm.get(tgt, {}) if tgt else {}
                    if not tgt:
                        newobj = {"so": a.get("so", ""), "cast": a.get("cast", ""), "sub": a.get("sub", ""), "odeslani": []}
                        tgt = post(db, "objekty/%s/SUB" % sid, tok, newobj)["name"]
                        cur = newobj
                arr = list(cur.get("odeslani") or [])
                if not any((x.get("verze") == sv and d_iso(x.get("d")) == sd) for x in arr):
                    arr.append({"verze": sv or str(len(arr) + 1), "d": sd, "pozn": sp})
                    upd = {"odeslani": arr}
                    if a.get("sub") and not cur.get("sub"): upd["sub"] = a["sub"]
                    patch(db, "objekty/%s/SUB/%s" % (sid, tgt), tok, upd)
                    post(db, "log", tok, {"ts": int(time.time() * 1000), "stavba": sid, "typ": "SUB",
                                          "objekt": tgt, "verze": sv, "d": sd, "zdroj": u.get("zdroj", "")})
                    direct += 1
                else:
                    skip += 1
                continue
            else:
                if vid and vid in seen_vlakna: skip += 1; continue
                post(db, "inbox", tok, {"vlaknoId": vid, "ts": int(time.time() * 1000),
                    "zdroj": u.get("zdroj", u.get("predmet", "")), "stav": "novy", "jistota": jist, "typ": "SUB",
                    "stavbaId": sid, "objId": oid, "so": a.get("so", ""), "cast": a.get("cast", ""),
                    "popisNavrhu": "odesláno na SUB: v%s %s %s" % (sv, sd or "", sp)})
                inbox_n += 1; continue

        can_direct = (jist == "vysoká" and sid and sid != "?" and oid and oid != "new" and mil and (d or t))
        cur = ((objekty.get(sid, {}) or {}).get(typ, {}) or {}).get(oid, {}) if can_direct else {}
        already = bool((cur.get("milniky") or {}).get(mil)) if can_direct else False

        if can_direct and not already:
            patch(db, "objekty/%s/%s/%s/milniky/%s" % (sid, typ, oid, mil), tok,
                  {"d": d, "t": t})
            # projektant / chybí / poznámka (fill-if-empty pro projektanta)
            extra = {}
            if a.get("chybi"): extra["chybi"] = a["chybi"]
            if k and k.get("jmeno") and not cur.get("projektant"):
                extra["projektant"] = (k["jmeno"] + (" " + k["mail"] if k.get("mail") else "")).strip()
            if extra: patch(db, "objekty/%s/%s/%s" % (sid, typ, oid), tok, extra)
            if a.get("pozn"):
                pozn = list(cur.get("poznamky") or [])
                pozn.append({"ts": int(time.time() * 1000), "t": a["pozn"], "kdo": "plnič"})
                patch(db, "objekty/%s/%s/%s" % (sid, typ, oid), tok, {"poznamky": pozn})
            post(db, "log", tok, {"ts": int(time.time() * 1000), "stavba": sid, "typ": typ,
                                  "objekt": oid, "milnik": mil, "d": d, "t": t, "zdroj": u.get("zdroj", "")})
            direct += 1
        else:
            if vid and vid in seen_vlakna:
                skip += 1; continue
            post(db, "inbox", tok, {
                "vlaknoId": vid, "ts": int(time.time() * 1000), "zdroj": u.get("zdroj", u.get("predmet", "")),
                "stav": "novy", "jistota": jist, "typ": typ,
                "stavbaId": sid, "objId": oid, "so": a.get("so", ""), "cast": a.get("cast", ""),
                "milnik": mil, "d": d, "t": t,
                "popisNavrhu": (a.get("pozn") or ("milník %s = %s %s" % (mil, d or "", t or ""))).strip()})
            inbox_n += 1
    print("Hotovo: přímo zapsáno %d, do Schránky %d, přeskočeno (duplicita) %d." % (direct, inbox_n, skip))

# ---------- záloha ----------
def backup(db, tok):
    data = get(db, "", tok)
    if not data:
        print("Prázdná DB – záloha přeskočena."); return
    os.makedirs(os.path.join(HERE, "backups"), exist_ok=True)
    stamp = datetime.date.today().strftime("%Y-%m-%d")
    p = os.path.join(HERE, "backups", "rds-%s.json" % stamp)
    json.dump(data, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    # drž posledních ~30
    files = sorted(f for f in os.listdir(os.path.join(HERE, "backups")) if f.startswith("rds-") and f.endswith(".json"))
    for f in files[:-30]:
        os.remove(os.path.join(HERE, "backups", f))
    print("Záloha OK: backups/rds-%s.json" % stamp)

def prune(db, tok, days):
    inbox = get(db, "inbox", tok) or {}
    hranice = int(time.time() * 1000) - days * 86400000
    n = 0
    for k, v in inbox.items():
        if isinstance(v, dict) and v.get("stav") in ("aplikovano", "zahozeno") and (v.get("ts") or 0) < hranice:
            urllib.request.urlopen(urllib.request.Request(db + "/inbox/" + k + ".json?auth=" + tok, method="DELETE"), timeout=30)
            n += 1
    print("Úklid Schránky: smazáno %d starých položek." % n)

def main():
    api, db, email, pw = cfg()
    tok = signin(api, email, pw)
    args = sys.argv[1:]
    if not args or args[0] == "--get-context":
        get_context(db, tok); return
    if args[0] == "--backup":
        backup(db, tok); return
    if args[0] == "--prune":
        days = 45
        for a in args:
            if a.startswith("--days="): days = int(a.split("=")[1])
        prune(db, tok, days); return
    updates = json.load(open(args[0], encoding="utf-8"))
    if isinstance(updates, dict): updates = [updates]
    apply_updates(db, tok, updates)

if __name__ == "__main__":
    main()
