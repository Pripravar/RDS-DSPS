# RDS / DSPS — aplikace na sledování předávání dokumentace · návod na nastavení

Aplikace „velín RDS/DSPS": u každého **stavebního objektu (SO)** (a jeho části – sanace,
zemní těleso, vozovka, most: zakládání/spodní stavba/NK/…) ukazuje **kde se dokumentace
právě nachází** (u projektanta → u nás → VV → TDS → čistopis → tisk → předáno) a **jak
dlouho** už v té fázi je. Stejný princip a stejná architektura jako appky *poptávky/objednávky*
a *ZBV* (jeden `index.html` na GitHub Pages, data ve Firebase, plní se z mailů).

> **STAV (2026-07-22): FIREBASE ZAPOJEN, ŽIVÁ DATA.** Projekt `RDS-DSPS` (rds-dsps): web app,
> Realtime DB (europe-west1), pravidla `auth != null`, přihlášení e-mail/heslo — vše hotové.
> Config je v `index.html`. Data nahraná (Martinovice 182 + Sulice, D10 Kosmonosy, D4 Mníšek PHS,
> Votice = 5 staveb). Přihlašovací uživatel `priprava@msilnice.cz` založen.
> **Zbývá:** nasadit na GitHub Pages (repo `rds`), přidat `pripravar.github.io` do Authorized
> domains, zapnout denní plnič + zálohu, přepnout dlaždici RDS v rozcestníku na „živé".
> (Na localhostu appka záměrně jede v ukázkovém režimu z `rds_data.json`; ostrá data se berou
> z Firebase až na nasazené adrese.)

---

## Jak to funguje (3 části)
1. **Web app** `index.html` — na GitHub Pages, data ve Firebase. Tabulku tu vidíš a edituješ.
   - **Přehled**: karta akce → řádky SO/částí → sloupce *Kde se nachází* (barevný štítek) a
     *Jak dlouho* (dní ve fázi / dní po termínu SOD). Filtry: Rozpracované / Zpožděné / Změny /
     Hotové. Řazení: dle SO / nejdéle bez pohybu / největší zpoždění / dle fáze. Hledání. ⬇︎ CSV.
   - **Detail** (tlačítko u řádku): 10 milníků RDS (u DSPS 9) — u každého datum + poznámka
     „kdo/kým". Zelené = hotové. Plus termín SOD, projektant, SUB, VV, změny.
   - **+ SO** přidá objekt, **+ Akce** založí novou stavbu (RDS nebo DSPS).
2. **Migrace** `rds_parser.py` (Excel → `rds_data.json`) + `import_rds_to_firebase.py`
   (jednorázově nahraje do Firebase).
3. **Denní plnič z mailů** — scheduled task (Claude) 1×denně čte sběrný Gmail, pozná, kterého
   SO/milníku se mail týká, a **v automatickém režimu rovnou zapíše datum do tabulky** (bez
   potvrzování) + zaznamená do `/log`. (Volitelně lze přepnout na režim „návrh do Schránky",
   kde to jedním klikem potvrzuješ — Schránka je v appce připravená.)

---

## Co potřebuju od TEBE (účty a přihlášení za tebe udělat nemůžu)

### A) Firebase (databáze + přihlášení) — cca 10 min
1. **console.firebase.google.com** → přihlas se (klidně stejný Google účet jako u ostatních).
2. **Add project** → název `rds-dsps` → Analytics můžeš vypnout → Create.
3. **Build → Realtime Database → Create database** → lokace **europe-west1** → *locked mode*.
4. Záložka **Rules** → vlož obsah `database.rules.json` (`auth != null`) → **Publish**.
5. **Build → Authentication → Get started → Email/Password → Enable.**
   - **Users → Add user**: můžeš rovnou použít **stejný přihlašovací účet jako u ZBV**
     (`priprava@msilnice.cz` + tvé heslo), ať se nemusíš učit nové heslo.
6. **Project settings (⚙️) → Your apps → Web `</>`** → přezdívka `web` → Register →
   **zkopíruj mi blok `firebaseConfig`** (apiKey, authDomain, databaseURL, projectId, appId).

### B) GitHub (hosting stránky)
7. **github.com** (účet `Pripravar`) → **New repository** → název `rds` → **Public** → Create.
8. Nahraj soubory ze složky `web-rds` (přes **GitHub Mac app**, jako u ostatních) —
   do rootu dej **jen** `index.html`, `database.rules.json`, `NÁVOD-NASTAVENÍ.md`.
   **Žádná data na GitHub nejdou** — `rds_data.json`, `firebase.local.json`, `backups/` jsou
   v `.gitignore`. Data žijí jen ve Firebase a appka je ukáže **až po přihlášení** (gate).
   `FIREBASE_CONFIG` v `index.html` není tajný (bezpečnost řeší pravidla + přihlášení).
9. **Settings → Pages → Source: `main` / root** → za 1–2 min poběží na
   `https://pripravar.github.io/rds/`.
10. Doménu přidej ve Firebase: **Authentication → Settings → Authorized domains → Add domain**
    → `pripravar.github.io`.

---

## Co udělám JÁ, jakmile pošleš `firebaseConfig`
- Doplním config do `index.html` (vypne se ukázkový režim, zapne přihlášení + živá data).
- Vytvořím `firebase.local.json` a spustím `import_rds_to_firebase.py` (nahraje 182 SO Martinovic).
- Zprovozním **denní plnič z mailů** (scheduled task, automatický režim bez potvrzování).
- Zprovozním **denní zálohu** na Google Disk (`apps-script-zaloha-rds.gs`, viz níže).

## Záloha (bez PC, denně)
`apps-script-zaloha-rds.gs` přidáš do **stejného Apps Script projektu** jako zálohy poptávek/ZBV
(účet `popobjmsilniceozjih@gmail.com`), doplníš 3 hodnoty (DB URL, apiKey, heslo) a spustíš
`nastavTriggerZalohaRDS()`. Stáhne celou DB každý den ~4:15 do složky „RDS DSPS – zálohy",
drží 120 dní.

## Mail
Sběrná schránka je **stejná jako u ZBV/poptávek** (`popobjmsilniceozjih@gmail.com`, už připojená
jako konektor). Kolegové/projektant ji dávají do **BCC** u mailů o RDS/DSPS. Plnič si maily sám
najde podle obsahu (SO, „koncept/čistopis/pokyn k tisku/výtisky", názvy akcí) a odbaví je;
zpracovaná vlákna štítkuje `RDS/Zpracovano`, aby se nemíchaly s poptávkami a ZBV.

## Co dělá uživatel vs. Claude
- **Uživatel:** účty, hesla, OAuth, finální push do repa, zapnutí cronu. (Vše s účty/klikáním
  v cizích službách.)
- **Claude:** `index.html`, parser/migrace, pravidla, scheduled task, zálohu, ladění.
