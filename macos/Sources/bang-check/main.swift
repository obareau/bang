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

print(failures == 0 ? "\n✓ tout vert" : "\n✗ \(failures) échec(s)")
exit(failures == 0 ? 0 : 1)
