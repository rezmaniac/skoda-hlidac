# Předání projektu — Hlídač vozů

Aktualizováno: 29. 8. 2026

## Co projekt dělá

Web sleduje veřejné nabídky Škoda Plus u vybraných prodejců v Ivančicích a Brně. Každou hodinu přes den stáhne nabídky, ukáže je na statickém webu a do Telegramu odešle upozornění pouze na nové vozy nebo zlevnění, které odpovídají nastavenému filtru.

## Kde je projekt

- Zdrojový kód a záloha: `https://github.com/rezmaniac/skoda-hlidac`
- Živý web: `https://rezmaniac.github.io/skoda-hlidac/`
- Produkční větev: `main`
- Lokální složka: `outputs/skoda-hlidac`

GitHub je hlavní záloha: každý odeslaný commit obsahuje kód, konfiguraci i poslední anonymní datový snapshot. Citlivé údaje nejsou v repozitáři.

## Architektura

| Část | Soubor / služba | Účel |
| --- | --- | --- |
| Web | `index.html`, `styles.css`, `app.js` | Statický přehled nabídek a filtry v prohlížeči. |
| Data | `data/latest.json` | Poslední stažené nabídky a stav pro porovnání změn. |
| Sběr dat | `scraper/update.py` | Volá veřejné GraphQL rozhraní Škoda Plus, porovnává nabídky a případně posílá Telegram. |
| Nastavení | `config/filters.json` | Pobočky a pravidla pro Telegram notifikace. |
| Automatizace | `.github/workflows/update-and-deploy.yml` | Hodinové aktualizace, ukládání dat a nasazení GitHub Pages. |
| Tajemství | GitHub Actions Secrets | Token bota a Telegram chat ID; nikdy je neukládat do souborů. |

## Aktuální nastavení

### Pobočky

- Ivančice: IVACAR 2000
- Brno: Porsche Brno, ARAVER CZ, AUTONOVA BRNO, Direct auto Brno a AUTO IN BRNO

### Telegram filtr

Notifikace se posílají jen pro:

- benzínové vozy,
- cenu maximálně 400 000 Kč,
- s výjimkou modelu Fabia.

Tento filtr ovlivňuje pouze Telegram. Web stále zobrazuje všechny stažené nabídky a má vlastní filtry značky, modelu, ceny, nájezdu, lokality a řazení.

### Čas kontroly

GitHub Actions kontroluje data každou hodinu v `:17`, od 07:17 do 22:17 v časovém pásmu Europe/Prague. Ruční spuštění workflow umožňuje testovací Telegram zprávu.

## Přenesení na jiný počítač nebo účet

1. Naklonovat repozitář:

   ```bash
   git clone https://github.com/rezmaniac/skoda-hlidac.git
   cd skoda-hlidac
   ```

2. Pro lokální náhled spustit:

   ```bash
   python3 -m http.server 4173
   ```

3. V cílovém GitHub repozitáři nastavit GitHub Pages z GitHub Actions.
4. V **Settings → Secrets and variables → Actions** znovu vložit:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. V souboru `config/filters.json` upravit pobočky a pravidla Telegramu podle potřeby.
6. Pustit workflow ručně s volbou testovací Telegram zprávy a potvrdit, že došla.

## Běžná údržba

- Změna textů a vzhledu: `index.html`, `styles.css`, `app.js`.
- Změna poboček nebo Telegram filtru: `config/filters.json`.
- Změna logiky sběru dat: `scraper/update.py`.
- Kontrola běhů: záložka **Actions** v GitHubu.
- Po úpravě odeslat změny:

  ```bash
  git add .
  git commit -m "Popis změny"
  git push
  ```

## Bezpečnost

- Token Telegram bota a chat ID patří jen do GitHub Secrets.
- Pokud se token objeví v chatu, terminálu, commitu nebo screenshotu, v BotFatheru jej ihned obnovit přes `/revoke` a přepsat secret v GitHubu.
- Do repozitáře nepatří soubory `.env`, exporty secrets ani soukromé přístupové údaje.

## Standard pro další projekty

Pro každý další projekt, včetně Platform APP, založit v kořeni repozitáře stejný soubor `PROJECT_HANDOFF.md`. Musí obsahovat: účel projektu, odkazy na repozitář a produkci, architekturu, běžné příkazy, nasazení, seznam secrets pouze podle názvů, aktuální stav a postup přenesení. Tím bude každý projekt samostatně zálohovaný a snadno předatelný.
