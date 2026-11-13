import Foundation

// MARK: - Strudel / TidalCycles

/// Export du pattern en mini-notation Strudel — portage de /export/strudel.
public enum StrudelExport {
    static let samples: [Int: String] = [
        35: "bd", 36: "bd", 38: "sd", 39: "cp", 40: "sd", 42: "hh", 44: "hh", 46: "oh", 37: "rim",
        41: "lt", 43: "mt", 45: "ht", 47: "ht", 48: "mt", 50: "ht", 49: "cr", 55: "cr", 57: "cr",
        51: "rd", 53: "rd", 59: "rd",
    ]
    static let noteNames = ["c", "cs", "d", "ds", "e", "f", "fs", "g", "gs", "a", "as", "b"]

    static func noteName(_ n: Int) -> String { "\(noteNames[((n % 12) + 12) % 12])\(n / 12 - 1)" }

    public static func code(_ s: BangSession, version: String = "macOS") -> String {
        guard !s.voices.isEmpty else { return "// Générez un pattern d'abord" }
        let input = s.renderInput()
        var lines: [String] = []
        for (i, v) in s.voices.enumerated() where !v.isCC && !v.isBabka {
            let name = v.label
            let note = input.outputNote(for: i)
            let sample = v.isMelodic ? noteName(note)
                : samples[note] ?? String(name.lowercased().filter { $0.isLetter || $0.isNumber }.prefix(8))
            let tokens = DNA.compile(v.dna).map { c -> String in
                if !c.trigger { return "~" }
                if c.ratchet > 1 { return "\(sample)*\(c.ratchet)" }
                if c.prob < 0.75 { return String(format: "%@?%.1f", sample, c.prob) }
                if c.prob < 0.95 { return "\(sample)?" }
                return sample
            }
            lines.append("  \(v.isMelodic ? "note" : "s")(\"\(tokens.joined(separator: " "))\") // \(name)")
        }
        let cps = (Double(s.params.bpm) / 60 / 4 * 10_000).rounded() / 10_000
        return "// BANG! \(version) — \(s.params.bpm) BPM\nsetcps(\(cps))\nstack(\n" + lines.joined(separator: ",\n") + "\n)"
    }
}

// MARK: - OSC (Open Sound Control 1.0)

/// Message OSC minimal : arguments entiers (i), flottants (f) et chaînes (s).
public struct OSCMessage: Equatable, Sendable {
    public enum Arg: Equatable, Sendable {
        case int(Int32), float(Float), string(String)

        public var number: Double? {
            switch self {
            case .int(let i): return Double(i)
            case .float(let f): return Double(f)
            case .string(let s): return Double(s)
            }
        }

        public var text: String {
            switch self {
            case .int(let i): return "\(i)"
            case .float(let f): return String(format: "%.3f", f)
            case .string(let s): return "\"\(s)\""
            }
        }
    }

    public var address: String
    public var args: [Arg]

    public init(_ address: String, _ args: [Arg] = []) {
        self.address = address
        self.args = args
    }

    static func pad(_ d: inout Data) { while d.count % 4 != 0 { d.append(0) } }

    static func str(_ s: String) -> Data {
        var d = Data(s.utf8); d.append(0); pad(&d); return d
    }

    public func encode() -> Data {
        var d = OSCMessage.str(address)
        d += OSCMessage.str("," + args.map { a -> String in
            switch a { case .int: return "i"; case .float: return "f"; case .string: return "s" }
        }.joined())
        for a in args {
            switch a {
            case .int(let i): withUnsafeBytes(of: i.bigEndian) { d.append(contentsOf: $0) }
            case .float(let f): withUnsafeBytes(of: f.bitPattern.bigEndian) { d.append(contentsOf: $0) }
            case .string(let s): d += OSCMessage.str(s)
            }
        }
        return d
    }

