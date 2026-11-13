import Foundation

/// Kits de batterie du synthé interne.
public enum DrumKit: String, CaseIterable, Codable, Sendable, Identifiable {
    case gm, tr808 = "808", tr909 = "909"
    public var id: String { rawValue }
    public var label: String {
        switch self {
        case .gm: return "General MIDI (acoustique)"
        case .tr808: return "808 — synthèse analogique"
        case .tr909: return "909 — synthèse analogique"
        }
    }
    public var short: String {
        switch self {
        case .gm: return "GM"
        case .tr808: return "808"
        case .tr909: return "909"
        }
    }
}

/// Batterie électro synthétisée — pas d'échantillons : chaque son est
/// construit comme dans les boîtes à rythmes analogiques (oscillateurs,
/// bruit, filtres, enveloppes). Pur Swift, sans AVFoundation, pour pouvoir
/// être rendu hors-ligne et testé (`bang-check`).
///
/// Thread : `trigger` peut être appelé depuis n'importe quel thread,
/// `render` depuis le thread audio. Un petit verrou protège la file
/// d'attente des déclenchements.
public final class DrumSynth: @unchecked Sendable {
    public let sampleRate: Double
    private var voices: [DrumVoice] = []
    private var pending: [(note: Int, vel: Int, kit: DrumKit)] = []
    private var clearRequested = false
    private let lock = NSLock()
    public var gain: Float = 0.8

    public init(sampleRate: Double = 48_000) { self.sampleRate = sampleRate }

    public func trigger(note: Int, velocity: Int, kit: DrumKit) {
        guard velocity > 0, kit != .gm else { return }
        lock.lock(); pending.append((note, velocity, kit)); lock.unlock()
    }

    /// Coupe tout au prochain bloc audio.
    public func allOff() {
        lock.lock(); pending.removeAll(); clearRequested = true; lock.unlock()
    }

    /// Remplit `out` (mono, `count` échantillons) en mixant les voix actives.
    public func render(_ out: UnsafeMutablePointer<Float>, count: Int) {
        lock.lock()
        let fresh = pending
        pending.removeAll(keepingCapacity: true)
        let clear = clearRequested
        clearRequested = false
        lock.unlock()

        if clear { voices.removeAll() }
        for t in fresh {
            guard let kind = DrumVoice.kind(for: t.note) else { continue }
            // Le charleston fermé coupe l'ouvert (choke), comme sur les machines.
            if kind == .closedHat { voices.removeAll { $0.kind == .openHat } }
            if voices.count >= 24 { voices.removeFirst() }
            voices.append(DrumVoice(kind: kind, kit: t.kit, note: t.note, velocity: t.vel, sr: sampleRate))
        }

        for i in 0..<count { out[i] = 0 }
        guard !voices.isEmpty else { return }
        for v in voices.indices {
            for i in 0..<count { out[i] += voices[v].next() }
        }
        voices.removeAll { $0.done }
        for i in 0..<count { out[i] = tanhf(out[i] * gain) }  // saturation douce
    }

    /// Rendu hors-ligne d'un seul coup (tests, aperçu).
    public static func renderHit(note: Int, kit: DrumKit, velocity: Int = 110,
                                 seconds: Double = 1.0, sampleRate: Double = 48_000) -> [Float] {
        let s = DrumSynth(sampleRate: sampleRate)
        s.trigger(note: note, velocity: velocity, kit: kit)
        var buf = [Float](repeating: 0, count: Int(seconds * sampleRate))
        buf.withUnsafeMutableBufferPointer { s.render($0.baseAddress!, count: $0.count) }
        return buf
    }
}

// MARK: - Voix

struct DrumVoice {
    enum Kind: Equatable { case kick, snare, clap, rim, closedHat, openHat, tom, cymbal, ride, cowbell }

    let kind: Kind
    let kit: DrumKit
    let sr: Float
    let amp: Float
    var t: Float = 0          // temps écoulé (s)
    var done = false
    let length: Float         // durée max (s)

    // Oscillateurs / bruit / filtres
    var phase: Float = 0
    var p0: Float = 0, p1: Float = 0, p2: Float = 0, p3: Float = 0, p4: Float = 0, p5: Float = 0
    var seed: UInt32
    var hp = OnePoleHP()
    var hp2 = OnePoleHP()
    var bp = Biquad()
    var lp: Float = 0
    let tomFreq: Float

