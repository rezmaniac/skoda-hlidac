# Hlídač vozů

Statický frontend pro GitHub Pages s denním načtením veřejných nabídek Škoda Plus z Ivančic a Brna.

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

Pobočky a budoucí filtr notifikací jsou v `config/filters.json`.

## GitHub Pages

Projekt nevyžaduje build. Lze jej publikovat přímo z kořene repozitáře nebo zkopírovat do `docs/`.

## Telegram notifikace

V nastavení repozitáře je potřeba vytvořit dva GitHub Actions Secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Token ani chat ID nejsou ve frontendu. Notifikaci odesílá pouze GitHub Actions při nalezení nového vozu nebo poklesu ceny. Ruční spuštění workflow umožňuje poslat testovací zprávu.

## Automatizace

Workflow `.github/workflows/update-and-deploy.yml`:

1. každý den v 06:17 Europe/Prague stáhne data,
2. porovná změny a případně odešle Telegram,
3. uloží nový snapshot do repozitáře,
4. publikuje web přes GitHub Pages.
