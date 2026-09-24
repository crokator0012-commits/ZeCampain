"""
Rebuild assets/codex_icons.js from the "Unit Icons/<realm>/" source art.

What it does differently from the old compress_icons.py step:
  * keeps each icon's real proportions (source art is a tall 64x152 portrait) instead of squashing it to 64x64
  * writes an explicit  CODEX_ICON_MAP  {unit_key: icon_key}  so the game does not have to guess names at runtime
  * matches roster units to icon files with a fuzzy scorer, looking in the unit's own realm folder first and then
    in every other realm's folder (mercenary / regional units often have their art filed under another realm)
  * a curated REJECT / ACCEPT_LOW / OVERRIDE list (below) was reviewed by hand, because a wrong icon is worse
    than the faction-emblem fallback

Run from the repo root:   python scripts/build_unit_icons.py
"""
import base64, difflib, io, json, os, re, sys
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ICONS_DIR = os.path.join(ROOT, "Unit Icons")
OUT = os.path.join(ROOT, "assets", "codex_icons.js")

MAX_W, MAX_H = 64, 152          # native size of the source portraits
WEBP_QUALITY = 84

# codex realm name -> folder name(s) in "Unit Icons" when they differ
REALM_FOLDER = {"Rhurrim": ["Rhun"], "Rhudaur": ["Rhudar"], "Khazad-dum": ["Khazadum"]}

# (realm, unit name) pairs that must NEVER get an icon from the scorer (checked by eye: different unit)
REJECT = {
    ("Rhurrim", "Loke-RIm Bows"), ("Mordor", "Warg Riders"), ("Lindon", "Noldorin Swordsmen"),
    ("Lindon", "Noldorin Archers"), ("Khazad-dum", "LongBeard Spearmen"), ("Khazad-dum", "balin"),
    ("Iron Hills", "Dwarven lumberjacks"), ("Iron Hills", "(AOR)-Warroirs of Ered Mithrin"),
    ("Dunlendings", "onager"), ("Gundabad", "Gundabad Warg Chiefs"), ("Ered Mithrin", "Ered mithrin Cohort"),
    ("Imraldris", "Rivendell Bows"), ("Mordor", "(AOR)-Morgul warband"), ("Dunlendings", "Dunleding hunters"),
    ("Mordor", "(AOR)-Morgul Guard"), ("Ered Mithrin", "ered Mithrin Veterans"),
    ("Anduin Vale", "(AOR)-Greenwood Axemen"), ("Khand", "Variag Axemen"),
    ("Ered Mithrin", "Grey Mountain Sentinels"), ("Dol Gul Dur", "Mirkwood reavers"),
    ("Dol Gul Dur", "Mirkwood raiders"), ("Dol Gul Dur", "Mirkwood trackers"), ("Dol Gul Dur", "Mirkwood Spiders"),
    ("Khazad-dum", "Onager"), ("Lothlorien", "Galadrim Bow warroirs"), ("Lothlorien", "Galadrim Sword Warroirs"),
    ("Khazad-dum", "Hunters of Khazad Dum"), ("Woodland Realm", "Lasgalen Warroirs"),
    ("Iron Hills", "Dwarven Boar Hunters"), ("Dale", "(AOR)-Rhovanion Rangers"), ("Umbar", "Corsair Raiders"),
    ("Gundabad", "Gundabad Wargs"), ("Lindon", "Falathrim Spearmen"), ("Ered Luin", "(S)-Merchant Swordsmen"),
    ("Dorwinion", "Earls of the Vinter Court"), ("Ered Mithrin", "Dwarven Mace Infantry"),
    ("Ered Mithrin", "Troll Hunters"), ("Mordor", "(Mercs AOR)-Mirkwood Reavers"),
}
REJECT_REALM_CONTAINS = [("Drudain", "Warlord")]     # four different Drudain units would all share one generic "Warlords" icon

# own-realm matches scoring 0.62-0.80 that were checked and are correct
ACCEPT_LOW = {
    ("Imraldris", "Imladris Swordsmen"), ("Erebor", "erebor Crossbows"), ("Dale", "Dalain Swordsmen"),
    ("Dale", "dalian SpearGuards"), ("Dale", "Yeomen"), ("Rhurrim", "(AOR)-Balchoth Spearmen"),
    ("Iron Hills", "Iron hill Crossbows"), ("Iron Hills", "Carnen River Guards"), ("Lindon", "Noldorin Spearmen"),
    ("Isengard", "(Mercs AOR)-Mordor Bow Rabble"), ("Isengard", "(Mercs AOR)-Mordor Rabble"),
    ("Lindon", "falathrim GreatSwords"), ("Rohan", "Musterd Axemen"), ("Lostladen Tribes", "Camel Riders"),
    ("Dorwinion", "Vinter Gaurd"), ("Lindon", "Falathrim Swordsmen"), ("Isengard", "Uruk Hia Pikes"),
}

