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
- Short: an entry is one or two short sentences, and so is a day's lead. No semicolons, and no long lists strung
  together with commas: name the main thing and leave the rest out.

## 16. novembra 2026.
Rasporedi imaju preview.

- 687–689 [novo] **Kalendar i rasporedi osnovnih studija** imaju preview prve strane.
- 690 **Kalendar profesora dana** počinje od današnjeg dana.
- 692 **Logo** se crta do kraja i kad ga ponovo dodirneš. Ime sajta na telefonu stoji 3 sekunde od prvog dodira.
- 693 **Profesor dana** se na telefonu ne prikazuje uz postove i liste threadova.
- 691 **Održavanje:** ova strana.

### Aplikacija za Android
- 700, 714, 719 [novo] **Sajt ima aplikaciju za Android.** U browseru na Android telefonu dugme
  `Skini aplikaciju` je u side panelu i u traci na dnu.
- 705–706 [novo] **Obaveštenja stižu i u aplikaciju**, kao u browseru.
- 702–703, 710 **Aplikacija se otvara uz logo koji se crta**, a header ne ide ispod status bar-a.
- 715, 718, 754 [novo] **Bez interneta** aplikacija kaže da sajt nije dostupan. `Pokušaj ponovo` učita baš stranu
  koja nije uspela.
- 730 [brže] **Animacije u aplikaciji** su glatkije na telefonima od 120 Hz.
- 760, 765 [novo] **Aplikacija sama proverava da li ima nova verzija** i skida je dugmetom `Skini noviju verziju`.
  U Android browseru `Skini aplikaciju` je i u traci na dnu.

### Sajt
- 728, 757 [novo] **PDF-ovi se otvaraju na samom sajtu**, u browseru i u aplikaciji. Back ga zatvara.
- 729, 735 [ispravka] **`Samo moji` na početnoj** pokazuje samo postove nastavnika koje si izabrao za predmet.
  Obaveštenja takođe. Kad pređeš mišem preko posta, tačka nestane.
- 732–734 [brže] **Sajt se brže učitava** jer browser duže čuva njegove fajlove.
- 722 [brže] **Slike nastavnika** su manje, pa se brže učitavaju.
- 720 **Traka predmeta** ide preko cele širine strane.
- 766 **Na telefonu nema linka za nazad** iznad naslova strane. Nazad vodi Back telefona.
- 767 [ispravka] **Dugačko ime nastavnika** na telefonu više ne ide preko ikonice katedre.
- 768 [novo] **Na iPhone-u** traka na dnu objašnjava kako da dodaš sajt na početni ekran, da bi obaveštenja stizala.
  PDF se otvara uz kratku animaciju, a red koji dodirneš odmah promeni boju.
- 697 **Ikonice na karticama katedri** su na sredini.
- 738–740 [ispravka] **Sitne greške:** naslovi listi se menjaju sa pismom, a `Predaju` na strani predmeta opet nalazi
  nastavnike.
- 741–742 [ispravka] **Imena studenata u tabelama** sa Teams-a se bolje zatamne.
- 743–744, 751–752 [ispravka] **Obaveštenja sa sajtova katedri** se više ne propuštaju.
- 748–749, 753 [ispravka] **Dva odgovora iz iste sekunde** imaju svaki svoj link. Naslovi vesti nemaju višak razmaka.
- 694–696, 698–699, 701, 704, 707–709, 711–713, 716–717, 721, 723–727, 731, 736–737, 745–747, 750, 755–756, 758–759,
  761–764 **Održavanje:** plan aplikacije, testovi i scraperi, ova strana.

## 15. novembra 2026.
Profesori emeritusi su u arhivi.

- 584 [novo] **Strana Katedre** pokazuje sve katedre na jednom mestu. U side panelu je sad `Katedre i predmeti`.
- 577, 579 [novo] **Profesori emeritusi su u arhivi** jer više ne predaju. Uz svakog piše kad je došao i kad je
  otišao u penziju.
