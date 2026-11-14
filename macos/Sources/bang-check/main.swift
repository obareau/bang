import Foundation
import BangCore

// Auto-test du moteur natif : `swift run bang-check [dossier_sortie]`.
// Vérifie le parser Babka (cas de babka.py), les transforms, le déterminisme
// par seed, les 14 modes, et écrit un .mid par mode pour contrôle externe.

var failures = 0
func check(_ cond: Bool, _ msg: String) {
    if cond { print("  ok   \(msg)") } else { print("  FAIL \(msg)"); failures += 1 }
}
func near(_ a: Double, _ b: Double) -> Bool { abs(a - b) < 1e-9 }

print("Babka")
let babkaCases: [(String, Int, Int, Double)] = [
    ("x-x-", 0, 4, 4), ("x-[x x]-?", 0, 6, 5), ("<x- -x>", 0, 2, 2), ("<x- -x>", 1, 2, 2),
    ("x(3,8)", 0, 8, 8), ("[x(3,8)]", 0, 8, 1), ("x-[x(2,4)]?", 0, 7, 4),
    ("<x-x- ?-?->", 1, 4, 4), ("↺-[x ?]-░(2,4)", 0, 9, 8),
]
for (pat, cyc, n, total) in babkaCases {
    let s = Babka.parse(pat, cycle: cyc)
    check(s.count == n && near(Babka.totalSteps(s), total), "\(pat) c=\(cyc) → \(s.count) steps, total \(Babka.totalSteps(s))")
}
check(Babka.parse("<x- -x>", cycle: 1).first?.cell.trigger == false, "alternance cycle 1 commence par un silence")
check(Babka.parse("x(3,8)").map { $0.cell.trigger ? "x" : "-" }.joined() == "x--x--x-", "euclidien 3/8 = x--x--x-")

print("DNA")
check(DNA.euclid(n: 8, k: 3) == "x--x--x-", "euclid(8,3)")
check(DNA.rotate("x---", by: 1) == "-x--", "rotate +1")
check(DNA.invert("x-?") == "-x?", "invert garde les ?")
check(DNA.halve("x-x-x-x-") == "x-x-", "halve")
check(DNA.resize("x-?", to: 7) == "x-?x-?x", "resize")
let r = Dice(seed: 1)
check(DNA.mutate("↺(2,8)", intensity: 1, rng: r).hasSuffix("(2,8)"), "mutate épargne la syntaxe Babka")
check(Scales.rootNote("A") == 33 && Scales.rootNote("C") == 36 && Scales.rootNote("G#") == 44, "toniques")

print("Seed")
var s1 = BangSession(); s1.params.seed = "deadbeefcafebabe0123"; s1.generate()
var s2 = BangSession(); s2.params.seed = "deadbeefcafebabe0123"; s2.generate()
check(s1.voices == s2.voices, "même seed → mêmes voix")
let m1 = MIDIFileWriter.export(s1.renderInput(), numSteps: 64, seed: s1.lastSeed)
let m2 = MIDIFileWriter.export(s2.renderInput(), numSteps: 64, seed: s2.lastSeed)
check(m1 == m2, "même seed → même fichier MIDI (\(m1.count) octets)")

print("Modes")
let outDir = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : NSTemporaryDirectory())
try? FileManager.default.createDirectory(at: outDir, withIntermediateDirectories: true)
for mode in Mode.allCases {
    var s = BangSession()
    s.params.mode = mode
    s.params.chaos = 0.6
    s.params.steps = 32
    s.weather = Weather(temperature: 14, windSpeed: 30)
    s.generate()
    let input = s.renderInput()
    let ev = Renderer.render(input, numSteps: s.params.steps, rng: Dice(seed: 7))
    let notes = ev.filter { $0.kind == .noteOn }.count
    let data = MIDIFileWriter.export(input, numSteps: s.params.steps, seed: s.lastSeed, name: mode.rawValue)
    try? data.write(to: outDir.appendingPathComponent("\(mode.rawValue).mid"))
    let pl = s.plocks.flatMap { $0 }.count
    check(!s.voices.isEmpty && notes > 0 && data.starts(with: Array("MThd".utf8)),
          "\(mode.label): \(s.voices.count) voix, \(notes) notes\(pl > 0 ? ", \(pl) p-locks" : "")")
}

print("Changement de mode (moins de voix)")
var shrink = BangSession()
shrink.params.mode = .noise; shrink.generate()          // 8 voix
shrink.params.mode = .ambient; shrink.generate()        // 3 voix
let staleInput = shrink.renderInput()
check(staleInput.channel(for: 7) == 9 && staleInput.outputNote(for: 7) == 0,
      "index périmé (voix 8 sur 3) : pas de plantage")

