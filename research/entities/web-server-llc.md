# Web Server LLC (ООО «ВЕБ-СЕРВЕР» / Angie Software)

The Russian company behind the **Angie** fork of nginx, staffed by former nginx Moscow R&D engineers. Brand: "Angie Software". Domains: angie.software, wbsrv.ru, github.com/webserver-llc/angie.

## Registration (EGRUL)
- Legal name: ОБЩЕСТВО С ОГРАНИЧЕННОЙ ОТВЕТСТВЕННОСТЬЮ "ВЕБ-СЕРВЕР"
- Jurisdiction: Russia (Moscow)
- INN: 9704151517 | OGRN: 1227700436578 | KPP: 771401001
- Legal form: OOO (LLC)
- Date incorporated: 2022-07-21
- Status: active
- Registered address: ул. Вятская д.27 стр.7, г. Москва, 127015 (Savyolovsky district)
- Charter capital: 1,333,333.34 RUB
- Primary activity: OKVED 62.01 (computer software development)
- Source: OpenSanctions `ru-inn-9704151517` (dataset `ext_ru_egrul`); Rusprofile/Checko
- OpenSanctions topic: **sanction.linked** (via institutional owner)

## Officers
| Name | Role | Period |
|------|------|--------|
| Zaur Shidibegovich Abasmirzoev | General Director (also 7.2% owner) | 2022-07-21 → present |

Abasmirzoev = reported former technical director of **Lenta.ru**.

## Ownership chain
### Current cap table (open-ended EGRUL edges; 100% = 1,333,333.34 shares)
| Owner | % | Shares | Since |
|------|---|--------|-------|
| OOO «Оператор» (GS-Invest SPV) | 40.0 | 533,333.34 | 2024-08-12 |
| Denis G. Agaronov | 13.2 | 176,000 | 2022-07-21 |
| Maxim V. Ivanov | 13.2 | 176,000 | 2022-07-21 |
| Valentin V. Bartenev | 10.2 | 136,000 | 2022-07-21 |
| Anton S. Klyuchkin | 9.0 | 120,000 | 2022-07-21 |
| Zaur Sh. Abasmirzoev (GD) | 7.2 | 96,000 | 2024-03-26 |
| Ruslan A. Ermilov | 7.2 | 96,000 | 2022-07-21 |

**Exited 2024-03** (founding co-owners, no current share edge):
- Oleg A. Mamontov — former NGINX Inc support lead (was 12%)
- Ivan V. Poluyanov — former front-end lead at Rambler & Mail.ru (was 13%)

Operator's 40% entered via a **charter-capital increase** (500,000 → 1,333,333.34 shares on 2024-08-12) — an investment round that diluted founders, not a buyout.

### Upstream (who controls the 40% institutional owner)
```
AO «ГС-Инвест» (GS-Invest, INN 7708378868, SANCTIONED) ─ 90% ─┐
Igor Vedyokhin (GD of Rubytech) ───────────────────────  10% ─┤
                                                               ▼
                                          OOO «Оператор» (INN 9717146602, inc. 2023-10-31)
                                               └─ 40% ─> OOO «ВЕБ-СЕРВЕР» (Web Server LLC)
```
**Disclosed deal (ComNews, 2024-08-23):** Headline "ГС-Инвест и гендиректор Rubytech купили 40% долей разработчика Angie." De jure buyer = OOO Operator (90% GS-Invest / 10% Igor Vedyokhin, Rubytech GD). Closed 2024-08-12. Price not disclosed; Finam analyst Leonid Delitsyn estimated the 40% at **300–400M RUB (~$3.3–4.4M)** — far larger than the 2022 "$1M". Rationale: Rubytech provides Angie a sales channel + client base into Russian import-substitution procurement.
- **GS-Invest**: Russian IT "import-substitution" holding — portfolio: Arenadata, Avanpost, Rubytech, IT_One, Skala-R, BFT, Centr Razrabotki, Astrey Soft. Founded by IBS co-founder **Sergey Matsotsky**; GD **Vasily M. Belov** (Wikidata Q54911783; also Operator GD 2023–2024).
- **Sanctions**: Ukraine NSDC decree **227/2023** (2023-04-15) on GS-Invest. OpenSanctions tags Operator and Web Server LLC `sanction.linked` by descent.
- Adjacency: d-russia.ru reports GS-Invest joined "Cloud Platform" created by **Rostelecom + YADRO** (state-telecom).

## Funding
- **2022 founding round**: Public reporting (Habr/OpenNET/managedserver.eu) says "formed fall 2022 and received a **$1 million investment**"; original 2022 investor **not named** (open lead #47827). Operator was formed 2023-10-31, so it cannot be the 2022 vehicle.
- **2024 strategic round (CONFIRMED, primary)**: GS-Invest + Rubytech GD Igor Vedyokhin bought 40% on 2024-08-12 via OOO Operator (90/10). Estimated 300–400M RUB (~$3.3–4.4M; ComNews/Finam). Structured as a charter-capital increase (500,000 → 1,333,333.34 shares), diluting founders.

## Financial activity
- FY2022: net loss ~19,929 thousand RUB (~₽19.9M)
- 23 employees (per Rusprofile); 7 shareholders
- 2023/2024 revenue/profit: paywalled (SPARK/Checko/Rusprofile HTTP 403/429)

## Russian Software Register (Unified Register, reestr.digital.gov.ru; applicant ООО Веб-Сервер)
| Product | Reg № | Added |
|---------|-------|-------|
| Angie PRO | 17604 | 2023-05-24 (first Russian web server in the registry) |
| ANIC (Angie Ingress Controller) | 20891 | 2023-12-29 |
| Angie ADC (Application Delivery Controller) | 24972 | 2024-11-27 |
Certified compatible with Astra Linux Special Edition, RED OS, Alt Server 10, ROSA — positioned for Russian state/defense procurement and nginx/NGINX Plus import substitution.

## Connection to investigation network
- Founded by ex-nginx Moscow R&D engineers (Bartenev #312, Ermilov #310, Mamontov, + Vladimir Homutov/Khomutov who later committed to Angie via vl@wbsrv.ru — finding #9844).
- Successor-of relationship to NGINX, Inc. (the Angie fork continues nginx development after F5 closed the Moscow office).
- Institutional control by GS-Invest links the fork to Russia's sanctioned sovereign-IT sector — a distinct channel from the Rambler/Sberbank corporate-control thread (which operates at the people level only via Poluyanov, now exited).

## Source coverage
- [x] OpenSanctions / ext_ru_egrul — entity ru-inn-9704151517 + full ownership/directorship graph
- [x] Rusprofile / Checko (RU aggregators) — capital, employees, FY2022 loss
- [x] reestr.digital.gov.ru + CNews/Vedomosti/Habr — software register numbers
- [x] angie.software / wbsrv.ru / GitHub webserver-llc — company self-description
- [x] GLEIF — no LEI (negative result)
- [x] ICIJ Offshore Leaks — no match (false positives only)
- [ ] SPARK (authenticated) — 2023/24 financials, GS-Invest AO shareholders (paywalled)

## DB references
- Findings: #11340 (corp record), #11341 (cap table), #11342 (GS-Invest/Operator/sanctions), #11343 ($1M funding), #11344 (software register)
- Connections: #6083–6092
- Entities: Web Server LLC #4244, GS-Invest #4245, OOO Operator #4253
- Leads: #47827, #47829, #47831, #47833