- **Svi nastavnici imaju godinu od kad su na fakultetu.** Znak `~` znači procenu.
- 575–576, 598 [novo] **Oznaka „Studenti pobeđuju“** stoji uz nastavnike sa Studentske liste.
- 578, 581 **Kartice nastavnika su niže.** Slike nastavnika se pojave postepeno.
- 580, 582–583 [ispravka] **Scrollbar u Firefox-u** više ne prekriva stranu.
- 590–591 [novo] **Strana Privatnost** kaže kratko šta sajt čuva o tebi.
- 586–589, 600 **Verzije se sad zovu Šta je novo.** Uz svaki dan piše njegova poslednja verzija.
- 592, 594–597 **Footer je kraći.** Ima linkove na Šta je novo i `Piši mi :)`.
- 601–603 **Oznaka „Studenti pobeđuju“** je jača i stoji u uglu kartice. Na telefonu je ispod ikonice katedre.
- 604 **Obaveštenja u side panelu** zauzimaju manje mesta na desktopu.
- 606 **Sajt se lakše nalazi na Google-u.** Naslov taba je sad uvek latinicom.
- 605 [ispravka] **`www.masinci.org`** sad vodi na sajt.
- 608 [novo] **Novi postovi od tvoje poslednje posete** imaju crvenu tačku.
- [novo] **Tačna pretraga:** reč u navodnicima, npr. `"ispit"`, ne nalazi `ispita`. Radi i za ceo izraz.
- [novo] **Pretraga daje primere** čim klikneš na nju.
- [novo] **Dugme Podeli** stoji ispod posta i threada.
- **Strana koja ne postoji** nudi pretragu po rečima iz linka.
- 649–651 [novo] **Profesor dana** u side panelu: svaki dan drugi nastavnik, sa slikom i katedrom.
- 615 [novo] **Pretraga pokazuje i ko predaje** predmete koje si našao. Skraćenice kao `TMO` ili `ME1` traže ceo
  naziv predmeta.
- 611 [novo] **Obaveštenja i vesti idu po godinama** i po stranama. Biraš koliko ih ima na jednoj strani.
- [novo] **Obaveštenja smera** koja nisu ni za jedan predmet stoje na strani smera.
- [novo] **Upis na Studijama** ima kratak pregled iznad svakog taba.
- 634 [novo] **Link Nazad** ispod putanje vodi na stranu sa koje si došao.
- **Na telefonu,** scroll strane zatvara pretragu i tastaturu.
- 613–614 [ispravka] **Prekidač za obaveštenja** radi i kad brzo klikćeš. Broj prijavljenih browsera je sad tačan.
- 622, 625, 627–628, 633, 635–637, 642 **Biografije nastavnika su prepisane i proverene.** Stigla je i jedna nova slika.
- 624 **Puno ime nastavnika,** sa oba prezimena, stoji na kartici i na strani nastavnika.
- 626, 629, 631 [ispravka] **Dva nastavnika upisana dvaput** sad imaju po jednu stranu. Stari link vodi na novu.
- 623 **Brojevi telefona nastavnika** su skinuti sa sajta.
- 638, 641, 645–646 **Rezultati u prilozima** su bez imena i indeksa studenata. Bodovi i ocene su ostali.
- 656 [ispravka] **Siva silueta sa sajta fakulteta** se više ne prikazuje kao slika nastavnika.
- 647 **Strana nastavnika bez predmeta** nema praznu kolonu.
- 655 **Liste na početnoj** imaju link na celu listu.
- 652–654 **Dugme `Izaberi predmete`** je crveno.
- 657, 659 [novo] **Logo** se ponovo nacrta kad klikneš na njega.
- 663–669 **Profesor dana** bira i profesore emerituse, one koji su otišli posle 2024. i tri profesora iz prvih
  godina fakulteta.
- 670 [novo] **Na rođendan profesora Ognjanovića,** 23. oktobra, on je profesor dana.
- 671–674 [novo] **Kalendar profesora dana:** klik na naslov kartice pokazuje ko je bio profesor dana svakog dana.
- 675–676 [ispravka] **Godine na fakultetu** su tačne za još 140 nastavnika, po njihovim biografijama.
- 677 **Nastavnici bez slike** imaju siluetu umesto inicijala.
- 679 [novo] **Crvena tačka nestaje** kad otvoriš post. Dok su na početnoj samo Moji predmeti, tačka stoji samo uz
  tvoje predmete.
