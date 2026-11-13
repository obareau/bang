import Foundation

/// Un step DNA compilé : [trigger, velocity, prob, ratchet, jitter].
public struct DNACell: Equatable, Sendable {
    public var trigger: Bool
    public var velocity: Int
    public var prob: Double
    public var ratchet: Int
    public var jitter: Int
}

/// Syntaxe DNA BANG — portage de bang_engine.py / pattern_lib.py.
public enum DNA {
    public static let symbols: [Character] = ["x", "-", "?", "↺", "░"]

    public static func cell(_ c: Character) -> DNACell {
        switch c {
        case "x": return DNACell(trigger: true, velocity: 105, prob: 1.0, ratchet: 1, jitter: 0)
        case "?": return DNACell(trigger: true, velocity: 90, prob: 0.5, ratchet: 1, jitter: 0)
        case "↺": return DNACell(trigger: true, velocity: 110, prob: 1.0, ratchet: 3, jitter: 0)
        case "░": return DNACell(trigger: true, velocity: 85, prob: 1.0, ratchet: 1, jitter: 25)
        default:  return DNACell(trigger: false, velocity: 0, prob: 0.0, ratchet: 1, jitter: 0)
        }
    }

    public static func compile(_ dna: String) -> [DNACell] { dna.map(cell) }

    /// Vrai si la chaîne n'utilise que les 5 symboles (donc éditable en grille).
    public static func isPlain(_ dna: String) -> Bool {
        !dna.isEmpty && dna.allSatisfy { symbols.contains($0) }
    }

    /// Cycle d'édition au clic : - → x → ? → ↺ → ░ → -
    public static func nextSymbol(_ c: Character) -> Character {
        switch c {
        case "-": return "x"
        case "x": return "?"
        case "?": return "↺"
        case "↺": return "░"
        default:  return "-"
        }
    }

    public static func random(length: Int = 16, rng: Dice) -> String {
        String((0..<length).map { _ in rng.choice(symbols) })
    }

    /// Croisement + mutation entre deux patterns.
    public static func morph(_ p1: String, _ p2: String, mutationRate: Double = 0.2, rng: Dice) -> String {
        let a = Array(p1), b = Array(p2)
        let length = min(a.count, b.count)
        let mid = length / 2
        var child = Array(a[0..<mid]) + Array(b[mid..<length])
        for i in child.indices where rng.random() < mutationRate {
            child[i] = rng.choice(symbols)
        }
        return String(child)
    }

    /// Glisse chaque symbole vers un voisin ; laisse intacte la syntaxe Babka.
    public static func mutate(_ dna: String, intensity: Double = 0.2, rng: Dice) -> String {
        String(dna.map { c -> Character in
            guard let idx = symbols.firstIndex(of: c), rng.random() < intensity else { return c }
            let shift = rng.random() < 0.5 ? -1 : 1
            return symbols[max(0, min(symbols.count - 1, idx + shift))]
        })
    }

    /// k hits répartis sur n steps (Bresenham).
    public static func euclid(n: Int, k: Int) -> String {
        guard n > 0 else { return "" }
        let k = max(0, min(k, n))
        if k == 0 { return String(repeating: "-", count: n) }
        return String((0..<n).map { ($0 * k % n) < k ? "x" : "-" })
    }

    public static func invert(_ dna: String) -> String {
        String(dna.map { $0 == "x" ? "-" : ($0 == "-" ? "x" : $0) })
    }

    public static func rotate(_ dna: String, by n: Int) -> String {
        let a = Array(dna)
        guard !a.isEmpty else { return dna }
        let shift = ((n % a.count) + a.count) % a.count
        guard shift > 0 else { return dna }
        return String(a[(a.count - shift)...] + a[..<(a.count - shift)])
    }

    public static func reverse(_ dna: String) -> String { String(dna.reversed()) }
    public static func double(_ dna: String) -> String { dna + dna }

    public static func halve(_ dna: String) -> String {
        guard !dna.isEmpty else { return dna }
        return String(dna.prefix(max(1, dna.count / 2)))
    }

    /// Mutation garantie non triviale (8 essais max).
    public static func vary(_ dna: String, intensity: Double = 0.15, rng: Dice) -> String {
        var out = mutate(dna, intensity: intensity, rng: rng)
        var tries = 0
        while out == dna && tries < 8 {
            out = mutate(dna, intensity: intensity, rng: rng)
            tries += 1
        }
        return out
    }

    public static func resize(_ dna: String, to n: Int) -> String {
        guard !dna.isEmpty, n > 0, dna.count != n else { return dna }
        if dna.count > n { return String(dna.prefix(n)) }
        return String(String(repeating: dna, count: n / dna.count + 1).prefix(n))
    }
}
