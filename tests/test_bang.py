#!/usr/bin/env python3
"""
BANG! — Harnais de test & chasse au bug (stdlib only, zero dependency).

Usage:
    python3 test_bang.py [BASE_URL]      # defaut http://localhost:7777
    python3 test_bang.py --no-restore    # ne pas restaurer l'etat (debug)

Oracle de verite  : GET /session/export  -> JSON {params, voices:[{note,pattern,type}]}
Securite          : snapshot de l'etat au demarrage, restauration en fin de run.
Sortie            : rapport PASS/FAIL/WARN, exit code 1 si au moins un FAIL.

Cible explicitement les 5 regressions corrigees en session du 2026-05-27/29 :
  R1  generate non-deterministe (bug locked_voices=[0,1,2,3])
  R2  toutes les voix se regenerent (bug voix 2-4 hardcodees morph/markov/phase2/babka)
  R3  /vary modifie reellement (bug exclusion babka/cc)
  R4  /lock_voice fige la voix verrouillee, les autres mutent
  R5  front-end servi en local, pas de dependance CDN unpkg (htmx/sse)
"""
import sys, json, time, urllib.request, urllib.parse, urllib.error, hashlib, uuid

BASE = "http://localhost:7777"
RESTORE = True
for a in sys.argv[1:]:
    if a == "--no-restore": RESTORE = False
    elif a.startswith("http"): BASE = a.rstrip("/")

# ── HTTP ────────────────────────────────────────────────────────────────────
def _req(method, path, form=None, multipart=None, timeout=15):
    url = BASE + path
    data = None
    headers = {}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif multipart is not None:
        boundary = "----bang" + uuid.uuid4().hex
        field, filename, payload = multipart
        body = []
        body.append(f"--{boundary}".encode())
        body.append(f'Content-Disposition: form-data; name="{field}"; filename="{filename}"'.encode())
        body.append(b"Content-Type: application/json")
        body.append(b"")
        body.append(payload if isinstance(payload, bytes) else payload.encode())
        body.append(f"--{boundary}--".encode())
        data = b"\r\n".join(body)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"

def GET(p, **kw):  return _req("GET", p, **kw)
def POST(p, form=None, **kw): return _req("POST", p, form=form, **kw)

def export():
    """Oracle: renvoie le dict de session, ou None."""
    st, body = GET("/session/export")
    if st != 200: return None
    try: return json.loads(body)
    except json.JSONDecodeError: return None

def voices_sig(exp):
    """Signature des patterns de voix (tuple), depuis un export."""
    if not exp: return None
    return tuple(v["pattern"] for v in exp.get("voices", []))

def gen(mode="morph", chaos=1.0, steps=16, bpm=120, seed="", **extra):
    f = {"mode": mode, "chaos": chaos, "steps": steps, "bpm": bpm, "gravity": 0.7,
         "cc_depth": 0.5, "seed": seed, "microtiming": 1.0}
    f.update(extra)
    return POST("/generate", f)

# ── Framework de test minimal ───────────────────────────────────────────────
RESULTS = []  # (cat, name, status, detail)
def record(cat, name, status, detail="", info=""):
    RESULTS.append((cat, name, status, detail))
    sym = {"PASS":"\033[32m+\033[0m", "FAIL":"\033[31mx\033[0m",
           "WARN":"\033[33m!\033[0m", "SKIP":"\033[90m-\033[0m"}.get(status, "?")
    line = f"  {sym} [{cat}] {name}"
    if info: line += f"  ({info})"                      # diagnostic, toujours affiche
    if detail and status in ("FAIL", "WARN"):           # raison d'echec, seulement si KO
        line += f"  — {detail}"
    print(line, flush=True)

def ok(cat, name, cond, detail="", warn_only=False, info=""):
    record(cat, name, ("PASS" if cond else ("WARN" if warn_only else "FAIL")), detail, info)
    return cond

# ── Snapshot / restore ──────────────────────────────────────────────────────
SNAPSHOT = None
INITIAL_LOCKS = set()

def live_locks():
    """locked_voices lu en direct depuis /session/export (live, portable)."""
    exp = export()
    return set(exp.get("locked_voices", [])) if exp else set()

def snapshot():
    global SNAPSHOT, INITIAL_LOCKS
    st, body = GET("/session/export")
    if st == 200:
        SNAPSHOT = body
    INITIAL_LOCKS = live_locks()
    print(f"[snapshot] etat sauve ({len(SNAPSHOT or '')} o), locks initiaux={sorted(INITIAL_LOCKS)}")