- 680 [novo] **Dugme Pročitano** skida sve crvene tačke odjednom.
- 681, 683 [novo] **Prilozi postova od oktobra su sad na sajtu.** PDF-ovi i slike imaju preview uz post i na strani
  fajla.
- 682 [novo] **Fajlovi sa Teams-a i iz mejlova** isto imaju preview.
- 585, 593, 599, 607, 609–610, 612, 616–621, 630, 632, 639–640, 643–644, 648, 658, 660–662, 678, 684–686 **Održavanje:** ova
  strana.

## 14. novembra 2026.
Arhiva nastavnika ima biografije za skoro sve.

- 541–545, 547–550, 553–562, 564–565, 567–573 [novo] **Skoro svaki nastavnik iz arhive ima kratku biografiju.**
  Dodate su i godine rođenja i nove slike.
- 563, 566 [novo] **Arhiva prati istoriju fakulteta.** Između nastavnika stoje važne godine, od Velike škole 1863.
- 551–552 [novo] **Strane sa sajtova katedri** su na stranama katedri i nastavnika.
- 525, 534 [novo] **Materijal sa Moodle-a** je stigao za dva predmeta.
- 539–540 **Najnoviji threadovi** se menjaju zajedno sa Studijama.
- 538 **`RSS` u prozoru za obaveštenja** se otvara na klik.
- 520 **Strana predmeta** ima link ka svojoj katedri.
- 521 **Moji predmeti** imaju veće ikonice.
- 546 [ispravka] **Stavke sa cent-a bez naslova** su otvorene.
- 518 [brže] **Ćirilica** se primenjuje jednom po strani.
- 498–517, 519, 522–524, 526–533, 535–537, 574 **Održavanje:** kod sajta je podeljen u manje delove.

## 13. novembra 2026.
Novi izgled za Moje predmete. Objave su sad threadovi.

### Moji predmeti i obaveštenja
- 381–382, 386–390, 392–402, 405–407, 411–412, 414–418, 421, 480 **Prekidač `Samo moji predmeti`** stavlja tvoje
  smerove na vrh početne. Ostali se posive.
- 434–438 **Izbor predmeta je lakši.** Prvo biraš program pa predmete.
- 425, 427–428 **Obaveštenja u side panelu** su u jednom redu sa zvoncem.
- 431, 487, 490–491 [novo] **Kad obaveštenja ne rade,** klik na prekidač kaže zašto. Tu je i `RSS` kao zamena.
- 475 [novo] **Statistika** pokazuje koliko je browsera prijavljeno za obaveštenja.

### Ostalo
- 439 **Objava je sad thread** svuda na sajtu.
- 403 [novo] **Strana Threadovi** ima sve threadove po godinama.
- 404, 408 **Thread se otvara na najnovijem postu.**
- 481 [novo] **Spisak threadova** pokazuje koji ima fajl ili link.
- 446–447, 455, 465–467, 477 [novo] **Ceo sajt fakulteta je u Linkovima,** složen po temama.
- 419–420, 423–424, 444, 492 **Sajt se zove `masinci.org`.** Ima i novu favicon.
- 371 **Nove slike** kad pošalješ link.
- 450–454, 468 [novo] **Strana Stil** ima logo i boje sajta.
- 374–380, 383–384 [novo] **Nastavnici imaju kratku biografiju** na svojoj strani.
- 445, 448 **Siva silueta nije slika nastavnika.** Dodato je i 11 novih slika.
- 410, 413 **Neki nastavnici sa dva prezimena** se van svoje strane zovu samo po prvom.
- 462, 464 **`Svi rezultati` u pretrazi** su uvek na dnu.
- 432–433 **Tekst kaže browser i fajl** umesto prevoda.
- 422 [brže] **Talas u footer-u** stoji dok nije na ekranu.
- 372, 409, 426, 429–430, 440–443, 449, 484–486, 493–494 **Sitnice u izgledu.**
- 373, 385, 391, 456–461, 463, 469–474, 476, 478–479, 482–483, 488–489, 495–497 **Održavanje:** sređivanje koda.

## 12. novembra 2026.
Nova adresa masinci.org.

