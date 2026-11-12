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

## 11. novembra 2026.
Sajtovi deset katedri su u arhivi, a strane sa cent-a izgledaju kao na cent-u.

- 288 [ispravka] **Header u užem prozoru:** pretraga više ne prekriva ime sajta i dugmiće za pismo i temu, nego
  se sama suzi.
- 289 [novo] **Scrollbar u bojama sajta,** u svetloj i tamnoj temi, i na strani i u spiskovima koji se skroluju
  (pretraga, side panel).
- 290 [ispravka] **Objave nastavnika iz Teams-a** više ne pokazuju imena i brojeve indeksa studenata (spisak
  rezultata, raspored odbrana), kao ni studentske mejlove. Bodovi i ocene ostaju, bez imena.
- 291 [ispravka] **Obaveštenja sa sajtova katedri ostaju** i kad katedra skloni stranu na kojoj su bila, ili kad
  se sajt jednom ne javi na vreme.
- 292 [ispravka] **Dva obaveštenja sa cent-a istog naslova i datuma** (dva puta `Rezultati` istog dana) su dva
  posta, a ne jedan koji sakrije drugi.
- 269–273 [novo] **Objave iz Teams-a** za šest predmeta: Termodinamika B, Osnovi otpornosti konstrukcija, Otpornost
  materijala, Inženjerska grafika, Estetski dizajn i Mašinsko inženjerstvo i održivi razvoj. Objave nastavnika su
  objave predmeta, sa prilozima. Odgovori studenata stoje kao `Student #1`, `Student #2`… bez imena, broja indeksa i
  mejla. Ostali fajlovi iz Teams-a su na strani predmeta, u delu `Materijal sa Teams-a`.
- 268 [novo] **Mejlovi sa predmeta Uvod u pumpe i ventilatore** su objave tog predmeta, sa prilozima (termini,
  rezultati, materijali), a odgovor na mejl je odgovor u objavi. Predmet Pumpe i ventilatori na OAS MI se sad zove
  Uvod u pumpe i ventilatore, kao kod fakulteta; link je isti.
- 264–265 [novo] **Obaveštenja sa sajtova katedri su objave,** sa oznakom sajta (`ie`, `fluidi`, `meh`…), na strani
  svog predmeta ili katedre, i stižu kao obaveštenja, kao ona sa cent-a. Materijal sa ie (`Literatura`) je na strani
  predmeta, kao spisak fajlova. Arhiva strana svakog sajta je sklonjena sa strane Linkovi.
- 256, 258–261 [novo] **Moji predmeti imaju svoju stranu,** do koje vodi `Obaveštenja` u side panelu. Prvo izabereš
  predmete, pa uključiš obaveštenja i izabereš od kojih nastavnika stižu; bez izbora stižu sve objave predmeta.
  Pretraga nalazi predmet po imenu, skraćenici ili nastavniku i ostaje u izabranom smeru, a godine se ne kriju kad
  izabereš smer. Tu je i RSS izabranih predmeta za čitač (OPML).
- 263 [ispravka] **Kad isključiš `Samo moji predmeti`,** početna je opet kao bez izabranih predmeta. Na telefonu
  dugmići na dnu strane Moji predmeti više ne pokrivaju pola spiska.
- 277 **Original je dugme** ispod posta, pored `Sve objave`, sa imenom sajta na kom je objavljen (`Original na
  ie.mas.bg.ac.rs`), umesto malog linka pored datuma.
- 280, 282–284, 286–287 [novo] **Izdvojeno na strani Linkovi:** Veliki drajv, studenti.mas i Mašinci na vrhu, kao
  kartice sa slikom, a ispod njih Predmeti, studentski webmail i Knjiga utisaka. Tu su i studentske organizacije
  (Drumska strela, Beoavia, Robotoid), u delu `Studenti`, i Biblioteka fakulteta.
- 251, 253 [novo] **Svaki smer ima svoju ikonicu** na početnoj i na strani smera, umesto fascikle.
- 254 **Filter po godinama** se ne vidi ispod objave i vesti, gde je samo smetao.
- 255, 257 **Strana O sajtu je u izradi,** pa je link ka njoj sklonjen ispod pretrage, kao i hint za prečice na
  tastaturi.