# (realm, unit name) -> (folder, file): the scorer picks the wrong file or misses it
OVERRIDE = {
    ("Erebor", "Erebor Halberds"): ("Erebor", "ere_t2_halberdiers.png"),
    ("Rachrohir", "Wainrider Nobles"): ("Khand", "kha_wainrider_nobles.png"),
    ("Mordor", "Uruk Archers"): ("Isengard", "07_Uruk_hai_archers_UCpng.png"),
    ("Goblins", "high Chiefton's Guard"): ("Goblins", "03_High_Chieftains_Guard_UCpng.png"),
    ("Gondor", "(AOR)-RingloVale men at arms"): ("Gondor", "02_Ringolo_Vale_Swordsjpg.jpg"),
}

NOISE = {"aor", "oar", "merc", "mercs", "av", "wr", "uc", "unit", "the", "of", "a"}
ALIAS = [(r"\bcalvary\b", "cavalry"), (r"\bgaurds?\b", "guard"), (r"\bwarroirs?\b", "warrior"),
         (r"\bdunleding\b", "dunlending"), (r"\bdeckemen\b", "deckmen"), (r"\bsergaents?\b", "sergeants"),
         (r"\bseargeants?\b", "sergeants"), (r"\bsergeants?\b", "sergeants"), (r"\bcoast\s+guard", "coastguard"),
         (r"\blossnarch\b", "lossarnach"), (r"\bolog hia\b", "olog hai"), (r"\bshirrifs\b", "shire reeves"),
         (r"\bpelagir\b", "pelargir"), (r"\bpeligir\b", "pelargir"), (r"\btrebucheet\b", "trebuchet"),
         (r"\bbalcoth\b", "bal"), (r"\bbalchoth\b", "bal")]

# Words that describe a kind of soldier rather than naming a specific unit. Two units sharing ONLY these words
# ("Balcoth Nobles" / "Ered Mithrin Nobles") are not the same unit, so cross-realm matches must share a distinctive word.
GENERIC = set("""noble spear spearman spearguard archer bow bowman crossbow crossbowman raider guard sword swordsman axe axeman
rider cavalry infantry warrior militia man men at arm hunter scout sentinel sentry ranger pike pikeman halberd champion
veteran chief knight lancer outrider horse horseman company warband band footman marine watchman warden guardian trooper
rabble levy servant slinger thrower skirmisher elite heavy light royal mounted retainer retinue wanderer patroller
protector defender soldier fighter blade huntsman spearmen swordsmen axemen bowmen crossbowmen pikemen horsemen
footmen watchmen huntsmen marksmen""".split())


def distinct(toks):
    return {t for t in toks if t not in GENERIC and not t.isdigit() and len(t) > 1}


def clean_file(fn, strip_prefix):
    n = re.sub(r"(?i)\.(png|jpg|jpeg)$", "", fn)
    n = re.sub(r"(?i)(?:_?UC\d*(?:png|jpg)?|_?v\d+(?:png|jpg)?|(?<=[a-z])(?:png|jpg))$", "", n)
    n = re.sub(r"^\d+_", "", n)
    if strip_prefix:                                   # kha_, wain_, ere_t4_, T2_ ...
        n = re.sub(r"(?i)^t\d_", "", n)
        if re.match(r"(?i)^[a-z]{2,4}_[a-z]", n):
            n = re.sub(r"(?i)^[a-z]{2,4}_(?:t\d_)?", "", n)
    return n


def norm(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower()).replace("_", " ").replace("-", " ")
    for a, b in ALIAS:
        s = re.sub(a, b, s)
    toks = [t for t in re.sub(r"[^a-z0-9]+", " ", s).split() if t not in NOISE]
    return [t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t for t in toks]


def score(u, f):
    if not u or not f:
        return 0.0
    us, fs = set(u), set(f)
    inter = len(us & fs)
    jac, cont = inter / len(us | fs), inter / len(fs)
    seq = difflib.SequenceMatcher(None, "".join(u), "".join(f)).ratio()
    return max(jac, 0.92 * cont if cont == 1 else 0.6 * cont, seq * 0.95)