print("Jeu live : morph, Song, mémoires, LFO")
do {
    var p = GenParams(); p.steps = 16
    let a = [Voice(36, "x---x---x---x---", "drum")]
    let b = [Voice(36, "--x---x---x---x-", "drum")]
    func onsets(_ m: MorphTarget?) -> [Int] {
        var inp = RenderInput(voices: a, params: p); inp.morph = m
        return Renderer.render(inp, numSteps: 16, rng: Dice(seed: 3)).filter { $0.kind == .noteOn }.map { $0.tick / 120 }
    }
    check(onsets(MorphTarget(voices: b, progress: 0)) == [0, 4, 8, 12], "morph 0 % = pattern de départ")
    check(onsets(MorphTarget(voices: b, progress: 1)) == [2, 6, 10, 14], "morph 100 % = pattern cible")
    let mid = (0..<4000).map { s -> Int in
        var inp = RenderInput(voices: a, params: p); inp.morph = MorphTarget(voices: b, progress: 0.5)
        return Renderer.render(inp, numSteps: 16, rng: Dice(seed: UInt64(s))).filter { $0.kind == .noteOn }.count
    }
    let avg = Double(mid.reduce(0, +)) / 4000
    check(abs(avg - 4) < 0.15, String(format: "morph 50 %% : %.2f coups en moyenne sur 8 positions (attendu ≈ 4)", avg))

    let song = SongChain.parse("1x4 2×2, 3 9x2 4:0")
    check(song.parts.map { [$0.slot, $0.repeats] } == [[0, 4], [1, 2], [2, 1], [3, 1]], "Song « 1x4 2×2, 3 9x2 4:0 » → \(song.description)")

    var ss = BangSession(); ss.generate(); ss.saveSlot(0); ss.generate(); ss.saveSlot(2); ss.slotWeights[2] = 9
    let picks = (0..<50).compactMap { s -> Int? in var t = ss; t.currentSlot = 5; return t.advanceSlot(rng: Dice(seed: UInt64(s))) }
    check(Set(picks).isSubset(of: [0, 2]) && picks.filter { $0 == 2 }.count > 35, "avance auto : seulement les mémoires pleines, pondérées (\(picks.filter { $0 == 2 }.count)/50 vers la 3)")
    var ab = ss; ab.storeAB(false); let saved = ab.voices; ab.generate(); _ = ab.loadAB(false)
    check(ab.voices == saved, "A/B : recharger A rend le pattern mémorisé")

    var lp = GenParams(); lp.steps = 64
    let hat = [Voice(42, String(repeating: "x", count: 64), "drum")]
    var st = VoiceSettings(); st.lfo = VoiceLFO(shape: .ramp, target: .density, freq: 1, depth: 1)
    let inp = RenderInput(voices: hat, params: lp, settings: ["HiHat": st])
    var firstHalf = 0, secondHalf = 0
    for s in 0..<50 {
        for e in Renderer.render(inp, numSteps: 64, rng: Dice(seed: UInt64(s))) where e.kind == .noteOn {
            if e.tick < 32 * 120 { firstHalf += 1 } else { secondHalf += 1 }
        }
    }
    check(secondHalf > firstHalf * 2, "LFO rampe sur la densité : \(firstHalf) coups en 1re moitié, \(secondHalf) en 2de")
}