- 243–244 [novo] **Sajtovi katedri** (ie, etc, motori, meh, bmi, pt, ppm, fluidi, hidro i ciah) se čuvaju ovde,
  strana po strana, sa ranijim verzijama, kao cent. Spisak strana svakog sajta je na strani Linkovi, u delu
  `Arhiva sajtova katedri`. Strana koja pripada predmetu je i na strani predmeta, označena imenom sajta.
- 242, 245–246 **Sajtovi katedri se proveravaju pri svakom osvežavanju sajta,** kao cent, pa materijal predmeta
  prati njegove objave. Strane koje traže login (studentski wiki katedre pt) se ne čuvaju.
- 235 [ispravka] **Strane sa cent-a zadržavaju svoj izgled,** u stilu ovog sajta: nedelje se sklapaju, dugmići
  su opet dugmići a ne običan tekst, a link na fajl pokazuje vrstu fajla. Dugme koje ni na cent-u ne radi ima
  isprekidanu ivicu. Kopije starog TMO template-a, koje cent drži na stranama mnogih predmeta, su sklonjene, pa ti
  predmeti više ne pokazuju tuđi sadržaj.
- 236–237, 239 [novo] **Svaki predmet ima svoju stranu,** i kad nema objava: umesto praznog spiska tu je kartica
  sa jednom rečenicom (`Tih kao miš...`). Na strani smera su predmeti bez objava na dnu, u svom spisku.
- 240 [ispravka] **Filter na strani smera** pretražuje i opšta obaveštenja smera, a spisak bez rezultata se
  sakrije zajedno sa naslovom.
- 241 [novo] **Svetozar Zorić, Vladimir Farmakovski i Nikola Obradović** imaju i istorijat katedre hidro među
  izvorima.
- 238, 248 **Ikonica objave sa odgovorima** više nije u tamnom krugu, a oznaka sa kog je sajta nešto (`cent`) ima
  oštrije uglove.
- 247, 249–250, 252, 262, 266–267, 274–276, 278–279, 281, 285, 293–297 **Održavanje:** plan za Android aplikaciju, dnevnik osvežavanja sajta,
  ispravke deploy-a i rezervna kopija fajlova sa sajtova katedri.

## 10. novembra 2026.
Strana Linkovi, novi font, oblak reči i broj posetilaca na statistici, strana Verzije i dosta popravki za
  telefon, iPhone i Safari.

### Novo na sajtu
- 189 [novo] **Strana Verzije.** Šta se menjalo na sajtu, po danima i po verzijama, od najnovijeg.
- 211, 213–214, 218, 221 [novo] **Strana Linkovi** (/link/): sajtovi fakulteta, katedri i studenata na jednom
  mestu, kao kartice sa ikonicom svakog sajta. Sajt koji ne radi ima oznaku `ne radi`. Na telefonu su Linkovi u
  donjem meniju, na mestu Predmeta.
- 227 [novo] **Novi font na celom sajtu:** `IBM Plex Sans`, a za username-ove i prečice sa tastature `IBM Plex Mono`.
- 187–188, 191, 197–198 [novo] **Oblak reči na statistici:** 60 reči koje se najčešće javljaju u postovima, a
  svaka vodi na pretragu te reči. Najčešća je u sredini i najveća, a ostale su oko nje. Padeži iste reči se broje
  zajedno (ispit, ispita, ispitu).
- 193–194 [novo] **Broj posetilaca na statistici.** Sajt zato pamti IP adresu tri dana, da istog posetioca ne
  broji dvaput, pa je briše; to piše i na strani O sajtu.
- 203–205, 207 **Sajt se osvežava pet puta dnevno** u prijavama ispita i ispitnim rokovima, na svakih pet
  sati od 6:52 do 2:52, a ostalih dana tri puta: u 11:52, 16:52 i 21:52 (leti sat kasnije).
- 202 **`Provereno` u footer-u** je vreme kada je sajt poslednji put proverio forum, i kad nije bilo novih objava.
- 185 [novo] **Svaki deo sajta ima svoj preview** kad pošalješ link: forum, raspored, nastavnici, arhiva, predmeti
  i vesti.
- 212 [novo] **Sajt radi i bez JavaScript-a:** ono što bez njega ne radi (pretraga, filteri, dugmad za pismo i
  temu) je sakriveno, a sve što se sklapa je otvoreno.

