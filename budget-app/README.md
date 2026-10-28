# Šeimos biudžetas (Swedbank)

Paprasta vietinė web programėlė šeimos pajamoms ir išlaidoms sekti pagal
Swedbank sąskaitų išrašus (CSV). Duomenys saugomi tik jūsų kompiuteryje
(`data/budget.db`, SQLite).

## Paleidimas

```bash
cd budget-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Atidarykite <http://127.0.0.1:5000>.

### Atidarymas telefonu

Kompiuteryje ir telefone turi būti tas pats namų Wi-Fi.

```bash
BUDGET_HOST=0.0.0.0 python app.py          # Windows (PowerShell): $env:BUDGET_HOST="0.0.0.0"; python app.py
```

Sužinokite kompiuterio vietinį IP (pvz. `192.168.1.25`) ir telefone atidarykite
`http://192.168.1.25:5000`. Programėlė neturi prisijungimo, todėl taip leiskite
tik namų tinkle, ne viešame Wi-Fi.

## Naudojimas

1. Swedbank internetinėje bankininkystėje eksportuokite sąskaitos išrašą CSV formatu
   (savo, žmonos, kredito kortelės).
2. **Įkelti išrašą** – galima kelti kelis failus iš karto ir persidengiančius laikotarpius.
3. **Nustatymai** – įrašykite šeimos narių vardus ir pavardes, sąskaitoms nurodykite
   savininką ir pavadinimą.
4. **Sandoriai** – pataisykite tipą ar kategoriją; pažymėjus „visada“ sukuriama
   taisyklė visiems to gavėjo sandoriams.

## Kaip skaičiuojama

- **Dublikatai.** Kiekvienas sandoris atpažįstamas pagal sąskaitą ir banko įrašo
  numerį, todėl tas pats sandoris niekada neįrašomas du kartus.
- **Pervedimai neskaičiuojami** į pajamas ir išlaidas:
  - „Kredito padengimas“, „Pervedimas tarp savo sąskaitų“;
  - pervedimai šeimos nariams ir iš jų (pagal vardus nustatymuose);
  - ta pati suma priešingu ženklu dviejose savo sąskaitose per 3 dienas.
- **Kredito kortelė.** Išlaidos yra patys pirkiniai kortele, o kortelės padengimas
  yra pervedimas. Pirkinys priskiriamas tikrajai pirkinio datai (iš aprašymo
  „PIRKINYS … 2026.09.01 …“), net jei bankas jį nurašė mėnesiu vėliau.
- **Grąžinimai** kortele mažina išlaidas, o ne didina pajamas.
- Rankiniu būdu pataisyti sandoriai automatinio perklasifikavimo nebeliečia.

## Testai

```bash
pytest
```

Testų failai `tests/fixtures/` yra išgalvoti, ne tikri išrašai.