    static func kind(for note: Int) -> Kind? {
        switch note {
        case 35, 36: return .kick
        case 37: return .rim
        case 38, 40: return .snare
        case 39: return .clap
        case 42, 44, 54: return .closedHat
        case 46: return .openHat
        case 41, 43, 45, 47, 48, 50: return .tom
        case 49, 52, 55, 57: return .cymbal
        case 51, 53, 59: return .ride
        case 56: return .cowbell
        default: return note > 0 ? .tom : nil  // percussion accordée sur la note
        }
    }

    init(kind: Kind, kit: DrumKit, note: Int, velocity: Int, sr: Double) {
        self.kind = kind
        self.kit = kit
        self.sr = Float(sr)
        let v = Float(max(1, min(127, velocity))) / 127
        amp = 0.25 + 0.75 * v * v
        seed = UInt32(truncatingIfNeeded: note &* 2_654_435_761 &+ velocity &* 40503) | 1

        // Toms : low / mid / high selon la note GM, sinon la hauteur de la note.
        switch note {
        case 41, 43: tomFreq = kit == .tr909 ? 95 : 82
        case 45, 47: tomFreq = kit == .tr909 ? 135 : 120
        case 48, 50: tomFreq = kit == .tr909 ? 190 : 165
        default: tomFreq = min(900, max(60, 440 * powf(2, Float(note - 69) / 12)))
        }

        switch kind {
        case .kick: length = kit == .tr808 ? 1.4 : 0.6
        case .snare: length = 0.45
        case .clap: length = 0.5
        case .rim: length = 0.08
        case .closedHat: length = 0.15
        case .openHat: length = kit == .tr808 ? 0.7 : 0.9
        case .tom: length = 0.8
        case .cymbal: length = 2.2
        case .ride: length = 2.0
        case .cowbell: length = 0.6
        }

        let fs = Float(sr)
        switch kind {
        case .snare:
            hp.set(cutoff: kit == .tr909 ? 1800 : 1200, sr: fs)
        case .clap:
            bp.setBandpass(freq: kit == .tr909 ? 1300 : 1000, q: 1.6, sr: fs)
        case .rim:
            bp.setBandpass(freq: 1700, q: 4, sr: fs)
        case .closedHat, .openHat:
            bp.setBandpass(freq: kit == .tr909 ? 10_500 : 9_000, q: 1.2, sr: fs)
            hp.set(cutoff: 7_000, sr: fs)
        case .cymbal, .ride:
            bp.setBandpass(freq: kind == .ride ? 8_500 : 7_000, q: 0.9, sr: fs)
            hp.set(cutoff: kind == .ride ? 6_000 : 4_500, sr: fs)
        case .cowbell:
            bp.setBandpass(freq: 2_640, q: 3, sr: fs)
        default:
            break
        }
        hp2.set(cutoff: 30, sr: fs)  // anti-DC
    }

    mutating func noise() -> Float {
        seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5
        return Float(Int32(bitPattern: seed)) / Float(Int32.max)
    }

    mutating func sine(_ f: Float) -> Float {
        phase += f / sr
        if phase >= 1 { phase -= 1 }
        return sinf(2 * .pi * phase)
    }

    @inline(__always) static func step(_ p: inout Float, _ inc: Float) -> Float {
        p += inc
        if p >= 1 { p -= 1 }
        return p < 0.5 ? 1 : -1
    }

    /// Six carrés désaccordés aux fréquences « métalliques » des charlestons
    /// et cymbales analogiques (× ratio de transposition).
    mutating func metallic(_ r: Float) -> Float {
        let k = r / sr
        let s = DrumVoice.step(&p0, 205.3 * k) + DrumVoice.step(&p1, 304.4 * k)
            + DrumVoice.step(&p2, 369.6 * k) + DrumVoice.step(&p3, 522.7 * k)
            + DrumVoice.step(&p4, 540.0 * k) + DrumVoice.step(&p5, 800.0 * k)
        return s / 6
    }

    @inline(__always) func env(_ decay: Float) -> Float { expf(-t / decay) }