    /// Décode un message (ou le 1er message d'un bundle). nil si illisible.
    public static func decode(_ data: Data) -> [OSCMessage] {
        let b = [UInt8](data)
        if b.starts(with: Array("#bundle".utf8)) {
            var out: [OSCMessage] = []
            var i = 16
            while i + 4 <= b.count {
                let n = Int(UInt32(b[i]) << 24 | UInt32(b[i + 1]) << 16 | UInt32(b[i + 2]) << 8 | UInt32(b[i + 3]))
                i += 4
                guard n > 0, i + n <= b.count else { break }
                out += decode(Data(b[i..<i + n]))
                i += n
            }
            return out
        }
        var i = 0
        func readString() -> String? {
            guard let end = b[i...].firstIndex(of: 0) else { return nil }
            let s = String(decoding: b[i..<end], as: UTF8.self)
            i = (end + 4) & ~3
            return s
        }
        func read32() -> UInt32? {
            guard i + 4 <= b.count else { return nil }
            defer { i += 4 }
            return UInt32(b[i]) << 24 | UInt32(b[i + 1]) << 16 | UInt32(b[i + 2]) << 8 | UInt32(b[i + 3])
        }
        guard let addr = readString(), addr.hasPrefix("/") else { return [] }
        var args: [Arg] = []
        if i < b.count, let tags = readString(), tags.hasPrefix(",") {
            for t in tags.dropFirst() {
                switch t {
                case "i": if let v = read32() { args.append(.int(Int32(bitPattern: v))) }
                case "f": if let v = read32() { args.append(.float(Float(bitPattern: v))) }
                case "s": if let s = readString() { args.append(.string(s)) }
                case "T": args.append(.int(1))
                case "F": args.append(.int(0))
                default: return [OSCMessage(addr, args)]  // type non géré : on s'arrête là
                }
            }
        }
        return [OSCMessage(addr, args)]
    }
}

// MARK: - Notes par voix (Ableton, export séparé)

public struct ClipNote: Equatable, Sendable {
    public var pitch: Int
    public var startBeats: Double
    public var durationBeats: Double
    public var velocity: Int
}

public enum VoiceNotes {
    /// Notes d'un cycle, voix par voix (rendu avec la seed de la session).
    public static func clips(_ s: BangSession) -> [(voice: Int, label: String, notes: [ClipNote])] {
        let input = s.renderInput(respectMute: false)
        let events = Renderer.render(input, numSteps: s.params.steps,
                                     rng: Dice(seedString: s.lastSeed.isEmpty ? "0" : s.lastSeed))
        let tpb = Double(Renderer.ppq)
        var out: [(Int, String, [ClipNote])] = []
        for (vi, v) in s.voices.enumerated() where !v.isCC {
            var open: [Int: [(Int, Int)]] = [:]
            var notes: [ClipNote] = []
            for e in events where e.voice == vi {
                if e.kind == .noteOn { open[e.data1, default: []].append((e.tick, e.data2)) }
                if e.kind == .noteOff, var st = open[e.data1], !st.isEmpty {
                    let (t, vel) = st.removeFirst()
                    open[e.data1] = st
                    notes.append(ClipNote(pitch: e.data1, startBeats: Double(t) / tpb,
                                          durationBeats: max(1, Double(e.tick - t)) / tpb, velocity: vel))
                }
            }
            out.append((vi, v.label, notes.sorted { $0.startBeats < $1.startBeats }))
        }
        return out
    }
}

extension MIDIFileWriter {
    /// Un .mid ne contenant qu'une voix (pour un clip par voix).
    public static func exportVoice(_ s: BangSession, voice: Int) -> Data {
        var input = s.renderInput(respectMute: false)
        input.audible = s.voices.indices.map { $0 == voice }
        return export(input, numSteps: s.params.steps, seed: s.lastSeed.isEmpty ? "0" : s.lastSeed,
                      name: s.voices.indices.contains(voice) ? s.voices[voice].label : "voix", type: 0)
    }
}

// MARK: - MIDI Learn

public enum MIDILearn {
    /// Quantifie des frappes (secondes depuis le début de la prise) en DNA :
    /// chaque frappe donne un « x » au step le plus proche (comme le webapp).
    public static func quantize(_ hits: [Double], steps: Int, stepSeconds: Double) -> String {
        guard steps > 0, stepSeconds > 0 else { return "" }
        var dna = Array(repeating: Character("-"), count: steps)
        for t in hits {
            let idx = min(steps - 1, max(0, Int((t / stepSeconds).rounded()) % steps))
            dna[idx] = "x"
        }
        return String(dna)
    }
}
