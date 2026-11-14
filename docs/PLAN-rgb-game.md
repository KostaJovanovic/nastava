# RGB desk game (Godot) — plan

## Context
During the 2024–25 blokada, RGB (radna grupa za bezbednost) sat at a desk by the faculty entrance.
They checked indexes and student cards, logged money donations, kept the guest table and dealt with
whoever walked in. The user wants a full Godot game about that desk: document inspection in the genre
of "Papers, Please", with its own name, story, characters and look.
- It's a separate project from the nastava archive.
- A simpler web easter egg for the archive comes later, as its own plan.
- The game's name is still to be decided.

## Game design

### Core loop (one day = one shift)
1. **Morning**
   - The plenum's rules for the day: new exceptions, events, crna lista changes.
   - The day's headline: a real blokada event of that date.
   - Phone messages.
2. **Shift**
   - Visitors arrive one at a time, sometimes as a pair.
   - Between visitors there's downtime: colleague talk, the phone group chat, the sveska and spiskovi.
3. **Each visitor**
   - They hand over documents. You drag them onto the desk, inspect, zoom and compare.
   - You click two fields that disagree to confront the visitor, and they react.
   - You talk: ask for the lična karta, ask who vouches, small talk, calm them down.
   - You decide: **Pusti / Odbij / Zovi**.
4. **End of day**
   - The plenum report with the same-day consequences.
   - Meters carry over.
   - Some decisions are flagged to come back days later.

### Entry rules
- Only **mašinci** get in.
- Students from other faculties get in only if:
  - a mašinac vouches for them, or
  - it's an event day (pab kviz, sastanak krovnih radnih grupa).
- Every guest goes into the **guest table**: full name, faculty, broj indeksa. The player fills the
  rows, and low energy causes typos.
- Each morning the plenum adds or changes rules: new exceptions, a new document format, a new
  crna lista name.

