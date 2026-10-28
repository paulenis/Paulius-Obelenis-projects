# Šaltinių tyrimas (2026-10-28)

Asmeninis šeimos apsipirkimo įrankis: apsipirkimo sąrašas + kainų palyginimas
tarp tinklų (įskaitant kainą už kg/l). Tinklai: Lidl, Maxima, Iki, Norfa, Rimi.

## Santrauka

| Tinklas | Sudėtingumas | Geriausias šaltinis | Formatas | Kaina už kg/l | Įprastos kainos | Galiojimo datos |
|---|---|---|---|---|---|---|
| Maxima | lengva | barbora.lt + maxima.lt/pasiulymai | JSON / HTML | yra | yra (Barbora) | maxima.lt („Iki 11.02“) |
| Rimi | lengva | rimi.lt/e-parduotuve/lt/akcijos | HTML | yra | yra | tik prekės puslapyje |
| Iki | vidutinė | lastmile.lt API | JSON | skaičiuojama | yra | yra |
| Norfa | lengva | norfa.lt praktiški pasiūlymai | HTML | skaičiuojama iš pavadinimo | nėra | yra |
| Lidl | lengva / sunki | lidl.lt puslapio JSON (~21 maisto prekė) | JSON HTML'e | dažnai yra | nėra | yra |

## Lidl

- Akcijos: `https://www.lidl.lt/c/svarbiausios-sios-savaites-akcijos/a10023711`
  (21 maisto prekė), `https://www.lidl.lt/c/ne-maisto-prekiu-pasiulymai/a10086868` (34).
- Kiekviena prekė HTML'e turi atributą `data-grid-data` su JSON (html-escaped).
  Laukai: `fullTitle`, `price.price`, `price.oldPrice`, `price.discount.percentageDiscount`,
  `price.packaging.text` („500 g“), `price.basePrice.text` („1 kg = 5,98 €“),
  `lidlPlus[].price` (Lidl Plus kaina), `stockAvailability.badgeInfoV2[].validFrom/validUntil`
  (unix laikas, yra ir būsimos datos), `productId`, `canonicalUrl`.
- Paieškos API: `https://www.lidl.lt/q/api/search?assortment=LT&locale=lt_LT&version=v2.0.0&q=...&fetchsize=48&offset=0`
  (JSON, `items[].gridbox.data` toks pat kaip aukščiau). Tik ~50 prekių, ne pilnas asortimentas.
- Pilnas leidinys: `https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=<id>&region_id=0`
  (id iš nuorodų `lidl.lt/l/lt/leidinys/<id>/...`). JSON turi tik puslapių paveikslėlius ir
  `pdfUrl` (~33 MB). PDF turi teksto sluoksnį, bet maketas suardytas – pradžioje neapdoroti.
- E. parduotuvės nėra → įprastų kainų nėra.

## Maxima

- Akcijos: `https://www.maxima.lt/pasiulymai` – viename HTML puslapyje visos (~191).
  Kortelė: `data-controller="offerCard"`, pavadinimas `<h4>`, kaina
  `offer-price-tag__price-integer` + `__price-fraction`, sena kaina `offer-price-tag__old-price`,
  nuolaida `offer-price-tag__bottom-discount`, `offer-price-tag__meta-line` („1 kg – 2,49 €“,
  „Iki 11.02“), kortelės sąlyga – `<img alt="Tik su AČIŪ kortele">`.
  Tipai: `specialWithRegularAndPercentage`, `quantityOrBundle` („2 vnt. už“),
  `topPercentage` (tik „-20 % gaminiams X“, be kainos).
- Leidinys `maxima.lt/leidiniai/...` – iPaper (paveikslėliai), nereikia.
- **Barbora** (`https://barbora.lt`): pilnas asortimentas. HTML'e `window.b_productList = [...]`
  (JSON), 52 prekės puslapyje, `?page=N`. Pvz. `https://barbora.lt/akcijos?page=2`.
  Laukai: `title`, `price`, `retail_price`, `comparative_unit_price` + `comparative_unit`,
  `promotion` (`type`: `LOYALTY_PRICE`, `X_FOR_Y`; `oldPrice`, `percentage`,
  `loyaltyCardRequired`), `category_name_full_path`. Galiojimo datų nėra.

