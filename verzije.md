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
- 187–188 [novo] **Oblak reči na statistici:** 60 reči koje se najčešće javljaju u postovima, a svaka vodi na
  pretragu te reči. Broje se iz celog teksta, bez linkova, adresa i imena fajlova.
- 183–184 [novo] **Nastavni planovi na strani Predmeti su pregledniji.** Svaki program se sklapa (prvi je otvoren),
  semestar je jedan blok, a izborni predmeti su u obojenim trakama. Dugačak izborni blok pokazuje prvih pet, a
  ostale posle `Prikaži još`.
- 185 [novo] **Svaki deo sajta ima svoju sliku** kad se link podeli: forum, raspored, nastavnici, arhiva, predmeti
  i vesti. Slika je centrirana, pa se vidi i kad je Viber ili WhatsApp iseku na kvadrat.
- 179 **Na strani nastavnika je deset najnovijih postova,** a ostali su ispod dugmeta `Prikaži još`.
- 180 **Filteri na spiskovima nastavnika i predmeta** su u jednom redu, kao zaobljena dugmad, a broj rezultata je
  desno.
- 181–182 **Arhiva nastavnika je plavo dugme sa brojem.** Kartica nastavnika uvek pokazuje kabinet, a broj
  postova samo kad je spisak poređan po njemu.
- 178 **Kod bivših nastavnika piše samo godina odlaska,** jer je tačan datum samo datum kopije sa Wayback Machine-a.
- 177 **Potpis u podnožju prati pismo:** latinicom `valjdakosta`, ćirilicom `Временска Прогноза`.
- 174 [ispravka] **Posle izmene sajta pregledač odmah uzima nove stilove i skripte**, umesto stare verzije iz keša.
- 176 [ispravka] **Animacije:** na telefonu kartica više ne ostaje podignuta posle dodira, kvačica u izboru
  predmeta iskače samo na kartici koju si izabrao, a brzo menjanje teme se više ne zaglavi. Pozadina prozora se
  pojavljuje postepeno, a više dugmadi reaguje na pritisak.
- 173 [ispravka] **Strana sa sajta predmeta koja nestane pa se vrati** više nije označena kao uklonjena.
- 186 [ispravka] **Tekst u izboru pretrage** je centriran po visini.
- 175, 190 **Održavanje:** beleške u planu, a ova strana je prepravljena prema stvarnim izmenama u kodu.

## 9. novembra 2026.
Najveći dan do sad: obaveštenja na telefon, vesti fakulteta, sajtovi predmeta, strana O sajtu i arhiva bivših
  nastavnika sa fotografijama i biografijama.

### Novo na sajtu
- 57 [novo] **Obaveštenja o novim objavama** na telefon i računar, za predmete koje pratiš: prekidač je u delu
  Moji predmeti. Tu je i link koji daje `RSS` svih praćenih predmeta u jednom fajlu (`OPML`), za čitač.
- 62–63 [novo] **Vesti fakulteta** (/vesti/): godina po strana, filter po kategoriji, svaka vest na svojoj strani.
  Pet najnovijih je na početnoj, a imaju i svoj `RSS` i svoje mesto u pretrazi.
- 80–81, 83 [novo] **Sajtovi predmeta** sa cent.mas.bg.ac.rs (Katedra za proizvodno mašinstvo) su sada ovde.
  Njihova obaveštenja su među objavama predmeta, označena sa `cent`, a strane (predavanja, rezultati) su na strani
  predmeta, sa ranijim verzijama. Ono što cent isprazni ili izmeni ovde ostaje u poslednjem obliku. Predmet bez
  foruma sada ima svoju stranu, sa linkom na sajt predmeta.
- 100–101, 103 [novo] **Strana O sajtu:** šta je ovo, odakle su podaci, šta ovde ne može da stigne i kako da
  tražiš da nešto uklonim. Ista strana je i na adresi /about.
- 61, 151, 155 [novo] **Sajt se sam osvežava sa foruma** tri puta dnevno. Kalendar nastave određuje šta se još
  proverava: u upisu i ispitnim rokovima više, rasporedi jednom mesečno, nastavnici i predmeti jednom godišnje.
- 59 **Sajt je na adresi nastava.masinci.org.**

### Pretraga
- 56 [brže] **Pretraga je brža,** a objava se u rezultatima pojavljuje jednom, sa linkom `+ još N postova iz ove
  objave`. Bez upita red pokazuje početak teksta. Uz to i `RSS` za ceo forum i za svaki predmet.
- 60, 64–65 [novo] **Biraš šta pretražuješ:** sve, postove, nastavnike ili predmete, u meniju pored polja. Kad je
  izabrano sve, ispod polja se dok kucaš pojave predmeti, nastavnici i stavke rasporeda (kalendar, sale, ispiti).