print("Édition fine par voix")
do {
    var p = GenParams(); p.steps = 8
    func ons(_ dna: String, _ st: VoiceSettings, seed: UInt64 = 1) -> [MIDIEvent] {
        let inp = RenderInput(voices: [Voice(36, dna, "drum")], params: p, settings: ["Kick": st])
        return Renderer.render(inp, numSteps: 8, rng: Dice(seed: seed)).filter { $0.kind == .noteOn }
    }
    var v = VoiceSettings(); v.velLane = [0, 0, 0, 0, 40]
    let e = ons("x---x---", v)
    check(e.map(\.data2) == [105, 40], "lane vélocité : step 5 forcé à 40 (\(e.map(\.data2)))")
    var pr = VoiceSettings(); pr.probLane = [100, 0, 0, 0, 100, 0, 0, 0]
    let always = (0..<40).allSatisfy { ons("?---?---", pr, seed: UInt64($0)).count == 2 }
    check(always, "lane probabilité : « ? » à 100 % joue à chaque fois")
    var th = VoiceSettings(); th.thin = 2
    check(ons("xxxxxxxx", th).map { $0.tick / 120 } == [0, 2, 4, 6], "Thin ÷2 : un coup sur deux")
    var of = VoiceSettings(); of.offset = 3
    check(ons("x---x---", of).map { $0.tick / 120 }.sorted() == [3, 7], "décalage +3 : steps 1 et 5 → 4 et 8")
    var of2 = VoiceSettings(); of2.offset = 6
    check(ons("x---x---", of2).map { $0.tick / 120 }.sorted() == [2, 6], "décalage +6 : ce qui dépasse revient au début")

    var ss = BangSession(); ss.generate()
    ss.setLength(0, 5)
    let l1 = ss.voices[0].dna.count
    ss.generate()
    check(l1 == 5 && ss.voices[0].dna.count == 5, "longueur 5 conservée après une nouvelle génération")
    ss.updateSettings(0) { $0.velLane = [90]; $0.thin = 4; $0.offset = 2 }
    ss.setNote(0, 35)
    var back = BangSession()
    let data = try! JSONEncoder().encode(SessionFile(ss))
    try! JSONDecoder().decode(SessionFile.self, from: data).apply(to: &back)
    check(back.settings(for: 0) == ss.settings(for: 0) && back.noteRemap == ss.noteRemap,
          "session : lanes, thin, décalage, longueur et note relus à l'identique")
}

print("DAW / matériel")
do {
    var s = BangSession()
    s.voices = [Voice(36, "x-?-↺---", "drum"), Voice(24, "x---", "markov"), Voice(0, "CC74", "cc")]
    s.params.bpm = 120
    let code = StrudelExport.code(s)
    check(code.contains("setcps(0.5)") && code.contains("s(\"bd ~ bd?0.5 ~ bd*3 ~ ~ ~\")") && code.contains("note(\""),
          "Strudel : « x-?-↺--- » → bd ~ bd?0.5 ~ bd*3 …")

    let m = OSCMessage("/bang/param/chaos", [.float(0.7), .int(-3), .string("hé")])
    let back = OSCMessage.decode(m.encode())
    check(back == [m] && m.encode().count % 4 == 0, "OSC : encodage / décodage aller-retour (i, f, s)")
    var bundle = Data("#bundle".utf8); bundle.append(0); bundle.append(Data(count: 8))
    for msg in [OSCMessage("/bang/generate"), OSCMessage("/bang/vary")] {
        let d = msg.encode()
        withUnsafeBytes(of: UInt32(d.count).bigEndian) { bundle.append(contentsOf: $0) }
        bundle += d
    }
    check(OSCMessage.decode(bundle).map(\.address) == ["/bang/generate", "/bang/vary"], "OSC : bundle de 2 messages")

    check(MIDILearn.quantize([0.0, 0.26, 0.49, 1.01, 3.9], steps: 16, stepSeconds: 0.125) == "x-x-x---x------x",
          "MIDI Learn : frappes quantifiées au step le plus proche")

    var c = BangSession(); c.voices = [Voice(36, "x---x---", "drum"), Voice(42, "--x---x-", "drum")]; c.params.steps = 8
    let clips = VoiceNotes.clips(c)
    check(clips.count == 2 && clips[0].notes.map(\.startBeats) == [0, 1] && clips[1].notes.map(\.startBeats) == [0.5, 1.5],
          "clips par voix : temps en noires (kick 0 / 1, charleston 0,5 / 1,5)")
    let one = MIDIFileWriter.exportVoice(c, voice: 1)
    let all = MIDIFileWriter.export(c.renderInput(), numSteps: 8, seed: "0", type: 0)
    check(one.count < all.count && one.starts(with: Array("MThd".utf8)), "export d'une seule voix (\(one.count) octets)")
}

