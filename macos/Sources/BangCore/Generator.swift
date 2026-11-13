import Foundation

/// Les 14 modes de génération — portage de pattern_lib.build_voices.
public enum Generator {
    public static func buildVoices(_ p: GenParams, weather: Weather?, rng: Dice) -> [Voice] {
        let chaos = p.chaos
        let w = weather ?? .neutral
        func mut(_ s: String, _ k: Double) -> String { DNA.mutate(s, intensity: chaos * k, rng: rng) }

        switch p.mode {
        case .random:
            return [36, 38, 42, 48].map { Voice($0, DNA.random(length: 16, rng: rng), "drum") }

        case .morph:
            let base = DNA.morph("x---x---x---x---", "x---?---x↺--░---", mutationRate: chaos * 0.5, rng: rng)
            return [
                Voice(36, mut(base, 0.6), "drum"),
                Voice(38, mut("----x-------x---", 0.25), "drum"),
                Voice(42, mut("x-x-x-x-x-x-x-x", 0.2), "drum"),
                Voice(24, mut("x-?-░", 0.3), "drum"),
            ]

        case .weather:
            return [(36, 16), (38, 8), (42, 16), (24, 5)].map { note, len in
                Voice(note, mut(weatherDNA(w, length: len, rng: rng), 0.4), "drum")
            }

        case .markov, .phase2:
            var v = [
                Voice(36, mut("x---x---", 0.4), "drum"),
                Voice(38, mut("----x-------x---", 0.25), "drum"),
                Voice(42, mut("x-x-x-x-x-x-x-x", 0.2), "drum"),
                Voice(24, mut("x-?-░", 0.3), "markov"),
            ]
            if p.mode == .phase2 {
                v.append(Voice(0, "CC74 → 20…\(Int(20 + p.ccDepth * 100))…20", "cc"))
                if weather != nil { v.append(Voice(0, "CC91 réverb (météo)", "cc")) }
            }
            return v

        case .noise:
            let layout = [(36, 11), (38, 7), (42, 13), (48, 5), (40, 9), (43, 11), (24, 7), (33, 13)]
            let wDense = [2 + chaos * 3, max(0.1, 2 - chaos * 1.5), 1 + chaos, chaos * 1.5, chaos]
            let wHH = [0.8, 6.0, 0.4, 0.0, 0.0]
            return layout.map { note, len in
                let ws = note == 42 ? wHH : wDense
                let raw = String((0..<len).map { _ in rng.weighted(DNA.symbols, ws) })
                return Voice(note, DNA.mutate(raw, intensity: note == 42 ? chaos * 0.08 : chaos * 0.4, rng: rng), "drum")
            }

        case .ambient:
            let ws = [0.3 + chaos * 0.3, 9.0, 0.5 + chaos * 0.2, 0.0, 0.0]
            return [36, 24, 33].map { note in
                let raw = String((0..<p.steps).map { _ in rng.weighted(DNA.symbols, ws) })
                return Voice(note, DNA.mutate(raw, intensity: chaos * 0.05, rng: rng), "drum")
            }

        case .babka:
            if chaos < 0.4 {
                return [
                    Voice(36, mut("x---x---", 0.3), "babka"),
                    Voice(38, mut("x(3,8)", 0.2), "babka"),
                    Voice(42, mut("[x x]-x-[x x]-x-", 0.15), "babka"),
                    Voice(24, mut("?-░-", 0.3), "babka"),
                ]
            } else if chaos < 0.7 {
                return [
                    Voice(36, mut("<x---x--- x-[x-]x-->", 0.25), "babka"),
                    Voice(38, mut("?(3,8)", 0.2), "babka"),
                    Voice(42, mut("<[x x]-x- x-[x x]->", 0.15), "babka"),
                    Voice(24, mut("↺(2,8)", 0.25), "babka"),
                ]
            } else {
                let nSnare = min(7, max(2, Int(chaos * 8)))
                return [
                    Voice(36, mut("<x-[x x]- [x x]-->", 0.3), "babka"),
                    Voice(38, mut("?(\(nSnare),8)", 0.25), "babka"),
                    Voice(42, mut("<[x x x]-x- x-[x x]->", 0.2), "babka"),
                    Voice(24, mut("<↺(2,8) ░(3,8)>", 0.3), "babka"),
                ]
            }

        case .bassline:
            let trigA: String, trigB: String, kick: String, snare: String, hh: String
            if chaos < 0.30 {
                trigA = "x---x---"; trigB = "x-------x-------"
            } else if chaos < 0.55 {
                trigA = mut("x---x-x-", 0.5); trigB = mut("x-------x--x----", 0.3)
            } else {
                trigA = mut("x-x--x-?", 0.55); trigB = mut("?--x-x--x---?---", 0.45)
            }
            if chaos < 0.30 {
                kick = "x---x---x---x---"; snare = "----x-------x---"; hh = "x-x-x-x-x-x-x-x"
            } else if chaos < 0.55 {
                kick = mut("x---x--x-x---x---", 0.4); snare = mut("----x-------x---", 0.3)
                hh = mut("x-x-x-x-x?x-x-x-", 0.25)
            } else {
                kick = mut("x--x-x--x-x--x-?", 0.5); snare = mut("----x---?---x-?-", 0.4)
                hh = mut("x?x-x?x-x?x-x?x-", 0.35)
            }
            var v = [
                Voice(33, trigA, "bl"), Voice(33, trigB, "bl"),
                Voice(36, kick, "drum"), Voice(38, snare, "drum"), Voice(42, hh, "drum"),
                Voice(0, "CC74 → 20…\(Int(20 + p.ccDepth * 80))…20", "cc"),
            ]
            if chaos > 0.35 { v.append(Voice(0, "CC5 portamento ↗\(Int(chaos * 60))", "cc")) }
            return v

        case .volcaKick:
            let bases = [
                ("x---x---x---x---", "x---?---x---?---"),
                ("x-?-x---x-?-x---", "?---x---?---x---"),
                ("x---x-?-x---x-?-", "x---?-x-x---?-x-"),
            ]
            let pair = bases[Int(chaos * Double(bases.count)) % bases.count]
            let dna = mut(DNA.morph(pair.0, pair.1, mutationRate: chaos * 0.35, rng: rng), 0.25)
            return [Voice(60, dna, "vk")]

        case .microfreak:
            let notes = [45, 40, 36]
            let bases = [
                ("x---x-x-x---x---", "x--?x-x-x--?x---"),
                ("--x---x---x---x-", "--x---x?--x---?-"),
                ("x-----------x---", "?-----------?---"),
            ]
            return bases.enumerated().map { i, b in
                Voice(notes[i], mut(DNA.morph(b.0, b.1, mutationRate: chaos * 0.45, rng: rng), 0.30), "mf\(i)")
            }

        case .volcaFM:
            let notes = [36, 43, 48]
            let bases = [
                ("x---x---x---x---", "x---x--?x---x---"),
                ("--x---x---x---x-", "--x?--x---x---x-"),
                ("---?---x--------", "---?--------x---"),
            ]
            return bases.enumerated().map { i, b in
                Voice(notes[i], mut(DNA.morph(b.0, b.1, mutationRate: chaos * 0.45, rng: rng), 0.25), "vfm\(i)")
            }

        case .volcaDrum:
            let bases = [
                ("x---x---x---x---", "x---?---x---?---"),
                ("----x-------x---", "---?x-------x?--"),
                ("x-x-x-x-x-x-x-x", "x-x?x-x-x-x?x-x"),
                ("?---?---?---?---", "?--░?---?---░?--"),
                ("x-?-░-?-x-?-░-?", "?-░-x-░-?-x-░-?"),
                ("---x---?---x---?", "x--?---x---?--x-"),
            ]
            return bases.enumerated().map { i, b in
                Voice(60, mut(DNA.morph(b.0, b.1, mutationRate: chaos * 0.4, rng: rng), 0.3), "vd\(i)")
            }

        case .keystepPro:
            return [
                Voice(36, mut("x---x---x---x---", 0.3), "drum"),
                Voice(38, mut("----x-------x---", 0.3), "drum"),
                Voice(42, mut("x-x-x-x-x-x-x-x", 0.2), "drum"),
                Voice(0, mut("x---?-x-?---x---", 0.5), "ksp1"),
                Voice(0, mut("x---x-x-x---x---", 0.4), "ksp2"),
                Voice(0, mut("?---x---?---x---", 0.3), "ksp3"),
                Voice(0, mut("x-x---x-x-?---x-", 0.5), "ksp4"),
            ]
        }
    }