### Predmeti
- 183–184 [novo] **Nastavni planovi na strani Predmeti su pregledniji.** Svaki program se sklapa (prvi je otvoren),
  semestar je jedan blok, a izborni predmeti su u obojenim trakama. Dugačak izborni blok pokazuje prvih pet, a
  ostale posle `Prikaži još`.
- 201 [novo] **Strana predmeta iz Knjige predmeta je u karticama:** cilj, ishod, sadržaj predavanja i vežbi kao
  spisak po lekcijama, fond časova i poeni kao trake, a literatura kao spisak knjiga.
- 195 [novo] **Predmet možeš da nađeš i po skraćenici** (`OOK`, `ME1`, `BMIO`): u pretrazi, u izboru predmeta i na
  spiskovima.
- 196 [novo] **Enter na filtriranom spisku** otvara predmet kad je na spisku ostao samo on.
- 229, 232 [novo] **Svaki predmet na forumu ima ikonicu svoje katedre,** i kad je Knjiga predmeta ne navodi: po
  nosiocu ili nastavnicima predmeta. Katedre i moduli imaju svoje ikonice.
- 210 **Smerovi na početnoj su sortirani** po nivou studija: osnovne, master i doktorske, pa katedre i moduli.

### Nastavnici
- 179 **Na strani nastavnika je deset najnovijih postova,** a ostali su ispod dugmeta `Prikaži još`.
- 180, 225 **Filteri na spiskovima nastavnika i predmeta** su u jednom redu, kao dugmad, a broj rezultata je
  desno.
- 181–182 **Arhiva nastavnika je plavo dugme sa brojem.** Kartica nastavnika uvek pokazuje kabinet, a broj
  postova samo kad je spisak sortiran po njemu.
- 178 **Kod bivših nastavnika piše samo godina odlaska,** jer je tačan datum samo datum kopije sa Wayback Machine-a.
- 192 [ispravka] **Nastavnik koga nema na spisku nastavnika, a ima ga na spisku katedre** (asistent koji je sada
  istraživač) više nije među bivšima.

### Telefon, iPhone i Safari
- 200 [ispravka] **Safari i iPhone:** filteri i pretraga rade i u starijem Safariju, sajt radi na iOS 16 (u svetloj
  temi), u landscape-u ništa nije ispod notch-a, a otvaranje grupe ne seče ivice kartica.
- 222, 228 [ispravka] **Promena teme na iPhone-u** ima animaciju kruga kao na računaru, umesto da strana odmah
  potamni.
- 206, 208 **Na telefonu su imena smerova kraća** (`Основне академске студије - МИ`), pa su i redovi niži.
- 219, 223–224, 230 **Pretraga na telefonu:** tekst u polju je manji, pa staje, iPhone ne zumira kad dodirneš
  polje, a meni pored pretrage piše celo ime i ima veće redove za prst.
- 231, 233 [ispravka] **Moji predmeti na telefonu:** naslov i dugme su u jednom redu, i u Safariju.
- 234 **Na telefonu objava bez odgovora** ne piše `0 odgovora`, a objava sa cent-a ima oznaku `cent`.

### Izgled
- 177, 199, 209 **Potpis u footer-u prati pismo:** latinicom `valjdakosta`, ćirilicom `Временска Прогноза`. Talas
  ide ravnomerno preko razmaka i ne preskače kad promeniš pismo.
- 174 [ispravka] **Posle izmene sajta browser odmah uzima nove stilove i skripte**, umesto stare verzije iz keša.
- 176 [ispravka] **Animacije:** na telefonu kartica više ne ostaje podignuta posle dodira, kvačica u izboru
  predmeta iskače samo na kartici koju si izabrao, a brzo menjanje teme se više ne zaglavi. Pozadina iza popup-a
  se pojavljuje postepeno, a više dugmadi reaguje na pritisak.
- 173 [ispravka] **Strana sa sajta predmeta koja nestane pa se vrati** više nije označena kao uklonjena.
- 186 [ispravka] **Tekst u meniju pored pretrage** je centriran po visini.

- 175, 190, 215–217, 220, 226 **Održavanje:** beleške u planu, ova strana prepravljena prema stvarnim izmenama u
  kodu, i skriveni meni za probu fontova, u kom je izabran novi font.

