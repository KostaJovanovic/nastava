"""Kept by hand: the renamed subjects, the departments' sites and forums, teachers no list has, links."""

import re
from .text import slug


# A board subject under the name the faculty gives it now; its URL keeps the board's name. oas-mi's "Пумпе и
# вентилатори (0442)" is the subject book's "Увод у пумпе и вентилаторе" (1505), which the mails (mail/) name.
RENAMED = {"/predmet/oas-mi/pumpe-i-ventilatori/": "Увод у пумпе и вентилаторе"}

# Where a subject's material is besides the board (a post links it): a service's name and its hosts.
ELSEWHERE = [
    ("Teams", r"^(teams\.microsoft\.com|teams\.live\.com|teams\.cloud\.microsoft)$"),
    ("Classroom", r"^classroom\.google\.com$"),
    ("Google Drive", r"^(drive|docs)\.google\.com$"),
    ("Moodle", r"^elearning\.rcub\.bg\.ac\.rs$"),
    # The faculty's SharePoint only: another one's is a company's (a software download).
    ("OneDrive", r"^(onedrive\.live\.com|1drv\.ms|masbgacrs(-my)?\.sharepoint\.com)$"),
    ("Dropbox", r"(^|\.)dropbox\.com$"),
    ("Box", r"(^|\.)box\.com$"),
    ("YouTube", r"^(www\.|m\.)?(youtube\.com|youtu\.be)$"),
]

FILE_HOSTS = {"Google Drive", "OneDrive", "Dropbox", "Box", "YouTube"}

# A folder, a playlist or a channel on them (a shared OneDrive folder: ':f:').
FOLDER = r"/folders/|/folder/|/sh/|/scl/fo/|/:f:/|/playlist|/channel/|/@|/c/"

# The departments' own sites katedre.py crawls, as the Linkovi page names them.
SITES = {
    "ie": "Katedra za industrijsko inženjerstvo",
    "fluidi": "Katedra za mehaniku fluida",
    "etc": "Prezentacije nastavnika",
    "pt": "Katedra za procesnu tehniku",
    "meh": "Katedra za mehanizaciju",
    "hidro": "Katedra za hidraulične mašine i energetske sisteme",
    "motori": "Katedra za motore",
    "ppm": "Katedra za poljoprivredno mašinstvo",
    "bmi": "Katedra za biomedicinsko inženjerstvo",
    "ciah": "Laboratorija CIAH",
}

# A department site's name for a subject the board and the book name otherwise (ie shortens some): the book's name,
# and the smer when the name is in several (ie's "Inženjerska ekonomija" is ITM's; MI has one too).
SITE_NAMES = {
    "strucna praksa b iie": ("Стручна пракса Б", None),
    "menadzment informacionih sistema": ("Менаџмент информациони системи", None),
    "primena metoda i tehnika ie u brodogradnji": ("Примена метода и техника индустријског инжењерства у бродоградњи", None),
    "savremeni menadz. i mrezna org. preduzeca": ("Савремени менаџмент и мрежна организација предузећа", None),
    "interfejsi za interoperabilnost sistema za i4.0": ("Интерфејси за интероперабилност система за Индустрију 4.0", None),
    "upravljanje kvalitetom i rizikom u i4.0": ("Управљање квалитетом и ризиком у индустрији 4.0", None),
    "vrednovanje projekata u oblasti it": ("Вредновање пројеката у области информационих технологија", None),
    "inzenjerska ekonomija": ("Инжењерска економија", "oas-itm"),
}

# A department site's forum on the board (smer "Katedre"): its notices that are no subject's. Made when the board has
# none (bmi, ciah).
FORUMS = {
    "ie": "катедра за индустријско инжењерство",
    "meh": "катедра за механизацију",
    "pt": "катедра за процесну технику",
    "hidro": "катедра за хидрауличне машине и енергетске системе",
    "fluidi": "катедра за механику флуида",
    "bmi": "катедра за биомедицинско инжењерство",
    "ciah": "лабораторија ЦИАХ",
}

# The sites whose pages are each a subject's (ie's subject pages, fluidi's); the others' are the department's.
SUBJECT_PAGE = re.compile(r"ie\.mas\.bg\.ac\.rs/predmeti_p|fluidi\.mas\.bg\.ac\.rs/[a-z]+/$")

# The posts not from the board or a department's site: their tag (style.css .src--<mark>) and its title.
VIA = {"teams": dict(mark="teams", name="Sa Microsoft Teams-a"), "moodle": dict(mark="moodle", name="Sa Moodle-a"),
       "webmail": dict(mark="webmail", name="Mejl studentima")}

