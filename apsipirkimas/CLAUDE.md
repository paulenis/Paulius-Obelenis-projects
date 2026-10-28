# Apsipirkimo įrankis

Asmeninis šeimos įrankis kompiuteryje: apsipirkimo sąrašas + kainų palyginimas tarp
Lidl, Maxima, Iki, Norfa, Rimi (įskaitant kainą už kg/l). Bendravimas su naudotoju – lietuviškai.

Šaltinių tyrimas (URL, laukai, API): `TYRIMAS.md`.

Sprendimas (2026-10-28): pradžioje **variantas A** – viskas veikia naudotojo kompiuteryje
(Python surinkimas + vietinis puslapis naršyklėje; šeima gali jungtis per namų Wi-Fi).
Vėliau galbūt variantas B (GitHub Actions + GitHub Pages + bendras sąrašas Supabase/Firebase),
todėl kodą rašyti taip, kad surinkimą ir puslapį būtų lengva perkelti.
Dizaino pavyzdžiai: https://claude.ai/artifact/3CrhAVLJ7zisLPzTGyYxQ2 (A–D).

## Privalomi atsparumo reikalavimai (naudotojas paprašė įsiminti)

Svetainės keičiasi be įspėjimo – įrankis turi tai išgyventi nuo pirmos versijos:

1. **Atskiras modulis kiekvienam tinklui.** Vieno tinklo klaida nestabdo kitų.
2. **Patikra prieš įrašant.** Po kiekvieno surinkimo tikrinti: prekių kiekis ≥ ~50 % praėjusio
   karto, beveik visos prekės turi pavadinimą ir kainą, kainos realios (ne 0, ne absurdiškos).
   Nepraėjus patikros – nauji duomenys neįrašomi, lieka paskutiniai geri.
3. **Matomas senumas.** Programoje prie tinklo rodyti duomenų datą ir įspėjimą, jei
   atnaujinti nepavyko (pvz. „⚠ Norfa – duomenys iš 10-21“).
4. **Saugoti žalius atsakymus** (HTML/JSON) kiekvienam paleidimui – derinimui ir
   pakartotiniam apdorojimui be naujo siuntimo.
5. **Testai su išsaugotais pavyzdžiais** kiekvienam tinklo moduliui.
6. Pirmenybė stabiliems JSON šaltiniams (Barbora, Lidl JSON, LastMile) prieš HTML klases.
7. Neapeiti apsaugos nuo botų (pvz. iki.lt Cloudflare). Jei šaltinis užsidaro – rankinis
   įvedimas arba tinklas nelyginamas.
