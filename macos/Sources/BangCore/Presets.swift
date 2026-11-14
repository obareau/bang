import Foundation

/// Presets — portage de presets_lib.py (grooves + mappings boîtes à rythme).
public enum Presets {
    public static let grooves: [(name: String, dna: [String])] = [
        ("MPC Boom Bap", ["x---x---x---x---", "----x-------x---", "x-x-x-x-x-x-x-x", "---x-----------x"]),
        ("Trap", ["x-----------x---", "----x-----x-x---", "xxxxxxxxxxxxxxxx", "x-x-x-----------"]),
        ("Bossa Nova", ["x--x--x-x--x--x-", "---x-----x------", "x-x-x-x-x-x-x-x", "x---x---x---x---"]),
        ("Reggae", ["--------x-------", "x---x---x---x---", "x-x-x-x-x-x-x-x", "----x-------x---"]),
        ("Afrobeat", ["x--x--x--x--x--x", "--x---x---x---x-", "x-x-x-x-x-x-x-x", "x--x-x--x--x-x--"]),
        ("Techno", ["x---x---x---x---", "----x-------x---", "-x-x-x-x-x-x-x-", "x-----------x---"]),
        ("Drum'n'Bass", ["x-----------x-x-", "----x-----------", "x-x-x-x-x-x-x-x", "x--x--x--x--x---"]),
        ("Hip-Hop Swing", ["x---x--x----x---", "----x-------x---", "x--x--x-x--x--x-", "--x---x-------x-"]),
        ("Breakbeat", ["x-x---x-x-x---x-", "---x-----x------", "x-x-x-x-x-x-x-x", "--x---x-------x-"]),
        ("Cumbia", ["x--x-x--x--x-x--", "----x-------x---", "-x-x-x-x-x-x-x-", "x---x---x---x---"]),
        ("Soca", ["x---x---x---x---", "--x---x---x---x-", "x-x-x-x-x-x-x-x", "x-x---x-x-x---x-"]),
        ("Clave 3-2", ["x--x--x---------", "--------x--x-x--", "x-x-x-x-x-x-x-x", "x--x--x--x-x-x--"]),
        ("Waltz 3/4", ["x-----x-----x---", "--x-----x-----x-", "x-x-x-x-x-x-x-x", "x---x---x---x---"]),
        ("Shuffle", ["x---x---x---x---", "----x-------x---", "x--x--x--x--x--x", "--------x-------"]),
        ("Minimal Techno", ["x-----------x---", "----x-----------", "-x-x-x-x-x-x-x-", "x---------------"]),
        ("Straight", ["x---x---x---x---", "----x-------x---", "x---x---x---x---", ""]),
    ]

