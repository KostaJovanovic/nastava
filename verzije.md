# Verzije: izvor strane /verzije/

The only place the page's text is written; `pages/build.py` (load_verzije) renders it into `/verzije/`. Everything
above the first `## ` is this note and is not shown.

- The version is the commit number: commit N is `0.N`. Every commit from the first to the newest is listed exactly
  once (build.py checks it), so a gap shows rather than hides.
- A day runs from 05:00 to 05:00: a commit at 3am on the 10th belongs to the 9th. Newest day first; within a day,
  write the bullets in whatever order reads best.
- `## <date>`: the day, as `10. novembra 2026.` Then one plain line, the day's lead: what the day was for.
- `- <commits> [tag] text`: one entry. `<commits>` as `54`, `56–58` or `8, 21, 24–25`. Tags: `[novo]`, `[ispravka]`,
  `[brže]`, or none. An indented line continues the one above.
- `### <heading>` groups a busy day's entries.
- Bold (`**`) the thing an entry is about; backticks keep a word in Latin when the page is read in Cyrillic.
- Write for someone who uses the site, in plain Serbian: what is different for them. Internal work (plans, CI,
  tests, tools) goes into one `Održavanje` entry a day, not a line each.

## 10. novembra 2026.
Sitnice po stranama nastavnika i predmeta, i ova strana.

- 189 [novo] **Strana Verzije.** Šta se menjalo na sajtu, po danima i po verzijama, od najnovijeg.
- 187–188 [novo] **Oblak reči na statistici:** reči koje se najčešće javljaju u objavama, iz celog teksta, bez
  linkova i imena fajlova.
- 185 [novo] **Svaki deo sajta ima svoju sliku** kad se link podeli: predmeti, nastavnici, arhiva, raspored i vesti.
- 183–184 [novo] **Nastavni planovi na strani Predmeti se sklapaju**, pa se lakše nađe ono što tražiš.
- 180 **Filteri na spiskovima nastavnika i predmeta** su manji i zauzimaju manje mesta.
- 181 **Dugme za arhivu nastavnika** se sada vidi.
- 182 **Broj postova pored nastavnika** piše samo kad je spisak poređan po njemu.
- 179 [novo] **Postovi nastavnika** na njegovoj strani: prikazuje se više njih odjednom.
- 178 **Kod bivših nastavnika** piše samo godina odlaska.
- 177 **Potpis u podnožju prati pismo:** latinicom `valjdakosta`, ćirilicom `Временска Прогноза`.
- 186 [ispravka] **Tekst u izboru pretrage** je centriran.
- 174 [ispravka] **Posle izmene sajta pregledač odmah uzima nove stilove i skripte**, umesto stare verzije
  iz keša.
- 176 [ispravka] **Animacije** su doterane posle pregleda.
- 173, 175 **Održavanje:** ispravke posle pregleda koda i beleška u planu.

## 9. novembra 2026.
Najveći dan do sad: obaveštenja na telefon, vesti fakulteta, sajtovi predmeta, strana O sajtu i arhiva bivših
  nastavnika sa fotografijama i biografijama.

### Novo na sajtu
- 57 [novo] **Obaveštenja na telefon i računar** za predmete koje pratiš, kad stigne nova objava. Uz to i spisak
  svih `RSS` feedova u jednom fajlu (`OPML`).
- 62–63 [novo] **Vesti fakulteta** imaju svoj deo sajta, sa pretragom i `RSS`-om.
- 80–81, 83 [novo] **Sajtovi predmeta** sa cent.mas.bg.ac.rs (Katedra za proizvodno mašinstvo) su sada ovde, sa
  obaveštenjima i rezultatima. Ono što nestane sa njih ostaje ovde, a strana predmeta vodi na njegov sajt.
- 100–101, 103 [novo] **Strana O sajtu:** šta je ovo, odakle su podaci i kako da tražiš da nešto uklonim. Ista
  strana je i na adresi /about.
- 61, 151, 155 [novo] **Sajt se sam osvežava sa foruma** nekoliko puta dnevno, a koliko često, određuje
  kalendar fakulteta.
- 59 **Sajt je na adresi nastava.masinci.org.**

### Pretraga
- 56 [brže] **Pretraga je brža,** a jedna objava se u rezultatima pojavljuje jednom, sa linkom na ostale postove iz
  nje. Uz to i `RSS` za ceo forum i za svaki predmet.
- 60, 64–65 [novo] **Biraš šta pretražuješ:** sve, objave, vesti, nastavnike ili predmete, u meniju pored polja
  za pretragu.
- 66 [novo] **Nastavnici i predmeti se pojavljuju dok kucaš**, ispod polja za pretragu.
- 152 [novo] **Fotografije nastavnika u pretrazi.**
- 169 **Na telefonu je tekst u polju za pretragu kraći**, pa staje.
- 97–98 [ispravka] **Kad pretraga ne uspe,** kaže zašto, jasno i bez tehničkih detalja.

### Predmeti
- 54 [novo] **Samo moji predmeti:** prekidač u bočnom meniju koji na celom sajtu prikazuje samo predmete koje pratiš.
  Reči su ujednačene: tema sa foruma je **objava**, jedna poruka u njoj **post**.
- 84–85, 105–106, 114–116, 150 [novo] **Gde je još materijal:** predmet pokazuje kad se materijal deli i van
  foruma (`Teams`, `Google Drive`, `Moodle`, `YouTube`, sajt katedre) i ko ga tu deli. Računaju se samo prava
  mesta, ne jedan usputni link.