    // MARK: - Météo

    /// Froid → sparse, chaud → dense, vent → ratchets/jitter.
    public static func weatherDNA(_ w: Weather, length: Int, rng: Dice) -> String {
        let density = ((w.temperature + 10) / 40).clamped(0.15, 0.85)
        let wind = min(1.0, w.windSpeed / 60)
        return String((0..<length).map { _ -> Character in
            if rng.random() > density { return "-" }
            let r = rng.random()
            if r < wind * 0.25 { return "↺" }
            if r < wind * 0.50 { return "░" }
            if r < 0.40 { return "?" }
            return "x"
        })
    }

    public static func weatherCCBreakpoints(_ w: Weather, points: Int = 5) -> [Int] {
        let base = Int(((w.temperature + 10) / 40 * 110).clamped(10, 100))
        let depth = Int(min(60, w.windSpeed / 60 * 80))
        return (0..<points).map { i in
            let v = Double(base) + sin(Double(i) / Double(points - 1) * .pi) * Double(depth)
            return min(127, max(0, Int(v)))
        }
    }

    /// Météo de Scaër via Open-Meteo (sans clé). nil si hors-ligne.
    public static func fetchWeather() async -> Weather? {
        let url = URL(string: "https://api.open-meteo.com/v1/forecast?latitude=48.0253&longitude=-3.6854&current=temperature_2m,wind_speed_10m&forecast_days=1")!
        var req = URLRequest(url: url)
        req.timeoutInterval = 5
        guard let (data, _) = try? await URLSession.shared.data(for: req),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let cur = json["current"] as? [String: Any],
              let t = cur["temperature_2m"] as? Double,
              let ws = cur["wind_speed_10m"] as? Double else { return nil }
        return Weather(temperature: t, windSpeed: ws)
    }

