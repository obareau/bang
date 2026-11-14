import Foundation

/// Chaîne de Markov d'ordre 1 entre notes MIDI — portage de MarkovChain.
public struct MarkovChain: Sendable {
    public let notes: [Int]
    /// weights[i][j] = P(notes[j] | notes[i])
    public let weights: [[Double]]

    public init(notes: [Int], weights: [[Double]]) {
        self.notes = notes
        self.weights = weights.map { row in
            let t = row.reduce(0, +)
            return t > 0 ? row.map { $0 / t } : row
        }
    }

    public func generate(_ length: Int, rng: Dice) -> [Int] {
        guard !notes.isEmpty, length > 0 else { return [] }
        var i = rng.int(0, notes.count - 1)
        var seq = [notes[i]]
        let idx = Array(notes.indices)
        for _ in 1..<max(1, length) where seq.count < length {
            i = rng.weighted(idx, weights[i])
            seq.append(notes[i])
        }
        return seq
    }

    /// Note suivante tirée depuis `note` (inchangée si elle n'est pas dans la chaîne).
    public func next(after note: Int, rng: Dice) -> Int {
        guard let i = notes.firstIndex(of: note) else { return note }
        return notes[rng.weighted(Array(notes.indices), weights[i])]
    }

    /// Mélange avec une matrice uniforme selon la gravité (pattern_lib.markov_from_gravity).
    public func withGravity(_ gravity: Double) -> MarkovChain {
        if gravity >= 0.98 { return self }
        let u = 1.0 / Double(notes.count)
        return MarkovChain(notes: notes, weights: weights.map { row in
            row.map { $0 * gravity + u * (1 - gravity) }
        })
    }
}

public enum Scales {
    public static let intervals: [(id: String, name: String, steps: [Int])] = [
        ("penta_min", "Penta min", [0, 3, 5, 7, 10]),
        ("penta_maj", "Penta maj", [0, 2, 4, 7, 9]),
        ("minor", "Mineur", [0, 2, 3, 5, 7, 8, 10]),
        ("dorian", "Dorien", [0, 2, 3, 5, 7, 9, 10]),
        ("phrygian", "Phrygien", [0, 1, 3, 5, 7, 8, 10]),
        ("major", "Majeur", [0, 2, 4, 5, 7, 9, 11]),
        ("mixo", "Mixolydien", [0, 2, 4, 5, 7, 9, 10]),
        ("lydian", "Lydien", [0, 2, 4, 6, 7, 9, 11]),
    ]

    public static func steps(_ id: String) -> [Int] {
        intervals.first { $0.id == id }?.steps ?? [0, 3, 5, 7, 10]
    }

    public static let chromatic = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    /// Tonique → note MIDI grave (A→33 … G#→44), comme pattern_lib.ROOTS.
    public static func rootNote(_ name: String) -> Int {
        guard let i = chromatic.firstIndex(of: name) else { return 33 }
        return 33 + (((i - 9) % 12) + 12) % 12
    }

    /// Construction algorithmique d'une chaîne pour une gamme (build_markov_chain).
    public static func chain(root: Int, intervals: [Int], octaves: Int = 1) -> MarkovChain {
        var set = Set<Int>()
        for o in 0..<octaves {
            for iv in intervals {
                let n = root + o * 12 + iv
                if (21...108).contains(n) { set.insert(n) }
            }
        }
        let closing = root + octaves * 12
        if (21...108).contains(closing) { set.insert(closing) }
        var notes = set.sorted()
        if notes.isEmpty { notes = [root] }

        let rootClass = root % 12
        let fifthClass = (root + 7) % 12
        let weights: [[Double]] = notes.indices.map { i in
            notes.indices.map { j in
                var w = exp(-Double(abs(i - j)) * 0.45)
                if notes[j] % 12 == rootClass { w *= 1.5 }
                else if notes[j] % 12 == fifthClass { w *= 1.2 }
                if i == j { w *= 0.35 }
                return w
            }
        }
        return MarkovChain(notes: notes, weights: weights)
    }
}

public enum Chords {
    public static let all: [(id: String, intervals: [Int])] = [
        ("mono", []), ("power", [7]), ("minor", [3, 7]), ("major", [4, 7]),
        ("sus2", [2, 7]), ("sus4", [5, 7]), ("m7", [3, 7, 10]), ("M7", [4, 7, 11]),
        ("dom7", [4, 7, 10]), ("dim", [3, 6]), ("aug", [4, 8]),
    ]

    public static func intervals(_ id: String) -> [Int] {
        all.first { $0.id == id }?.intervals ?? []
    }
}