def main():
    html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    cx = json.loads(re.search(r'<script id="codexdata" type="application/json">(.*?)</script>', html, re.S).group(1))
    folders = sorted(d for d in os.listdir(ICONS_DIR) if os.path.isdir(os.path.join(ICONS_DIR, d)))
    files = {d: [f for f in os.listdir(os.path.join(ICONS_DIR, d)) if f.lower().endswith((".png", ".jpg", ".jpeg"))] for d in folders}
    variants = {(d, f): [norm(clean_file(f, False)), norm(clean_file(f, True))] for d in folders for f in files[d]}

    def best(utoks_list, pool, need_distinct=False):
        top = (0.0, None, None)
        udist = set().union(*[distinct(u) for u in utoks_list])
        for (d, f) in pool:
            sc = 0.0
            for ft in variants[(d, f)]:
                if need_distinct and not (udist & distinct(ft)):
                    continue
                sc = max(sc, max(score(u, ft) for u in utoks_list))
            if sc > top[0]:
                top = (sc, d, f)
        return top

    chosen, source = {}, {}
    for u in cx["units"]:
        realm, name, key = u["faction"], u["name"], u["unit_key"]
        if (realm, name) in REJECT or any(r == realm and w in name for r, w in REJECT_REALM_CONTAINS):
            continue
        if (realm, name) in OVERRIDE:
            chosen[key], source[key] = OVERRIDE[(realm, name)], "override"
            continue
        if len(norm(name)) == 1 and norm(name)[0] in ("onager", "ballista", "catapult"):
            continue                                    # siege engines: no matching art
        rk = norm(re.sub("^" + re.escape(realm.lower().replace(" ", "_").replace("-", "")) + "_", "", key))
        utoks = [norm(name), rk]
        own = REALM_FOLDER.get(realm, [realm] if realm in folders else [])
        so, do, fo = best(utoks, [(d, f) for d in own for f in files[d]])
        sg, dg, fg = best(utoks, [(d, f) for d in folders for f in files[d]], need_distinct=True)
        if so >= 0.80:
            chosen[key], source[key] = (do, fo), "own"
        elif sg >= 0.85:
            chosen[key], source[key] = (dg, fg), "cross-realm"
        elif so >= 0.62 and (realm, name) in ACCEPT_LOW:
            chosen[key], source[key] = (do, fo), "curated"

    # encode each distinct source file once
    icon_key_for, icons = {}, {}
    def icon_key(folder, fn):
        if (folder, fn) in icon_key_for:
            return icon_key_for[(folder, fn)]
        body = re.sub(r"[^a-z0-9]+", "_", re.sub(r"(?i)\.(png|jpg|jpeg)$", "", fn).lower()).strip("_")
        k = f"{folder.lower().replace(' ', '_')}_{body}"
        while k in icons:
            k += "_"
        im = Image.open(os.path.join(ICONS_DIR, folder, fn)).convert("RGBA")   # keep transparency (644 of 648 sources have it)
        w, h = im.size
        ratio = MAX_W / MAX_H
        if abs(w / h - ratio) > 0.08:                     # a wide concept-art poster, not a portrait card: crop the centre column
            if w / h > ratio:
                nw = int(h * ratio); x0 = (w - nw) // 2; im = im.crop((x0, 0, x0 + nw, h))
            else:
                nh = int(w / ratio); y0 = (h - nh) // 2; im = im.crop((0, y0, w, y0 + nh))
        im.thumbnail((MAX_W, MAX_H), Image.Resampling.LANCZOS)          # keep the real aspect ratio, never upscale
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=WEBP_QUALITY, method=6, alpha_quality=90)
        icons[k] = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        icon_key_for[(folder, fn)] = k
        return k

    unit_map = {key: icon_key(*ff) for key, ff in chosen.items()}

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('"use strict";\n/* Generated by scripts/build_unit_icons.py - do not edit by hand. */\nconst CODEX_ICONS={\n')
        for k, v in icons.items():
            fh.write(f'  "{k}":"{v}",\n')
        fh.write("};\nconst CODEX_ICON_MAP={\n")
        for k, v in unit_map.items():
            fh.write(f'  "{k}":"{v}",\n')
        fh.write("};\n")

    by_src = {}
    for s in source.values():
        by_src[s] = by_src.get(s, 0) + 1
    print(f"units: {len(cx['units'])} | with an icon: {len(unit_map)} | distinct icon files used: {len(icons)}")
    print("how they were matched:", by_src)
    print(f"{os.path.relpath(OUT, ROOT)}: {os.path.getsize(OUT) / 1024:.0f} KB")
    json.dump({"map": {k: list(v) for k, v in chosen.items()}, "source": source},
              open(os.path.join(os.environ.get("TEMP", "."), "icon_build_report.json"), "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main()