# A subject page without posts (predmet.html): one of these, in place of the empty list.
QUIET = [
    "Ćuti kao zaliven...",
    "Tih kao miš...",
    "Mačka mu pojela jezik?",
    "Ni muk da se čuje...",
    "Nema žive duše.",
    "Ni traga, ni glasa...",
    "Niko ni da pisne",
    "Ćuti kao kamen.",
]

# Linkovi's cards (link.html), also found by the header search (izbor.json linkovi): (group, [(name, href, icon from
# icons.svg, data-domain)]). An href "mf:<path>" is a page of www.mas.bg.ac.rs this site shows (studije.py SHOWN).
LINKS = [
    (
        "Fakultet",
        [
            ("Forum nastave", "https://nastava.mas.bg.ac.rs/nastava/", "msgs", None),
            ("studenti.mas", "https://studenti.mas.bg.ac.rs/", "user", None),
            ("Studentski webmail", "https://webmail.studenti.mas.bg.ac.rs/", "mail", None),
            ("Mašinski fakultet", "https://www.mas.bg.ac.rs/", "globe", None),
            ("Vesti o predmetima", "https://www.mas.bg.ac.rs/studije/vesti", "news", None),
            ("Raspored ispita", "https://www.mas.bg.ac.rs/studije/raspored-ispita", "calendar", None),
            ("Vesti fakulteta", "https://vesti.mas.bg.ac.rs/", "news", None),
            ("Prezentacije nastavnika", "https://etc.mas.bg.ac.rs/", "file", None),
            ("FSEL (Moodle)", "https://fsel.mas.bg.ac.rs/moodle/", "book", None),
            ("Biblioteka", "https://www.mas.bg.ac.rs/biblioteka/start", "book", None),
        ],
    ),
    # Only what no other of these pages links: Upis has OAS, MAS, DAS and the higher years as tabs, each with its
    # dates; the higher years' page links the choice of subjects, the fees, the payments and the student e-mail.
    (
        "Upis i studiranje",
        [
            ("Upis i obnova godine", "mf:upis/start", "enter", None),
            ("Prijava ispita", "mf:studenti/prijava-ispita", "calendar", None),
            ("eduroam", "mf:servisi/eduroam", "globe", None),
            ("VPN", "mf:servisi/vpn", "globe", None),
            ("Microsoft softver za studente", "mf:servisi/microsoft-imagine", "cloud", None),
            ("Kontakt fakulteta", "mf:fakultet/kontakt", "home", None),
        ],
    ),
    (
        "Studenti",
        [
            (
                "Veliki drajv",
                "https://flatsoftcors-my.sharepoint.com/:f:/g/personal/kosta_jovanovic_flatsoft_co_rs/IgDBZZS1d7bBRahqaiN4S9K9AbIi_4GKg8Zbq4vVmLJJMaU",
                "cloud",
                "kosta-onedrive.com",
            ),
            ("Mašinci", "https://stepen.masinci.org/", "users", None),
            ("Drumska strela", "https://fsra.stt.org.rs/", "katedra-za-motorna-vozila", None),
            ("Beoavia", "https://beoavia.org/", "katedra-za-vazduhoplovstvo", None),
            ("Robotoid", "https://robotoid.stt.org.rs/", "katedra-za-automatsko-upravljanje", None),
        ],
    ),
    (
        "Katedre i programi",
        [
            ("Katedra za proizvodno mašinstvo", "https://cent.mas.bg.ac.rs/", "katedra-za-proizvodno-masinstvo", None),
            ("Industrijsko inženjerstvo", "https://ie.mas.bg.ac.rs/", "katedra-za-industrijsko-inzenjerstvo", None),
            ("Katedra za procesnu tehniku", "https://pt.mas.bg.ac.rs/", "katedra-za-procesnu-tehniku", None),
            ("Katedra za motore", "https://motori.mas.bg.ac.rs/", "katedra-za-motore", None),
            ("Katedra za mehanizaciju", "https://meh.mas.bg.ac.rs/", "katedra-za-mehanizaciju", None),
            ("Katedra za mehaniku fluida", "https://fluidi.mas.bg.ac.rs/", "katedra-za-mehaniku-fluida", None),
            ("Katedra za vazduhoplovstvo", "http://vaz.mas.bg.ac.rs/", "katedra-za-vazduhoplovstvo", None),
            ("Katedra za opšte mašinske konstrukcije", "https://omk.mas.bg.ac.rs/", "katedra-za-opste-masinske-konstrukcije", None),
            ("Katedra za matematiku", "https://mat.mas.bg.ac.rs/", "katedra-za-matematiku", None),
            ("Poljoprivredno prehrambeno mašinstvo", "https://ppm.mas.bg.ac.rs/", "katedra-za-poljoprivredno-masinstvo", None),
            ("Informacione tehnologije u mašinstvu", "https://it0.mas.bg.ac.rs/", "katedra-za-informacione-tehnologije-u-masinstvu", None),
            ("MF-ITM", "http://cs.mas.bg.ac.rs/", "katedra-za-informacione-tehnologije-u-masinstvu", None),
            ("Mašinstvo i informacione tehnologije", "http://mit.mas.bg.ac.rs/", "folder", None),
            ("Industrija 4.0", "https://i40.mas.bg.ac.rs/", "folder", None),
            ("Modul ZZK", "https://zzk.mas.bg.ac.rs/", "folder", None),
        ],
    ),
    (
        "Ostali sajtovi fakulteta",
        [
            ("Sajt na engleskom", "http://www.en.mas.bg.ac.rs/", "globe", None),
            ("Pretprijava kandidata", "https://pretprijava.mas.bg.ac.rs/", "user", None),
            ("Probni prijemni testovi", "https://testovi.mas.bg.ac.rs/", "file", None),
            ("Repozitorijum Machinery", "https://machinery.mas.bg.ac.rs/", "book", None),
            ("Alumni fondacija", "https://alumni.mas.bg.ac.rs/", "users", None),
            ("Inovacioni inkubator", "https://inkubator.mas.bg.ac.rs/", "globe", None),
            ("Laboratorija za toplotne turbomašine", "https://ltt.mas.bg.ac.rs/", "globe", None),
            ("Mission4.0", "https://mission4-0.mas.bg.ac.rs/", "globe", None),
            ("LGS", "https://lgs.mas.bg.ac.rs/", "globe", None),
            ("Geotermal", "https://geotermal.mas.bg.ac.rs/", "globe", None),
        ],
    ),
    (
        "Ovaj sajt",
        [
            ("Predmeti", "/predmeti/", "book", None),
            ("O sajtu", "/o-sajtu/", "file", None),
            ("Statistika", "/statistika/", "file", None),
            ("Verzije", "/verzije/", "file", None),
            ("Kod na GitHub-u", "https://github.com/KostaJovanovic/nastava", "globe", None),
            ("Prijavi grešku", "https://github.com/KostaJovanovic/nastava/issues", "msg", None),
            ("Knjiga utisaka", "https://valjdakosta.com/guestbook", "msgs", None),
        ],
    ),
]

