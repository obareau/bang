// Icône BANG! — tête Robōtarii dithérée (charte Robōtariis).
// Rendu en basse résolution (128×128) puis agrandi au plus proche (×8),
// comme le pipeline pixel-art : superellipse |x|⁴+|y|⁴ ≤ 1, bord dithéré
// Bayer 4×4 mêlé de bruit déterministe, deux tirets pour les yeux, halo orange.
// Usage : swift make_icon.swift sortie.png
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let N = 128, scale = 8, S = N * scale
let bayer: [[Double]] = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

func noise(_ x: Int, _ y: Int) -> Double {
    var h = UInt32(truncatingIfNeeded: x &* 374_761_393 &+ y &* 668_265_263)
    h = (h ^ (h >> 13)) &* 1_274_126_177
    return Double((h ^ (h >> 16)) & 0xFFFF) / 65535.0
}

func threshold(_ x: Int, _ y: Int) -> Double {
    0.55 * (bayer[y % 4][x % 4] + 0.5) / 16 + 0.45 * noise(x, y)
}

typealias RGB = (Double, Double, Double)
let bg: RGB = (0x0A / 255.0, 0x0A / 255.0, 0x0A / 255.0)
let ink: RGB = (0xF2 / 255.0, 0xF2 / 255.0, 0xF2 / 255.0)
let orange: RGB = (0xF9 / 255.0, 0x73 / 255.0, 0x16 / 255.0)

var low = [RGB?](repeating: nil, count: N * N)  // nil = transparent (hors squircle)
let c = Double(N) / 2

for y in 0..<N {
    for x in 0..<N {
        // Plaque de l'icône : squircle macOS (marge ~10 %)
        let px = (Double(x) + 0.5 - c) / (c * 0.80)
        let py = (Double(y) + 0.5 - c) / (c * 0.80)
        let plate = pow(abs(px), 5) + pow(abs(py), 5)
        if plate > 1 { continue }

        var col = bg
        // Halo orange additif autour de la tête
        let hx = (Double(x) + 0.5 - c) / (c * 0.42)
        let hy = (Double(y) + 0.5 - c * 1.02) / (c * 0.42)
        let head = pow(abs(hx), 4) + pow(abs(hy), 4)  // ≤ 1 : dans la tête
        let halo = max(0, 1 - (pow(head, 0.25) - 1) / 0.75)
        if head > 1 {
            let a = 0.55 * halo * halo
            if a > threshold(x, y) * 0.9 {
                col = (bg.0 + orange.0 * 0.9, bg.1 + orange.1 * 0.9, bg.2 + orange.2 * 0.9)
            }
        }

        // Tête : pleine au centre, bord dithéré sur une large bande
        let r = pow(head, 0.25)
        let fill = r < 0.72 ? 1.0 : max(0, (1 - r) / 0.28)
        if fill > threshold(x, y) { col = ink }

        // Yeux : deux tirets horizontaux
        let ey = abs((Double(y) + 0.5) - c * 0.98)
        let exL = abs((Double(x) + 0.5) - c * 0.80)
        let exR = abs((Double(x) + 0.5) - c * 1.20)
        if ey < 2.6 && (exL < 7.5 || exR < 7.5) { col = bg }

        low[y * N + x] = col
    }
}

// Agrandissement au plus proche
var pixels = [UInt8](repeating: 0, count: S * S * 4)
for y in 0..<S {
    for x in 0..<S {
        guard let p = low[(y / scale) * N + (x / scale)] else { continue }
        let i = (y * S + x) * 4
        pixels[i] = UInt8(min(255, p.0 * 255))
        pixels[i + 1] = UInt8(min(255, p.1 * 255))
        pixels[i + 2] = UInt8(min(255, p.2 * 255))
        pixels[i + 3] = 255
    }
}

let ctx = CGContext(data: &pixels, width: S, height: S, bitsPerComponent: 8, bytesPerRow: S * 4,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!,
                    bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
let image = ctx.makeImage()!
let out = URL(fileURLWithPath: CommandLine.arguments[1])
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, image, nil)
CGImageDestinationFinalize(dest)
print("icône : \(out.path)")