## 9. novembra 2026.
Najveći dan do sad: obaveštenja na telefon, vesti fakulteta, sajtovi predmeta, strana O sajtu i arhiva bivših
  nastavnika sa fotografijama i biografijama.

### Novo na sajtu
- 57 [novo] **Obaveštenja o novim objavama** na telefon i računar, za predmete koje pratiš: prekidač je u delu
  Moji predmeti. Tu je i link koji daje `RSS` svih praćenih predmeta u jednom fajlu (`OPML`), za čitač.
- 62–63 [novo] **Vesti fakulteta** (/vesti/): svaka godina na svojoj strani, filter po kategoriji, svaka vest na svojoj strani.
  Pet najnovijih je na početnoj, a imaju i svoj `RSS` i svoje mesto u pretrazi.
- 80–81, 83 [novo] **Sajtovi predmeta** sa cent.mas.bg.ac.rs (Katedra za proizvodno mašinstvo) su sada ovde.
  Njihova obaveštenja su među objavama predmeta, označena sa `cent`, a strane (predavanja, rezultati) su na strani
  predmeta, sa ranijim verzijama. Ono što cent isprazni ili izmeni ovde ostaje u poslednjem obliku. Predmet bez
  foruma sada ima svoju stranu, sa linkom na sajt predmeta.
- 100–101, 103 [novo] **Strana O sajtu:** šta je ovo, odakle su podaci, šta ovde ne može da stigne i kako da
  tražiš da nešto uklonim.
- 61, 151, 155 [novo] **Sajt se sam osvežava sa foruma** tri puta dnevno. Kalendar nastave određuje šta se još
  proverava: u prijavama ispita i ispitnim rokovima više, rasporedi jednom mesečno, nastavnici i predmeti jednom godišnje.
- 59 **Sajt je na adresi nastava.masinci.org.**

### Pretraga
- 56 [brže] **Pretraga je brža,** a objava se u rezultatima pojavljuje jednom, sa linkom `+ još N postova iz ove
  objave`. Dok ništa ne kucaš, red pokazuje početak teksta. Uz to i `RSS` za ceo forum i za svaki predmet.
- 60, 64–65 [novo] **Biraš šta pretražuješ:** sve, postove, nastavnike ili predmete, u meniju pored polja. Kad je
  izabrano sve, ispod polja se dok kucaš pojave predmeti, nastavnici i stavke rasporeda (kalendar, sale, ispiti).
- 66 [novo] **Na ostalim stranama, dok kucaš,** ispod polja se pojavi pet najboljih rezultata iz postova i vesti,
  sa linkom na sve rezultate.
- 152 [novo] **Nastavnici u pretrazi imaju fotografiju,** zvanje i katedru. Bivši su posle sadašnjih, a i katedre
  su među rezultatima, sa linkom na svoje nastavnike.
- 169 **Na telefonu je tekst u polju za pretragu kraći**, pa staje.
- [ispravka] **Odlomci u rezultatima** su na srpskom (`preuzeto 5 puta`) i ne lome se na kraju teksta. Prazne
  tabele su sklonjene sa strane sa ispitima.
- 97–98 [ispravka] **Kad pretraga ne može da se učita,** kaže zašto, običnim rečima: nema interneta, nema indeksa ili
  greška na serveru.

### Predmeti
- 54 [novo] **Samo moji predmeti:** prekidač u bočnom meniju koji na celom sajtu prikazuje samo predmete koje pratiš,
  i pretraga ga prati. Reči su ujednačene: tema sa foruma je **objava**, jedna poruka u njoj **post**.
- 84–85, 105–106, 114–116, 150 [novo] **Gde je još materijal:** predmet pokazuje gde se materijal deli i van
  foruma (`Teams`, `Classroom`, `Google Drive`, `OneDrive`, `Moodle`, `YouTube`, sajt katedre) i ko ga tu deli, po
  linkovima iz postova. Računaju se samo prava mesta: folder, plejlista ili više linkova, a ne Google Form ili jedan
  Teams meeting. Na strani nastavnika su oznake za njegove linkove.
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
- 67–69, 71–72, 75–76, 88–93, 95, 129, 168, 170 [novo] **Footer** u boji header-a: link na stranu fakulteta
  koju ova strana kopira, `RSS`, `Prijavi grešku`, vreme poslednje provere i potpis koji talasa. Na telefonu su
  linkovi u dve kolone.
