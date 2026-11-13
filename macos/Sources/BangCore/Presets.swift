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
    public var noteRemap: [String: Int]
    public var lockedVoices: [Int]
    public var plocks: [[PLock]]?

    enum CodingKeys: String, CodingKey {
        case seed, params, voices, timestamp, plocks
        case bangVersion = "bang_version", voiceDensity = "voice_density"
        case voiceChords = "voice_chords", voiceMidiCh = "voice_midi_ch"
        case noteRemap = "note_remap", lockedVoices = "locked_voices"
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
        s.settings = settings
    }
}