UPIS = "upis/start"

# upis/start's tabs: (short, long name) for the pages it links; another one it links later gets its own title.
UPIS_TABS = {
    "upis/oas": ("OAS", "Osnovne akademske studije"),
    "upis/mas": ("MAS", "Master akademske studije"),
    "upis/das": ("DAS", "Doktorske akademske studije"),
    "studenti/start": ("Viša godina", "Upis u više godine ili obnova"),
}

# A teacher whose forum account is not their e-mail's name (the e-mail changed with a surname): theirs on the board.
# Sonja Josipović, née Grbić (ie.mas.bg.ac.rs/zaposleni.html); Nevena Rosić, née Aranđelović (signs her posts, as
# post 23279; the faculty's list gives her forum f=752).
FORUM_ACCOUNT = {"sjosipovic": "sgrbic", "nrosic": "narandjelovic"}

# Teachers who post on the board but are on no list of the faculty's (nastavnici.py), from the faculty's other pages.
# source: where the profile's facts are from.
_JOKSIMOVIC = "https://mas.bg.ac.rs/_media/fakultet/izbori-u-zvanja/referati/2020/referat_komisije_-_kandidat_joksimovic_aleksandra.pdf"

OTHER_TEACHERS = [
    dict(
        id="ajoksimovic",
        name="Александра Д. Јоксимовић",
        full_name="Александра Д. Јоксимовић",
        title="асистент",
        katedra="Катедра за теорију механизама и машина",
        katedra_id=None,
        office=None,
        email=None,
        username="ajoksimovic",
        phone=None,
        hours=None,
        research=None,
        emeritus=0,
        photo=None,
        first_seen="2026-11-09",
        last_seen="2026-11-09",
        gone=0,
        source=_JOKSIMOVIC,
        source_name="реферат комисије, mas.bg.ac.rs",
        html="<p>Мастер инжењер машинства (2017, модул Прехрамбено машинство). На Машинском факултету од 2012. ради на "
        "предмету Инжењерска графика, од 2015. на предмету Мехатроника. Истраживач-приправник од 2017, изабрана у "
        "звање асистента на Катедри за теорију механизама и машина 2020. године.</p>"
        "<p>Није на списку наставника на сајту факултета; ово је из реферата комисије за њен избор у звање асистента "
        f'(2020): <a href="{_JOKSIMOVIC}">PDF</a>.</p>',
    )
]