- 77–79 [novo] **Animacije:** dugmad reaguju na pritisak, popup-ovi se gase postepeno, zvezdica iskoči kad
  zapratiš predmet, a tema se menja krugom koji prelazi preko strane.
- 94, 96 **Početna** nema naslov, a red sa brojevima nema duple linkove.
- 102, 104, 117, 123 [novo] **Podeljen link ima sliku i opis** (Viber, Discord), latinicom. Google dobija
  sitemap i breadcrumbs. Postovi se ne indeksiraju, jer sadrže imena studenata.
- 166 [ispravka] **Između dve strane nema flešovanja.**
- 128 [ispravka] **Povratak putanjom na vrhu strane** vraća na mesto gde si stao.

- 55, 58, 70, 73–74, 82, 99, 124 **Održavanje:** planovi za sledeće delove, licenca (GPL v3) i podešavanja servera.

## 8. novembra 2026.
Prvi dan: arhiva foruma je na internetu, sa novim izgledom, stranama nastavnika, Knjigom predmeta i rasporedom.

- 1 [novo] **Arhiva foruma nastave.** Sve objave sa foruma od 2014, sa pretragom ćirilicom i latinicom.
- 2–5 [novo] **Novi izgled:** plavi header sa talasom u logu, svetla i tamna tema na jedno dugme, novi font i
  mekša crvena. Forum i predmeti su tabele kao na forumu, objava ima dugmad `Preuzmi` i `Cela tema`, a filteri
  pretrage u bočnom meniju deluju čim ih promeniš.
- 10–11 **Sve je gušće, složeno kao na forumu:** manji tekst, tešnji redovi, oštriji uglovi. Početna nema uvodni
  tekst.
- 12 [novo] **Čitljive adrese:** predmeti, smerovi i nastavnici imaju adresu po imenu, kao
  /nastavnik/dusan-lj-djukic/.
- 13–14, 17, 19, 22–23 [novo] **Nastavnici:** spisak kartica sa fotografijom, zvanjem, katedrom i kabinetom, sa
  filterima i sortiranjem po zvanju. Strana nastavnika ima traku sa podacima i predmetima (prvo oni sa objavama na
  forumu), njegove postove po godinama i ceo profil sa sajta fakulteta. Imena su bez srednjeg slova.
- 15–16 **Delovi sajta su na vrhu bočnog menija,** sa označenim delom u kom si, a header je niži.
- 18 [novo] **Knjiga predmeta** (/predmeti/): svi predmeti sa pretragom i filterima po programu i katedri, i
  strana svakog predmeta sa opisom fakulteta. Nastavnici se mogu grupisati i sortirati.
- 30 [novo] **Praćenje predmeta:** najnovije objave praćenih predmeta su na početnoj. Post vodi na prethodni i
  sledeći u objavi, a stare verzije rasporeda imaju svoje strane.
- 31, 33, 47–48 [novo] **Biranje predmeta:** popup sa programima, godinama i izbornim blokovima. Izbor programa
  ili godine sužava spisak, a bez izbora su svi predmeti po imenu.
- 32 [novo] **Pretraga u header-u zna gde si:** na spisku nastavnika ili predmeta filtrira taj spisak, a na
  strani nastavnika traži nastavnike.
- 34, 44, 46 [novo] **Telefon:** donji meni i header u jednom redu. Pismo je samo latinica ili
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
  i temu rade i kad browser ne dozvoli čuvanje podešavanja.
- 20 [ispravka] **Filteri u adresi su latinicom,** pa se link sa filterom deli bez čudnih znakova.
- 26 [ispravka] **Kad pretraga ne može da se učita,** piše `Pretraga trenutno nije dostupna` umesto da večno traži.
- 42, 50–52 [ispravka] **Tamna tema:** jedna ista crvena, bolji kontrast, a polje za pretragu se ističe. Traka sa
  kalendarom više ne pocrveni pod mišem.
- 7–8, 21, 24–25, 27–29, 35, 37, 39, 41 **Održavanje:** sajt se pravi na mom računaru i odatle objavljuje, strane
  se čuvaju kao delovi koje server spaja, i alati za lokalni server i čuvanje.
