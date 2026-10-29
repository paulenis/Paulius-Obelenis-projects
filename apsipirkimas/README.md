# Pirkinių sąrašas

Šeimos apsipirkimo sąrašas su kainų palyginimu tarp **Lidl, Maxima, Iki, Rimi ir Norfa**
(įskaitant kainą už kg / l). Veikia jūsų kompiuteryje; telefonai jungiasi per namų Wi-Fi.

## Ko reikia

- **Python 3.9 ar naujesnis** (nemokamai: <https://www.python.org/downloads/>).
  Windows diegimo lange pažymėkite „Add python.exe to PATH“.
- Daugiau nieko diegti nereikia – programa naudoja tik standartinę Python biblioteką.

## Paleidimas

- **Windows:** du kartus spustelėkite `paleisti.bat`.
- **Mac / Linux:** terminale `./paleisti.sh` (arba `python3 -m kainos.server`).

Atsidarys langas su adresais:

```
Programa veikia: http://localhost:8000
Telefone (tas pats Wi-Fi): http://192.168.1.23:8000
```

Kompiuteryje atidarykite pirmą adresą naršyklėje. Langą palikite atidarytą, kol naudojatės.

Pirmą kartą (ir vėliau, kai kainos senesnės nei 6 dienos) programa **pati surenka kainas** –
tai užtrunka apie 10 minučių. Kainas galima atnaujinti ir mygtuku „Atnaujinti kainas“.

### Telefone

1. Telefonas turi būti prisijungęs prie to paties namų Wi-Fi.
2. Naršyklėje atidarykite antrą adresą (`http://192.168...:8000`).
3. Įsidėkite į pagrindinį ekraną: Android Chrome – meniu ⋮ → „Pridėti prie pagrindinio ekrano“;
   iPhone Safari – „Bendrinti“ → „Į pagrindinį ekraną“.
4. Windows gali paklausti, ar leisti Python prieigą prie tinklo – pasirinkite **privatų tinklą** ir leiskite.

Kiekvienas šeimos narys pirmą kartą įveda savo vardą – jis rodomas prie jo pridėtų prekių.

### Parduotuvėje (be ryšio su kompiuteriu)

Sąrašas saugomas pačiame telefone, todėl atidarytame puslapyje galite žymėti nupirktas prekes
ir be ryšio. Pakeitimai išsiunčiami į kompiuterį, kai grįžtate į namų Wi-Fi.

**Svarbu:** prieš išeidami atidarykite programą namuose ir **neuždarykite jos lango**.
Jei telefonas puslapį uždarys, be namų Wi-Fi jo iš naujo atidaryti nepavyks (paprastu
`http://` adresu naršyklės neleidžia išsaugoti puslapio darbui be ryšio). Tai išsispręs,
jei vėliau programą perkelsime į internetą.

## Kainų rinkimas atskirai

```
python3 -m kainos.collect              # visi tinklai
python3 -m kainos.collect rimi norfa   # tik šie
python3 -m kainos.collect --reparse    # perskaityti paskutinius išsaugotus failus be siuntimo
```

## Kai kuris tinklas nebeatsinaujina

Parduotuvių svetainės keičiasi. Tada programos viršuje prie tinklo matysite oranžinį ženkliuką,
pvz. „Norfa – nepavyko, rodoma 10-21“, o paieškoje liks paskutiniai geri to tinklo duomenys.
Kiti tinklai veikia toliau.

Kiekvieno rinkimo „žali“ failai saugomi `data/raw/<tinklas>/` (paskutiniai 6 kartai) – pagal juos
gedimą galima rasti ir pataisyti.

## Kaip tai veikia

| Tinklas | Šaltinis |
|---|---|
| Lidl | lidl.lt savaitės akcijų puslapiai |
| Maxima | barbora.lt AČIŪ akcijos |
| Iki | lastmile.lt (IKI e. parduotuvės partneris) |
| Rimi | rimi.lt e. parduotuvės akcijos |
| Norfa | norfa.lt „Praktiški pasiūlymai“ |

Šiuo metu renkamos **akcijinės** prekės (apie 15 000). Kodas:

- `kainos/chains/` – po vieną modulį kiekvienam tinklui (`fetch` atsisiunčia, `parse` ištraukia prekes);
- `kainos/validation.py` – patikra prieš įrašant (prekių kiekis, kainos);
- `kainos/collect.py` – rinkimas, žalių failų saugojimas;
- `kainos/storage.py` – SQLite duomenų bazė `data/kainos.db`;
- `kainos/server.py` – vietinis serveris ir API;
- `web/` – programos puslapis.

Testai: `python3 -m unittest discover -s tests -t .`
