# TDD Age of Men — Codebase & Gameplay Documentation

A browser-based grand-strategy wargame for a Lord of the Rings (Dawnless Days / Total War: Attila) Discord campaign. Players command realms on a Middle-earth map; battles are fought in Total War and recorded here. There is **no backend**: the whole game is one static page plus one JSON file that the page commits to GitHub.

> **AI agents / new developers: do NOT read `index.html`, `campaign.json` or `assets/*.js` whole** — they total ~30 MB (~900k tokens), almost all of it base64 images and data. Read this file, then use the [Code map](#18-code-map-for-agents-navigate-dont-read) to jump to the exact lines you need.

> This document describes what the code in `index.html` actually does. Where the in-game Rules text or older notes disagree with the code, the code is described and the difference is called out in [§14 Known gaps](#14-known-gaps--things-the-code-does-not-enforce).

---

## Contents

1. [Architecture at a glance](#1-architecture-at-a-glance)
2. [Repository layout](#2-repository-layout)
3. [Data model — `campaign.json`](#3-data-model--campaignjson)
4. [Factions & realms](#4-factions--realms)
5. [Provinces, settlements & economy](#5-provinces-settlements--economy)
6. [Buildings & the construction queue](#6-buildings--the-construction-queue)
7. [Units & recruitment](#7-units--recruitment)
8. [Armies & movement](#8-armies--movement)
9. [Battles, sieges & occupation](#9-battles-sieges--occupation)
10. [Zeal, war & diplomacy](#10-zeal-war--diplomacy)
11. [Turn-based play: the round cycle](#11-turn-based-play-the-round-cycle)
12. [Player controls](#12-player-controls)
13. [GM controls](#13-gm-controls)
14. [Known gaps](#14-known-gaps--things-the-code-does-not-enforce)
15. [Publishing, hosting & secrets](#15-publishing-hosting--secrets)
16. [Offline tooling (Python scripts)](#16-offline-tooling-python-scripts)
17. [Developer notes](#17-developer-notes)
18. [Code map for agents](#18-code-map-for-agents-navigate-dont-read)

---

## 1. Architecture at a glance

```
                  ┌────────────────────────────────────────────────┐
  GitHub repo     │  campaign.json  ← single source of truth       │
  (main branch)   │  index.html + assets/*.js  ← the whole app     │
                  └───────────▲───────────────────────┬────────────┘
        PUT contents API      │                       │ Vercel deploy
   (token in client JS)       │                       ▼
                  ┌───────────┴────────┐      ┌──────────────────┐
                  │  Browser (player   │◄─────│ Static site      │
                  │  or GM) – index.html│ GET  │ (Vercel)         │
                  └────────────────────┘      └──────────────────┘
```

- **One page, two roles.** Everyone opens the same `index.html`. It starts read-only (`body.readonly`). A player can *unlock their own realm* with a passphrase when it is their turn; the GM unlocks *GM mode* with a separate passphrase.
- **State = one object `S`**, loaded from `campaign.json` at page start and mutated in memory. Nothing is saved until someone presses **End turn** (player) or **⇧ Publish** (GM), which commits the whole of `S` to `campaign.json` on GitHub.
- **Stack:** vanilla JS, HTML5 canvas, CSS. No framework, no bundler. Heavy binary data (map images, emblems, unit icons) is base64 inside `assets/*.js`.
- **Hosting:** Vercel static hosting. The build step injects the GitHub token into the page (see [§15](#15-publishing-hosting--secrets)).

### Start-up sequence

1. An inline script synchronously fetches `./campaign.json?t=<timestamp>` (cache-busted) and overwrites the embedded `<script id="mapdata">` fallback. If that fails and `localStorage.rqRepo` is set, it falls back to `raw.githubusercontent.com/<repo>/main/campaign.json`.
2. `assets/*.js` define `MAP_B64`/terrain/shade images, `EMBLEMS`, `CODEX_ICONS`, `TRADE_BUILDINGS`.
3. The main script parses the data, normalises it (see below), builds the province hit-map, then `boot()` paints and shows the map.

Normalisation on load: the legacy realm id `Rhun` is renamed `Rhurrim`; `Harad` and **NPC factions** (`faction.npc`) are dropped from the turn order; `S.active` is re-derived from the faction that was current; wars/alliances are re-keyed canonically; per-realm colours are overridden from a built-in palette; settlement `value` is reset to the tier's standard revenue; legacy building ids are migrated (see `TRADE_BUILDING_ALIASES`).

**Players only see new state after reloading the page** — there is no polling.

---

## 2. Repository layout

| Path | Purpose |
| :-- | :-- |
| `index.html` | **The entire application** (~4,200 lines of markup/CSS/JS plus the embedded `mapdata` and `codexdata` JSON). The only file that runs in production. |
| `campaign.json` | Live game state. Written by the page via the GitHub API; each commit is titled `Turn N — Season Year`. |
| `assets/map_assets.js` | Base64 province colour-map, terrain texture and relief heightmap. |
| `assets/emblems.js`, `emblems_extra.js`, `emblem_aliases.js` | Faction emblems (`EMBLEMS[factionId]`) and alias mapping. `emblems.js` is ~25 MB. |
| `assets/codex_icons.js` | Unit icons for the Codex (`CODEX_ICONS`, `CODEX_ICON_MAP`). |
| `assets/trade_buildings.js` | `TRADE_BUILDINGS`: the 20 level-1–5 income buildings (cost + revenue per level). |
| `Faction Icons/`, `Unit Icons/`, `Unit Icons.rar` | Source artwork; compiled into the `assets/*.js` files by scripts. |
| `unit.md` | Raw unit roster (tier, name, recruitment cost per faction). |
| `vercel.json`, `package.json` | Vercel config; build command runs `scripts/inject-token.js`. |
| `scripts/inject-token.js` | Build step: replaces `__GH_TOKEN_PLACEHOLDER__` in `index.html` with `$GH_TOKEN`. |
| `scripts/build_*.py`, root `*.py` | One-off / maintenance Python tools (map sync, roster ingest, icon build, repair). See [§16](#16-offline-tooling-python-scripts). |
| `TASK.md` | The brief the self-service turn system was built from (kept for context). |
| `AGENTS.md` | Rules for autonomous AI agents working in this repo. |

---

## 3. Data model — `campaign.json`

Top level (`S` in the code):

| Key | Type | Meaning |
| :-- | :-- | :-- |
| `title`, `w`, `h`, `sea` | misc | Campaign name, map size (3821 × 2687), sea colour. |
| `turn`, `year`, `season` | int/str | Campaign clock. `season` ∈ Spring, Summer, Autumn, Winter; the year increments when Spring starts. |
| `factions[]` | array | Realms — see §4. |
| `provinces[]` | array | The map tiles — see §5. |
| `armies[]` | array | Hosts in the field — see §8. |
| `order[]` | array of faction ids | Turn order for the current round (NPC factions excluded). |
| `active` | int | Index into `order[]` of the realm whose turn it is. |
| `moved[]` | array of faction ids | Realms that have already ended their turn this round. |
| `pendingReview` | bool | `true` once every realm has moved; locks all players until the GM resolves the round. |
| `allowance` | int | Movement points per move (currently `3`). |
| `wars[]`, `allies[]` | `"A\|B"` strings | Unordered pairs, stored sorted alphabetically. |
| `truces` | `{ "A\|B": seasonsLeft }` | Truces tick down each season resolution. |
| `battles[]` | array | Staged battles awaiting an outcome. `fought{}` counts battles per province (for "Second Battle of …"). |
| `crossings[]`, `rivers[]` | arrays | Province-pair keys with a great-ford river crossing (+1 move). Currently empty in the live data. |
| `log[]` | array | Chronicle: `{t, d, txt, kind, detail}` newest first. `kind` is `""`, `"turn"` or `"battle"`. |
| `turnlog[]` | array | Per-turn map snapshots for the **Turn map** timeline (capped at 200). |
| `hmax` | number | Heightmap max, used by relief shading. |

**Faction**: `{id, name, color, treasury, capital, zeal, npc?}`.

**Province** (only `playable: true` tiles take part in the game):
`id`, `modern`, `displayName`, `owner` (faction id or `null`), `tier` (0–4), `terrain` (`plains`/`hills`/`mountain`), `value` (revenue), `move` (entry cost 1–3), `garrison`, `bld[]` (built ids), `bldLevel{}`, `bldOwner{}`, `availableBld[]` / `availableBldOwner{}` (buildings the GM has unlocked for a realm here), `buildQueue[]`, `upg` (pending settlement upgrade), `siege` (`{by, turns}`), `occ` (`{by}`), `raid` (`{by}`), `adj[]`, `cx`/`cy` (label position), `coastal`.

**Army**: `{name, faction, at, men, units[], xp[], upkeep, order, fort?, holy?}`.
`units[]` holds codex `unit_key`s (one per regiment); `men` and `upkeep` are re-derived from it (`syncMen`). Armies without `units[]` are legacy "free-form" hosts (just a `men` count).

---

## 4. Factions & realms

There are ~38 factions in `campaign.json`; 28 of them are in the playable `order[]` (the rest are NPC/regional factions the GM controls). Playable realms with a turn passphrase: Anduin Vale, Dale, Dol Amroth, Dol Gul Dur, Dorvinion, Dunland, Erebor, Ered Luin, Ered Mithrin, Goblins, Gondor, Gundabad, Imraldris, Iron Hills, Isengard, Khand, Khazad-dum, Lindon, Lostladen Tribes, Lothlorien, Mahud, Mordor, Rachrohir, Rhudaur, Rhurrim, Rohan, Umbar, Woodland Realm.

Each realm has a **treasury** (castas), a **capital** province, and **Zeal**. The *realm sheet* (click a realm in the legend) shows provinces held, income breakdown, upkeep, net income per turn, Zeal, hosts, host cap, capital and diplomatic relations.

- **Capital loss:** if a province that is a realm's capital changes hands (annex, siege fall, GM reassign), the capital is cleared and the chronicle records it. The GM picks a new one (the realm sheet has a "clear capital" ✕).
- **Realm names / colours / emblems** are editable by the GM (name, colour picker). Realms can be created (**+** in the legend) and dissolved (realm sheet → *Dissolve realm…*, two-click confirm; frees its land and removes its armies, wars, alliances, truces and turn slot).

---

## 5. Provinces, settlements & economy

### Currency
All money is **castas**. Income and upkeep are settled when the GM resolves the season (§11).

### Settlement tiers

| Tier | Name | Revenue/season | Default garrison | Siege |
| :-: | :-- | --: | --: | :-- |
| 0 | Village | 250 | 50 | none — falls by occupation |
| 1 | Unfortified town | 500 | 200 | none — falls by occupation |
| 2 | Fortified city · small | 850 | 600 | 3 seasons |
| 3 | Fortified city · large | 1,300 | 1,200 | 4 seasons |
| 4 | Grand city | 1,900 | 2,000 | 5 seasons |

Siege length (`holdout`) = base (3 / 4 / 5 for tier 2 / 3 / 4) **+1 Port, +1 Granary, −1 Synagogue**, minimum 1.

### Settlement upgrades

| To tier | Cost | New revenue |
| :-: | --: | --: |
| 1 | 2,000 | 500 |
| 2 | 4,000 | 850 |
| 3 | 7,000 | 1,300 |
| 4 | 11,000 | 1,900 |

Upgrades are **queued and paid immediately**, then completed by the GM (§6). Completing sets the tier, garrison and revenue.

### Income formula (per realm, per season)

```
income  = Σ over owned, un-occupied playable provinces ( province.value + Σ trade-building revenue )
        + Σ revenue of provinces this realm is raiding            (raided provinces pay the raider, not the owner)
        + 5% of the above × (number of Synagogues the realm owns)
upkeep  = round( Σ army upkeep × 0.20 ) + round( Σ barracks upkeep × 0.20 )
treasury ← max(0, treasury + income − upkeep)
```

- **Occupied** provinces (`occ` set) pay nobody.
- **Upkeep discount:** a global constant `UPKEEP_DISCOUNT = 0.80` means every realm pays only **20 %** of nominal upkeep (armies and barracks). It is changed by hand in the source, never automatically.
- **Army upkeep** = sum of its regiments' codex `upkeep` (falls back to `men × 2.1` for free-form hosts). **Holy (crusade) hosts pay nothing.**
- **Barracks upkeep** per level: I 50, II 100, III 175, IV 275 (before discount).
- If a realm cannot pay, the treasury is floored at 0 and the chronicle notes the shortfall — the GM decides what suffers.

---

## 6. Buildings & the construction queue

### Standard buildings (`BLD`)

| Building | Notes (values from code) |
| :-- | :-- |
| **Barracks** | Level 1–4. Build cost 1,000; upgrade to L2/L3/L4 costs 2,000 / 3,500 / 5,500. Level N lets a province recruit units of tier ≤ N. Requires tier ≥ 1. Upkeep per level above. |
| **Road** | Entry cost becomes 1 and bridges a river crossing. Not allowed in mountains. |
| **Port** | Needs a coastal province, tier ≥ 1. +1 siege season. |
| **Granary** | +1 siege season. |
| **Market, Slave Market, Moria Mines, …** | Defined with cost/effect text; several are "custom" buildings (cost 0 in the table) that the GM prices/assigns by hand. |
| **Synagogue** | Tier ≥ 2, max 2 per realm. +5 % revenue each, −1 siege season, lowers the realm's Zeal ceiling by 1 each. A realm can *expel the community* (1,500 castas, +1 ✦) which permanently bars a new one in that city. |
| **Church** | Max 2 per realm. +1 ✦ per season each. |

### Trade buildings (`assets/trade_buildings.js`)
22 buildings, **levels 1–5**, each with `[build/upgrade cost, revenue per season]` per level — e.g. Gold Mine `[750,50] → [4500,400]`, Grain Farm `[500,50] → [3500,325]`. Their revenue is added into the province's income. Two entries are special:
- **Slavers' Market** (`slavers_market`, replaces the old `slavemarket`; tier ≥ 1): revenue 40 / 75 / 125 / 200 / 300 — deliberately lower at every level than the weakest mine (Copper: 50 / 100 / 150 / 250 / 350). Keep it below every mine if you retune either.
- **Blacksmith** (`blacksmith`, no revenue, costs 750 / 1,250 / 2,000 / 3,000 / 4,500): regiments **mustered or reinforced on that exact province** start with **chevrons (`xp`) equal to the Blacksmith level** (L1 = +1 … L5 = +5, max 9) — **but only if the province also has a Barracks** (`forgeRank()`). It applies to new hosts, reinforcements (new regiments only) and imported `RQ1` plans; existing regiments are unchanged. Built and upgraded through the normal construction queue.

Old ids are auto-migrated (e.g. `vineyards → winery`, `timber → timber_yard`).

### How construction works (important)

1. **The GM makes a building *available*** to a realm on a province (province drawer → *Adjust* → "Make buildings available to…"). Players can only see/queue what has been made available to them. (Barracks upgrades, trade-building upgrades and settlement upgrades on one's own provinces are offered directly.)
2. **Queueing pays up-front.** The cost is deducted from the payer's treasury immediately and a job is added to the province's `buildQueue` (or `upg` for a settlement upgrade).
3. **The GM completes or declines each job** in the province's *Construction queue* panel. *Complete* applies the effect (new building, level, or tier) and removes the job. *Decline* removes it and **refunds** the payer.
4. A player may cancel their own queued job (while it is their turn) — handled through the same refund path.

Nothing completes automatically at season end — construction is always a GM decision.

---

## 7. Units & recruitment

### The Codex (unit roster)
`<script id="codexdata">` holds **575 units** across 36 rosters. Each unit: `unit_key`, `name`, `faction`, `tier` (1–4), `cost` (recruitment, castas), `upkeep`, `men`, `class`/`category`, `missile`, `mounted`. Press **C** (or the *Codex* button) to open it; it can filter by realm/faction/class, sort, and show a stat panel for each regiment.

- **Regional (AOR) and mercenary** units are listed under the realm that recruits them (`AOR_ROSTERS`), e.g. Beorning/Eotheod/Greenwood units under Anduin Vale. Units from the "wrong" roster are allowed but flagged to the GM ("foreign unit(s), your call").
- **Army size cap: 20 regiments per host** (`CAPU`).
- **Chevrons (veterancy):** each regiment has an `xp` rank 0–9, edited by the GM.

### How a player recruits (live, on their own turn)

Prerequisites (all enforced in the UI):
1. It is the realm's turn, the player has unlocked the realm, and no round is pending GM review (`canAct`).
2. The recruiting province is **owned by that realm** and has a **Barracks**.
3. Every new regiment's **tier ≤ the Barracks level** there.
4. The treasury covers the **total cost** (checked per regiment as it is added).

Two ways in:
- **New host:** select an owned province → **⚔ Muster & Recruit Army Here** (`bMusterTile`) → pick regiments in the Codex → **⚔ Muster to Map**. The host appears at that province and the cost is deducted at once.
- **Reinforce an existing host:** open a host in the province drawer → *Recruit* → add regiments → **⚔ Muster to Map**. Only regiments added in this session can be taken back; the existing roster is fixed. The host must be standing in its own realm's territory on a Barracks.

Charged cost = total cost of the final roster − the cost already paid for it. Crusade ("holy") hosts are free.

### Army plan codes (offline drafting)
A player can draft an army without it being their turn using **Build army / planner** — plans are free to draft. **Copy for GM** produces:

```
═══ ARMY PLAN — Gondor ═══
4/20 units · 480 men · 3,450g raise · 1,725g/turn upkeep
  1× Gondor Sword Militia
  …
▸ CODE (paste to the GM):
RQ1|Gondor|gondor_gondor_sword_militia,gondor_aor_ringlovale_men_at_arms,…
```

The GM pastes the `RQ1|<realm>|<unit_key,…>` line into **Import plan**; it validates the realm, unit keys and the 20-unit cap, then musters at the selected province (or the realm's capital). The GM bypasses the Barracks rules; the treasury must still cover the bill.

---

## 8. Armies & movement

### Movement
- **Allowance:** `S.allowance` = **3 movement points** per move.
- **Entry cost** of a province = its `move` (plains 1, hills 2, mountain 3); **1** if it has a **Road**; **+1** to cross a river crossing unless the destination has a Road.
- **Enemy ground:** a realm at war with the owner of a province may enter it but cannot move on from it in the same move (it ends the march).
- Selecting one of your hosts on your turn highlights every province in reach (Dijkstra over the allowance). Clicking a highlighted province moves the host **immediately** and logs `X moved A → B`. Out-of-reach clicks are rejected for players.
- Moving a host abandons its fort (see Entrench, §10).
- The GM can move any host **anywhere with no limit** (click host, click destination).

> The code does **not** track movement spent across multiple moves in one turn — see §14.

### Managing hosts
Each host card (province drawer) shows regiments, men, and — for the GM — reassign realm, edit men, rename, **Split** (halves the men into a detachment), **Merge here** (combines same-realm hosts in a province), disband, chevron editing and Entrench. Clicking a host name opens its full muster roll in the Codex.

---

## 9. Battles, sieges & occupation

### Battles
- When hosts of two or more realms share a province, the GM presses **⚔ Stage battle**. The battle is **fought in Total War: Attila** (the map matches the province terrain; an entrenched host gets the fort map) and the outcome is recorded here.
- **Record outcome:** the GM picks the victor and enters each side's losses. Losses are spread across that side's hosts proportionally and removed **regiment by regiment, cheapest first** (`applyLoss`); each struck regiment is named in the chronicle. A draw ends "without decision".
- **Defeat:** each losing host with men left retreats to an adjacent province owned by its realm; hosts reduced to 0 men are destroyed.
- Ransom, force-march battlefield choice and allied reinforcement are story rules adjudicated by the GM, not coded.

### Occupation
Realm sheet / province drawer → **Claim**:
- **Occupy** — stripes the province; it pays nobody and **annexes automatically** when the GM resolves the season.
- **Annex now** — immediate ownership change. **Zealous annex (1 ✦)** — immediate annex of an occupied province.
- **Raid (2 ✦)** — the province's next season of revenue goes to the raider instead of its owner.

### Sieges (tier ≥ 2 only)
- **Besiege** starts a siege clock = `holdout` seasons. At each season resolution every siege clock drops by 1; at 0 the city falls to the besieger.
- GM tools: ±1 season, lift siege, **Sabotage (2 ✦ from the defender; +1 season)**, **Bribe the gates (3 ✦ + 1,500 castas from the besieger; −1 season)**.

---

## 10. Zeal, war & diplomacy

### Zeal (✦)
- **Gain:** +1 per season, **+1 per Church** the realm owns, resolved with the season.
- **Cap:** `10 − (number of Synagogues owned)`. (The in-game Rules text says "bank of 6"; the code's ceiling is 10.)
- **Spending (coded):**

| Cost | Action |
| :-: | :-- |
| 1 ✦ | Declare war (waived if the GM grants cause — then free); Zealous annex |
| 2 ✦ | Raid; Sabotage a siege |
| 3 ✦ + 1,500 | Bribe the gates; **Entrench** (host raises a fort — battles there use the fort map until it marches) |
| 10 ✦ | **Crusade / Jihad** — spawns a free "holy" host above the cap, no upkeep; disbands when the realm is no longer at war with anyone |
| −3 ✦ | Penalty applied when the GM records *breaking a truce* or *betraying an ally* ("INFAMY") |

Force March, Ransom and the +2 ✦ for losing a capital are in the Rules text but are applied by the GM by hand (edit Zeal on the realm sheet).

### Diplomacy (realm sheet → *Relations*, GM-only buttons)
War, Peace, **Truce (2 seasons, ticks down automatically)**, End truce, Ally, Unally, and the two infamy actions above. All are written to the chronicle. Realms can also **gift castas** to each other (GM-recorded, chronicled). Official talks happen on Discord; the GM opens private channels.

### Victory
Per the Rules: conquer the capitals of three other realms. Not tracked in code.

---

## 11. Turn-based play: the round cycle

A **round** = every realm in `order[]` takes one turn; then the GM resolves the **season**. Four seasons make a year.

```
 ┌──────────── round (one season) ────────────┐
 │ realm 1 → realm 2 → … → realm N            │   players, each on their own turn
 └──────────────────────┬─────────────────────┘
                        ▼
        pendingReview = true   (everyone locked)
                        ▼
        GM presses "Next realm ▸"  → season resolution
                        ▼
        turn++, season advances, moved[] cleared, active → first realm
```

### 11.1 State that drives it
- `order[]` — who goes in what order. `active` — index of the current realm. `moved[]` — realms that have finished this round. `pendingReview` — end-of-round lock.
- The "next" realm is always **the first realm in `order[]` that is not in `moved[]`**, not simply `active + 1`. This means the GM can reshuffle the order mid-round without anyone being skipped or getting a second turn.

### 11.2 The turn gate (top bar, players only)
`renderTurnGate()` shows one of:

| State | Message | Controls |
| :-- | :-- | :-- |
| It is *not* your realm's turn | `Waiting for <Realm>` | **This is my realm — unlock** (opens the passphrase prompt for the *current* realm) · **Just skip to mine** (§11.4a; shown while any other un-moved realm has a passphrase) |
| You unlocked the active realm | `Your turn, <Realm> — unlocked` | **End turn** |
| Round complete | `Turn complete — awaiting GM review` | none |

`canAct(fid)` is the single permission check used for every player action (move, recruit, reinforce, build, upgrade, cancel):

```js
canAct(fid) = gm
           || ( factionAuth && !S.pendingReview
                && factionAuth === activeFactionId() && factionAuth === fid )
```

### 11.3 Unlocking a realm
- The passphrase map `FACTION_PASSWORDS` lives in `index.html`: faction id → **SHA-256 hex digest** of the passphrase (never plaintext).
- To set or change one, open the browser console on the page and run `await sha256("the passphrase")`, then paste the result into `FACTION_PASSWORDS`. Keys must match faction ids exactly.
- A correct passphrase sets `factionAuth` (stored in `sessionStorage`, so it lasts for that tab/session). Because `canAct` also requires `factionAuth === activeFactionId()`, an unlocked tab goes read-only as soon as the turn passes, and becomes active again automatically when that realm's turn next comes round in the same session.
- Normally only the realm whose turn it is can be unlocked; every other realm sees the read-only "waiting" view — unless it uses **Just skip to mine** (§11.4a).

### 11.4a Just skip to mine (player skip-ahead)
For when the active player is AFK and everyone is stuck waiting. Next to *This is my realm — unlock*, a waiting player presses **Just skip to mine**:
1. The passphrase dialog opens with a realm picker listing `skipCandidates()` — every realm in `order[]` that is **not** the active realm, **not** in `moved[]`, and has a `FACTION_PASSWORDS` entry. The player picks their realm and enters **their own** passphrase (they can only skip as a realm whose passphrase they know).
2. On success (`pwGateTry` in `"skip"` mode): undo snapshot, `S.active` is set to the chosen realm, the realm is unlocked (`factionAuth`), and the chronicle records `"<Realm> grew tired of waiting on <Slow realm> and skips ahead — <Slow realm> keeps its turn for later this round."`
3. It works exactly like the GM's **Set active**: the skipped realm is **not** marked as moved. The skipper plays and presses **End turn**, which adds them to `moved[]` and hands the turn to the first un-moved realm — normally the skipped realm, which gets its turn back.
4. Nothing is published until End turn; if the skipper reloads without ending, the skip is lost.

Because a skip means two people may be playing at once (the skipper and the slow player in a stale tab), player **End turn** publishes with a **stale-page guard** (`publishTurn({guard:true})`): it reads the live `campaign.json` and refuses to write if its `turn` differs or its `moved[]` contains a realm this page doesn't know has moved. Whoever ends second is told to reload and redo their turn, instead of silently wiping the other's. The GM's **⇧ Publish** is not guarded.

### 11.4 Taking a turn (player)
With the realm unlocked, the player may, in any order: **move hosts**, **recruit/reinforce**, **queue buildings, barracks/trade-building upgrades and settlement upgrades**, and cancel their own queued work. All of this happens **locally in the browser** and is written to the chronicle — nothing is shared until **End turn**. (Diplomacy, claims, sieges, battle staging, treasury edits and everything else listed in §13 remain GM-only.)

### 11.5 End turn (`endTurn()`)
1. Requires `canAct(active realm)`. Shows a **confirm dialog** ("This publishes immediately and locks <Realm> out…").
2. Takes an undo snapshot, adds the realm to `moved[]`.
3. Advances `active` to the first un-moved realm (the round only closes when *no* realm is left un-moved, regardless of who sits in the last slot) and logs `"<Realm> ends its turn — <Next> to move."` — **or**, if it was the last realm / nobody is left, sets `pendingReview = true` and logs `"…every realm has moved this round. Awaiting GM review."`
4. Calls `publishTurn()` (§15).
5. **On success:** toast, UI re-renders for the next realm. **On failure:** `active`, `moved`, `pendingReview` and the log line are rolled back, and the player is told to try again. *(Only the turn bookkeeping is rolled back — the player's own moves/recruits for that turn remain in the in-memory state.)*

### 11.6 Season resolution (GM, "Next realm ▸" after the round is complete)
When no realm is left un-moved, the GM's **Next realm ▸** runs the season, in this order:

1. Queued **army orders** (`a.order`, legacy) execute.
2. **Occupations annex** — each striped province changes owner (capital-loss handling applies).
3. **Siege clocks −1**; clocks reaching 0 are starved out and the city changes hands.
4. **Income** is gathered per realm: province values + trade-building revenue; raids redirect revenue to the raider; Synagogue +5 % each.
5. **Upkeep** (armies + barracks, ×0.20) is deducted; treasury floored at 0 with a chronicle warning.
6. **Zeal** `+1 + churches`, capped at `10 − synagogues`.
7. **Truces tick down**; expired truces are announced.
8. `turn++`, season advances (Spring → Summer → Autumn → Winter → Spring, year++ on Spring), `moved[] = []`, `pendingReview = false`, `active` returns to the first realm. A chronicle line "`<Season> <Year> opens — the round begins with <Realm>.`" is written, followed by the events above.

Construction is **not** part of this step (§6). The GM should then press **⇧ Publish** to push the resolved season.

### 11.7 GM overrides to the automated flow
- **Set active** (Order dialog) — hand the turn to a specific un-moved realm, e.g. an AFK player's next neighbour, without marking anyone as moved.
- Players can skip ahead of a stalled realm themselves with **Just skip to mine** (§11.4a), so most AFK cases no longer need the GM.
- **Next realm ▸** — skips/finishes the current realm (marks it moved and passes the turn): this is the "force-skip" for a stuck or inactive player.
- **Order** — reorder realms with ↑↑ / ↑ / ↓; new realms can be inserted at a chosen slot.
- **Set turn** — manually set the campaign turn number.
- **Load / Save** — load a `campaign.json` from disk (restores turn state, factions, provinces, armies, wars…) or download the current state.
- **Undo** (Ctrl+Z) — step back through the GM's/players' edits this session.
- GM mode ignores `canAct`, so the GM can edit anything at any time, regardless of turn or `pendingReview`.

---

## 12. Player controls

| Action | How |
| :-- | :-- |
| Pan / zoom | Drag; mouse wheel zooms to cursor; double-click zooms in; `+`/`-`; **F** fits the map |
| Open a province | Click it (drawer shows owner, tier, garrison, revenue, terrain, movement cost, hosts, works, construction) |
| Find a province | **/** then type, Enter to jump |
| Map modes | **1** Political · **2** Settlements · **3** Wealth · **4** Terrain; **R** toggles relief shading |
| Realm sheet | Click a realm in the left legend |
| Codex (unit browser) | **C** / *Codex* button |
| Chronicle / Wars / Battles | **Ledger** button |
| Turn map timeline | **Turn map** — how the map stood each turn |
| Help / Rules | **?** panel; **Rules** opens the full campaign rules document |
| Unlock realm | When it is your realm's turn: **This is my realm — unlock** → passphrase |
| Skip a slow realm | **Just skip to mine** → pick your realm → your passphrase → play → **End turn** (the skipped realm moves after you) |
| Move a host | Click host → click a highlighted province (≤ 3 movement) |
| Recruit | Own province with Barracks → *Muster & Recruit Army Here* → Codex → **⚔ Muster to Map** |
| Reinforce | Host card → *Recruit* → add regiments → **⚔ Muster to Map** |
| Build / upgrade | Province drawer → Works: queue an available building, upgrade Barracks / trade building / settlement |
| End your turn | **End turn** → confirm. Irreversible; publishes to GitHub |
| Draft for later | Codex planner → **Copy for GM** (an `RQ1|…` code) |

Players cannot act on other realms, change diplomacy, claim land, stage battles, edit numbers or publish manually.

---

## 13. GM controls

Enter **GM mode** with the **GM** button (or **G**) and the GM passphrase (SHA-256 hash `GM_HASH` in `index.html`; session-remembered). In GM mode the `.gm` elements appear and the `canAct` check is bypassed.

| Area | Capability |
| :-- | :-- |
| **Turn flow** | **Next realm ▸** (advance / skip / resolve season), **Order** (reorder, *Set active*), **Set turn**, `pendingReview` handled by resolving the season |
| **Publish** | **⇧ Publish** — commit current state to GitHub (§15) |
| **Files** | **Save** (download `campaign.json`), **Load** (from disk), **Export** (full-map PNG), **Undo** (Ctrl+Z) |
| **Map editing** | Province drawer *Adjust*: holder, display name, tier, terrain, garrison, revenue, notes. **Claim brush** ✎ (click provinces to claim for a realm); **Shift-drag** box-select, **Ctrl-click** multi-select, then click a realm to claim many (stripes annex at season end); right-click clears selection |
| **Realms** | Create/dissolve realms, rename, recolour, edit treasury and Zeal, **Gift castas**, **GM treasury adjustment**, clear/reassign capital |
| **Armies** | Move any host anywhere, edit men, reassign realm, rename, split, merge, disband, chevron ranks, Entrench, raise a free-form host, import `RQ1` plans, convert a free-form host to a codex host |
| **Construction** | Make buildings available to a realm per province, **Complete** / **Decline (refund)** queued jobs, set custom building cost/owner |
| **War** | Stage battles, record outcomes (victor + losses), call off, start/lift/adjust sieges, occupy/annex/zeal-annex/raid, diplomacy (war, peace, truce, ally, break/betray) |
| **Zeal** | Edit directly; Crusade/Jihad button (10 ✦) |
| **Passwords** | Edit `FACTION_PASSWORDS` / `GM_HASH` in source (hashes only) |

A typical GM session between rounds: pull latest → review the chronicle and queued constructions → complete/decline works → stage and record battles → adjudicate diplomacy/claims → press **Next realm ▸** to resolve the season → review → **⇧ Publish**.

---

## 14. Known gaps — things the code does not enforce

These are accurate as of this writing; they are *design realities*, not necessarily bugs, but are worth knowing before relying on them.

- **Host cap is informational.** The realm sheet shows `min(1 + ⌊provinces/4⌋, 1 + barracks count)`, but no code stops a player mustering more hosts than that. Older notes describing per-class composition limits (pike/missile/cavalry/artillery caps) and rank-based upkeep percentages are **not implemented** — the only limits are 20 regiments per host and the flat 80 % upkeep discount.
- **Movement is not cumulative.** Each move is checked against the full 3-point allowance from the host's current position; spent points are not remembered, so a host can be moved repeatedly in one turn. The GM review step (and trust) is the control.
- **Rules text vs. code:** the Rules document lists Barracks at 5,000 and a Zeal bank of 6; the code uses Barracks 1,000 (+ upgrades) and a Zeal cap of 10 (− synagogues). Market/Port/Road are listed as cost 0 in `BLD` and are priced by the GM. Force March, Ransom, "capital lost +2 ✦" and victory conditions are narrative.
- **Publishing overwrites the whole file** from the publisher's in-memory state after fetching only the latest `sha`. There is no merge. If two people publish from stale pages the later write wins; the turn gate (one active realm at a time) is what prevents this in practice. Player **End turn** has a stale-page guard (§11.4a) that refuses if another realm ended its turn since the page loaded; GM publishes are unguarded. Players should reload before their turn.
- **Players do not auto-refresh.** A player must reload to see others' turns.
- **Client-side secrets (accepted trade-off).** The GitHub token and all passphrase hashes are readable in the page. This was a deliberate decision (burner token account; trusted players) — see [§15](#15-publishing-hosting--secrets). The GM gate also contains a hard-coded plaintext passphrase fallback in `gmTry()`; removing it so only `GM_HASH` is accepted is an easy hardening step.
- **Stuck-round repair:** on load, if `pendingReview` is set but some realm is not in `moved[]`, the lock is cleared and `active` is set to the first un-moved realm (`index.html` ~697). Earlier versions closed the round when the *last slot* realm ended its turn early; now only an empty un-moved list closes it (`endTurn` and the `bTurn` wrapper).
- **A failed End turn** rolls back only turn bookkeeping, not the player's moves/recruitment that turn.
- **Construction never auto-completes** — it waits for the GM.

---

## 15. Publishing, hosting & secrets

### `publishTurn()`
1. Target: `crokator0012-commits/ZeCampain`, file `campaign.json` (`ghTarget()`).
2. `GET /repos/{o}/{r}/contents/campaign.json` to fetch the current `sha` (HTTP 401/403/404 → "Token rejected — the GitHub token in index.html needs to be updated").
3. `PUT` the same path with the base64 of `JSON.stringify(S, null, 1)`, the `sha`, and the message `Turn <turn> — <Season> <year>`.
4. Returns `true`/`false`; the **⇧ Publish** button shows "Publishing…" meanwhile. The GM button requires GM mode; **End turn** calls the same function for players.
5. Vercel redeploys on the new commit; players see it after a reload (≈ a minute).

Required token scope: **`repo`** (contents write).

### Token handling
`GH_TOKEN` in `index.html` is the literal placeholder `__GH_TOKEN_PLACEHOLDER__` in git. GitHub secret scanning auto-revokes any real token committed to the repo, so the real value lives only in the **Vercel project environment variable `GH_TOKEN`**. On every build (`vercel.json` → `npm run build` → `scripts/inject-token.js`) the placeholder is replaced in the deployed copy. The script aborts the build if `GH_TOKEN` is unset or the placeholder doesn't occur exactly once. **Never paste a real token into the source.** To rotate: update the env var in Vercel and redeploy.

Deliberately, there is no serverless function or backend (see `TASK.md`).

### Other persistence
- `sessionStorage`: GM unlock flag (`gmOK`) and realm unlock (`rqFactionAuth`).
- `localStorage`: `rqCampaignState` (cached province display names), `rqRepo` (fallback raw-GitHub source).

---

## 16. Offline tooling (Python scripts)

Run from the repository root; most need Pillow/numpy. These regenerate data and assets, they are not part of the running game.

| Script | Role |
| :-- | :-- |
| `sync_all.py` | Master pipeline: ingest unit icons, rebuild rosters, process map-tile masks, update campaign data. |
| `update_unit_roster.py` | Build the codex roster from the Dawnless Days CSV (`DAWNLESS_DAYS_CSV` or `dawnless_days.csv`). |
| `implement_factions.py`, `add_regional_factions.py` | Inject new factions/rosters. |
| `generate_middle_earth_map.py`, `sync_middle_earth.py`, `sync_painted_tiles.py` | Build/refresh the province map, terrain texture and relief shading from source images. |
| `compress_icons.py`, `scripts/build_unit_icons.py`, `scripts/build_emblems_extra.py`, `fix_emblems_dedup.py` | Compress and encode emblem/unit icons into `assets/*.js`. |
| `deploy_campaign.py` | Embed `campaign.json` into `index.html`'s fallback `mapdata`. |
| `split_province_*.py`, `patch_unclaimed_white.py`, `apply_armies_fix.py`, `fix_script_order.py` | One-off repairs of specific map/data problems. |
| `check_*.py`, `verify_sync.py`, `compare_layers.py`, `analyze_test_map.py`, `inspect_*`/`tools_inspect.py` | Diagnostics and validation. |
| `modularize.py` | Historical: split large inline data out of `index.html` into `assets/`. |

Because several scripts rewrite `index.html`, back it up first and review the diff.

---

## 17. Developer notes

- **Always pull first.** Players publish `campaign.json` commits straight to `main` from the live site. Run `git fetch`, inspect, and `git pull --rebase --autostash origin main` **before committing and again before pushing**. Never overwrite `campaign.json` with a stale local copy and never force-push `main`.
- Gameplay code lives in `index.html`; `campaign.json` should only change via the app (or deliberate GM data fixes).
- Preserve the schema (§3) when adding provinces/factions; new playable tiles need `adj`, `tier`, `value`, `garrison`, `bld`, `bldLevel`, `buildQueue`.
- Don't put heavy work or new listeners inside the render loop `draw()`.
- Any new player-facing action must be gated through `canAct(fid)`; GM-only UI uses the `.gm` class.
- Don't commit a real GitHub token; keep the placeholder (§15).
- `gm.html`/`player.html`/`index.html.bak` from earlier versions no longer exist as active files; everything is `index.html`.
- The in-game **Rules** button links to the campaign rules Google Doc; gameplay text embedded in `#rulesBody` is legacy (still lists the old Iberian realm order) and should not be treated as authoritative.

---

## 18. Code map for agents (navigate, don't read)

### What is huge (never open these in full)
| File / lines | Size | What it is |
| :-- | --: | :-- |
| `index.html` line 667 | ~196 KB, one line | embedded `mapdata` JSON copy of `campaign.json` |
| `index.html` line 3004 | ~154 KB, one line | `codexdata` — all 575 units |
| `index.html` line 3005 | ~196 KB, one line | `FLAG_LIBRARY` base64 flags |
| `assets/emblems.js` | 25 MB | faction emblems (base64) |
| `assets/codex_icons.js`, `map_assets.js`, `emblems_extra.js` | 2.4 MB / 1.8 MB / 0.7 MB | icons & map images (base64) |
| `campaign.json` | ~380 KB | live state; inspect with a script, e.g. `python -c "import json;d=json.load(open('campaign.json',encoding='utf-8'));print(d['turn'],d['active'],d['order'][d['active']])"` |

Use `Grep` with `-n` and `output_mode: content`, then `Read` with `offset`/`limit` (≈50–150 lines). Add `| cut -c1-300` in shell greps, because lines 667/3004/3005 will flood the output.

### `index.html` layout (line numbers at time of writing — re-grep the function name if they drift)
| Lines | Content |
| :-- | :-- |
| 1–396 | CSS (`.readonly .gm{display:none}` hides GM UI; `.player-view` shows turn-gate) |
| 397–666 | HTML: top bar (`#bTurn`, `#bPub`, `#turnGate`, `#tgUnlock`, `#tgSkip`, `#tgEndTurn`), legend, ledger, drawer, modals (`#gmask` GM prompt, `#pwGate` realm prompt + skip-ahead realm picker `#pwGateRealm`, `#help`, `#ordM` order dialog) |
| 667–682 | embedded data + `<script src="assets/…">` tags |
| 683–830 | load-time normalisation, `reconcileTurnOrder`, `UPG`, `BLD`, barracks/trade helpers (`barracksLevel`, `tradeIncome`), `atWar/isAllied`, `chargeZeal`, `toggleFort`, `holdout` (763), `effMove` (762) |
| 830–1110 | `boot`, map painting (`paintMap`, `colourOf`), view/zoom (`draw`) |
| 1173–1340 | labels, armies, settlements drawing; `snap`/`undo` (1311/1323), `loseCapitalIfNeeded`, `claim` |
| 1355–1512 | `reachableFrom` (movement), mouse/keyboard handlers, **`click` (1423 — player/GM move logic)**, `provAt` |
| 1513–1560 | `openProv` (province drawer) |
| 1561–1780 | `facIncomeCalc`, **`openRealm` (realm sheet, diplomacy, crusade, dissolve)** |
| 1785–1884 | `drawerArmies`, `bMusterTile` (legacy copy), `bRaise` |
| 1885–2163 | **`renderWorksBox`, `renderConstructionQueue`, `renderClaimBox`, `renderSiegeBox`** |
| 2169–2300 | `legend`, `stats`, `normalizeCampaignClock`, search, map modes |
| 2298–2368 | `GM_HASH`, `store` (sessionStorage), `sha256`, `setGM`, `gmTry` |
| **2379–2553** | **Turn gate:** `FACTION_PASSWORDS` (2383), `canAct` (2419), `reinforceBlocker`, `renderTurnGate` (2430), `skipCandidates` (2454), `tgSkip` "Just skip to mine" (2472), `endTurn` (2487), `pwGateTry` (2524, unlock + skip modes) |
| 2554–2585 | `logIt`, `UPKEEP_DISCOUNT`, `armyUpkeep`, `stageBattle` |
| **2586–2685** | **`bTurn` onclick — season resolution** (movement, annex, sieges, income, upkeep, zeal, truces, clock) |
| 2636–2820 | ledger (`openLedger`, `drawLedger`), turn-map timeline |
| **2870–2940** | **`GH_TOKEN` placeholder (2890), `publishTurn` (2894, stale-page guard), `bPub`, Load/Save handlers** |
| 2934–2967 | turn snapshots (`turnlog`) |
| 3006–3350 | Codex: `AOR_ROSTERS`, `canServe`, `unitTier`, `cxRender`, `openCodex` |
| 3355–3545 | `.army_setup` export for Attila |
| **3547–3714** | **Recruitment:** `planText`, `parsePlan`, `musterPlan` (3591), **`cxMusterMap` onclick (3643)**, add/remove regiment handlers |
| 3786–3945 | Recruit-here button, drawer armies/roster, split/merge |
| 3946–4005 | `applyLoss`, battle-result handler (wrapped `drawLedger`) |
| 4026–4088 | flag library + new-realm picker |
| **4157–4260** | **Turn-order module:** wrapper around `bTurn` (4169) that uses `moved[]`, `setActiveManually` (4215), `paintOrder`, `insertRealmAt` |

Note that some handlers are **wrapped later in the file** (`bTurn` is assigned at 2536, wrapped at 3960 and again at 4108; `drawLedger` is wrapped at ~3962; `bMusterTile` is assigned at 1856 and 3787 — the later one wins). Always grep for every assignment (`grep -n '\$("bTurn").onclick' index.html`) before editing.

### "Where do I change…?"
| Task | Go to |
| :-- | :-- |
| Realm passphrase | `FACTION_PASSWORDS` (~2383); generate with `await sha256("pw")` in the browser console |
| What a player may do / when | `canAct` (~2419) and its call sites (`grep -n 'canAct(' index.html`) |
| End turn / round-complete logic | `endTurn` (~2487) and the `bTurn` wrapper (~4169) |
| Player skip-ahead | `skipCandidates` (~2454), `tgSkip` onclick (~2472), skip branch of `pwGateTry` (~2524) |
| Season income, upkeep, zeal, clock | `bTurn` handler (~2586) |
| Upkeep discount | `UPKEEP_DISCOUNT` (~2556) |
| Settlement costs / revenue | `UPG` (~735), `SETTLEMENT_REVENUE`, `GARR` |
| Building costs / barracks levels | `BLD`, `BARRACKS_UPGRADE_COST`, `BARRACKS_UPKEEP` (~743), `assets/trade_buildings.js` |
| Movement allowance / terrain | `campaign.json` `allowance`, province `move`; `reachableFrom` (~1355), `effMove` (~762) |
| Siege length | `holdout` (~763) |
| Recruitment rules (barracks, tier, cost) | `cxMusterMap` (~3643), `musterPlan` (~3591), `reinforceBlocker` (~2412) |
| Army size cap | `CAPU` from `codexdata.cap` (20) |
| Publish target / commit message | `ghTarget`, `publishTurn` (~2894) |
| New unit / roster | `unit.md` + `update_unit_roster.py`/`sync_all.py` → regenerates `codexdata` |

### Cheap verification
- Syntax check without a browser: extract the main `<script>` blocks and run `node --check` on them (skip the giant data lines).
- State sanity: load `campaign.json` with Python and check `order`, `active`, `moved`, `pendingReview` consistency (`moved` ⊆ `order`; if `pendingReview` then every realm is in `moved`).
