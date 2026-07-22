# Denní plnič RDS/DSPS z mailů — zadání pro scheduled task

> Aktivuje se **až po zapojení Firebase** (do té doby appka běží v ukázkovém režimu).
> Instalace: zkopírovat do `~/.claude/scheduled-tasks/rds-mail-update/SKILL.md` a zapnout
> přes skill **schedule** — **1×denně** (např. 6:30). Běží v cloudu, nezávisle na zapnutém Macu.

## Cíl
Každý den projít sběrný Gmail (`popobjmsilniceozjih@gmail.com`) a u akcí sledovaných v appce
RDS/DSPS **automaticky doplnit milníky předávání** do Firebase — **bez potvrzování** (automatický
režim, jak si přál uživatel). Každou změnu zapsat i do `/log` (audit).

## Vstup
- Firebase Realtime DB (přihlášení z `firebase.local.json`): uzly `/stavby`, `/objekty`, `/kontakty`.
- **Feed staveb** (Power Automate endpoint, viz `OBJ a poptávky/GetAllProjectsJihAndMosty.md`) —
  autoritativní seznam staveb: `name`, `iposNumber`, `division`, `prepEngineer`, `siteManager`,
  `zbvPreparer` (Title+EMail), `startDate`, `finishDate`, `sharepointUrl`. URL bere z `feed.local.txt`.
- Gmail konektor (sběrná schránka). Přílohy (koncept/čistopis PDF) přes Google Disk, pokud budou.

## Nová akce, kterou appka nezná (párování přes feed)
Když mail zmiňuje stavbu, která ještě není v `/stavby`:
1. Zkus ji spárovat s feedem — přes **číslo IPOS** v mailu, fallback přes **číslo silnice**
   (I/16, II/610…). Pozor: tatáž stavba může být ve feedu 2× (OZ MOSTY + JIH) — neduplikuj.
2. Když je jednoznačná shoda → založ `/stavby/<id>` s **přesným názvem z feedu** + doplň
   `cislo`, `pripravar`, `stavbyvedouci`, termíny, `sharepointUrl`. Nemusí se psát ručně.
3. Když shoda není jistá → dej návrh do `/inbox` (ne přímý zápis).

## Kontakty (auto-doplnění)
Kontakty projektantů/SUB k jednotlivým SO chodí z mailů (feed je nemá). Když z mailu poznáš
jméno + mail (příp. telefon) projektanta k danému SO, ulož do `objekty/<…>/projektant` a do
`/kontakty/<slug jména>` = `{jmeno, mail, tel, role, akce, so}` (adresář, ať se nabízí příště).

## Postup
1. Načti `/stavby` + `/objekty` → seznam sledovaných akcí a jejich SO/částí + aktuální milníky.
2. V Gmailu najdi vlákna za posledních ~2 dny, která se týkají RDS/DSPS (klíčová slova:
   názvy akcí, „RDS", „DSPS", „koncept", „čistopis", „předkoncept", „pokyn k tisku", „výtisky",
   „VV / výrobní výbor", „ASPE HUB / proconom", jména projektantů), a **nejsou** poptávka/ZBV
   ani už zpracovaná (štítek `RDS/Zpracovano`).
3. Pro každé relevantní vlákno urči: **akce → SO (příp. část) → který milník** (m1…m10 dle
   `CHAIN` v `index.html`) a **datum** (z těla/přílohy; když chybí, datum mailu).
   - Směr toku napovídá milník: „projektant → M-SILNICE" = m1/m3, „M-SILNICE → projektant" = m2,
     „připomínky TDS" = m5, „čistopis" = m6, „pokyn k tisku" = m9, „výtisky předány" = m10 atd.
4. **Zapiš** `objekty/<stavba>/<RDS|DSPS>/<objekt>/milniky/<mID> = { d: "YYYY-MM-DD", t: "<kdo>→<komu> (mail)" }`
   (každá stavba má zvlášť sekci RDS a DSPS — vyber podle typu dokumentace, které se mail týká).
   Nikdy nepřepisuj už vyplněný milník jinou hodnotou bez toho, že bys to poznamenal do `/log`.
5. Přidej řádek do `/log`: `{ ts, stavba, objekt, milnik, d, zdroj:"<předmět mailu>" }`.
6. Vlákno oštítkuj `RDS/Zpracovano`. Nejednoznačné (nevíš SO/milník) dej do `/inbox`
   jako návrh k ruční kontrole (Schránka v appce) místo přímého zápisu.

## Bezpečnostní zásady
- Píše se jen do `/objekty`, `/inbox`, `/log`. Nemazat SO ani stavby.
- Nízká jistota (nevíš SO nebo milník) → `/inbox`, ne přímý zápis.
- Do mailů/dokumentů se jen čte; nic se neodesílá.
