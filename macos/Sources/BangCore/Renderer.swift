import Foundation

public struct MIDIEvent: Equatable, Sendable {
    public enum Kind: Sendable { case noteOn, noteOff, cc }
    public var tick: Int
    public var kind: Kind
    public var channel: Int
    public var data1: Int
    public var data2: Int
    /// Index de la voix source (>= 0), ou -(n+1) pour la n-ième piste CC drone.
    public var voice: Int

    /// Au même tick : note-off et CC avant note-on (comme le tri (tick, priorité) Python).
    var order: Int { kind == .noteOn ? 1 : 0 }

    public var statusByte: UInt8 {
        let ch = UInt8(channel & 0x0F)
        switch kind {
        case .noteOn: return 0x90 | ch
        case .noteOff: return 0x80 | ch
        case .cc: return 0xB0 | ch
        }
    }
}

/// Tout ce qu'il faut pour rendre un pattern en évènements MIDI.
public struct RenderInput: Sendable {
    public var voices: [Voice]
    public var params: GenParams
    public var settings: [String: VoiceSettings]
    public var plocks: [[PLock]]
    public var weather: Weather?
    public var drumChannel: Int
    /// Mapping label → note (preset boîte à rythme), appliqué à la sortie.
    public var noteRemap: [String: Int]
    /// false = voix muette (mute/solo). Vide = toutes audibles.
    public var audible: [Bool]

    public init(voices: [Voice], params: GenParams, settings: [String: VoiceSettings] = [:],
                plocks: [[PLock]] = [], weather: Weather? = nil, drumChannel: Int = 9, noteRemap: [String: Int] = [:],
                audible: [Bool] = []) {
        self.voices = voices
        self.params = params
        self.settings = settings
        self.plocks = plocks
        self.weather = weather
        self.drumChannel = drumChannel
        self.noteRemap = noteRemap
        self.audible = audible
    }

    /// Note réellement envoyée pour une voix non mélodique.
    public func outputNote(for v: Voice) -> Int {
        if v.type.hasPrefix("vd") || v.isMelodic || v.isCC { return v.note }
        let key = v.isBabka ? (Voice.noteNames[v.note] ?? v.label) : v.label
        return noteRemap[key] ?? v.note
    }

    public func channel(for v: Voice) -> Int {
        settings[v.label]?.channel ?? v.defaultChannel(drumChannel: drumChannel)
    }

    // Variantes par index : tolèrent un index périmé (une vue SwiftUI peut se
    // redessiner une dernière fois juste après que le nombre de voix a baissé).
    public func outputNote(for i: Int) -> Int {
        voices.indices.contains(i) ? outputNote(for: voices[i]) : 0
    }

    public func channel(for i: Int) -> Int {
        voices.indices.contains(i) ? channel(for: voices[i]) : drumChannel
    }
}

/// Portage de BangEngine.export_midi + pattern_lib.assemble_engine.
/// Sert à la fois à l'export .mid et à la lecture live (un cycle à la fois).
public enum Renderer {
    public static let ticksPerStep = 120
    public static let ppq = 480  // 4 steps par noire

    struct CCTrack { var control: Int; var breakpoints: [Int] }

    static func velMap(_ vel: Int, _ p: GenParams) -> Int {
        let floor = p.velFloor, ceiling = p.velCeiling
        if ceiling <= floor { return max(1, floor) }
        var t = (Double(vel) / 127).clamped(0, 1)
        if p.velCurve != 1 { t = pow(t, p.velCurve) }
        return max(1, min(127, Int(Double(floor) + t * Double(ceiling - floor))))
    }

    static func ccTracks(_ p: GenParams, weather: Weather?) -> [CCTrack] {
        let peak = Int(20 + p.ccDepth * 100)
        let bps = [20, peak, peak, (20 + peak) / 2, 20]
        var out: [CCTrack] = []
        if p.mode == .markov || p.mode == .phase2 {
            out.append(CCTrack(control: 74, breakpoints: bps))
            if p.mode == .phase2, let w = weather {
                out.append(CCTrack(control: 91, breakpoints: Generator.weatherCCBreakpoints(w, points: 7).reversed()))
            }
        }
        if p.mode == .bassline {
            out.append(CCTrack(control: 74, breakpoints: bps))
            if p.chaos > 0.35 {
                let pp = Int(p.chaos * 60)
                out.append(CCTrack(control: 5, breakpoints: [0, pp, pp / 2, 0]))
            }
        }
        return out
    }

    /// Chaîne de Markov d'une voix mélodique (assemble_engine).
    static func chain(for v: Voice, _ p: GenParams) -> MarkovChain {
        let root = Scales.rootNote(p.root)
        let ivs = Scales.steps(p.scale)
        if v.type.hasPrefix("ksp") {
            let ch = (Int(v.type.dropFirst(3)) ?? 1) - 1
            let shift = [24, 0, 12, 24][min(max(ch, 0), 3)]
            return Scales.chain(root: root + shift, intervals: ivs, octaves: ch == 1 ? 1 : 2)
        }
        if v.type == "bl" {
            return Scales.chain(root: root, intervals: ivs, octaves: 2).withGravity(p.gravity)
        }
        return Scales.chain(root: root, intervals: ivs, octaves: 1).withGravity(p.gravity)
    }

