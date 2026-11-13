import Foundation

public struct Weather: Codable, Equatable, Sendable {
    public var temperature: Double
    public var windSpeed: Double

    public init(temperature: Double, windSpeed: Double) {
        self.temperature = temperature
        self.windSpeed = windSpeed
    }

    public static let neutral = Weather(temperature: 10, windSpeed: 10)

    enum CodingKeys: String, CodingKey {
        case temperature
        case windSpeed = "wind_speed"
    }
}

public enum Mode: String, CaseIterable, Codable, Sendable, Identifiable {
    case morph, random, weather, markov, phase2, noise, ambient, babka, bassline
    case volcaKick = "volca_kick", microfreak, volcaFM = "volca_fm"
    case volcaDrum = "volca_drum", keystepPro = "keystep_pro"

    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .morph: return "Morph"
        case .random: return "Random"
        case .weather: return "Weather"
        case .markov: return "Markov"
        case .phase2: return "Phase 2"
        case .noise: return "Noise ◼"
        case .ambient: return "Ambient ◌"
        case .babka: return "Babka ⚗"
        case .bassline: return "Bassline"
        case .volcaKick: return "Volca Kick"
        case .microfreak: return "MicroFreak"
        case .volcaFM: return "Volca FM"
        case .volcaDrum: return "Volca Drum ★"
        case .keystepPro: return "Keystep Pro"
        }
    }

    public var usesScale: Bool {
        [.markov, .phase2, .bassline, .keystepPro].contains(self)
    }

    public var hasPlocks: Bool {
        [.volcaDrum, .volcaKick, .volcaFM, .microfreak].contains(self)
    }
}

/// Paramètres de génération — mêmes clés JSON que `last_p` côté Python.
public struct GenParams: Codable, Equatable, Sendable {
    public var mode: Mode = .morph
    public var chaos: Double = 0.30
    public var bpm: Int = 110
    public var steps: Int = 64
    public var gravity: Double = 0.70
    public var ccDepth: Double = 0.50
    public var root: String = "A"
    public var scale: String = "penta_min"
    public var seed: String = ""
    public var swing: Double = 0.0
    public var velFloor: Int = 0
    public var velCeiling: Int = 127
    public var velCurve: Double = 1.0
    public var velHumanize: Int = 0
    public var microtiming: Double = 1.0

    public init() {}

    enum CodingKeys: String, CodingKey {
        case mode, chaos, bpm, steps, gravity, root, scale, seed, swing, microtiming
        case ccDepth = "cc_depth", velFloor = "vel_floor", velCeiling = "vel_ceiling"
        case velCurve = "vel_curve", velHumanize = "vel_humanize"
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let d = GenParams()
        mode = (try? c.decode(Mode.self, forKey: .mode)) ?? d.mode
        chaos = (try? c.decode(Double.self, forKey: .chaos)) ?? d.chaos
        bpm = (try? c.decode(Int.self, forKey: .bpm)) ?? d.bpm
        steps = (try? c.decode(Int.self, forKey: .steps)) ?? d.steps
        gravity = (try? c.decode(Double.self, forKey: .gravity)) ?? d.gravity
        ccDepth = (try? c.decode(Double.self, forKey: .ccDepth)) ?? d.ccDepth
        root = (try? c.decode(String.self, forKey: .root)) ?? d.root
        scale = (try? c.decode(String.self, forKey: .scale)) ?? d.scale
        seed = (try? c.decode(String.self, forKey: .seed)) ?? d.seed
        swing = (try? c.decode(Double.self, forKey: .swing)) ?? d.swing
        velFloor = (try? c.decode(Int.self, forKey: .velFloor)) ?? d.velFloor
        velCeiling = (try? c.decode(Int.self, forKey: .velCeiling)) ?? d.velCeiling
        velCurve = (try? c.decode(Double.self, forKey: .velCurve)) ?? d.velCurve
        velHumanize = (try? c.decode(Int.self, forKey: .velHumanize)) ?? d.velHumanize
        microtiming = (try? c.decode(Double.self, forKey: .microtiming)) ?? d.microtiming
    }

    /// Bornes de `read_form`.
    public func normalized() -> GenParams {
        var p = self
        p.steps = max(1, steps)
        if [.volcaDrum, .volcaKick, .volcaFM].contains(mode) { p.steps = min(p.steps, 16) }
        if mode == .bassline { p.steps = min(p.steps, 128) }
        if !Scales.chromatic.contains(root) { p.root = "A" }
        if !Scales.intervals.contains(where: { $0.id == scale }) { p.scale = "penta_min" }
        p.chaos = chaos.clamped(0, 1)
        p.bpm = max(1, bpm)
        p.gravity = gravity.clamped(0, 1)
        p.ccDepth = ccDepth.clamped(0, 1)
        p.swing = swing.clamped(0, 1)
        p.velFloor = min(max(velFloor, 0), 126)
        p.velCeiling = min(max(velCeiling, 1), 127)
        p.velCurve = velCurve.clamped(0.1, 4)
        p.velHumanize = min(max(velHumanize, 0), 40)
        p.microtiming = microtiming.clamped(0, 1)
        p.seed = seed.trimmingCharacters(in: .whitespaces)
        return p
    }
}

/// Une voix : (note, dna, type) comme le tuple Python.
/// Types : drum, markov, babka, cc, bl, vk, vd0-5, vfm0-2, mf0-2, ksp1-4.
public struct Voice: Codable, Equatable, Hashable, Sendable {
    public var note: Int
    public var dna: String
    public var type: String

    public init(_ note: Int, _ dna: String, _ type: String) {
        self.note = note
        self.dna = dna
        self.type = type
    }