    public static let drumMachines: [(name: String, map: [String: Int])] = [
        ("GM", ["Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48, "Bass": 24, "A1": 33, "E1": 40, "G1": 43]),
        ("TR-808", ["Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 43, "Bass": 36, "A1": 46, "E1": 39, "G1": 45]),
        ("TR-909", ["Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 50, "Bass": 36, "A1": 49, "E1": 40, "G1": 47]),
        ("MPC60", ["Kick": 35, "Snare": 40, "HiHat": 42, "Tom": 47, "Bass": 36, "A1": 38, "E1": 39, "G1": 43]),
        ("Battery 4", ["Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48, "Bass": 24, "A1": 33, "E1": 40, "G1": 43]),
        ("Tekno", ["Kick": 36, "Bass": 37, "Snare": 38, "E1": 39, "HiHat": 40, "G1": 41, "A1": 42, "Tom": 43]),
        ("LinnDrum", ["Kick": 36, "Snare": 38, "HiHat": 42, "Tom": 48, "Bass": 43, "A1": 46, "E1": 37, "G1": 41]),
        ("Volca Kick", ["VKick": 60]),
        ("Volca FM", ["FM1": 36, "FM2": 43, "FM3": 48]),
        ("MicroFreak", ["MF1": 45, "MF2": 40, "MF3": 36]),
    ]
}

/// Preset d'harmonie (KeyStep Pro) — même schéma que KSP_PRESETS_BUILTIN.
public struct KSPPreset: Codable, Equatable, Sendable {
    public var root: String
    public var scale: String
    public var gravity: Double
    public var chords: [String: String]

    public init(root: String, scale: String, gravity: Double, chords: [String: String]) {
        self.root = root; self.scale = scale; self.gravity = gravity; self.chords = chords
    }
}

extension Presets {
    public static let ksp: [(name: String, preset: KSPPreset)] = [
        ("Dark Penta", KSPPreset(root: "A", scale: "penta_min", gravity: 0.75,
                                 chords: ["KSP Lead": "minor", "KSP Bass": "power", "KSP Chord": "m7", "KSP Arp": "mono"])),
        ("Dorian Jazz", KSPPreset(root: "D", scale: "dorian", gravity: 0.60,
                                  chords: ["KSP Lead": "m7", "KSP Bass": "power", "KSP Chord": "M7", "KSP Arp": "sus2"])),
        ("Phrygian Noise", KSPPreset(root: "E", scale: "phrygian", gravity: 0.85,
                                     chords: ["KSP Lead": "dim", "KSP Bass": "power", "KSP Chord": "minor", "KSP Arp": "mono"])),
        ("Lydian Dream", KSPPreset(root: "C", scale: "lydian", gravity: 0.55,
                                   chords: ["KSP Lead": "M7", "KSP Bass": "mono", "KSP Chord": "sus2", "KSP Arp": "aug"])),
        ("Blues Minor", KSPPreset(root: "A", scale: "minor", gravity: 0.70,
                                  chords: ["KSP Lead": "minor", "KSP Bass": "power", "KSP Chord": "dom7", "KSP Arp": "minor"])),
    ]
}

/// Fichier de session JSON — même schéma que `session_to_dict` (presets_lib.py),
/// donc échangeable avec le webapp et l'app Qt.
public struct SessionFile: Codable {
    public var bangVersion: String
    public var timestamp: String
    public var seed: String
    public var params: GenParams
    public var voices: [Voice]
    public var voiceDensity: [String: Double]
    public var voiceChords: [String: String]
    public var voiceMidiCh: [String: Int]?
    public var voiceLFO: [String: VoiceLFO]?
    public var voiceDrop: [String: Double]?
    public var voiceSwing: [String: Double]?
    public var voiceVelLane: [String: [Int]]?
    public var voiceProbLane: [String: [Int]]?
    public var voiceOffset: [String: Int]?
    public var voiceThin: [String: Int]?
    public var voiceSteps: [String: Int]?
    public var maxPoly: Int?
    public var plockInterp: PLockInterpolation?
    public var voiceRatchetLane: [String: [Int]]?
    public var voiceRatchetDecay: [String: Double]?
    public var voiceRatchetVar: [String: Double]?
    public var voiceCondition: [String: String]?
    public var voiceCCLanes: [String: [PLock]]?
    public var voicePort: [String: Int32]?
    public var slots: [BangSession.Snapshot?]?
    public var slotWeights: [Int]?
    public var slotA: BangSession.Snapshot?
    public var slotB: BangSession.Snapshot?
    public var noteRemap: [String: Int]
    public var lockedVoices: [Int]
    public var plocks: [[PLock]]?

    enum CodingKeys: String, CodingKey {
        case seed, params, voices, timestamp, plocks
        case bangVersion = "bang_version", voiceDensity = "voice_density"
        case voiceChords = "voice_chords", voiceMidiCh = "voice_midi_ch"
        case noteRemap = "note_remap", lockedVoices = "locked_voices"
        case voiceLFO = "voice_lfo", voiceDrop = "voice_drop", voiceSwing = "voice_swing"
        case voiceVelLane = "voice_vel_lane", voiceProbLane = "voice_prob_lane"
        case voiceOffset = "voice_offset", voiceThin = "voice_thin", voiceSteps = "voice_steps"
        case maxPoly = "max_poly", plockInterp = "plock_interpolation"
        case voiceRatchetLane = "voice_ratchet_lane", voiceRatchetDecay = "voice_ratchet_decay"
        case voiceRatchetVar = "voice_ratchet_variation", voiceCondition = "voice_condition"
        case voiceCCLanes = "voice_cc_lanes", voicePort = "voice_port"
        case slots = "native_slots", slotWeights = "seq_weights", slotA = "native_slot_a", slotB = "native_slot_b"
    }

    public init(_ s: BangSession) {
        bangVersion = "swiftui"
        timestamp = ISO8601DateFormatter().string(from: Date())
        seed = s.lastSeed
        params = s.params
        voices = s.voices
        voiceDensity = s.settings.compactMapValues { $0.density == 1 ? nil : $0.density }
        voiceChords = s.settings.compactMapValues { $0.chord == "mono" ? nil : $0.chord }
        voiceMidiCh = s.settings.compactMapValues { $0.channel }
        voiceLFO = s.settings.compactMapValues { $0.lfo }
        voiceDrop = s.settings.compactMapValues { $0.drop < 1 ? $0.drop : nil }
        voiceSwing = s.settings.compactMapValues { $0.swing > 0 ? $0.swing : nil }
        voiceVelLane = s.settings.compactMapValues { $0.velLane.contains { $0 > 0 } ? $0.velLane : nil }
        voiceProbLane = s.settings.compactMapValues { $0.probLane.contains { $0 > 0 } ? $0.probLane : nil }
        voiceOffset = s.settings.compactMapValues { $0.offset != 0 ? $0.offset : nil }
        voiceThin = s.settings.compactMapValues { $0.thin > 1 ? $0.thin : nil }
        voiceSteps = s.settings.compactMapValues { $0.length }
        maxPoly = s.maxPoly
        plockInterp = s.plockInterp
        voiceRatchetLane = s.settings.compactMapValues { $0.ratchetLane.contains { $0 > 0 } ? $0.ratchetLane : nil }
        voiceRatchetDecay = s.settings.compactMapValues { $0.ratchetDecay > 0 ? $0.ratchetDecay : nil }
        voiceRatchetVar = s.settings.compactMapValues { $0.ratchetVariation > 0 ? $0.ratchetVariation : nil }
        voiceCondition = s.settings.compactMapValues { $0.condition.isEmpty ? nil : $0.condition }
        voiceCCLanes = s.settings.compactMapValues { $0.ccLanes.isEmpty ? nil : $0.ccLanes }
        voicePort = s.settings.compactMapValues { $0.port }
        slots = s.slots.contains { $0 != nil } ? s.slots : nil
        slotWeights = s.slotWeights
        slotA = s.slotA
        slotB = s.slotB
        noteRemap = s.noteRemap
        lockedVoices = s.locked.sorted()
        plocks = s.plocks.isEmpty ? nil : s.plocks
    }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        bangVersion = (try? c.decode(String.self, forKey: .bangVersion)) ?? "?"
        timestamp = (try? c.decode(String.self, forKey: .timestamp)) ?? ""
        seed = (try? c.decode(String.self, forKey: .seed)) ?? ""
        params = (try? c.decode(GenParams.self, forKey: .params)) ?? GenParams()
        voices = try c.decode([Voice].self, forKey: .voices)
        voiceDensity = (try? c.decode([String: Double].self, forKey: .voiceDensity)) ?? [:]
        voiceChords = (try? c.decode([String: String].self, forKey: .voiceChords)) ?? [:]
        voiceMidiCh = try? c.decode([String: Int].self, forKey: .voiceMidiCh)
        voiceLFO = try? c.decode([String: VoiceLFO].self, forKey: .voiceLFO)
        voiceDrop = try? c.decode([String: Double].self, forKey: .voiceDrop)
        voiceSwing = try? c.decode([String: Double].self, forKey: .voiceSwing)
        voiceVelLane = try? c.decode([String: [Int]].self, forKey: .voiceVelLane)
        voiceProbLane = try? c.decode([String: [Int]].self, forKey: .voiceProbLane)
        voiceOffset = try? c.decode([String: Int].self, forKey: .voiceOffset)
        voiceThin = try? c.decode([String: Int].self, forKey: .voiceThin)
        voiceSteps = try? c.decode([String: Int].self, forKey: .voiceSteps)
        maxPoly = try? c.decode(Int.self, forKey: .maxPoly)
        plockInterp = try? c.decode(PLockInterpolation.self, forKey: .plockInterp)
        voiceRatchetLane = try? c.decode([String: [Int]].self, forKey: .voiceRatchetLane)
        voiceRatchetDecay = try? c.decode([String: Double].self, forKey: .voiceRatchetDecay)
        voiceRatchetVar = try? c.decode([String: Double].self, forKey: .voiceRatchetVar)
        voiceCondition = try? c.decode([String: String].self, forKey: .voiceCondition)
        voiceCCLanes = try? c.decode([String: [PLock]].self, forKey: .voiceCCLanes)
        voicePort = try? c.decode([String: Int32].self, forKey: .voicePort)
        slots = try? c.decode([BangSession.Snapshot?].self, forKey: .slots)
        slotWeights = try? c.decode([Int].self, forKey: .slotWeights)
        slotA = try? c.decode(BangSession.Snapshot.self, forKey: .slotA)
        slotB = try? c.decode(BangSession.Snapshot.self, forKey: .slotB)
        noteRemap = (try? c.decode([String: Int].self, forKey: .noteRemap)) ?? [:]
        lockedVoices = (try? c.decode([Int].self, forKey: .lockedVoices)) ?? []
        plocks = try? c.decode([[PLock]].self, forKey: .plocks)
    }

    public func apply(to s: inout BangSession) {
        s.pushHistory()
        s.params = params.normalized()
        s.voices = voices
        s.plocks = plocks ?? []
        s.lastSeed = seed
        s.noteRemap = noteRemap
        s.locked = Set(lockedVoices.filter { $0 < voices.count })
        s.muted = []
        s.soloed = []
        var settings: [String: VoiceSettings] = [:]
        for (k, d) in voiceDensity { settings[k, default: VoiceSettings()].density = d }
        for (k, ch) in voiceChords { settings[k, default: VoiceSettings()].chord = ch }
        for (k, ch) in voiceMidiCh ?? [:] { settings[k, default: VoiceSettings()].channel = ch }
        for (k, l) in voiceLFO ?? [:] { settings[k, default: VoiceSettings()].lfo = l }
        for (k, d) in voiceDrop ?? [:] { settings[k, default: VoiceSettings()].drop = d }
        for (k, w) in voiceSwing ?? [:] { settings[k, default: VoiceSettings()].swing = w }
        for (k, l) in voiceVelLane ?? [:] { settings[k, default: VoiceSettings()].velLane = l }
        for (k, l) in voiceProbLane ?? [:] { settings[k, default: VoiceSettings()].probLane = l }
        for (k, o) in voiceOffset ?? [:] { settings[k, default: VoiceSettings()].offset = o }
        for (k, t) in voiceThin ?? [:] { settings[k, default: VoiceSettings()].thin = max(1, t) }
        for (k, n) in voiceSteps ?? [:] where n > 0 { settings[k, default: VoiceSettings()].length = n }
        for (k, l) in voiceRatchetLane ?? [:] { settings[k, default: VoiceSettings()].ratchetLane = l }
        for (k, d) in voiceRatchetDecay ?? [:] { settings[k, default: VoiceSettings()].ratchetDecay = d.clamped(0, 1) }
        for (k, v) in voiceRatchetVar ?? [:] { settings[k, default: VoiceSettings()].ratchetVariation = v.clamped(0, 1) }
        for (k, c) in voiceCondition ?? [:] where TrigCondition.all.contains(c) { settings[k, default: VoiceSettings()].condition = c }
        for (k, l) in voiceCCLanes ?? [:] { settings[k, default: VoiceSettings()].ccLanes = l }
        for (k, p) in voicePort ?? [:] { settings[k, default: VoiceSettings()].port = p }
        s.settings = settings
        s.maxPoly = max(0, maxPoly ?? 0)
        s.plockInterp = plockInterp ?? .off
        if let sl = slots, sl.count == 8 { s.slots = sl }
        if let w = slotWeights, w.count == 8 { s.slotWeights = w.map { max(1, min(9, $0)) } }
        if slotA != nil { s.slotA = slotA }
        if slotB != nil { s.slotB = slotB }
    }
}