- 299, 315, 317 **Sajt se osvežava pet puta dnevno.** Sad to radi tačno na vreme.
- 301–304 [novo] **Nova adresa je `masinci.org`.** Stare adrese vode na nju.
- 300 [ispravka] **Vreme provere u footer-u** je tačno u svakoj vremenskoj zoni.
- 305 [novo] **Objave iz Teams-a i sa mejla** imaju svoju oznaku.
- 308 [novo] **Predmeti i nastavnici se traže zajedno** u jednom filteru.
- 312 [ispravka] **Filter pretrage na telefonu** zauzima manje mesta.
- 306–307 [novo] **Asistenti sa foruma** imaju svoje strane i kad ih nema na sajtu fakulteta.
- 309 [novo] **Spisak istraživača** koji rade sa našim nastavnicima.
- 310–311, 313–314 [novo] **Najnovije objave su iznad vesti** na početnoj.
- 316 **Održavanje:** ova strana.
- 367 [novo] **Svaka katedra ima svoju stranu** sa nastavnicima i predmetima.
- 368–369 [novo] **Strana nastavnika ima spisak radova.** Prvi nastavnici imaju i kratku biografiju.
- 370 **Predmeti nastavnika na telefonu** pokazuju prvih pet.
- 338 [novo] **Pretraga u header-u radi na svakoj strani.**
- 364–365 **Predmeti u pretrazi imaju ikonicu katedre.**
- 342 [novo] **Najnovije objave** pokazuju samo tvoje predmete kad je uključeno `Samo moji predmeti`.
- 318–323, 325, 327–328, 339–341 **Spiskovi na početnoj** izviruju sa dna ekrana.
- 324, 326 **Scrollbar** menja boju sa temom.
- 343–347, 351 [novo] **Novi logo** po uzoru na znak fakulteta.
- 330–332, 353–356, 358–359, 366 **Nove ikonice katedri.**
- 333–336 [novo] **Istraživači i demonstratori** imaju svoju stranu.
- 329 **Moji predmeti imaju dugme `Poništi izbor`.**
- 337 **Statistika je prešla u footer.**
- 349 [ispravka] **Manje treperenja** kad se strana otvori.
- 363 **Tabovi na Rasporedu** imaju kratka imena.
- 348, 350, 352, 357, 360–362 **Održavanje:** server za pregled izmena.

## 11. novembra 2026.
Sajtovi deset katedri su u arhivi.

- 288 [ispravka] **Pretraga u header-u** više ne prekriva ime sajta u užem prozoru.
- 289 [novo] **Scrollbar je u bojama sajta.**
- 290 [ispravka] **Objave iz Teams-a** više ne pokazuju imena studenata.
- 291 [ispravka] **Obaveštenja sa sajtova katedri ostaju** i kad ih katedra skloni.
- 292 [ispravka] **Dva cent obaveštenja istog naslova** više ne sakrivaju jedno drugo.
- 269–273 [novo] **Objave iz Teams-a** za šest predmeta. Odgovori studenata su bez imena.
- 268 [novo] **Mejlovi predmeta Uvod u pumpe i ventilatore** su sad objave.
- 264–265 [novo] **Obaveštenja sa sajtova katedri** su objave predmeta. Stižu i kao obaveštenja.
- 256, 258–261 [novo] **Moji predmeti imaju svoju stranu.** Tu biraš predmete i uključuješ obaveštenja.
- 263 [ispravka] **Isključen `Samo moji predmeti`** vraća celu početnu.
- 277 **Link na original je dugme** ispod posta.
- 280, 282–284, 286–287 [novo] **Strana Linkovi** ima izdvojene kartice na vrhu.
- 251, 253 [novo] **Svaki smer ima svoju ikonicu.**
- 254 **Filter po godinama** se ne vidi tamo gde smeta.
- 255, 257 **Link na O sajtu je sklonjen** dok je strana u izradi.
- 243–244 [novo] **Sajtovi katedri se čuvaju ovde** sa ranijim verzijama.
- 242, 245–246 **Sajtovi katedri se proveravaju** pri svakom osvežavanju.
- 235 [ispravka] **Strane sa cent-a** izgledaju kao na cent-u.
- 236–237, 239 [novo] **Svaki predmet ima svoju stranu** i kad nema objava.
- 240 [ispravka] **Filter na strani smera** traži i opšta obaveštenja.
- 241 [novo] **Istorijat katedre hidro** je među izvorima za tri nastavnika.
- 238, 248 **Ikonice objava** su jednostavnije.
- 247, 249–250, 252, 262, 266–267, 274–276, 278–279, 281, 285, 293–298 **Održavanje:** ispravke objavljivanja
  sajta.