def _mentioned(id, name, title, katedra, seen, gone, source, source_name, html, aside=False):
    """A makeshift page: someone the board or the faculty's pages name at their work (exercises, labs, papers), on no
    list of the faculty's; what is known, from where. seen: the last date a source names them. aside: a
    researcher or demonstrator, on /nastavnici/istrazivaci/ and not among the teachers (their list, the searches, the count)."""
    return dict(
        id=id,
        name=name,
        full_name=name,
        title=title,
        katedra=katedra,
        katedra_id=None,
        office=None,
        email=None,
        username=None,
        phone=None,
        hours=None,
        research=None,
        emeritus=0,
        photo=None,
        first_seen=seen,
        last_seen=seen,
        gone=gone,
        source=source,
        source_name=source_name,
        aside=aside or title == "демонстратор",
        html=html + "<p>Није на списку наставника на сајту факултета: ова страница је састављена из помена.</p>",
    )


_POST = "https://nastava.mas.bg.ac.rs/nastava/viewtopic.php?p={}"

OTHER_TEACHERS += [
    _mentioned(
        "mentioned-maslarevic",
        "Александар Масларевић",
        "асистент",
        "Катедра за технологију материјала",
        "2025-10-28",
        0,
        _POST.format(25454),
        "форум наставе",
        '<p>Држао вежбе из Машинских материјала 2 (од 2016, <a href="/item/p3263/">резултати колоквијума</a>), '
        "а 2025. са проф. Братиславом Рајичићем дежурао на испитима из ММ2 и ПЗСУЕ "
        '(<a href="/item/p25454/">„др Александар Масларевић“</a>). Коаутор радова наставника Катедре за '
        "технологију материјала.</p>",
    ),
    _mentioned(
        "mentioned-opacic",
        "Мирјана Опачић",
        "асистент",
        "Катедра за технологију материјала",
        "2016-05-31",
        1,
        _POST.format(2533),
        "форум наставе",
        "<p>Предметни асистент на лабораторијским вежбама из Машинских материјала 1 у школској 2015/16 "
        '(<a href="/item/p2348/">резултати колоквијума</a>, <a href="/item/p2533/">поправни колоквијум</a>).</p>',
    ),
    _mentioned(
        "mentioned-vukojevic",
        "Филип Вукојевић",
        "сарадник у настави",
        "Катедра за математику",
        "2026-11-07",
        0,
        _POST.format(27977),
        "форум наставе",
        "<p>Мастер инжењер, сарадник у настави из математике од 2026, са проф. Јеленом Матовић, Александром "
        'Пејчевим и Душаном Ђукићем (<a href="/item/p27977/">„предметни асистент“</a>, '
        '<a href="/item/p29351/">распоред смена</a>).</p>',
    ),
    _mentioned(
        "mentioned-marajnovic",
        "Андријана Марајновић",
        "асистент",
        "Катедра за математику",
        "2021-11-13",
        1,
        _POST.format(15483),
        "форум наставе",
        "<p>Асистент на математици; припремила материјал о непрекидним расподелама за предавања проф. "
        'Александра Пејчева (<a href="/item/p15483/">2021</a>).</p>',
    ),
    _mentioned(
        "mentioned-berdic",
        "Стефан Бердић",
        "демонстратор",
        "Катедра за опште машинске конструкције",
        "2025-12-01",
        0,
        _POST.format(26454),
        "форум наставе",
        "<p>Демонстратор на Машинским елементима, на прегледу пројектних задатака код проф. Ненада Коларевића и "
        'Александра Димића (<a href="/item/p20558/">2023</a>, <a href="/item/p23229/">2024</a>, '
        '<a href="/item/p26454/">2025</a>).</p>',
    ),
    *[
        _mentioned(
            f"ic-{slug(lat)}",
            name,
            "истраживач",
            None,
            "2026-11-12",
            0,
            f"https://machinery.mas.bg.ac.rs/APP/faces/author.xhtml?author_id=orcid%3A%3A{orcid}",
            "machinery.mas.bg.ac.rs",
            f"<p>Истраживач Иновационог центра Машинског факултета: {n} радова у збирци „IC – radovi "
            "istraživača“ репозиторијума факултета (Machinery).</p>",
            aside=True,
        )
        # The repository's most frequent authors of its Innovation Centre collection (2026-11-12): 100+ works each.
        for name, lat, orcid, n in [
            ("Симон Седмак", "Simon Sedmak", "0000-0002-2674-541X", 222),
            ("Милош Милошевић", "Miloš Milošević", "0000-0002-2418-1032", 194),
            ("Бранислав Ђорђевић", "Branislav Đorđević", "0000-0001-8595-6930", 120),
            ("Алекса Миловановић", "Aleksa Milovanović", "0000-0003-4668-8800", 113),
            ("Снежана Кирин", "Snežana Kirin", "0000-0002-2176-3969", 111),
        ]
    ],
    _mentioned(
        "mentioned-kovacevic",
        "Сандра Ковачевић",
        "",
        "Катедра за термомеханику",
        "2026-11-11",
        0,
        "https://vesti.mas.bg.ac.rs/?p=24064",
        "vesti.mas.bg.ac.rs",
        "<p>Мастер инжењер машинства (модул за термотехнику). 2023. награђена на Националном студентском "
        'такмичењу из КГХ (<a href="https://vesti.mas.bg.ac.rs/?p=24064">вест</a>). Коаутор радова '
        "проф. Милоша Бањца и Бранислава Петровића (2026) и Приручника за обуку енергетских саветника "
        "(Машински факултет, 2025).</p>",
    ),
]