    mutating func next() -> Float {
        if done { return 0 }
        let is909 = kit == .tr909
        var y: Float = 0
        switch kind {
        case .kick:
            if !is909 {
                // Sinus dont la hauteur plonge vite de ~120 à ~49 Hz, longue queue.
                let f: Float = 49 + 70 * expf(-t / 0.018)
                y = sine(f) * env(0.45) + noise() * 0.12 * env(0.002)
            } else {
                // 909 : attaque plus dure, balayage plus large, sinus saturé + clic.
                let f: Float = 52 + 180 * expf(-t / 0.012)
                y = tanhf(sine(f) * 2.2) * 0.8 * env(0.22) + noise() * 0.35 * env(0.003)
            }
        case .snare:
            let toneA = sine(is909 ? 190 : 180)
            let toneB = sinf(2 * .pi * (is909 ? 345 : 330) * t)
            let tone = (toneA * 0.6 + toneB * 0.4) * env(is909 ? 0.06 : 0.09)
            // Bruit « snappy » : passe-haut puis passe-bas (~6 kHz), comme le circuit.
            lp += 0.55 * (hp.process(noise()) - lp)
            let n = lp * env(is909 ? 0.12 : 0.09)
            y = tone * (is909 ? 0.75 : 0.95) + n * (is909 ? 0.85 : 0.55)
        case .clap:
            // Trois rafales rapprochées puis une queue réverbérée.
            var e: Float
            if t < 0.011 { e = expf(-t / 0.004) }
            else if t < 0.022 { e = 0.9 * expf(-(t - 0.011) / 0.004) }
            else if t < 0.033 { e = 0.8 * expf(-(t - 0.022) / 0.004) }
            else { e = 0.85 * expf(-(t - 0.033) / 0.11) }
            y = bp.process(noise()) * e * 2.2
        case .rim:
            y = (bp.process(noise()) * 1.5 + sine(1_700) * 0.5) * env(0.012)
        case .closedHat:
            let m = metallic(is909 ? 1.35 : 1.0) + (is909 ? noise() * 0.5 : 0)
            y = hp.process(bp.process(m)) * env(is909 ? 0.035 : 0.045) * 1.6
        case .openHat:
            let m = metallic(is909 ? 1.35 : 1.0) + (is909 ? noise() * 0.5 : 0)
            y = hp.process(bp.process(m)) * env(is909 ? 0.28 : 0.22) * 1.4
        case .tom:
            let drop: Float = is909 ? 0.35 : 0.15
            let f = tomFreq * (1 + drop * expf(-t / 0.05))
            y = sine(f) * env(is909 ? 0.22 : 0.28) + noise() * 0.05 * env(0.004)
        case .cymbal:
            let m = metallic(1.6) * 0.6 + noise() * 0.6
            y = hp.process(bp.process(m)) * env(0.75) * 1.1
        case .ride:
            let m = metallic(2.1) * 0.8 + noise() * 0.25
            y = hp.process(bp.process(m)) * env(0.6) * 0.9
        case .cowbell:
            // Deux carrés à 540 et 800 Hz filtrés, enveloppe à deux pentes.
            let sq = (DrumVoice.step(&p0, 540 / sr) + DrumVoice.step(&p1, 800 / sr)) * 0.5
            lp += 0.35 * (bp.process(sq) - lp)
            y = lp * (0.6 * env(0.015) + 0.4 * env(0.18)) * 1.8
        }
        // Fondu de fin (30 ms) : pas de clic quand la voix s'arrête.
        let fade = min(1, (length - t) / 0.03)
        t += 1 / sr
        if t >= length { done = true }
        return hp2.process(y) * amp * max(0, fade)
    }
}

// MARK: - Filtres

struct OnePoleHP {
    var a: Float = 0.99
    var x1: Float = 0
    var y1: Float = 0

    mutating func set(cutoff: Float, sr: Float) {
        let rc = 1 / (2 * .pi * cutoff)
        a = rc / (rc + 1 / sr)
    }

    mutating func process(_ x: Float) -> Float {
        let y = a * (y1 + x - x1)
        x1 = x; y1 = y
        return y
    }
}

/// Biquad RBJ passe-bande (gain de pic 0 dB).
struct Biquad {
    var b0: Float = 1, b1: Float = 0, b2: Float = 0, a1: Float = 0, a2: Float = 0
    var x1: Float = 0, x2: Float = 0, y1: Float = 0, y2: Float = 0

    mutating func setBandpass(freq: Float, q: Float, sr: Float) {
        let w = 2 * .pi * min(freq, sr * 0.45) / sr
        let alpha = sinf(w) / (2 * q)
        let a0 = 1 + alpha
        b0 = alpha / a0; b1 = 0; b2 = -alpha / a0
        a1 = -2 * cosf(w) / a0; a2 = (1 - alpha) / a0
    }

    mutating func process(_ x: Float) -> Float {
        let y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1; x1 = x; y2 = y1; y1 = y
        return y
    }
}