## 10. novembra 2026.
Strana Linkovi i novi font.

### Novo na sajtu
- 189 [novo] **Strana Verzije** pokazuje šta se menjalo na sajtu.
- 211, 213–214, 218, 221 [novo] **Strana Linkovi** ima sajtove fakulteta i studenata na jednom mestu.
- 227 [novo] **Novi font** je `IBM Plex Sans`.
- 187–188, 191, 197–198 [novo] **Oblak reči na statistici** pokazuje najčešće reči sa foruma.
- 193–194 [novo] **Statistika broji posetioce.** IP adresa se čuva tri dana pa se briše.
- 203–205, 207 **Sajt se osvežava češće** u ispitnim rokovima.
- 202 **`Provereno` u footer-u** je vreme poslednje provere foruma.
- 185 [novo] **Svaki deo sajta ima svoj preview** kad pošalješ link.
- 212 [novo] **Sajt radi i bez JavaScript-a.**

### Predmeti
- 183–184 [novo] **Nastavni planovi su pregledniji.** Svaki program se sklapa.
- 201 [novo] **Strana predmeta** ima opis iz Knjige predmeta u karticama.
- 195 [novo] **Predmet se nalazi i po skraćenici** kao `OOK`.
- 196 [novo] **Enter otvara predmet** kad je jedini na spisku.
- 229, 232 [novo] **Svaki predmet ima ikonicu svoje katedre.**
- 210 **Smerovi na početnoj** idu po nivou studija.

### Nastavnici
- 179 **Strana nastavnika** pokazuje deset najnovijih postova.
- 180, 225 **Filteri na spiskovima** su u jednom redu.
- 181–182 **Arhiva nastavnika** je dugme sa brojem.
- 178 **Kod bivših nastavnika piše samo godina odlaska.**
- 192 [ispravka] **Asistent koji je sad istraživač** više nije među bivšima.

### Telefon, iPhone i Safari
- 200 [ispravka] **Sajt radi u starijem Safariju** i na iOS 16.
- 222, 228 [ispravka] **Promena teme na iPhone-u** ima animaciju.
- 206, 208 **Imena smerova na telefonu** su kraća.
- 219, 223–224, 230 **Pretraga na telefonu** staje u ekran. iPhone ne zumira kad je dodirneš.
- 231, 233 [ispravka] **Moji predmeti na telefonu** imaju naslov i dugme u jednom redu.
- 234 **Objava bez odgovora** ne piše `0 odgovora`.

### Izgled
- 177, 199, 209 **Potpis u footer-u** prati pismo.
- 174 [ispravka] **Browser odmah uzima novu verziju sajta.**
- 176 [ispravka] **Animacije su popravljene** na telefonu.
- 173 [ispravka] **Strana koja nestane pa se vrati** nije više označena kao uklonjena.
- 186 [ispravka] **Tekst u meniju pretrage** je centriran.

- 175, 190, 215–217, 220, 226 **Održavanje:** plan i ova strana.

## 9. novembra 2026.
Obaveštenja na telefon i vesti fakulteta.

### Novo na sajtu
- 57 [novo] **Obaveštenja o novim objavama** stižu na telefon i računar.
- 62–63 [novo] **Vesti fakulteta** imaju svoju stranu.
- 80–81, 83 [novo] **Sajtovi predmeta sa cent-a** su sad ovde.
- 100–101, 103 [novo] **Strana O sajtu** kaže šta je ovo i odakle su podaci.
- 61, 151, 155 [novo] **Sajt se sam osvežava** tri puta dnevno.
- 59 **Sajt je na adresi nastava.masinci.org.**