### Documents and checks
| Item | Checks | Notes |
|---|---|---|
| Indeks | name, broj indeksa, photo, overa for this year | ćirilica |
| Studentska kartica | name, photo, faculty, validity | |
| eStudent (visitor's own phone) | name, year, status, live vs screenshot | usually no photo |
| Lična karta | name only, matched against eStudent | You can **ask** for it but can't demand it (only police can). The visitor may decline politely or angrily. |
| Crna lista | names only | student-voted |
| Guest table / sveska | rows you write | money must match the cash |

**Tricks to spot:**
- tuđi indeks or kartica
- eStudent screenshot (old year or someone else's account)
- isteklo / nije overeno
- priče i pritisak (forgot the index, a professor is waiting, name-dropping, anger, filming)
- a crna lista name

**Pairs:** both people are checked, each with their own documents. Often the friend is the one with the
problem, or the one vouching.

### Zovi
| Who | What happens |
|---|---|
| Neko ko ga poznaje | vouches, and may be lying or covering for a friend |
| Plenum / spisak | slow and reliable |
| Obezbeđenje / policija | escalates, raises stress and has story consequences |

### Meters
- **Poverenje plenuma:** mistakes lower it. Too low ends the game with *Skinut/a sa stola*.
- **Stres** (within a shift):
  - Angry visitors and mistakes raise it.
  - Kind moments and breaks lower it.
  - At the maximum you quit today's shift. Repeated quits lead to *Izgoreo/la si*.
- **Energija:**
  - Every encounter drains it.
  - It sets how fast you act and multiplies stress gain: almost no stress at full energy, much more
    when low.
  - Energy drinks, a smoke break, a funny joke or food donations restore it.
- **Red:** there's no queue on normal days. A queue only forms on event days (plenumi, meetings before
  big actions).

### Donations
- Food and other items only pile up as decoration on the table. Food donations also restore energy.
- **Money** goes into the sveska, and the cash has to match the log at the end of the day.
- **Sumnjive donacije:** party or media strings attached, or someone wants a receipt or photo.

### Mistakes and consequences
- Most are revealed in the same day's report.
- A few are flagged and come back days later as a story event.

### Story (~15 days, about an hour)
- **Tone:** mixed. Mostly warm and funny, with a few heavy days.
- **Realism:** real places, and real blokada events as day headlines. Every person is fictional.
- **The player:**
  - enters a name, year and module
  - picks gender, which is needed for Serbian grammar
- **Recurring characters:**
  - the **hungry guy**: asks for leftover food or drink, thanks you and leaves. You gain nothing; it's
    a pure moral moment.
  - a first-year who keeps forgetting the index
  - others, written with the user
- **Colleague side stories:** they play out in downtime.
- **NNV subplot:** the professors' naučno-nastavno veće, told only through dialogue with professors
  and assistants at the desk.
- **Endings:**
  - *Izgoreo/la si*
  - *Skinut/a sa stola*
  - *Izdržao/la do kraja*: day 15 is reached and the blokada goes on without a clean resolution.

### Look and text
- **Backgrounds:** photo-collage. The user takes new photos of the entrance and desk.
- **People:** pixel art assembled from a procedural parts kit (head, hair, face, clothes, bag). The kit
  has to leave room to:
  - swap in hand-drawn parts, and
  - use a fully drawn sprite for key characters.
- **Language:** Serbian, mixed by context: dialogue in latinica, official documents in ćirilica. There
  is an English translation.
- **Platforms:** Windows, Linux, Mac, Android, iOS. Every interaction must work with mouse and touch.
- **Release:** decide later.

## Technical plan (Godot 4, latest stable, GDScript)
The user is new to Godot, so each piece gets explained when it's built.

### Project layout
```
project.godot
scenes/   main_menu, morning, desk, day_report, ending
scripts/
  game_state.gd      autoload: meters, day, flags, player name/gender, save/load
  rules.gd           checks a visitor against today's rules, returns the problems
  visitor_gen.gd     random visitors from parts + documents with planted flaws
  content.gd         loads days/*.txt, resolves {m|f} and {ime}, picks the language
  documents/         one scene per document type, shared field-click handling
  people/            pixel-person assembler: parts kit or full sprite
content/
  days/01.txt ...    rules, headline, scripted visitors, dialogue (Serbian)
  days/01.en.txt     English, same line ids
  people/*.txt       recurring characters
art/  photos/  parts/  documents/
```

### Content format (plain text, one file per day)
This is a small custom format parsed in `content.gd`. Godot ships no YAML parser, and hand-written JSON
is painful.
```
headline: <real event of that date>
rules: only_masinci, guest_vouch, event:pab_kviz
blacklist+: Marko Petrović

visitor gladni
  line g1: Imaš možda nešto da se pojede?
  choice: daj -> g2 | nemam -> g3
  line g2: Hvala ti, {brate|sestro}.
```
- `{a|b}` is the player-gender form.
- `{ime}` is the player's name.
- Every line has an id, and the `.en.txt` file translates the same ids. A missing id is reported when
  the game loads.

### Visitors and the rules engine
- A visitor is stored as the **true identity** plus the **documents generated from it**.
- `visitor_gen.gd` plants 0–2 flaws from the day's allowed tricks.
- `rules.gd` compares the documents against the truth and today's rules, and lists the problems with
  the decision each one requires.
- The same code then:
  - scores the player's decision,
  - powers the field-mismatch clicking,
  - writes the day report.
- Scripted visitors from the day files use the same structure, with fixed values.

### Saving
- Save after each day: `user://save.json` holds the meters, day, flags and pending delayed consequences.

## Milestones
1. **Desk prototype:**
   - one day, gray boxes
   - drag documents, Pusti/Odbij, the rules engine, a day report
2. **All checks:**
   - eStudent phone, lična karta ask/decline, pairs, crna lista
   - guest table writing, Zovi
3. **Meters:** stres, energija, poverenje, breaks and items, the sveska money log.
4. **Content pipeline:**
   - day file parser, gender forms, English files
   - morning screen, phone chat, colleague dialogue
5. **People:** procedural pixel-part assembler, plus the hook for hand-drawn parts and full sprites.
6. **Story:** 15 days, recurring characters, the NNV subplot, delayed consequences, three endings.
7. **Art pass:** the user's photos, document art in ćirilica.
8. **Platforms:** mobile touch layout, exports for all five targets, save/load.

## Verification
- **Rules engine and day file parser:** GDScript self-check scripts run headless
  (`godot --headless -s test/...`). Generated visitors with known flaws must produce exactly those
  problems.
- **Each milestone:** play a full day in the editor. After milestone 8, test on a phone and a desktop
  export.
- **Translation:** a script lists ids that are missing from the `.en.txt` files.

## Still open
- Game title and repo folder.
- The exact list of the 15 days and their real headlines.
- Recurring characters beyond the hungry guy and the forgetful first-year.
- How hard the stress/energy numbers should push. This gets tuned in milestone 3 by playing.