def restore():
    if not RESTORE:
        print("[restore] saute (--no-restore)"); return
    # remet d'abord les locks a l'etat initial (avant import qui ne les touche pas)
    for i in live_locks() ^ INITIAL_LOCKS:   # toggle la difference symetrique
        POST("/lock_voice", {"idx": i})
    if SNAPSHOT:
        st, _ = POST("/session/import", multipart=("file", "restore.json", SNAPSHOT))
        print(f"[restore] /session/import -> {st}")
    print(f"[restore] locks remis a {sorted(INITIAL_LOCKS)}")

# ── Helpers locks (lecture live -> toggle deterministe) ──────────────────────
def ensure_unlocked(indices, tracker=None):
    """Force le deverrouillage des indices : lit l'etat live puis toggle si lock."""
    cur = live_locks()
    for i in indices:
        if i in cur:
            POST("/lock_voice", {"idx": i})

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║ TESTS                                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def t_smoke():
    cat = "SMOKE"
    core_200 = ["/", "/live", "/params/live", "/pattern", "/archive", "/grooves",
                "/presets", "/ksp/presets", "/midi/ports", "/files", "/doc",
                "/setup", "/session/export", "/next-filename", "/pianoroll/live"]
    for p in core_200:
        st, _ = GET(p)
        ok(cat, f"GET {p}", st == 200, f"status={st}")
    # endpoints toleres < 500 (peuvent 404/400 selon etat)
    soft = ["/browse", "/osc/log", "/export/strudel", "/touchosc", "/touchosc/minimal",
            "/ableton/sync_bpm", "/morph/prepare"]
    for p in soft:
        st, _ = GET(p)
        ok(cat, f"GET {p}", 0 < st < 500, f"status={st}", warn_only=True)

def t_frontend_local():
    """R5 : front-end servi en local, pas de CDN unpkg."""
    cat = "R5-frontend"
    st, body = GET("/")
    ok(cat, "index sert htmx local", "/static/js/htmx" in body, "ref /static/js/htmx absente")
    ok(cat, "index sans dependance unpkg", "unpkg.com" not in body,
       "unpkg.com encore reference !")
    for asset in ["/static/js/htmx.min.js", "/static/js/sse.js"]:
        st, body = GET(asset)
        ok(cat, f"asset {asset}", st == 200 and len(body) > 1000, f"status={st} len={len(body)}")
    st, body = GET("/live")
    for needle in ["sl-bpm", "sl-chaos", "btn-generate", "EventSource"]:
        ok(cat, f"/live contient '{needle}'", needle in body, "absent du template live")

def t_variety():
    """R1 : generate non-deterministe (no seed, no lock)."""
    cat = "R1-variety"
    tracker = set(INITIAL_LOCKS)
    ensure_unlocked([0,1,2,3,4,5], tracker)
    sigs = []
    for _ in range(6):
        gen(mode="morph", chaos=1.0, steps=16)
        sigs.append(voices_sig(export()))
    distinct = len(set(sigs))
    ok(cat, "generate produit des sorties variees", distinct > 1,
       detail="1 seule signature => determinisme/locks",
       info=f"{distinct}/6 distinctes")

def t_all_voices():
    """R2 : toutes les voix se regenerent, pas seulement la voix 0."""
    cat = "R2-allvoices"
    tracker = set(INITIAL_LOCKS); ensure_unlocked([0,1,2,3,4,5], tracker)
    for mode in ["morph", "markov", "phase2", "babka", "ambient"]:
        runs = []
        for _ in range(6):
            gen(mode=mode, chaos=1.0, steps=16)
            exp = export()
            if exp: runs.append([v["pattern"] for v in exp["voices"]])
        if not runs:
            ok(cat, f"mode={mode}", False, "aucun export"); continue
        nvoices = min(len(r) for r in runs)
        varying = [pos for pos in range(nvoices)
                   if len({r[pos] for r in runs}) > 1]
        ok(cat, f"mode={mode}: >=2 voix varient", len(varying) >= 2,
           detail="seule la voix 0 varie => voix hardcodees",
           info=f"varient={varying}/{nvoices}")

def t_vary():
    """R3 : /vary modifie reellement le motif (y compris babka)."""
    cat = "R3-vary"
    for mode in ["babka", "morph"]:
        gen(mode=mode, chaos=0.6, steps=16)
        v0 = voices_sig(export())
        POST("/vary")
        v1 = voices_sig(export())
        ok(cat, f"/vary change la sortie (mode={mode})", v0 is not None and v0 != v1,
           "aucun changement apres /vary")
    # /voice/vary idx=0
    gen(mode="morph", chaos=0.6); v0 = voices_sig(export())
    st, _ = POST("/voice/vary", {"idx": 0}); v1 = voices_sig(export())
    ok(cat, "/voice/vary idx=0 repond", st == 200, f"status={st}")
    ok(cat, "/voice/vary modifie l'etat", v0 != v1, "aucun changement", warn_only=True)