### Pretraga
- 56 [brže] **Pretraga je brža.** Objava se u rezultatima javlja jednom.
- 60, 64–65 [novo] **Biraš šta pretražuješ** u meniju pored polja.
- 66 [novo] **Dok kucaš,** ispod polja se pojave najbolji rezultati.
- 152 [novo] **Nastavnici u pretrazi** imaju fotografiju.
- 169 **Tekst u polju za pretragu** staje na telefon.
- [ispravka] **Odlomci u rezultatima** su na srpskom.
- 97–98 [ispravka] **Kad pretraga ne radi,** kaže zašto.

### Predmeti
- 54 [novo] **Prekidač `Samo moji predmeti`** pokazuje samo predmete koje pratiš.
- 84–85, 105–106, 114–116, 150 [novo] **Predmet pokazuje gde se još deli materijal.**
- 87 [novo] **Spisak predmeta** ima i ESPB.
- 162 **Smerovi su ispisani celim imenom.**
- 125 [ispravka] **Završni predmet** je naveden po oblasti.
- 86 [ispravka] **Objava koja nestane sa foruma** ovde ostaje.

### Nastavnici
- 118–120, 126–127, 134, 146–149, 163, 171–172 [novo] **Arhiva nastavnika** ima one koji više nisu na fakultetu.
- 130 [novo] **Biografija iz monografije fakulteta** je na strani nastavnika.
- **Fotografije nastavnika se čuvaju ovde.**
- 110–113, 121–122, 165, 167 [novo] **Kartica bivšeg nastavnika** ima sivi ugao.
- 131–133, 135–145, 153–154, 156–161, 164 [novo] **Svaka katedra ima svoju ikonicu.**
- 107–109 [ispravka] **Kabinet je onaj sa sajta fakulteta.**

### Izgled
- 67–69, 71–72, 75–76, 88–93, 95, 129, 168, 170 [novo] **Footer** je u boji header-a.
- 77–79 [novo] **Dugmad i popup-ovi** imaju animacije.
- 94, 96 **Početna** nema naslov.
- 102, 104, 117, 123 [novo] **Podeljen link ima sliku i opis.**
- 166 [ispravka] **Između dve strane nema flešovanja.**
- 128 [ispravka] **Povratak putanjom** vraća na mesto gde si stao.

- 55, 58, 70, 73–74, 82, 99, 124 **Održavanje:** planovi i licenca.

## 8. novembra 2026.
Prvi dan: arhiva foruma je na internetu.

- 1 [novo] **Arhiva foruma nastave** sa svim objavama od 2014.
- 2–5 [novo] **Novi izgled** sa svetlom i tamnom temom.
- 10–11 **Sve je gušće** kao na forumu.
- 12 [novo] **Adrese su čitljive** kao /nastavnik/dusan-lj-djukic/.
- 13–14, 17, 19, 22–23 [novo] **Nastavnici** imaju spisak i svoje strane.
- 15–16 **Delovi sajta** su na vrhu bočnog menija.
- 18 [novo] **Knjiga predmeta** ima sve predmete.
- 30 [novo] **Možeš da pratiš predmete.** Njihove objave su na početnoj.
- 31, 33, 47–48 [novo] **Predmete biraš** po programu i godini.
- 32 [novo] **Pretraga u header-u** zna na kojoj si strani.
- 34, 44, 46 [novo] **Telefon ima donji meni.**
- 38 [novo] **Grupe na spiskovima se sklapaju.**
- 36 [novo] **Raspored** je na jednoj strani.
- 40 [novo] **Prilozi pokazuju vrstu fajla.**
- 43, 45 [novo] **Statistika** pokazuje objave po godinama.
- 49, 53 [novo] **Bivši nastavnici** imaju svoj deo spiska.
- 6 [brže] **Strane objava su manje.**
- 9 [ispravka] **Nastavnik koji ode** zadržava svoju stranu.
- 20 [ispravka] **Filteri u adresi su latinicom.**
- 26 [ispravka] **Kad pretraga ne radi,** to i piše.
- 42, 50–52 [ispravka] **Tamna tema** ima bolji kontrast.
- 7–8, 21, 24–25, 27–29, 35, 37, 39, 41 **Održavanje:** alati za pravljenje sajta.