print("Fonctions ajoutées (parité Python + roadmap)")
do {
    var p = GenParams(); p.steps = 4
    func ons(_ inp: RenderInput, _ n: Int = 4, seed: UInt64 = 1) -> [MIDIEvent] {
        Renderer.render(inp, numSteps: n, rng: Dice(seed: seed)).filter { $0.kind == .noteOn }
    }
    // Polyphonie max
    var poly = RenderInput(voices: [36, 38, 42, 48].map { Voice($0, "xxxx", "drum") }, params: p)
    poly.maxPoly = 2
    let perStep = Dictionary(grouping: ons(poly), by: { $0.tick / 120 }).mapValues(\.count)
    check(perStep.values.allSatisfy { $0 == 2 } && Set(ons(poly).map(\.data1)) == [36, 38],
          "polyphonie 2 : 2 voix par step, les premières de la liste")

    // Conditions façon Elektron
    var cs = VoiceSettings(); cs.condition = "1:2"
    var cin = RenderInput(voices: [Voice(36, "x---", "drum")], params: p, settings: ["Kick": cs])
    let c0 = ons(cin).count; cin.cycle = 1; let c1 = ons(cin).count; cin.cycle = 2; let c2 = ons(cin).count
    var fs = VoiceSettings(); fs.condition = "fill"
    var fin = RenderInput(voices: [Voice(36, "x---", "drum")], params: p, settings: ["Kick": fs])
    let f0 = ons(fin).count; fin.fill = true; let f1 = ons(fin).count
    check([c0, c1, c2] == [1, 0, 1] && [f0, f1] == [0, 1], "conditions : 1:2 joue 1 cycle sur 2, « fill » seulement en FILL")

    // Transposition (voix mélodiques seulement)
    var tp = p; tp.transpose = 12
    let base = ons(RenderInput(voices: [Voice(24, "xxxx", "markov"), Voice(36, "x---", "drum")], params: p), seed: 9)
    let up = ons(RenderInput(voices: [Voice(24, "xxxx", "markov"), Voice(36, "x---", "drum")], params: tp), seed: 9)
    check(zip(base, up).allSatisfy { $0.voice == 0 ? $1.data1 == $0.data1 + 12 : $1.data1 == $0.data1 },
          "transposition +12 : mélodie +12, batterie inchangée")

    // Ratchet par step + decay
    var rs = VoiceSettings(); rs.ratchetLane = [4]; rs.ratchetDecay = 0.5
    let rat = ons(RenderInput(voices: [Voice(36, "x---", "drum")], params: p, settings: ["Kick": rs]))
    check(rat.count == 4 && rat.map(\.tick) == [0, 30, 60, 90] && zip(rat, rat.dropFirst()).allSatisfy { $0.data2 > $1.data2 },
          "ratchet ×4 au step 1, vélocités décroissantes (\(rat.map(\.data2)))")

    // Interpolation des p-locks
    let pl = PLock(cc: 74, name: "Cutoff", style: "manuel", values: [0, nil, nil, nil, 100, nil, nil, nil])
    let off = Renderer.plockEvents(pl, numSteps: 8, interp: .off, channel: 0, voice: 0)
    let lin = Renderer.plockEvents(pl, numSteps: 8, interp: .linear, channel: 0, voice: 0)
    let cosv = Renderer.plockEvents(pl, numSteps: 8, interp: .cosine, channel: 0, voice: 0)
    let mid = lin.first { $0.tick == 240 }?.data2, cmid = cosv.first { $0.tick == 120 }?.data2
    check(off.count == 2 && mid == 50 && zip(lin, lin.dropFirst()).allSatisfy { $0.data2 < $1.data2 } && (cmid ?? 99) < 25 && lin.last?.data2 == 100,
          "p-locks interpolés : linéaire 50 à mi-chemin, cosinus plus lent au départ, tenue après la fin")

    // Presets KSP
    var ks = BangSession(); ks.params.mode = .keystepPro; ks.generate()
    ks.applyKSP("Dorian Jazz", Presets.ksp[1].preset)
    check(ks.params.root == "D" && ks.params.scale == "dorian" && ks.settings["KSP Chord"]?.chord == "M7",
          "preset KSP « Dorian Jazz » : D dorien, accords des pistes KSP")
    check(ks.currentKSP.chords["KSP Lead"] == "m7", "harmonie courante relue pour l'enregistrer")

    // Morceau
    let song = SongBuilder.build(chaos: 0.6, bpm: 110, gravity: 0.7, ccDepth: 0.5, weather: nil, seed: "abc123")
    let song2 = SongBuilder.build(chaos: 0.6, bpm: 110, gravity: 0.7, ccDepth: 0.5, weather: nil, seed: "abc123")
    let names = song.sections.map(\.name)
    check(song.sections.count == 30 && song.totalSteps == 944 && names.first == "01a-intro1" && names.last == "09d-fin4"
          && song.voices.count <= 8 && song.voices.allSatisfy { $0.dna.count == 944 } && song.voices == song2.voices,
          "morceau : 30 sections (01a-intro1 → 09d-fin4), 944 steps, \(song.voices.count) pistes, reproductible par seed")
    let songMid = MIDIFileWriter.export(song.renderInput(), numSteps: song.totalSteps, seed: song.seed,
                                        name: "song", markers: song.markers)
    try? songMid.write(to: outDir.appendingPathComponent("song.mid"))
    check(songMid.count > 2000, "morceau exporté en .mid avec marqueurs (\(songMid.count) octets)")

    // Entropie temporelle : hors seed
    var tpp = p; tpp.temporal = true
    let tin = RenderInput(voices: [Voice(36, "░░░░", "drum")], params: tpp)
    let runs = (0..<20).map { _ in ons(tin, seed: 5).map(\.tick) }
    check(Set(runs.map { "\($0)" }).count > 1, "entropie temporelle : même seed, timings différents")

    // P-locks aléatoires bornés + pistes CC ajoutées
    var rp = BangSession(); rp.params.mode = .morph; rp.generate()
    rp.addCCLane(0, cc: 74, name: "Cutoff")
    rp.randomizePlocks(0, density: 1, lo: 40, hi: 60, rng: Dice(seed: 2))
    let lane = rp.settings(for: 0).ccLanes.first
    check(lane?.values.allSatisfy { ($0 ?? -1) >= 40 && ($0 ?? 999) <= 60 } == true,
          "p-locks aléatoires bornés 40–60 sur une piste CC ajoutée")
    rp.generate()
    check(rp.settings(for: 0).ccLanes.first?.cc == 74, "piste CC ajoutée gardée après une nouvelle génération")

    // Relecture de session
    rp.maxPoly = 3; rp.plockInterp = .cosine
    rp.updateSettings(0) { $0.ratchetLane = [2, 0, 3]; $0.condition = "1:4"; $0.ratchetDecay = 0.4; $0.port = 123 }
    var back = BangSession()
    try! JSONDecoder().decode(SessionFile.self, from: JSONEncoder().encode(SessionFile(rp))).apply(to: &back)
    check(back.maxPoly == 3 && back.plockInterp == .cosine && back.settings(for: 0) == rp.settings(for: 0),
          "session : polyphonie, interpolation, ratchets, condition, pistes CC et port relus")
}