def t_lock():
    """R4 : voix verrouillee figee, voix libres mutent."""
    cat = "R4-lock"
    tracker = set(INITIAL_LOCKS); ensure_unlocked([0,1,2,3], tracker)
    gen(mode="morph", chaos=1.0, steps=16)
    exp = export()
    if not exp or len(exp["voices"]) < 2:
        ok(cat, "setup", False, "pas assez de voix"); return
    locked_pattern = exp["voices"][0]["pattern"]
    POST("/lock_voice", {"idx": 0}); tracker.add(0)
    frozen, others_changed = True, False
    for _ in range(4):
        gen(mode="morph", chaos=1.0, steps=16)
        e = export()
        if not e: continue
        if e["voices"][0]["pattern"] != locked_pattern: frozen = False
        if voices_sig(e)[1:] != voices_sig(exp)[1:]: others_changed = True
    ok(cat, "voix 0 verrouillee reste figee", frozen, "la voix lockee a change !")
    ok(cat, "voix non verrouillees mutent encore", others_changed,
       "aucune autre voix n'a change", warn_only=True)
    # nettoyage : deverrouiller
    ensure_unlocked([0], tracker)

def t_ctrl():
    """/ctrl mute un parametre SANS regenerer."""
    cat = "ctrl"
    gen(mode="morph", chaos=0.5, steps=16)
    v0 = voices_sig(export())
    st, _ = POST("/ctrl", {"key": "chaos", "val": "0.123"})
    ok(cat, "/ctrl repond 204", st == 204, f"status={st}")
    exp = export()
    ok(cat, "/ctrl applique chaos=0.123", exp and abs(exp["params"].get("chaos", 0) - 0.123) < 1e-6,
       f"chaos={exp['params'].get('chaos') if exp else '?'}")
    ok(cat, "/ctrl ne regenere PAS", voices_sig(exp) == v0, "les voix ont change apres /ctrl")
    st, _ = POST("/ctrl", {"key": "bpm", "val": "144"})
    exp = export()
    ok(cat, "/ctrl bpm coerce en int", exp and exp["params"].get("bpm") == 144,
       f"bpm={exp['params'].get('bpm') if exp else '?'}")
    st, _ = POST("/ctrl", {"key": "cle_invalide_xyz", "val": "9"})
    ok(cat, "/ctrl cle invalide -> 204 sans crash", st == 204, f"status={st}")

def t_undo_ab():
    """undo + round-trip A/B."""
    cat = "undo/AB"
    gen(mode="morph", chaos=0.8); va = voices_sig(export())
    gen(mode="random", chaos=0.8); vb = voices_sig(export())
    POST("/undo")
    ok(cat, "undo restaure l'etat precedent", voices_sig(export()) == va,
       "undo n'a pas restaure", warn_only=True)
    gen(mode="morph", chaos=0.8); va = voices_sig(export())
    POST("/ab/store", {"slot": "a"})
    gen(mode="noise", chaos=0.8); vb = voices_sig(export())
    POST("/ab/store", {"slot": "b"})
    POST("/ab/load", {"slot": "a"})
    ok(cat, "A/B: load A restaure A", voices_sig(export()) == va, "slot A incorrect")
    POST("/ab/load", {"slot": "b"})
    ok(cat, "A/B: load B restaure B", voices_sig(export()) == vb, "slot B incorrect")

def t_voice_ops():
    """Fuzz des operations par voix : aucun 500, etat reste valide."""
    cat = "voice-ops"
    gen(mode="morph", chaos=0.6, steps=16)  # Kick/Snare/HH/Bass
    ops = [
        ("/voice/density",  {"name": "Kick", "density": 0.7}),
        ("/voice/euclidean",{"idx": 0, "k": 5}),
        ("/voice/steps",    {"name": "Kick", "n": 12}),
        ("/voice/offset",   {"name": "Kick", "n": 2}),
        ("/voice/invert",   {"idx": 0}),
        ("/voice/drop",     {"name": "Kick", "pct": 50}),
        ("/voice/swing",    {"name": "Kick", "pct": 20}),
        ("/voice/midi_ch",  {"name": "Kick", "ch": 10}),
        ("/voice/rotate",   {"idx": 0, "n": 3}),
        ("/voice/reverse",  {"idx": 0}),
        ("/voice/double",   {"idx": 0}),
        ("/voice/halve",    {"idx": 0}),
        ("/voice/regen",    {"idx": 0}),
        ("/voice/thin",     {"name": "Kick", "factor": 2}),
        ("/voice/pattern",  {"idx": 0, "pattern": "x-x-x-x-x-x-x-x-"}),
        ("/voice/preview",  {"idx": 0, "pattern": "x---x---x---x---"}),
        ("/voice/lfo",      {"name": "Kick", "shape": "sine", "target": "velocity",
                             "freq": 0.5, "depth": 0.5}),
    ]
    soft = [
        ("/voice/chord",     {"name": "Kick", "chord_type": "min"}),
        ("/voice/vel_lane",  {"name": "Kick", "lane": "100,90,80,110"}),
        ("/voice/prob_lane", {"name": "Kick", "lane": "1,0.8,0.6,1"}),
    ]
    for path, payload in ops:
        st, _ = POST(path, payload)
        ok(cat, f"POST {path}", 0 < st < 500, f"status={st}")
    for path, payload in soft:
        st, _ = POST(path, payload)
        ok(cat, f"POST {path}", 0 < st < 500, f"status={st}", warn_only=True)
    # etat toujours valide ?
    exp = export()
    ok(cat, "etat valide apres fuzz", exp is not None and len(exp.get("voices", [])) > 0,
       "session/export casse apres les ops")

