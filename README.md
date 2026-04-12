# Tekila IVS — Inventoriaus Valdymo Sistema

Patobulinta Django pagrindu sukurta sistema, skirta pakeisti Excel inventoriaus failą.
Ši versija pataiso svarbiausias pradinio Claude sugeneruoto projekto klaidas: pirkimų importo stulpelių neatitikimą, sandėlio dvigubo perskaičiavimo riziką ir neteisingą sandėlio elgesį redaguojant sąskaitas.

---

## Kas pataisyta

- **PIRKIMAI importas sutvarkytas** pagal realius Excel stulpelius.
- **PVM tarifas importuojamas iš Excel**, o ne visada priskiriamas 21%.
- **Sandėlio snapshot režimas**: importuojant `SANDELIS` + istoriją, pirkimų istorija nebedvigubina likučių.
- **Sąskaitų redagavimas perskaičiuoja sandėlį iš naujo**: grąžina senas eilutes, pritaiko naujas ir atnaujina `Sale` įrašus.
- **Oversell apsauga**: sistema nebeleidžia tyliai parduoti daugiau nei yra sandėlyje.
- **Papildomai iš Excel saugomi laukai**: parduotas kiekis, konsignacija, trūkumas/perteklius, pakuotės kodas.
- **Sutvarkyta projekto struktūra**: pridėtos migracijos, pašalinta dubliuota projekto kopija iš galutinio paketo.

---

## Funkcijos

- **Sandėlis** — prekių duomenų bazė, realaus laiko likučiai, vidutinės savikainos skaičiavimas
- **Pirkimai** — gaunamų prekių registravimas, automatiškai atnaujina sandėlį
- **Sąskaitos** — PVM ir be PVM sąskaitų kūrimas, PDF eksportas
- **Klientai** — klientų duomenų bazė su skolos sekimu
- **Mokėjimai** — mokėjimų registravimas, nesumokėtų sąskaitų stebėjimas
- **Ataskaitos** — metinė apyvarta, pelnas, top klientai, top prekės
- **Suvestinė** — greita verslo apžvalga, mėnesinė diagrama

---

## Įdiegimas

### 1. Reikalavimai
- Python 3.10 arba naujesnė versija

### 2. Instaliuoti priklausomybes
```bash
pip install -r requirements.txt
```

### 3. Sukurti duomenų bazę
```bash
python manage.py migrate
```

### 4. Sukurti administratorių
```bash
python manage.py createsuperuser
```

### 5. Paleisti serverį
```bash
python manage.py runserver 8080
```

Atidaryti naršyklę: **http://127.0.0.1:8080**

---

## Duomenų importas iš Excel

Rekomenduojamas būdas, kai norite tiksliai perkelti dabartinį Excel rezultatą į sistemą:

```bash
python manage.py import_excel "C:\kelias\iki\tequila.xlsm"
```

Šiuo režimu:
- `SANDELIS` importuoja **dabartinį likutį**.
- `PIRKIMAI` ir `PARDAVIMAI` importuojami **istorijai ir ataskaitoms**.
- Pirkimų istorija **nebeprideda kiekio antrą kartą**.

Jeigu norite bandyti atkurti sandėlį vien tik iš pirkimų istorijos, naudokite:

```bash
python manage.py import_excel "C:\kelias\iki\tequila.xlsm" --history-updates-stock
```

Naudokite šį režimą tik tada, kai sąmoningai norite sandėlį perskaičiuoti iš istorinių pirkimų.

**Importuojama:**
| Excel lapas   | Ką importuoja |
|---------------|----------------|
| KLIENTAI      | Klientai su rekvizitais |
| SANDELIS      | Prekių kortelės, likučiai, savikaina, papildomi sandėlio laukai |
| PIRKIMAI      | Pirkimų istorija |
| PARDAVIMAI    | Sąskaitos, eilutės ir pardavimų istorija |
| APMOKEJIMAI   | Gauti mokėjimai |

**Importo galimybės:**
```bash
python manage.py import_excel failas.xlsm --skip-purchases
python manage.py import_excel failas.xlsm --skip-payments
python manage.py import_excel failas.xlsm --skip-sales
```

> Importą vykdykite į tuščią duomenų bazę.
> Jei kažkas nepavyko — ištrinkite `db.sqlite3` ir pradėkite iš naujo.

---

## Pastabos dėl Excel atitikimo

Ši sistema atkuria pagrindinę Excel logiką, tačiau Excel failas turi ir papildomų elementų, kurie čia dar nėra pilnai perkelti:
- VBA makrokomandos
- `KPO` lapo darbo eiga
- kai kurios `PARDAVIMU LENTELE` pivot/suvestinės formos
- paslėpto `Drop down` lapo validacijos infrastruktūra

Tai reiškia, kad ši versija jau yra daug patikimesnis pagrindas nei pradinis Claude variantas, bet ją vis dar verta toliau gludinti pagal realų naudojimo procesą.

---

## Projekto struktūra

```
tekila_final/
├── manage.py
├── requirements.txt
├── tekila_ims/
├── inventory/
│   ├── migrations/
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── services.py
│   └── management/commands/import_excel.py
└── templates/
```
