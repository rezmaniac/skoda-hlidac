# Hlídač vozů

Statický frontend pro GitHub Pages s hodinovým načítáním veřejných nabídek Škoda Plus z Brna a praktického dojezdového okruhu přibližně 100 km během dne.

## Lokální spuštění

```bash
python3 -m http.server 4173
```

Potom otevřete `http://localhost:4173`.

## Aktualizace dat

Skript `scraper/update.py` načte veřejné GraphQL rozhraní Škoda Plus, porovná nabídky s předchozím stavem a aktualizuje `data/latest.json`. Jednou denně zároveň obnoví kompaktní celorepublikový katalog vozů Škoda v `data/market.json`.

```bash
python3 scraper/update.py
```

Pobočky a filtr Telegram notifikací jsou v `config/filters.json`. Web zobrazuje všechny stažené nabídky; notifikační filtr rozhoduje pouze o odeslání zprávy.

Výchozí pohled zobrazuje vozy Škoda Scala. Značka, model i pobočka podporují vícenásobný výběr; prázdný výběr znamená všechny možnosti. Cenové hranice používají hodnoty 199 000 Kč, 249 000 Kč a poté kroky po 10 000 Kč od 259 000 do 999 000 Kč, následované volbou 1 000 000 Kč+. Uživatel může na kartách vybrat až tři vozy a porovnat jejich cenu, rok, nájezd, motor, výkon, palivo, převodovku, výbavovou linii, jednotlivé prvky výbavy a pobočku. U výbavy lze přepínat mezi celým seznamem a pouze rozdíly. Výběr se uchovává lokálně v prohlížeči.

U škodovek web ukazuje také typickou nabídkovou cenu z celé ČR. Jde o medián nejvýše 40 nejbližších vozů se stejným modelem, výbavovou linií, palivem a převodovkou, s výkonem ±15 kW, rokem registrace ±2 a nájezdem ±30 000 km. Výsledek se zobrazí jen při alespoň pěti srovnatelných nabídkách; nejde o realizovanou prodejní cenu.

U faceliftové Scaly modelového roku 2024 a novější web rozpoznává vybrané pakety, samostatné příplatky, barvu a kola. Katalogové ceny jsou v `config/scala-equipment-catalog.json` a vycházejí z oficiálního ceníku platného od 6. 3. 2024. Vedle původní ceny příplatků se zobrazuje konzervativní orientační zůstatková hodnota podle typu výbavy a stáří auta. Tato hodnota se nepřičítá k celorepublikové typické ceně, protože srovnávané inzeráty již různou výbavu obsahují. Pozdější akční edice, které referenční ceník nepopisuje, se záměrně neoceňují.

Detailní výbava se načítá dávkově z detailů nabídek. U nezměněných vozů se používá uložená výbava z předchozího snapshotu; nové dotazy se provádějí jen pro nové nabídky nebo inzeráty upravené prodejcem.

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
2. jednou denně obnoví celorepublikový cenový katalog Škoda,
3. porovná změny a případně odešle Telegram,
4. uloží nové snapshoty do repozitáře,
5. publikuje web přes GitHub Pages.
