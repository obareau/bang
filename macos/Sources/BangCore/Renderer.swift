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
    /// Numéro du cycle joué (phase des LFO de drop). Fixé par le lecteur.
    public var cycle: Int = 0
    /// Morphing en cours vers un autre pattern (voix cibles + avancement 0…1).
    public var morph: MorphTarget? = nil
    /// Polyphonie max : au plus N voix déclenchées par step (0 = illimité).
    public var maxPoly: Int = 0
    /// Interpolation des p-locks entre deux valeurs définies.
    public var plockInterp: PLockInterpolation = .off
    /// Mode FILL actif (conditions « fill » / « !fill »).
    public var fill: Bool = false

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

/// Cible d'un morphing : les voix d'une mémoire et l'avancement (0 = départ, 1 = cible).
/// Comme dans le webapp, chaque step mélange les probabilités et les vélocités
/// des deux patterns, voix par voix.
public struct MorphTarget: Sendable, Equatable {
    public var voices: [Voice]
    public var progress: Double

    public init(voices: [Voice], progress: Double) {
        self.voices = voices
        self.progress = progress
    }

    /// Cellule mélangée entre `a` (pattern courant) et `b` (cible).
    static func blend(_ a: DNACell, _ b: DNACell, _ p: Double) -> DNACell {
        let pa = a.trigger ? a.prob : 0, pb = b.trigger ? b.prob : 0
        let prob = pa * (1 - p) + pb * p
        guard prob >= 0.001 else { return DNA.cell("-") }
        let base = a.trigger ? a : b
        let vel = a.trigger && b.trigger
            ? Int((Double(a.velocity) * (1 - p) + Double(b.velocity) * p).rounded())
            : base.velocity
        return DNACell(trigger: true, velocity: vel, prob: prob, ratchet: base.ratchet, jitter: base.jitter)
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
        /// Entropie temporelle (webapp : time_ns() % 1000) — volontairement hors seed.
        func temporalJit(_ jitter: Int) -> Int {
            guard p.temporal, jitter > 0 else { return 0 }
            let micro = Double(DispatchTime.now().uptimeNanoseconds % 1000)
            return Int((micro / 1000 - 0.5) * Double(jitter) * 0.5)
        }
        // Polyphonie max : budget de déclenchements par step, attribué dans l'ordre des voix.
        var polyUsed: [Int: Int] = [:]
        func polyAllows(_ step: Int) -> Bool {
            guard input.maxPoly > 0 else { return true }
            let used = polyUsed[step, default: 0]
            guard used < input.maxPoly else { return false }
            polyUsed[step] = used + 1
            return true
        }

        for (vi, voice) in input.voices.enumerated() {
            if voice.isCC || voice.dna.isEmpty { continue }
            if vi < input.audible.count && !input.audible[vi] { continue }
            if voice.note == 0 && !voice.type.hasPrefix("ksp") { continue }

            let s = input.settings[voice.label] ?? VoiceSettings()
            if !TrigCondition.passes(s.condition, cycle: input.cycle, fill: input.fill) { continue }
            var drop = s.drop
            if let lfo = s.lfo, lfo.target == .drop {
                drop = lfo.modulate(drop, phase: Double(input.cycle) * lfo.freq, rng: rng)
            }
            if drop < 1 && rng.random() > drop { continue }
            /// Densité au step `pos` (LFO de densité : `freq` périodes par pattern).
            func densityAt(_ pos: Double) -> Double {
                guard let lfo = s.lfo, lfo.target == .density else { return s.density }
                return lfo.modulate(s.density, phase: pos / Double(max(1, numSteps)) * lfo.freq, rng: rng)
            }
            let ch = input.channel(for: vi)
            let swing = s.swing > 0 ? s.swing : p.swing
            let outNote = input.outputNote(for: vi)

            func emit(_ t: Int, _ dur: Int, _ note: Int, _ vel: Int) {
                let off = t + max(1, Int(Double(dur) * gate))
                events.append(MIDIEvent(tick: t, kind: .noteOn, channel: ch, data1: note & 0x7F, data2: vel, voice: vi))
                events.append(MIDIEvent(tick: off, kind: .noteOff, channel: ch, data1: note & 0x7F, data2: 0, voice: vi))
            }

            // --- Babka : durées fractionnaires, alternances par cycle interne ---
            let offsetTicks = ((s.offset % max(1, numSteps)) + numSteps) % max(1, numSteps) * tps
            let cycleLen = numSteps * tps
            /// Décalage de phase : la note glisse, et ce qui dépasse la fin revient au début.
            func shifted(_ t: Int) -> Int { offsetTicks == 0 ? t : (t + offsetTicks) % max(1, cycleLen) }
            let thin = max(1, s.thin)
            var trigCount = 0
            /// Thin ÷N : un déclenchement sur N est gardé.
            func keepTrigger() -> Bool {
                defer { trigCount += 1 }
                return thin == 1 || trigCount % thin == 0
            }

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
                        if c.trigger && keepTrigger() && rng.random() < c.prob * densityAt(cursor / Double(tps))
                            && polyAllows(Int(cursor) / tps) {
                            let jit = Int(rng.uniform(-Double(c.jitter), Double(c.jitter))) + temporalJit(c.jitter)
                            let start = shifted(max(0, Int(cursor) + jit + microJit()))
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
            let markov = melodic ? chain(for: voice, p) : nil
            let melody = markov?.generate(numSteps, rng: rng) ?? []
            let chordOffsets = melodic ? Chords.intervals(s.chord) : []
            let plocks = (vi < input.plocks.count ? input.plocks[vi] : []) + s.ccLanes
            // Morphing : la voix de même rang dans la cible, si c'est une grille DNA.
            var morphCells: [DNACell]? = nil
            if let m = input.morph, vi < m.voices.count, !m.voices[vi].isCC, !m.voices[vi].isBabka,
               DNA.isPlain(m.voices[vi].dna) {
                morphCells = DNA.compile(m.voices[vi].dna)
            }

            var pIdx = 0, sIdx = 0
            for i in 0..<numSteps {
                let pattern = patterns[pIdx]
                var c = pattern[sIdx]
                if let mc = morphCells, let m = input.morph {
                    c = MorphTarget.blend(c, mc[i % mc.count], m.progress)
                }
                let note = melodic ? min(127, max(0, melody[i] + p.transpose)) : outNote
                var baseVel = melodic ? 95 : c.velocity
                // Lanes (indexées par position DNA, 1er pattern seulement)
                if pIdx == 0 {
                    if sIdx < s.velLane.count, s.velLane[sIdx] > 0 { baseVel = min(127, s.velLane[sIdx]) }
                    if sIdx < s.probLane.count, s.probLane[sIdx] > 0, c.trigger { c.prob = Double(min(100, s.probLane[sIdx])) / 100 }
                    if sIdx < s.ratchetLane.count, s.ratchetLane[sIdx] > 0 { c.ratchet = min(8, s.ratchetLane[sIdx]) }
                }

                let outStep = (i + offsetTicks / tps) % max(1, numSteps)
                if c.trigger && keepTrigger() && rng.random() < c.prob * densityAt(Double(i)) && polyAllows(outStep) {
                    let swingOff = outStep % 2 == 1 ? Int(swing * Double(tps) * 0.5) : 0
                    let jit = Int(rng.uniform(-Double(c.jitter), Double(c.jitter))) + temporalJit(c.jitter)
                    let start = max(0, outStep * tps + swingOff + jit + microJit())
                    let rDiv = max(1, c.ratchet)
                    let rDur = tps / rDiv
                    let vel = velMap(baseVel + humanize(), p)
                    var rNote = note
                    for r in 0..<rDiv {
                        let t = start + r * rDur
                        // Ratchets : decay (chaque répétition plus douce) et variation
                        // (vélocité qui dérive, hauteur qui glisse sur la chaîne de Markov).
                        var rv = Double(vel) * pow(1 - s.ratchetDecay * 0.85, Double(r))
                        if r > 0 && s.ratchetVariation > 0 {
                            rv += rng.uniform(-1, 1) * s.ratchetVariation * 25
                            if let mk = markov, rng.random() < s.ratchetVariation * 0.5 {
                                rNote = min(127, max(0, mk.next(after: rNote - p.transpose, rng: rng) + p.transpose))
                            }
                        }
                        let rVel = max(1, min(127, Int(rv.rounded())))
                        emit(t, rDur, rNote, rVel)
                        for off in chordOffsets { emit(t, rDur, min(127, max(0, rNote + off)), rVel) }
                    }
                }
                sIdx += 1
                if sIdx >= pattern.count {
                    sIdx = 0
                    pIdx = (pIdx + 1) % patterns.count
                }
            }
            // P-locks (générés + pistes CC ajoutées), éventuellement interpolés.
            for pl in plocks {
                events += plockEvents(pl, numSteps: numSteps, interp: input.plockInterp, channel: ch, voice: vi)
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

    /// Évènements CC d'une piste de p-locks. Sans interpolation : une valeur aux
    /// steps définis. Avec : 4 valeurs par step entre deux p-locks définis
    /// (linéaire ou cosinus), valeur tenue avant le premier et après le dernier.
    public static func plockEvents(_ pl: PLock, numSteps: Int, interp: PLockInterpolation,
                            channel: Int, voice: Int) -> [MIDIEvent] {
        let tps = ticksPerStep
        let defined = pl.values.enumerated().compactMap { i, v in v.map { (i, $0) } }.filter { $0.0 < numSteps }
        guard !defined.isEmpty else { return [] }
        func cc(_ tick: Int, _ v: Int) -> MIDIEvent {
            MIDIEvent(tick: tick, kind: .cc, channel: channel, data1: pl.cc, data2: min(127, max(0, v)), voice: voice)
        }
        if interp == .off { return defined.map { cc($0.0 * tps, $0.1) } }
        var out: [MIDIEvent] = []
        var last = -1
        let sub = 4
        for k in 0..<(numSteps * sub) {
            let pos = Double(k) / Double(sub)
            let before = defined.last { Double($0.0) <= pos }
            let after = defined.first { Double($0.0) > pos }
            var v: Double
            if let b = before, let a = after {
                var t = (pos - Double(b.0)) / Double(a.0 - b.0)
                if interp == .cosine { t = (1 - cos(t * .pi)) / 2 }
                v = Double(b.1) + Double(a.1 - b.1) * t
            } else {
                v = Double((before ?? after!).1)
            }
            let iv = Int(v.rounded())
            if iv != last { out.append(cc(k * tps / sub, iv)); last = iv }
        }
        return out
    }

    /// Noms des pistes CC drone (pour l'export).
    public static func ccTrackNames(_ p: GenParams, weather: Weather?) -> [String] {
        ccTracks(p, weather: weather).map { "CC\($0.control)" }
    }
}