## Iki

- `iki.lt` saugomas Cloudflare apsaugos nuo botų („Just a moment...“) – automatiškai nepasiekiama,
  apeiti NEBANDYTI. Pasiekiamas tik `https://www.iki.lt/sitemap.xml`.
- **LastMile** (IKI e. parduotuvės partneris), neoficialus vidinis API:
  `POST https://searchservice-952707942140.europe-north1.run.app/v1/frontend-products`
  ```json
  {"params":{"type":"view_products","isActive":true,"isApproved":true,
   "filter":{"showOnlyPromoPrices":true},"sort":"karma",
   "chainIds":["CvKfTzV4TN5U8BTMF1Hl"],"categoryIds":[],"isUsingStock":true},
   "limit":60,"fromIndex":0}
  ```
  Atsakymas: `{"products":[{"frontEndProduct":{...}}],"count":N}`. IKI: ~14 900 prekių,
  ~3 800 akcijinių. Laukai: `name`, `prc.p` (įprasta), `prc.s` (akcijos), `prc.l` (su kortele),
  `prc.still` / `prc.ltill` (galioja iki), `lastMonthLowestPrice`, `conversionMeasure` +
  `conversionValue` (pvz. KG 0.5 → kaina už kg skaičiuojama).
- Rizika: API gali pasikeisti; kainos internete gali skirtis nuo parduotuvės (nepatikrinta).

## Norfa

- `https://www.norfa.lt/akciju-puslapiai/praktiski-pasiulymai/` – viename HTML ~736 prekės.
  `c-product__name`, `c-product__price`, `c-product__old-price`, `c-product__discount`,
  `c-more-info__content` („Galioja 10.29-11.11 d.“, „Nuolaida taikoma kasoje“, „be taros užstato“).
  Yra ir praėjusio laikotarpio prekių – filtruoti pagal datą. ~100 prekių tik su „-40 %“, be kainos.
- Kainos už kg/l nėra – skaičiuoti iš kiekio pavadinime („800 g“).
- `/akciju-puslapiai/akcijos/` – tik ~20 reklaminių straipsnių laisvu tekstu.
- Leidinys: `norfa.lt/leidiniai/download/N` (PDF) arba yumpu.com. E. parduotuvės nėra.

## Rimi

- Akcijos: `https://www.rimi.lt/e-parduotuve/lt/akcijos?currentPage=N&pageSize=80`
  (~3 400 akcijinių prekių; numatytai 40/psl., 86 psl.). Serverio HTML, be JS.
- Kortelė: `div.js-product-container[data-product-code]`, pavadinimas `p.card__name`,
  kaina `.price-tag.card__price .sr-only` („0.72 € už kg“), kaina už vnt. `.card__price-per`,
  sena kaina „Įprasta kaina: 0,85 €“, kortelės kaina `.price-label` su
  `promotion-labels/rimi-card.*.png` (+ kaina už kg/l joje).
  DĖMESIO: `data-gtm-eec-product` laukas `price` nepatikimas – nenaudoti.
- Galiojimo datos tik prekės puslapyje („Pasiūlymas galioja nuo 2026.10.27 iki 2026.11.02“).
  Imti tik pasirinktoms prekėms arba laikyti savaitės ciklu.
- Pilnas asortimentas per kategorijas: `/e-parduotuve/lt/produktai/<...>/c/SH-11?currentPage=N`.
- Leidinys: `leidiniai.rimi.lt/2026/weekly/rimi-savaitinis-leidinys-nr-44/` – iPaper, nereikia.
- `robots.txt` neleidžia tik `/search?q=*`, `/cart/`, `/checkout`, `/account`.
