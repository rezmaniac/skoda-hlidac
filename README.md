# Hlídač vozů

Statický frontend pro GitHub Pages s hodinovým načítáním veřejných nabídek Škoda Plus z Brna a praktického dojezdového okruhu přibližně 100 km během dne.

## Lokální spuštění

```bash
python3 -m http.server 4173
```

Potom otevřete `http://localhost:4173`.

## Aktualizace dat

Skript `scraper/update.py` načte veřejné GraphQL rozhraní Škoda Plus, porovná nabídky s předchozím stavem a aktualizuje `data/latest.json`.

```bash
python3 scraper/update.py
```

Pobočky a filtr Telegram notifikací jsou v `config/filters.json`. Web zobrazuje všechny stažené nabídky; notifikační filtr rozhoduje pouze o odeslání zprávy.

## GitHub Pages

Projekt nevyžaduje build. Lze jej publikovat přímo z kořene repozitáře nebo zkopírovat do `docs/`.

## Telegram notifikace

V nastavení repozitáře je potřeba vytvořit dva GitHub Actions Secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Token ani chat ID nejsou ve frontendu. Notifikaci odesílá pouze GitHub Actions při nalezení nového vozu nebo poklesu ceny. Ruční spuštění workflow umožňuje poslat testovací zprávu.

Pro bezpečné jednorázové nastavení lze použít pomocný skript. Token se při zadávání nezobrazuje, neukládá do souborů ani do historie shellu:

```bash
python3 scraper/setup_telegram.py
```

## Automatizace

Workflow `.github/workflows/update-and-deploy.yml`:

1. každou hodinu od 07:17 do 22:17 Europe/Prague stáhne data,
2. porovná změny a případně odešle Telegram,
3. uloží nový snapshot do repozitáře,
4. publikuje web přes GitHub Pages.
