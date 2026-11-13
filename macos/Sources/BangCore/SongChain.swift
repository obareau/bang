import Foundation

/// Mode Song : enchaînement de mémoires, ex. « 1x4 2x2 3 » = mémoire 1
/// pendant 4 cycles, puis 2 pendant 2 cycles, puis 3 pendant 1 cycle, et on
/// reboucle. Accepte x, ×, * ou : comme séparateur.
public struct SongChain: Equatable, Sendable {
    public struct Part: Equatable, Sendable {
        public var slot: Int      // 0…7
        public var repeats: Int   // ≥ 1
    }

    public var parts: [Part]

    public init(parts: [Part]) { self.parts = parts }

    public static func parse(_ text: String) -> SongChain {
        let tokens = text.lowercased()
            .replacingOccurrences(of: "×", with: "x")
            .replacingOccurrences(of: "*", with: "x")
            .replacingOccurrences(of: ":", with: "x")
            .split(whereSeparator: { $0 == " " || $0 == "," || $0 == "→" || $0 == ">" || $0 == "-" })
        var parts: [Part] = []
        for t in tokens {
            let bits = t.split(separator: "x", omittingEmptySubsequences: false)
            guard let slot = Int(bits[0]), (1...8).contains(slot) else { continue }
            let rep = bits.count > 1 ? Int(bits[1]) ?? 1 : 1
            parts.append(Part(slot: slot - 1, repeats: max(1, min(64, rep))))
        }
        return SongChain(parts: parts)
    }

    public var description: String {
        parts.map { "\($0.slot + 1)×\($0.repeats)" }.joined(separator: " → ")
    }
}
