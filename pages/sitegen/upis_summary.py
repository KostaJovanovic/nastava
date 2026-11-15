"""upis/start's tabs in short, written by hand from the faculty's pages (studije.html shows each above its tab).

seen: the sha (first 10) of each page the tab shows, its own and its dates pages, as when the summary was written.
Once one changes, the build warns with the new ones and the summary is left out until it is checked and rewritten:
a stale date or fee shown as the short version would mislead.
rows: (label, text); the text is HTML.
"""

ACCOUNT = "840-32848845-64"

UPIS_SUMMARY = {
    "upis/oas": dict(
        seen={"upis/oas": "09f88bfb3d", "upis/vaznidatumioas": "558040cf84", "upis/vaznidatumioas/mi": "a516a74fd3", "upis/vaznidatumioas/itm": "bd36f6cb6a"},
        rows=[
            ("Rok", "Treći upisni rok, septembar 2026."),
            ("Pretprijava", "Online, obavezna: 14–16. 9."),
            ("Prijava", "Sreda 16. 9, 12–14h, na fakultetu: info pult u holu, pa šalter Studentske službe."),
            ("Prijemni", "Matematika, petak 18. 9. u 10h; ispred sale najkasnije u 9:45. Rešenja u 15h."),
            ("Rang liste", "Preliminarna 18. 9. do 20h · prigovori do 21. 9. u 8h · konačna 22. 9. do 12h."),
            ("Upis", "23. 9. u 10h, prozivka po konačnoj listi. Ko se ne upiše na vreme, gubi mesto."),
            ("Slobodna mesta", "Posle drugog roka, MI: 2 na engleskom, 1 samofinansirajuće, 1 za završenu školu u inostranstvu."),
            ("Plaćaš", f"Prijemni <b>4.000 din</b> (račun {ACCOUNT}, poziv na broj 141).<br>"
             "Školarina za samofinansirajuće: MI <b>111.000 din</b>, ITM <b>180.000 din</b> (do 10 rata); "
             "strani državljani <b>1.800 €</b>; MI na engleskom <b>5.000 €</b> odjednom, pri upisu."),
            ("Za prijavu", "Odštampana i potpisana prijava i izjave (obrasci u Informatoru 2026), fotokopije svedočanstava "
             "sva 4 razreda i diplome mature, originali na uvid, uplatnica za prijemni."),
        ],
    ),
    "upis/mas": dict(
        seen={"upis/mas": "6ba95c7e14", "upis/vaznidatumimas": "a6390d9600"},
        rows=[
            ("Rok", "Treći upisni rok, novembar 2026."),
            ("Pretprijava", "Online, obavezna: 30. 10–2. 11. U njoj biraš module po prioritetu; posle se ne menja."),
            ("Prijava", "2. 11, 12:30–14:30, šalteri Studentske službe."),
            ("Rang liste", "Preliminarna 2. 11. u 16h · žalbe do 4. 11. u 8h (portirnica) · konačna 5. 11. do 13h."),
            ("Upis", "6. 11: Industrija 4.0 u 11:45, Mašinsko inženjerstvo u 12h."),
            ("Slobodna mesta", "MI na srpskom 75 budžetskih · MI na engleskom 9 samofinansirajućih · "
             "Industrija 4.0: 5 budžetskih i 17 samofinansirajućih."),
            ("Plaćaš", f"Prijava <b>4.000 din</b> (poziv 151) i upis <b>4.000 din</b> (poziv 152), račun {ACCOUNT}.<br>"
             "Školarina za samofinansirajuće: MI <b>111.000 din</b>, Industrija 4.0 <b>180.000 din</b> (do 10 rata, prva pri upisu); "
             "strani državljani <b>2.400 €</b>; MI na engleskom <b>7.500 €</b> odjednom.<br>"
             "Pri upisu još: Centar za razvoj karijere, a samofinansirajući i dopunski deo školarine UB <b>2.000 din</b> (strani 2.500)."),
            ("Za prijavu", "Prijavni list, fotokopije diplome i dodatka diplomi (ili uverenja o diplomiranju i položenim "
             "ispitima), originali na uvid, uplatnica."),
            ("Za upis", "Potvrda o prijavi, overene fotokopije, 2 slike 4,5×3,5 cm, ŠV-20, indeks i ugovor (Skriptarnica), uplatnice."),
        ],
    ),
    "upis/das": dict(
        seen={"upis/das": "4d00ce01c9", "upis/vaznidatumidas": "55a39fe7b0"},
        rows=[
            ("Rok", "Treći upisni rok, novembar 2026."),
            ("Uslov", "Master ili integrisane studije (300 ESPB) sa prosekom bar 8, ili radovi koji dopune do 8; znanje engleskog."),
            ("Pretprijava", "Online, obavezna: 12–13. 11."),
            ("Prijava", "13. 11, 12:30–14:30, šalter 7 Studentske službe."),
            ("Rang liste", "Preliminarna 13. 11. u 16h · žalbe do 16. 11. u 8h (portirnica) · konačna 17. 11. u 12h."),
            ("Upis", "17. 11. u 13h."),
            ("Mesta", "Do 50: 30 budžetskih i 15 samofinansirajućih na srpskom, 5 samofinansirajućih na engleskom."),
            ("Plaćaš", f"Prijava <b>4.000 din</b> (račun {ACCOUNT}, poziv 201).<br>"
             "Školarina <b>2.400 €</b> godišnje (do 10 rata; prva, <b>240 €</b>, pri upisu, poziv 101); "
             "na engleskom <b>10.000 €</b> odjednom. Pri upisu još Centar za razvoj karijere."),
            ("Za prijavu", "Prijavni list, fotokopije diploma OAS i MAS (sa dodacima), dokaz o engleskom (ako nije "
             "položen na studijama), uplatnica, izjave; originali na uvid."),
            ("Za upis", "Overene fotokopije, 2 slike 4,5×3,5 cm, ŠV-20, indeks i ugovor (Skriptarnica), uplatnice."),
        ],
    ),
    "studenti/start": dict(
        seen={"studenti/start": "5654ef1086"},
        rows=[
            ("Prijava za upis", "Elektronski, na Studentskom servisu, obavezna (bez nje gubiš status): OAS i MAS 14. 9–5. 10, "
             "DAS 14. 9–9. 10."),
            ("Molbe", "Mirovanje, produženje statusa, dugovanja: 10. 9–3. 10, samo sa fakultetskog mejla na "
             "molbe@mas.bg.ac.rs (subject: broj indeksa – tip molbe)."),
            ("Uslovi", "Budžet: bar 48 ESPB u 2025/26 i mesto u kvoti. Druga godina: 48 ESPB, treća (OAS): 96."),
            ("Izbor predmeta", "Petak 9. 10. ili subota 10. 10. Najviše 90 ESPB; preko 60 se plaća po bodu."),
            ("Rokovi", "Za upis na master OAS završiti do 14. 10; poslednja odbrana master rada 14. 10."),
            ("Plaćaš", f"Pri overi, račun {ACCOUNT}, model 97: Centar za razvoj karijere <b>300 din</b> (poziv 127), svi; "
             "dopunski deo školarine UB <b>2.000 din</b> (poziv 136), samo samofinansirajući (strani 2.500)."),
            ("Dolazak", "Overa indeksa i aneks ugovora na fakultetu, termini naknadno. Ponesi indeks i uplatnice."),
        ],
    ),
}