    enum CodingKeys: String, CodingKey {
        case note, type
        case dna = "pattern"
    }

    public var isCC: Bool { type == "cc" }
    public var isBabka: Bool { type == "babka" }

    /// Hauteur produite par une chaîne de Markov plutôt que par `note`.
    public var isMelodic: Bool { type == "markov" || type == "bl" || type.hasPrefix("ksp") }

    public static let noteNames: [Int: String] = [
        24: "Bass", 33: "A1", 36: "Kick", 38: "Snare",
        40: "E1", 42: "HiHat", 43: "G1", 48: "Tom",
    ]
    static let vdNames = ["Punch", "Snap", "HH", "OH", "Perc", "Acc"]
    static let vfmNames = ["FM1", "FM2", "FM3"]
    static let mfNames = ["MF1", "MF2", "MF3"]
    static let kspNames = ["Lead", "Bass", "Chord", "Arp"]

    private func suffixIndex(_ prefix: String) -> Int {
        Int(type.dropFirst(prefix.count)) ?? 0
    }

    /// Nom affiché — clé des réglages par voix (comme `voice_label`).
    public var label: String {
        if type.hasPrefix("vfm") { return Voice.vfmNames[min(suffixIndex("vfm"), 2)] }
        if type.hasPrefix("vd") { return Voice.vdNames[min(suffixIndex("vd"), 5)] }
        if type.hasPrefix("mf") { return Voice.mfNames[min(suffixIndex("mf"), 2)] }
        if type.hasPrefix("ksp") { return "KSP " + Voice.kspNames[min(max(suffixIndex("ksp") - 1, 0), 3)] }
        if type == "babka" { return (Voice.noteNames[note] ?? "n\(note)") + " ⚗" }
        if type == "bl" { return "Bass ♩" }
        if type == "vk" { return "VKick" }
        if type == "cc" { return "CC" }
        return Voice.noteNames[note] ?? "n\(note)"
    }

    /// Canal MIDI par défaut (0-based) — live_clock.default_channel.
    public func defaultChannel(drumChannel: Int = 9) -> Int {
        if type.hasPrefix("ksp") { return [1: 2, 2: 3, 3: 4, 4: 5][suffixIndex("ksp")] ?? 2 }
        if type == "vk" { return 6 }
        if type.hasPrefix("vfm") { return 7 }
        if type.hasPrefix("mf") { return 8 }
        if type.hasPrefix("vd") { return drumChannel }
        if type == "bl" { return 0 }
        if type == "markov" { return 1 }
        if type == "drum" || type == "babka" { return note >= 35 ? drumChannel : 0 }
        return drumChannel
    }
}

/// LFO par voix (portage du LFO du webapp) : module la densité step par
/// step, ou la probabilité de drop cycle par cycle.
public struct VoiceLFO: Codable, Equatable, Sendable {
    public enum Shape: String, Codable, CaseIterable, Sendable { case sin, tri, ramp, rnd }
    public enum Target: String, Codable, CaseIterable, Sendable { case density, drop }
    public var shape: Shape = .sin
    public var target: Target = .density
    /// Périodes par pattern (densité) ou par cycle (drop) : 0.25 = une période sur 4 cycles.
    public var freq: Double = 1.0
    public var depth: Double = 0.5

    public init(shape: Shape = .sin, target: Target = .density, freq: Double = 1, depth: Double = 0.5) {
        self.shape = shape; self.target = target; self.freq = freq; self.depth = depth
    }

    /// Valeur [0, 1] pour une phase [0, 1).
    public func value(_ phase: Double, rng: Dice) -> Double {
        switch shape {
        case .sin: return 0.5 + 0.5 * sin(2 * .pi * phase)
        case .tri: return phase < 0.5 ? 2 * phase : 2 * (1 - phase)
        case .ramp: return phase
        case .rnd: return rng.random()
        }
    }

    /// Applique la modulation à une valeur de base (comme le webapp).
    public func modulate(_ base: Double, phase: Double, rng: Dice) -> Double {
        let p = phase - floor(phase)
        return (base * (1 - depth + value(p, rng: rng) * depth)).clamped(0, 1)
    }
}

/// Réglages par voix, indexés par label (comme les dicts `voice_*` de BangSession).
public struct VoiceSettings: Codable, Equatable, Sendable {
    public var density: Double = 1.0
    public var chord: String = "mono"
    public var channel: Int? = nil      // nil = auto
    public var drop: Double = 1.0       // probabilité de jouer le cycle
    public var swing: Double = 0.0      // 0 = swing global
    public var lfo: VoiceLFO? = nil
    /// Vélocité imposée par position DNA (1…127, 0 = celle du symbole).
    public var velLane: [Int] = []
    /// Probabilité imposée par position DNA (1…100 %, 0 = celle du symbole).
    public var probLane: [Int] = []
    /// Décalage de phase en steps (la lecture glisse, la DNA ne change pas).
    public var offset: Int = 0
    /// Thin ÷N : ne garde qu'un déclenchement sur N (1 = tous).
    public var thin: Int = 1
    /// Longueur imposée (polymétrie), réappliquée à chaque génération. nil = naturelle.
    public var length: Int? = nil

    public init() {}

    public var isDefault: Bool { self == VoiceSettings() }
}

/// P-lock : une automation CC par step pour une voix synthé.
public struct PLock: Codable, Equatable, Sendable {
    public var cc: Int
    public var name: String
    public var style: String
    public var values: [Int?]
}

extension Double {
    public func clamped(_ lo: Double, _ hi: Double) -> Double { Swift.min(Swift.max(self, lo), hi) }
}
