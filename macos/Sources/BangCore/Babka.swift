import Foundation

/// Un step Babka : un DNACell + une durée relative (1.0 = un step plein).
public struct BabkaStep: Equatable, Sendable {
    public var cell: DNACell
    public var duration: Double
}

/// Syntaxe Babka (DNA + mini-notation Strudel) — portage de babka.py.
///   [a b c]   subdivision      <a b c>   alternance par cycle
///   x(n,k)    euclidien inline [x(n,k)]  euclidien overlay
public enum Babka {
    public static func parse(_ pattern: String, cycle: Int = 0) -> [BabkaStep] {
        var p = Parser(chars: Array(pattern.trimmingCharacters(in: .whitespaces)), cycle: cycle)
        return p.parse()
    }

    public static func totalSteps(_ steps: [BabkaStep]) -> Double {
        steps.reduce(0) { $0 + $1.duration }
    }

    /// Vrai si le pattern utilise des opérateurs Babka.
    public static func usesSyntax(_ s: String) -> Bool {
        s.contains { "[]<>(),".contains($0) }
    }

    static func atom(_ c: Character, _ duration: Double = 1.0) -> BabkaStep {
        BabkaStep(cell: DNA.cell(c), duration: duration)
    }

    static func euclidean(_ n: Int, _ k: Int, _ c: Character) -> [BabkaStep] {
        let k = max(k, 1)
        let n = min(max(n, 0), k)
        return (0..<k).map { atom(($0 * n % k) < n ? c : "-") }
    }

    struct Parser {
        let chars: [Character]
        var pos = 0
        let cycle: Int

        init(chars: [Character], cycle: Int) {
            self.chars = chars
            self.cycle = cycle
        }

        mutating func parse() -> [BabkaStep] {
            var out: [BabkaStep] = []
            while pos < chars.count { out += item() }
            return out
        }

        mutating func item() -> [BabkaStep] {
            guard pos < chars.count else { return [] }
            let c = chars[pos]
            if c == "<" { return alt() }
            if c == "[" { return group() }
            if DNA.symbols.contains(c) {
                pos += 1
                if pos < chars.count && chars[pos] == "(" {
                    let (n, k) = eucSuffix()
                    return Babka.euclidean(n, k, c)
                }
                return [Babka.atom(c)]
            }
            pos += 1  // caractère inconnu : ignoré
            return []
        }

        mutating func group() -> [BabkaStep] {
            pos += 1
            var inner: [BabkaStep] = []
            while pos < chars.count && chars[pos] != "]" { inner += item() }
            if pos < chars.count { pos += 1 }
            guard !inner.isEmpty else { return [] }
            let total = inner.reduce(0) { $0 + $1.duration }
            return inner.map { BabkaStep(cell: $0.cell, duration: $0.duration / total) }
        }

        mutating func alt() -> [BabkaStep] {
            pos += 1
            var alternatives: [String] = []
            var current: [Character] = []
            var depth = 0
            while pos < chars.count {
                let c = chars[pos]
                pos += 1
                if c == "<" || c == "[" {
                    depth += 1; current.append(c)
                } else if c == "]" {
                    depth -= 1; current.append(c)
                } else if c == ">" && depth > 0 {
                    depth -= 1; current.append(c)
                } else if c == ">" {
                    alternatives.append(String(current))
                    break
                } else if c == " " && depth == 0 {
                    alternatives.append(String(current)); current = []
                } else {
                    current.append(c)
                }
            }
            guard !alternatives.isEmpty else { return [] }
            let selected = alternatives[cycle % alternatives.count]
            var sub = Parser(chars: Array(selected), cycle: cycle)
            return sub.parse()
        }

        mutating func eucSuffix() -> (Int, Int) {
            pos += 1
            let start = pos
            while pos < chars.count && chars[pos] != ")" { pos += 1 }
            let inside = String(chars[start..<pos])
            if pos < chars.count { pos += 1 }
            let parts = inside.split(separator: ",", omittingEmptySubsequences: false)
                .map { $0.trimmingCharacters(in: .whitespaces) }
            guard parts.count >= 2, let n = Int(parts[0]), let k = Int(parts[1]) else { return (0, 1) }
            return (n, k)
        }
    }
}