- 87 [novo] **Na spisku predmeta** su i ESPB i link na sajt predmeta.
- 125 [novo] **Završni predmet** je na strani nastavnika naveden po oblasti, umesto jednog istog imena svuda.
- 86 [ispravka] **Objava koja nestane sa foruma** ovde ostaje, označena kao uklonjena.

### Nastavnici
- 118–120, 126–127, 130, 134, 146–149, 163, 171–172 [novo] **Arhiva nastavnika:** svi koji su nekad predavali na
  fakultetu, sa godinama, fotografijama, radovima i biografijama iz monografije fakulteta. Izvori su grupisani po
  delu iz kog su.
- 110–113, 121–122, 165, 167 [novo] **Kartica bivšeg nastavnika ima sivi ugao** koji raste sa godinama od odlaska.
- 131–133, 135–145, 153–154, 156–162, 164 [novo] **Svaka katedra ima svoju ikonicu,** na nastavnicima i na
  forumu: zupčanik, lokomotiva, osciloskop, logičko kolo i ostale. Redovi foruma su ujednačeni po visini.
- 107–109 [ispravka] **Kabineti i katedre nastavnika** su popunjeni, a dva nastavnika koji su bili samo na forumu
  su povezana sa svojim stranama.

### Izgled
- 67–69, 71–72, 75–76, 88–93, 95, 129, 168, 170 [novo] **Podnožje** u boji zaglavlja, sa linkom na stranu
  fakulteta koju ova strana kopira, `RSS`-om i potpisom koji talasa. Na telefonu je složeno u redove.
- 77–79 [novo] **Animacije:** dugmad reaguju na pritisak, prozori iskaču i nestaju, a tema se menja krugom koji se
  širi od dugmeta.
- 94, 96 **Početna** nema naslov, a red sa brojevima nema duple linkove.
- 102, 104, 117, 123 [novo] **Podeljen link ima sliku i opis** (Viber, Discord), latinicom. Google dobija mapu
  sajta i putanju strane. Postovi se ne indeksiraju, jer sadrže imena studenata.
- 166 [ispravka] **Između dve strane nema belog treptaja.**
- 128 [ispravka] **Povratak putanjom na vrhu strane** vraća na mesto gde si stao.

- 55, 58, 70, 73–74, 82, 99, 124 **Održavanje:** planovi za sledeće delove, licenca (GPL v3) i podešavanja servera.

## 8. novembra 2026.
Prvi dan: arhiva foruma je na internetu, sa novim izgledom, stranama nastavnika, Knjigom predmeta i rasporedom.

- 1 [novo] **Arhiva foruma nastave.** Sve objave sa foruma od 2014, sa pretragom ćirilicom i latinicom.
- 2–5 [novo] **Novi izgled:** plavo zaglavlje, svetla i tamna tema, nova slova i mekša crvena.
- 10–11 **Spiskovi su gušći,** složeni kao na forumu, a početna nema uvodni tekst.
- 12 [novo] **Čitljive adrese:** predmeti, smerovi i nastavnici imaju adresu po imenu.
- 13–14, 17, 19, 22–23 [novo] **Nove strane nastavnika:** kartica sa podacima na vrhu, predmeti sa foruma
  odvojeni od ostalih, spisak poređan po zvanju. Ime bez srednjeg slova svuda osim na strani nastavnika.
- 15–16 [novo] **Delovi sajta su kartice u zaglavlju,** a putanja na vrhu strane pokazuje i gde si.
- 18 [novo] **Knjiga predmeta:** svi predmeti sa opisom, grupisani i poređani kako biraš.
- 30 [novo] **Praćenje predmeta:** zvezdica na strani predmeta, a najnovije objave praćenih su na početnoj. Objava
  ima dugmad za prethodnu i sledeću.
- 31, 33, 47–48 [novo] **Biranje predmeta** po smeru i godini, u prozoru iz bočnog menija.
- 32 [novo] **Pretraga u zaglavlju zna gde si:** na strani nastavnika traži nastavnike, na strani predmeta predmete.
- 34, 38, 44, 46 [novo] **Telefon:** traka za kretanje, bočni meni kao panel, zaglavlje u jednom redu. Pre linka
  van sajta piše kuda vodi.
- 36 [novo] **Svi rasporedi na jednoj strani.**
- 40 [novo] **Prilozi** su redovi sa vrstom fajla, bez duplikata.
- 43, 45 [novo] **Statistika:** koliko objava, postova i preuzimanja ima, po godinama.
- 49, 53 [novo] **Bivši nastavnici** imaju svoj deo spiska, pronađeni u starim verzijama sajta fakulteta.
- 7 [brže] **Strane se učitavaju brže:** zaglavlje, meni i podnožje se preuzimaju jednom, a svaka strana nosi samo
  svoj sadržaj.
- 6 [brže] **Strane objava su manje:** tekst koji je bio tu samo za pretragu se uklanja.
- 20 [ispravka] **Filteri u adresi su latinicom,** pa se link sa filterom deli bez čudnih znakova.
- 26 [ispravka] **Pretraga radi i kad indeks ne stigne,** a nepostojeća strana je obična stranica sa linkom
  na početnu.
- 42, 50–52 [ispravka] **Tamna tema:** jedna ista crvena, bolji kontrast, svetlije polje za pretragu.
- 9 [ispravka] **Niz sitnih ispravki** u pretrazi, prebacivanju pisma i preuzimanju sa foruma.
- 8, 21, 24–25, 27–29, 35, 37, 39, 41 **Održavanje:** sajt se pravi na mom računaru i odatle objavljuje, uz
  alate za lokalni server i čuvanje.
