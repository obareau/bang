import Foundation
import CryptoKit

/// Source d'aléa seedable (SplitMix64). Équivalent du `random` global de
/// Python, mais passé explicitement : une seed BANG (hex SHA-256) donne
/// toujours le même pattern dans l'app native.
///
/// Note : l'algorithme n'est pas le Mersenne Twister de CPython, donc une
/// même seed ne produit pas le même pattern que le webapp Python — seulement
/// le même pattern d'une session native à l'autre.
public final class Dice: @unchecked Sendable {
    private var state: UInt64

    public init(seed: UInt64) { state = seed }

    public convenience init() {
        var g = SystemRandomNumberGenerator()
        self.init(seed: g.next())
    }

    /// Seed BANG au format hex (comme `_seed_to_int` : 16 premiers caractères).
    public convenience init(seedString: String) {
        self.init(seed: Dice.seedValue(seedString))
    }

    public static func seedValue(_ s: String) -> UInt64 {
        let hex = String(s.trimmingCharacters(in: .whitespaces).prefix(16))
        if let v = UInt64(hex, radix: 16) { return v }
        // Seed non hexadécimale : on la hache pour rester déterministe.
        let digest = SHA256.hash(data: Data(s.utf8))
        return digest.prefix(8).reduce(0) { ($0 << 8) | UInt64($1) }
    }

    /// Nouvelle seed : SHA-256 sur aléa système + horloge (+ météo si fournie).
    public static func generateSeed(weather: Weather? = nil) -> String {
        var bytes = [UInt8](repeating: 0, count: 16)
        var g = SystemRandomNumberGenerator()
        for i in bytes.indices { bytes[i] = UInt8.random(in: 0...255, using: &g) }
        var data = Data(bytes)
        data.append(contentsOf: Array(String(DispatchTime.now().uptimeNanoseconds).utf8))
        if let w = weather {
            data.append(contentsOf: Array(String(format: "%.1f%.1f", w.temperature, w.windSpeed).utf8))
        }
        return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    public func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    /// [0, 1)
    public func random() -> Double { Double(next() >> 11) * 0x1.0p-53 }

    public func uniform(_ a: Double, _ b: Double) -> Double { a + (b - a) * random() }

    /// Entier dans [lo, hi] inclus (comme `random.randint`).
    public func int(_ lo: Int, _ hi: Int) -> Int {
        guard hi > lo else { return lo }
        return lo + Int(next() % UInt64(hi - lo + 1))
    }

    public func choice<T>(_ items: [T]) -> T { items[int(0, items.count - 1)] }

    /// `random.choices(items, weights=…, k=1)[0]`
    public func weighted<T>(_ items: [T], _ weights: [Double]) -> T {
        let total = weights.reduce(0, +)
        guard total > 0 else { return choice(items) }
        var r = random() * total
        for (item, w) in zip(items, weights) {
            if r < w { return item }
            r -= w
        }
        return items[items.count - 1]
    }
}