def t_edge_params():
    """Bornes de parametres : pas de 500."""
    cat = "edge"
    cases = [
        {"steps": 8},   {"steps": 32},  {"steps": 128}, {"steps": 256},
        {"chaos": 0.0}, {"chaos": 1.0}, {"bpm": 40},     {"bpm": 240},
    ]
    for c in cases:
        st, _ = gen(mode="morph", **c)
        ok(cat, f"generate {c}", 0 < st < 500, f"status={st}")
    # bassline >128 (chemin special)
    st, _ = gen(mode="bassline", steps=192, chaos=0.6)
    ok(cat, "generate bassline steps=192", 0 < st < 500, f"status={st}")

def t_seed():
    """Reproductibilite par seed (informatif : WARN si non garanti)."""
    cat = "seed"
    gen(mode="morph", chaos=0.7, steps=16, seed="bang-test-seed-42")
    s1 = voices_sig(export())
    gen(mode="morph", chaos=0.7, steps=16, seed="bang-test-seed-42")
    s2 = voices_sig(export())
    ok(cat, "meme seed -> meme sortie", s1 == s2,
       "seed non reproductible (entropie temporelle ?)", warn_only=True)

def t_all_modes():
    """Chaque mode genere sans erreur et produit des voix."""
    cat = "modes"
    modes = ["random","morph","weather","markov","phase2","noise","ambient",
             "babka","bassline","keystep_pro","microfreak",
             "volca_drum","volca_fm","volca_kick"]
    for m in modes:
        st, _ = gen(mode=m, chaos=0.5, steps=16)
        exp = export()
        nv = len(exp.get("voices", [])) if exp else 0
        ok(cat, f"mode={m}", (0 < st < 500) and nv > 0, f"status={st} voix={nv}")

# ── Runner ──────────────────────────────────────────────────────────────────
def main():
    print(f"\n=== BANG! test harness — cible {BASE} ===")
    st, _ = GET("/")
    if st != 200:
        print(f"\033[31mServeur injoignable sur {BASE} (status={st}). Abandon.\033[0m")
        sys.exit(2)
    snapshot()
    print()
    try:
        t_smoke()
        t_frontend_local()
        t_all_modes()
        t_variety()
        t_all_voices()
        t_vary()
        t_lock()
        t_ctrl()
        t_undo_ab()
        t_voice_ops()
        t_edge_params()
        t_seed()
    finally:
        print()
        restore()

    # rapport
    n = len(RESULTS)
    fails = [r for r in RESULTS if r[2] == "FAIL"]
    warns = [r for r in RESULTS if r[2] == "WARN"]
    passes = [r for r in RESULTS if r[2] == "PASS"]
    print("\n" + "═"*70)
    print(f"  TOTAL {n}   \033[32mPASS {len(passes)}\033[0m   "
          f"\033[33mWARN {len(warns)}\033[0m   \033[31mFAIL {len(fails)}\033[0m")
    print("═"*70)
    if fails:
        print("\n  ⚑ ÉCHECS :")
        for cat, name, _, detail in fails:
            print(f"    \033[31m✗\033[0m [{cat}] {name} — {detail}")
    if warns:
        print("\n  ⚠ AVERTISSEMENTS :")
        for cat, name, _, detail in warns:
            print(f"    \033[33m!\033[0m [{cat}] {name} — {detail}")
    print()
    # JSON machine-readable en derniere ligne (pour le workflow)
    print("BANG_TEST_JSON=" + json.dumps({
        "total": n, "pass": len(passes), "warn": len(warns), "fail": len(fails),
        "failures": [{"cat": c, "name": nm, "detail": d} for c, nm, _, d in fails],
        "warnings": [{"cat": c, "name": nm, "detail": d} for c, nm, _, d in warns],
    }, ensure_ascii=False))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