# Teachers shown without their second surname, except on their own page (the user's choice): Vasić-Milovanović,
# Lazović-Kapor, Milošević-Mitić, Sretenović-Dobrić.
SHORT_SURNAME = {"30", "90", "115", "191"}

RANKS = ["професор емеритус", "редовни професор", "ванредни професор", "доцент", "асистент са докторатом", "асистент"]

# The faculty profile's bibliography headings, as a short kind ('ван SCI' before 'SCI').
BIB_KINDS = [
    ("конференциј", "konferencija"),
    ("ван SCI", "časopis"),
    ("SCI", "SCI časopis"),
    ("Поглавља", "poglavlje"),
    ("Књиге", "knjiga"),
]

# A katedra's own site that its faculty page does not link (the Linkovi page has them; mat.mas.bg.ac.rs is down).
OWN_SITES = {
    "Катедра за информационе технологије у машинству": "https://it0.mas.bg.ac.rs/",
    "Катедра за пољопривредно машинство": "https://ppm.mas.bg.ac.rs/",
}

MONTHS = "jan feb mar apr maj jun jul avg sep okt nov dec".split()

WEEKDAYS = "pon uto sre čet pet sub ned".split()

# Words of the posts the word cloud leaves out: frequent, but they say nothing of what a post is about.
CLOUD_STOP = set(
    """prof dela posle nakon koji koja koje koju kojima prvi drugi treći prva druga treća prve prvog drugog
    trećeg biće biti bilo bude mogu može možete imaju nisu nije neće samo treba više prema kako isto istom ukoliko tokom
    jedan preko radi putem zbog svih ovog ovom ovaj takođe""".split()
)

# The home page's smerovi, by level then program (their URL slugs); any other after them, in the board's order. Each
# has its icon in icons.svg, i-<key> (rows.html, smer.html); another smer has the folder.
HOME_ORDER = ["oas-mi", "oas-itm", "mas-mi", "mas-industrija-4-0", "doktorske-studije-mi", "katedre", "moduli"]

# verzije.md's tags: the shown word and the class (style.css .vz__tag--).
VZ_TAGS = {"novo": ("Novo", "new"), "ispravka": ("Ispravka", "fix"), "brže": ("Brže", "fast")}

VZ_ITEM = re.compile(r"- (?:(\d+(?:–\d+)?(?:, \d+(?:–\d+)?)*) )?(?:\[(\w+)\] )?(.*)")

# /stil/'s typefaces: (name, its font-family in style.css, its files in static/fonts, its weights, where it is used).
STIL_FONTS = (
    ("IBM Plex Sans", "IBM Plex Sans", ["IBMPlexSans.woff2"], (400, 700), "tekst celog sajta"),
    ("IBM Plex Mono", "IBM Plex Mono", ["IBMPlexMono-Regular.woff2", "IBMPlexMono-Bold.woff2"], (400, 700), "kodovi, brojevi, datumi"),
    ("Geist", "Geist", ["Geist-Regular.woff2", "Geist-ExtraBold.woff2"], (400, 800), "OG slike sekcija"),
    ("Golos Text", "Golos Text", ["lab/GolosText.woff2"], (800,), "OG slike linkova"),
    ("Roboto Mono", "Roboto Mono", ["RobotoMono-Regular.woff2"], (400,), "OG slike linkova"),
)

# /stil/'s logo files, in static/.
STIL_LOGOS = ("favicon.svg", "app-icon.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "badge.png")
