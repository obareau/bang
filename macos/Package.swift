// swift-tools-version:5.10
// BANG! — app macOS native (SwiftUI + CoreMIDI).
// BangCore = moteur pur (DNA, Babka, Markov, 14 modes, rendu, export .mid),
// BANG = l'app SwiftUI, bang-check = auto-test en ligne de commande.
import PackageDescription

let package = Package(
    name: "BANG",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "BANG", targets: ["BANG"]),
        .executable(name: "bang-check", targets: ["bang-check"]),
        .library(name: "BangCore", targets: ["BangCore"]),
    ],
    targets: [
        .target(name: "BangCore"),
        .executableTarget(name: "BANG", dependencies: ["BangCore"]),
        .executableTarget(name: "bang-check", dependencies: ["BangCore"]),
    ]
)
