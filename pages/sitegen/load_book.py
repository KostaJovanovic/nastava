"""The faculty's subject book and plans (predmeti.py's tables)."""

import re
from translit import fold
from .load_board import board_subject
from .text import PROGRAMS, acronyms, azbuka, set_hrefs, slot_label, slug


def load_book(db, subjects, teachers):
    """The faculty's subjects (predmeti.py), each with its places in the plans, its teachers and its forum subject:
    the same code, or else the same name in the board's smer of the same program."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name = 'subjects'").fetchone():
        return []
    # Before render_places, so the forum pages can link here; a forum subject with no topics (no page) is dropped later.
    by_code = {c: s for s in subjects.values() for c in s["codes"]}
    by_name = {(fold(s["smer"]["short"]), fold(s["name"])): s for s in subjects.values()}
    teacher = {t["id"]: t for t in teachers}
    book = [dict(r, places=[]) for r in db.execute("SELECT * FROM subjects ORDER BY rowid")]
    set_hrefs(book, lambda s: f"/predmeti/{slug(s['name'])}/")
    by_id = {s["id"]: s for s in book}
    for s in book:
        s["forum"] = board_subject(by_code, by_name, s["id"], s["name"], s["program"])
        # The holder first, then the other teachers of the page's head ('Извођачи').
        m = re.search(r"Извођачи</strong>(.*?)<br", s["html"] or "", re.S)
        ids = [s["holder"]] + re.findall(r"/fakultet/nastavnici/(\d+)", m[1] if m else "")
        s["teachers"] = [teacher[i] for i in dict.fromkeys(ids) if i in teacher]
        s["holder_t"] = teacher.get(s["holder"])
    # A teacher by the subjects their profile lists, for an area of Завршни предмет ('Завршни предмет - Трибологија').
    by_area = {(c["code"], fold(c["name"])): t for t in teachers if not t["gone"] for c in t["subjects"]}
    # i: the order the plans were read in (predmeti.py: programs, then the modules as the master's page lists them).
    for i, r in enumerate(db.execute("SELECT * FROM subject_places ORDER BY rowid")):
        if r["subject"] not in by_id:
            continue
        s = by_id[r["subject"]]
        key = lambda p: (p["program"], p["module"], p["semester"], p["slot"])
        place = next((p for p in s["places"] if key(p) == key(r)), None)
        if place is None:
            place = dict(r, i=i, label=slot_label(r["slot_name"], r["slot"]) if r["slot"] else None, names=[])
            s["places"].append(place)
        # The slot's list can link one page under several names, each a choice (Завршни предмет: 102 areas).
        # get: a database from before predmeti.py kept the names.
        if (name := dict(r).get("name")) and name not in place["names"]:
            place["names"].append(name)
    for s in book:
        s["acr"] = acronyms(s["name"]) | (s["forum"] or {}).get("acr", set())
        s["find"] = fold(
            " ".join(
                [s["name"], *sorted(s["acr"]), s["id"], s["katedra"] or "", s["program"]]
                + [t["name"] for t in s["teachers"]]
                + [p["module"] or "" for p in s["places"]]
            )
        )
        if s["forum"]:
            s["forum"].setdefault("info", s)
        # One row per name in the subject list; its own id, so site.js does not take the areas for one subject.
        for p in s["places"]:
            names, p["variants"] = p.pop("names"), []
            for n in names if len(names) > 1 else []:
                t = by_area.get((s["id"], fold(n)))
                # own: what only this area's row has; the subject's find is the page's once (predmeti.html #finds).
                p["variants"].append(dict(s, name=n, id=f"{s['id']}-{slug(n)}", holder_t=t, own=fold(f"{n} {t['name'] if t else ''}")))
    return book


def plan_groups(book):
    """The list's default grouping, as the faculty's plans: program (and module) > semester > the required subjects,
    then one group per elective slot. A subject in no plan is listed under its program at the end."""
    plans, first = {}, {}
    for s in book:
        if s["gone"]:
            continue
        for p in s["places"]:
            first[(p["program"], p["module"])] = min(p["i"], first.get((p["program"], p["module"]), p["i"]))
            plan = plans.setdefault((p["program"], p["module"]), {})
            sem = plan.setdefault(p["semester"], dict(sem=p["semester"], req=[], slots={}))
            if p["slot"]:
                sem["slots"].setdefault((p["pos"], p["slot"]), dict(label=p["label"], rows=[]))["rows"].extend(p["variants"] or [s])
            else:
                sem["req"].append((p["pos"], s))
        if not s["places"]:
            plans.setdefault((s["program"], "ван наставног плана"), {}).setdefault(0, dict(sem=0, req=[], slots={}))["req"].append((0, s))
    order = {p: i for i, p in enumerate(PROGRAMS)}
    out = []
    # Programs in study order; modules in the order of the master's page; 'not in a plan' last in its program.
    for (program, module), sems in sorted(plans.items(), key=lambda kv: (order.get(kv[0][0], len(order)), first.get(kv[0], 1e9))):
        out.append(
            dict(
                program=program,
                module=module,
                sems=[
                    dict(
                        sem=n,
                        req=[s for _, s in sorted(v["req"], key=lambda x: (x[0], azbuka(x[1]["name"])))],
                        slots=[v["slots"][k] for k in sorted(v["slots"])],
                    )
                    for n, v in sorted(sems.items())
                ],
            )
        )
    return out
