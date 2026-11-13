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
        s.settings = settings
        if let sl = slots, sl.count == 8 { s.slots = sl }
        if let w = slotWeights, w.count == 8 { s.slotWeights = w.map { max(1, min(9, $0)) } }
        if slotA != nil { s.slotA = slotA }
        if slotB != nil { s.slotB = slotB }
    }
}