print("Batterie 808 / 909 (synthèse)")
func analyse(_ b: [Float]) -> (peak: Float, dur: Double, hz: Double, nan: Bool) {
    let peak = b.map { abs($0) }.max() ?? 0
    let last = b.lastIndex { abs($0) > 0.002 } ?? 0
    let win = b.prefix(2400)  // 50 ms
    var zc = 0
    for i in 1..<win.count where (win[win.startIndex + i - 1] < 0) != (win[win.startIndex + i] < 0) { zc += 1 }
    return (peak, Double(last) / 48_000, Double(zc) / 2 / 0.05, b.contains { $0.isNaN })
}
let wavDir = outDir.appendingPathComponent("drums")
try? FileManager.default.createDirectory(at: wavDir, withIntermediateDirectories: true)
func writeWav(_ b: [Float], _ url: URL) {
    var d = Data()
    func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
    func u16(_ v: UInt16) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
    d.append(contentsOf: Array("RIFF".utf8)); u32(UInt32(36 + b.count * 2))
    d.append(contentsOf: Array("WAVEfmt ".utf8)); u32(16); u16(1); u16(1); u32(48_000); u32(96_000); u16(2); u16(16)
    d.append(contentsOf: Array("data".utf8)); u32(UInt32(b.count * 2))
    for x in b { u16(UInt16(bitPattern: Int16(max(-1, min(1, x)) * 32_000))) }
    try? d.write(to: url)
}
let sounds: [(Int, String, ClosedRange<Double>)] = [
    (36, "kick", 30...160), (38, "snare", 150...5000), (39, "clap", 400...6000),
    (42, "hh-fermé", 2500...20000), (46, "hh-ouvert", 2500...20000), (45, "tom", 60...300),
    (49, "crash", 2500...20000), (56, "cowbell", 300...3000), (37, "rim", 800...4000),
]
for kit in [DrumKit.tr808, .tr909] {
    var line: [String] = []
    var ok = true
    for (note, name, band) in sounds {
        let b = DrumSynth.renderHit(note: note, kit: kit, seconds: 2.4)
        let a = analyse(b)
        writeWav(b, wavDir.appendingPathComponent("\(kit.short)-\(name).wav"))
        // La caisse claire 909 est volontairement plus brillante (plus de bruit) que la 808.
        let range = name == "snare" ? (kit == .tr909 ? 1500.0...7000 : 1000.0...4000) : band
        let good = !a.nan && a.peak > 0.05 && a.peak <= 1 && range.contains(a.hz) && a.dur > 0.02
        if !good { ok = false }
        line.append(String(format: "%@ %.0fHz %.2fs%@", name, a.hz, a.dur, good ? "" : " ✗"))
    }
    check(ok, "\(kit.short) : " + line.joined(separator: " · "))
}

print(failures == 0 ? "\n✓ tout vert" : "\n✗ \(failures) échec(s)")
exit(failures == 0 ? 0 : 1)
