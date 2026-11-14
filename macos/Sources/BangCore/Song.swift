import Foundation

/// Morceau complet en « macro-arrangement » — portage de `_generate_song`
/// (web.py) et `BangSession.generate_song` (app Qt) : intro → transition →
/// couplets → break → couplet 2 → climax → break 2 → outro → fin.
public enum SongBuilder {
    /// (groupe, nom, mode, chaos départ, chaos fin, steps, nb de variations, break)
    public static let structure: [(group: Int, name: String, mode: Mode, chaosStart: Double, chaosEnd: Double,
                                    steps: Int, count: Int, isBreak: Bool)] = [
        (1, "intro", .ambient, 0.15, 0.35, 32, 4, false),
        (2, "transition", .noise, 0.55, 0.70, 16, 1, false),
        (3, "couplet", .noise, 0.70, 1.00, 32, 8, false),
        (4, "break", .ambient, 0.05, 0.12, 32, 1, true),
        (5, "couplet2", .noise, 0.90, 1.15, 32, 4, false),
        (6, "climax", .noise, 1.10, 1.40, 32, 4, false),
        (7, "break2", .ambient, 0.05, 0.18, 32, 2, true),
        (8, "outro", .ambient, 0.40, 0.12, 32, 2, false),
        (9, "fin", .ambient, 0.08, 0.04, 32, 4, false),
    ]

    public struct Section: Sendable {
        /// Nom de fichier du webapp, ex. « 01a-intro1 ».
        public var name: String
        public var startStep: Int
        public var steps: Int
        public var voices: [Voice]
        public var params: GenParams
    }

    public struct Song: Sendable {
        public var sections: [Section]
        public var totalSteps: Int
        /// Une voix par instrument (même nom), DNA sur toute la durée du morceau.
        public var voices: [Voice]
        public var params: GenParams
        public var seed: String

        /// Marqueurs de section (tick, nom) pour l'export MIDI.
        public var markers: [(Int, String)] {
            sections.map { ($0.startStep * Renderer.ticksPerStep, $0.name) }
        }

        /// Entrée de rendu du morceau entier (MIDI ou WAV).
        public func renderInput(settings: [String: VoiceSettings] = [:], noteRemap: [String: Int] = [:],
                                weather: Weather? = nil) -> RenderInput {
            var p = params
            p.steps = totalSteps
            p.mode = .noise   // pas de drone CC ni de p-locks : modes ambient / noise uniquement
            return RenderInput(voices: voices, params: p, settings: settings, weather: weather, noteRemap: noteRemap)
        }
    }

    static let letters = Array("abcdefghijklmnopqrstuvwxyz")

    public static func build(chaos: Double, bpm: Int, gravity: Double, ccDepth: Double,
                             weather: Weather?, seed: String) -> Song {
        let rng = Dice(seedString: seed)
        let chaos = chaos.clamped(0, 1)
        var sections: [Section] = []
        var offset = 0
        for part in structure {
            var prev: [Voice]? = nil
            for i in 0..<part.count {
                let mult = part.count == 1 ? part.chaosStart
                    : part.chaosStart + Double(i) / Double(part.count - 1) * (part.chaosEnd - part.chaosStart)
                var p = GenParams()
                p.mode = part.mode
                p.chaos = min(1, chaos * mult)
                p.bpm = bpm
                p.steps = part.steps
                p.gravity = gravity
                p.ccDepth = ccDepth
                p = p.normalized()
                var voices: [Voice]
                if part.isBreak || prev == nil {
                    voices = Generator.buildVoices(p, weather: weather, rng: rng)
                } else {
                    let intensity = 0.08 + p.chaos * 0.06
                    voices = prev!.map { v in var o = v; o.dna = DNA.mutate(v.dna, intensity: intensity, rng: rng); return o }
                }
                prev = voices
                let label: String
                if part.count == 1 { label = part.name }
                else if part.name.last?.isNumber == true { label = "\(part.name)-\(i + 1)" }
                else { label = "\(part.name)\(i + 1)" }
                sections.append(Section(name: String(format: "%02d", part.group) + "\(letters[i])-\(label)",
                                        startStep: offset, steps: part.steps, voices: voices, params: p))
                offset += part.steps
            }
        }

        // Une piste par instrument : chaque section écrit sa DNA (ajustée à sa
        // durée) à sa place dans la timeline ; ailleurs, silence.
        var order: [String] = []
        var tracks: [String: (note: Int, type: String, dna: [Character])] = [:]
        for sec in sections {
            for v in sec.voices where !v.isCC && !v.dna.isEmpty {
                let body = Array(DNA.resize(v.dna, to: sec.steps))
                if tracks[v.label] == nil {
                    order.append(v.label)
                    tracks[v.label] = (v.note, v.type, Array(repeating: "-", count: offset))
                }
                for (k, c) in body.enumerated() where c != "-" { tracks[v.label]!.dna[sec.startStep + k] = c }
            }
        }
        var p = GenParams()
        p.bpm = bpm; p.chaos = chaos; p.gravity = gravity; p.ccDepth = ccDepth
        let voices = order.map { l in Voice(tracks[l]!.note, String(tracks[l]!.dna), tracks[l]!.type) }
        return Song(sections: sections, totalSteps: offset, voices: voices, params: p, seed: seed)
    }
}