    // MARK: - P-locks synthés

    static let vdProfile: [[(Int, String, String)]] = [
        [(20, "Rel", "sweep"), (23, "Pitch", "sweep"), (49, "BitCrsh", "spike")],
        [(21, "Rel", "sweep"), (26, "ModAmt", "texture"), (51, "Drive", "spike")],
        [(29, "ModRate", "texture"), (23, "Pitch", "texture"), (50, "Fold", "spike")],
        [(21, "Rel", "sweep"), (117, "WGDecay", "sweep"), (118, "WGBody", "texture")],
        [(24, "Pitch", "sweep"), (27, "ModAmt", "texture"), (30, "ModRate", "texture")],
        [(49, "BitCrsh", "spike"), (50, "Fold", "spike"), (51, "Drive", "texture")],
    ]

    static let synthProfiles: [String: [(Int, String, String)]] = [
        "vk": [(40, "Pitch", "sweep"), (45, "Decay", "sweep"), (46, "Drive", "texture"),
               (47, "Fold", "texture"), (48, "BitRed", "spike")],
        "vfm0": [(40, "Algo", "spike"), (41, "Feedbk", "texture"), (44, "Op1Lvl", "sweep"),
                 (45, "Op2Lvl", "sweep"), (42, "LFOSpd", "texture")],
        "mf0": [(13, "Cutoff", "sweep"), (11, "Timbre", "texture"), (12, "Shape", "texture"),
                (16, "LFOAmt", "spike"), (15, "LFORate", "sweep")],
    ]

    static func plockValues(_ style: String, steps: Int, chaos: Double, phase: Double, rng: Dice) -> [Int?] {
        (0..<steps).map { step in
            let t = Double(step) / Double(steps)
            let val: Int, density: Double
            switch style {
            case "sweep":
                let base = Int(55 + 50 * sin(2 * .pi * t + phase))
                val = min(127, max(0, base + Int(chaos * 28 * (rng.random() * 2 - 1))))
                density = 0.45 + chaos * 0.3
            case "texture":
                let base = Int(38 + 52 * abs(sin(4 * .pi * t + phase)))
                val = min(127, max(0, base + Int(chaos * 44 * (rng.random() * 2 - 1))))
                density = 0.4 + chaos * 0.35
            default:
                val = rng.random() < chaos * 0.55 ? rng.int(60, 127) : rng.int(0, 35)
                density = 0.18 + chaos * 0.42
            }
            return rng.random() < density ? val : nil
        }
    }

    /// Une liste de p-locks par voix (vide pour les voix non-synthé).
    public static func plocks(for voices: [Voice], params p: GenParams, rng: Dice) -> [[PLock]] {
        let steps = [.volcaDrum, .volcaKick, .volcaFM].contains(p.mode) ? min(p.steps, 16) : p.steps
        return voices.map { v in
            let profile: [(Int, String, String)]
            let phase: Double
            if v.type.hasPrefix("vd"), let idx = Int(v.type.dropFirst(2)) {
                profile = vdProfile[idx % vdProfile.count]
                phase = Double(idx) * 1.4
            } else if let prof = synthProfiles[v.type] {
                profile = prof
                phase = 0
            } else {
                return []
            }
            return profile.map { cc, name, style in
                PLock(cc: cc, name: name, style: style,
                      values: plockValues(style, steps: steps, chaos: p.chaos, phase: phase, rng: rng))
            }
        }
    }
}