    /// Rend `numSteps` steps. `gate` < 1 raccourcit les notes (lecture live).
    public static func render(_ input: RenderInput, numSteps: Int, rng: Dice, gate: Double = 1.0) -> [MIDIEvent] {
        let p = input.params
        let tps = ticksPerStep
        let maxMJ = Int((Double(tps) * 0.12).rounded())
        var events: [MIDIEvent] = []
        var kickDone = false

        func microJit() -> Int { Int(rng.uniform(-Double(maxMJ), Double(maxMJ)) * (1 - p.microtiming)) }
        func humanize() -> Int { p.velHumanize > 0 ? rng.int(-p.velHumanize, p.velHumanize) : 0 }

        for (vi, voice) in input.voices.enumerated() {
            if voice.isCC || voice.dna.isEmpty { continue }
            if vi < input.audible.count && !input.audible[vi] { continue }
            if voice.note == 0 && !voice.type.hasPrefix("ksp") { continue }

            let s = input.settings[voice.label] ?? VoiceSettings()
            if s.drop < 1 && rng.random() > s.drop { continue }
            let ch = input.channel(for: vi)
            let density = s.density
            let swing = s.swing > 0 ? s.swing : p.swing
            let outNote = input.outputNote(for: vi)

            func emit(_ t: Int, _ dur: Int, _ note: Int, _ vel: Int) {
                let off = t + max(1, Int(Double(dur) * gate))
                events.append(MIDIEvent(tick: t, kind: .noteOn, channel: ch, data1: note & 0x7F, data2: vel, voice: vi))
                events.append(MIDIEvent(tick: off, kind: .noteOff, channel: ch, data1: note & 0x7F, data2: 0, voice: vi))
            }

            // --- Babka : durées fractionnaires, alternances par cycle interne ---
            if voice.isBabka {
                let total = Double(numSteps * tps)
                var cursor = 0.0
                var cyc = 0
                outer: while cursor < total {
                    let steps = Babka.parse(voice.dna, cycle: cyc)
                    if steps.isEmpty || Babka.totalSteps(steps) <= 0 { break }
                    for st in steps {
                        if cursor >= total { break outer }
                        let durTicks = st.duration * Double(tps)
                        let c = st.cell
                        if c.trigger && rng.random() < c.prob * density {
                            let jit = Int(rng.uniform(-Double(c.jitter), Double(c.jitter)))
                            let start = max(0, Int(cursor) + jit + microJit())
                            let rDiv = max(1, c.ratchet)
                            let rDur = max(1, Int(durTicks) / rDiv)
                            let vel = velMap(c.velocity + humanize(), p)
                            for r in 0..<rDiv { emit(start + r * rDur, rDur, outNote, vel) }
                        }
                        cursor += durTicks
                    }
                    cyc += 1
                }
                continue
            }

            // --- DNA grille (drum / markov / synthés) ---
            var patterns = [DNA.compile(voice.dna)]
            if p.mode == .phase2 && voice.note == 36 && voice.type == "drum" && !kickDone {
                patterns.append(DNA.compile(DNA.mutate("x---x--x", intensity: p.chaos * 0.8, rng: rng)))
                kickDone = true
            }
            let melodic = voice.isMelodic
            let melody = melodic ? chain(for: voice, p).generate(numSteps, rng: rng) : []
            let chordOffsets = melodic ? Chords.intervals(s.chord) : []
            let plocks = vi < input.plocks.count ? input.plocks[vi] : []

            var pIdx = 0, sIdx = 0
            for i in 0..<numSteps {
                let pattern = patterns[pIdx]
                let c = pattern[sIdx]
                let note = melodic ? melody[i] : outNote
                let baseVel = melodic ? 95 : c.velocity

                if c.trigger && rng.random() < c.prob * density {
                    let swingOff = i % 2 == 1 ? Int(swing * Double(tps) * 0.5) : 0
                    let jit = Int(rng.uniform(-Double(c.jitter), Double(c.jitter)))
                    let start = max(0, i * tps + swingOff + jit + microJit())
                    let rDiv = max(1, c.ratchet)
                    let rDur = tps / rDiv
                    let vel = velMap(baseVel + humanize(), p)
                    for r in 0..<rDiv {
                        let t = start + r * rDur
                        emit(t, rDur, note, vel)
                        for off in chordOffsets { emit(t, rDur, min(127, max(0, note + off)), vel) }
                    }
                }
                for pl in plocks where i < pl.values.count {
                    if let v = pl.values[i] {
                        events.append(MIDIEvent(tick: i * tps, kind: .cc, channel: ch, data1: pl.cc, data2: v, voice: vi))
                    }
                }
                sIdx += 1
                if sIdx >= pattern.count {
                    sIdx = 0
                    pIdx = (pIdx + 1) % patterns.count
                }
            }
        }

        // --- Drones CC interpolés ---
        let ccCh = input.drumChannel == 0 ? 1 : 0
        for (k, cc) in ccTracks(p, weather: input.weather).enumerated() {
            let bps = cc.breakpoints
            for i in 0..<numSteps {
                var val = bps[0]
                if bps.count > 1 {
                    let t = numSteps > 1 ? Double(i) / Double(numSteps - 1) * Double(bps.count - 1) : 0
                    let idx = Int(t)
                    let frac = t - Double(idx)
                    let a = bps[min(idx, bps.count - 1)], b = bps[min(idx + 1, bps.count - 1)]
                    val = Int(Double(a) * (1 - frac) + Double(b) * frac)
                }
                events.append(MIDIEvent(tick: i * tps, kind: .cc, channel: ccCh, data1: cc.control,
                                        data2: min(127, max(0, val)), voice: -(k + 1)))
            }
        }

        events.sort { ($0.tick, $0.order) < ($1.tick, $1.order) }
        return events
    }

    /// Noms des pistes CC drone (pour l'export).
    public static func ccTrackNames(_ p: GenParams, weather: Weather?) -> [String] {
        ccTracks(p, weather: weather).map { "CC\($0.control)" }
    }
}