- 66 [novo] **Na ostalim stranama, dok kucaš,** ispod polja se pojavi pet najboljih pogodaka iz postova i vesti,
  sa linkom na sve rezultate.
- 152 [novo] **Nastavnici u pretrazi imaju fotografiju,** zvanje i katedru. Bivši su posle sadašnjih, a i katedre
  su među rezultatima, sa linkom na svoje nastavnike.
- 169 **Na telefonu je tekst u polju za pretragu kraći**, pa staje.
- [ispravka] **Odlomci u rezultatima** su na srpskom (`preuzeto 5 puta`) i ne lome se na kraju teksta. Prazne
  tabele su sklonjene sa strane sa ispitima.
- 97–98 [ispravka] **Kad pretraga ne može da se učita,** kaže zašto, običnim rečima: nema mreže, nema indeksa ili
  greška na serveru.

### Predmeti
- 54 [novo] **Samo moji predmeti:** prekidač u bočnom meniju koji na celom sajtu prikazuje samo predmete koje pratiš,
  i pretraga ga prati. Reči su ujednačene: tema sa foruma je **objava**, jedna poruka u njoj **post**.
- 84–85, 105–106, 114–116, 150 [novo] **Gde je još materijal:** predmet pokazuje gde se materijal deli i van
  foruma (`Teams`, `Classroom`, `Google Drive`, `OneDrive`, `Moodle`, `YouTube`, sajt katedre) i ko ga tu deli, po
  linkovima iz postova. Računaju se samo prava mesta: folder, plejlista ili više linkova, a ne formular ili jedan
  sastanak. Na strani nastavnika su oznake za njegove linkove.
- 87 [novo] **Na spisku predmeta** su i ESPB i link na sajt predmeta.
- 162 **Smerovi su ispisani celim imenom** u izboru predmeta i Knjizi predmeta (`МИ` je Машинско инжењерство).
- 125 [ispravka] **Završni predmet** je kod nastavnika naveden po oblasti (`Завршни предмет - Трибологија`),
  umesto jednog istog reda.
- 86 [ispravka] **Objava koja nestane sa foruma** ovde ostaje, označena kao uklonjena.

### Nastavnici
- 118–120, 126–127, 134, 146–149, 163, 171–172 [novo] **Arhiva nastavnika** (/nastavnici/arhiva/): oni koji
  više nisu na fakultetu, sa godinama na fakultetu. Svako ima svoju stranu, sa podacima iz monografije fakulteta,
  In Memoriam, starog sajta fakulteta i Vikipedije, uz izvore grupisane po delu. Tu su i radovi iz repozitorijuma
  fakulteta, profil sa starog sajta i fotografije gde postoje.
- 130 [novo] **Biografija iz monografije fakulteta** (2023), sa brojem strane, kod bivših i sadašnjih nastavnika.
- **Fotografije nastavnika se čuvaju ovde,** pa bivši zadržavaju svoju i kad je fakultet skloni.
- 110–113, 121–122, 165, 167 [novo] **Kartica bivšeg nastavnika ima sivi ugao** koji raste sa godinama od odlaska.
- 131–133, 135–145, 153–154, 156–161, 164 [novo] **Svaka katedra ima svoju ikonicu,** na karticama i stranama
  nastavnika i u redovima foruma: zupčanik, lokomotiva sa parom, osciloskop, logičko kolo i ostale. Redovi foruma
  su iste visine.
- 107–109 [ispravka] **Kabinet je onaj iz profila na sajtu fakulteta,** emeritusi imaju katedru, a dva nastavnika
  sa foruma su povezana sa svojim stranama.

### Izgled
- 67–69, 71–72, 75–76, 88–93, 95, 129, 168, 170 [novo] **Podnožje** u boji zaglavlja: link na stranu fakulteta
  koju ova strana kopira, `RSS`, `Prijavi grešku`, vreme poslednje provere i potpis koji talasa. Na telefonu su
  linkovi u mreži.
- 77–79 [novo] **Animacije:** dugmad reaguju na pritisak, prozori se gase postepeno, zvezdica iskoči kad
  zapratiš predmet, a tema se menja krugom koji prelazi preko strane.
- 94, 96 **Početna** nema naslov, a red sa brojevima nema duple linkove.
- 102, 104, 117, 123 [novo] **Podeljen link ima sliku i opis** (Viber, Discord), latinicom. Google dobija mapu
  sajta i putanju strane. Postovi se ne indeksiraju, jer sadrže imena studenata.
- 166 [ispravka] **Između dve strane nema belog treptaja.**
- 128 [ispravka] **Povratak putanjom na vrhu strane** vraća na mesto gde si stao.

