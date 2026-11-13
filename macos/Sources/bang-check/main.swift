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