- 55, 58, 70, 73–74, 82, 99, 124 **Održavanje:** planovi za sledeće delove, licenca (GPL v3) i podešavanja servera.

## 8. novembra 2026.
Prvi dan: arhiva foruma je na internetu, sa novim izgledom, stranama nastavnika, Knjigom predmeta i rasporedom.

- 1 [novo] **Arhiva foruma nastave.** Sve objave sa foruma od 2014, sa pretragom ćirilicom i latinicom.
- 2–5 [novo] **Novi izgled:** plavo zaglavlje sa talasom u logu, svetla i tamna tema na jedno dugme, nova slova i
  mekša crvena. Forum i predmeti su tabele kao na forumu, objava ima dugmad `Preuzmi` i `Cela tema`, a filteri
  pretrage u bočnom meniju deluju čim ih promeniš.
- 10–11 **Sve je gušće, složeno kao na forumu:** manja slova, tešnji redovi, oštriji uglovi. Početna nema uvodni
  tekst.
- 12 [novo] **Čitljive adrese:** predmeti, smerovi i nastavnici imaju adresu po imenu, kao
  /nastavnik/dusan-lj-djukic/.
- 13–14, 17, 19, 22–23 [novo] **Nastavnici:** spisak kartica sa fotografijom, zvanjem, katedrom i kabinetom, sa
  filterima i poretkom po zvanju. Strana nastavnika ima traku sa podacima i predmetima (prvo oni sa objavama na
  forumu), njegove postove po godinama i ceo profil sa sajta fakulteta. Imena su bez srednjeg slova.
- 15–16 **Delovi sajta su na vrhu bočnog menija,** sa označenim delom u kom si, a zaglavlje je niže.
- 18 [novo] **Knjiga predmeta** (/predmeti/): svi predmeti sa pretragom i filterima po programu i katedri, i
  strana svakog predmeta sa opisom fakulteta. Nastavnici se mogu grupisati i poređati.
- 30 [novo] **Praćenje predmeta:** najnovije objave praćenih predmeta su na početnoj. Post vodi na prethodni i
  sledeći u objavi, a stare verzije rasporeda imaju svoje strane.
- 31, 33, 47–48 [novo] **Biranje predmeta:** prozor sa programima, godinama i izbornim blokovima. Izbor programa
  ili godine sužava spisak, a bez izbora su svi predmeti po imenu.
- 32 [novo] **Pretraga u zaglavlju zna gde si:** na spisku nastavnika ili predmeta filtrira taj spisak, a na
  strani nastavnika traži nastavnike.
- 34, 44, 46 [novo] **Telefon:** donja traka za kretanje i zaglavlje u jednom redu. Pismo je samo latinica ili
  ćirilica, a tema je svetla dok je ne promeniš.
- 38 [novo] **Grupe na spiskovima se sklapaju** i same se otvore kad filter nađe nešto u njima. Pre linka van
  sajta piše kuda vodi, a PDF se otvara u novom tabu.
- 36 [novo] **Raspored** (/raspored/): jedna strana, program po program, a sajt pamti koji si izabrao.
- 40 [novo] **Prilozi** su redovi sa obojenom vrstom fajla, bez duplikata, a linkovi u tekstu imaju ikonicu.
- 43, 45 [novo] **Statistika** (/statistika/): objave po godinama i drugo. U bočnom meniju je grafikon po godinama
  umesto polja od-do, a klik na godinu filtrira pretragu.
- 49, 53 [novo] **Bivši nastavnici** imaju svoj deo spiska, sa profilima i fotografijama vraćenim sa Wayback
  Machine-a i masinac.org.
- 6 [brže] **Strane objava su manje:** tekst koji je bio tu samo za pretragu se uklanja.
- 9 [ispravka] **Nastavnik koji ode sa fakulteta** zadržava svoju stranu i linkove na postove. Prekidači za pismo
  i temu rade i kad pregledač ne dozvoli čuvanje podešavanja.
- 20 [ispravka] **Filteri u adresi su latinicom,** pa se link sa filterom deli bez čudnih znakova.
- 26 [ispravka] **Kad pretraga ne može da se učita,** piše `Pretraga trenutno nije dostupna` umesto da večno traži.
- 42, 50–52 [ispravka] **Tamna tema:** jedna ista crvena, bolji kontrast, a polje za pretragu se ističe. Traka sa
  kalendarom više ne pocrveni pod mišem.
- 7–8, 21, 24–25, 27–29, 35, 37, 39, 41 **Održavanje:** sajt se pravi na mom računaru i odatle objavljuje, strane
  se čuvaju kao delovi koje server spaja, i alati za lokalni server i čuvanje.
