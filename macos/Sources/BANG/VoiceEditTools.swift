import AppKit
import BangCore
import SwiftUI

/// Noms de notes : 60 = C3 (convention Ableton / Yamaha), donc 36 = C1.
enum NoteNames {
    static let pitch = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    static func name(_ n: Int) -> String { "\(pitch[((n % 12) + 12) % 12])\(n / 12 - 2)" }

    /// Percussions General MIDI (canal 10).
    static let gmDrums: [(Int, String)] = [
        (35, "Kick 2"), (36, "Kick"), (37, "Rim"), (38, "Snare"), (39, "Clap"), (40, "Snare 2"),
        (41, "Tom grave 2"), (42, "HH fermé"), (43, "Tom grave"), (44, "HH pédale"), (45, "Tom médium"),
        (46, "HH ouvert"), (47, "Tom médium 2"), (48, "Tom aigu"), (49, "Crash"), (50, "Tom aigu 2"),
        (51, "Ride"), (52, "China"), (53, "Ride bell"), (54, "Tambourin"), (55, "Splash"),
        (56, "Cowbell"), (57, "Crash 2"), (59, "Ride 2"),
    ]

    static func label(_ n: Int) -> String {
        if let d = gmDrums.first(where: { $0.0 == n }) { return "\(n) · \(name(n)) · \(d.1)" }
        return "\(n) · \(name(n))"
    }
}

/// Ligne STRUCTURE : longueur (polymétrie), décalage, Thin, note de sortie.
struct StructureRow: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    let index: Int
    let voice: Voice

    private var settings: VoiceSettings { model.session.settings(for: index) }

    private func stepper(_ title: String, _ value: String, minus: @escaping () -> Void, plus: @escaping () -> Void) -> some View {
        HStack(spacing: 4 * z) {
            Text(title).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
            Button(action: minus) { Text("−") }.buttonStyle(BangButtonStyle(compact: true))
            Text(value).font(Theme.mono(11 * z, .bold)).frame(minWidth: 30 * z)
            Button(action: plus) { Text("+") }.buttonStyle(BangButtonStyle(compact: true))
        }
    }

    var body: some View {
        HStack(spacing: 16 * z) {
            if !voice.isBabka {
                let len = voice.dna.count
                stepper("LONGUEUR", "\(len)\(settings.length == nil ? "" : "•")",
                        minus: { model.session.setLength(index, max(1, len - 1)) },
                        plus: { model.session.setLength(index, min(128, len + 1)) })
                    .help("Longueur de la voix en steps (polymétrie). • = imposée, gardée à la prochaine génération")
                if settings.length != nil {
                    Button("auto") { model.session.setLength(index, 0) }
                        .buttonStyle(BangButtonStyle(compact: true))
                        .help("Revenir à la longueur naturelle du mode à la prochaine génération")
                }
            }
            stepper("DÉCALAGE", settings.offset == 0 ? "0" : "+\(settings.offset)",
                    minus: { model.session.updateSettings(index) { $0.offset = max(0, $0.offset - 1) } },
                    plus: { model.session.updateSettings(index) { $0.offset = min(127, $0.offset + 1) } })
                .help("Fait glisser la lecture de N steps sans modifier la DNA")
            HStack(spacing: 4 * z) {
                Text("THIN").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
                Segmented(options: [1, 2, 4], selection: Binding(
                    get: { settings.thin },
                    set: { v in model.session.updateSettings(index) { $0.thin = v } })) { $0 == 1 ? "÷1" : "÷\($0)" }
                    .frame(width: 120 * z)
            }
            .help("Ne garde qu'un déclenchement sur 2 ou sur 4")
            if !voice.isMelodic && !voice.type.hasPrefix("vd") {
                let current = model.session.renderInput().outputNote(for: voice)
                HStack(spacing: 4 * z) {
                    Text("NOTE").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
                    PopMenu(compact: true, entries: {
                        var e: [MenuEntry] = [.item("Note d'origine (\(NoteNames.label(voice.note)))", checked: current == voice.note) {
                            model.session.setNote(index, nil)
                        }, .separator]
                        e.append(.submenu("Batterie General MIDI", NoteNames.gmDrums.map { n, _ in
                            .item(NoteNames.label(n), checked: current == n) { model.session.setNote(index, n) }
                        }))
                        for oct in 0..<8 {
                            let lo = 12 + oct * 12
                            e.append(.submenu("Octave \(oct - 1)  (\(NoteNames.name(lo))–\(NoteNames.name(lo + 11)))",
                                              (lo...lo + 11).map { n in
                                .item(NoteNames.label(n), checked: current == n) { model.session.setNote(index, n) }
                            }))
                        }
                        return e
                    }) { Text("\(current) \(NoteNames.name(current))") }
                    .frame(width: 96 * z)
                }
                .help("Note MIDI envoyée par cette voix")
            }
            Spacer()
        }
    }
}

/// Lane dessinable : une barre par position DNA. Glisser pour dessiner,
/// ⌥ + glisser pour effacer (retour à la valeur du symbole).
struct LaneEditor: View {
    @Environment(\.uiScale) private var z
    let title: String
    let dna: String
    let maxValue: Int
    let values: [Int]
    /// Valeur d'origine de chaque position (fantôme), nil = pas de déclenchement.
    let ghost: (DNACell) -> Int?
    let onChange: ([Int]) -> Void

    var body: some View {
        let cells = DNA.compile(dna)
        HStack(spacing: 8 * z) {
            Text(title).font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).frame(width: 40 * z, alignment: .leading)
            GeometryReader { geo in
                Canvas { ctx, size in
                    guard !cells.isEmpty else { return }
                    let w = size.width / CGFloat(cells.count)
                    for (i, c) in cells.enumerated() {
                        let x = CGFloat(i) * w
                        let frame = CGRect(x: x + 1, y: 0, width: max(1, w - 2), height: size.height)
                        ctx.fill(Path(CGRect(x: frame.minX, y: size.height - 1, width: frame.width, height: 1)),
                                 with: .color(Theme.line))
                        if let g = ghost(c) {
                            let h = size.height * CGFloat(g) / CGFloat(maxValue)
                            ctx.stroke(Path(CGRect(x: frame.minX, y: size.height - h, width: frame.width, height: h)),
                                       with: .color(Theme.dim), lineWidth: 1)
                        }
                        if i < values.count, values[i] > 0 {
                            let h = size.height * CGFloat(values[i]) / CGFloat(maxValue)
                            ctx.fill(Path(CGRect(x: frame.minX, y: size.height - h, width: frame.width, height: h)),
                                     with: .color(Theme.accent.opacity(0.85)))
                        }
                    }
                }
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0).onChanged { g in
                    guard !cells.isEmpty, geo.size.width > 0 else { return }
                    let i = Int(g.location.x / (geo.size.width / CGFloat(cells.count)))
                    guard i >= 0 && i < cells.count else { return }
                    var arr = values + Array(repeating: 0, count: max(0, cells.count - values.count))
                    if NSEvent.modifierFlags.contains(.option) {
                        arr[i] = 0
                    } else {
                        let t = 1 - g.location.y / max(1, geo.size.height)
                        arr[i] = max(1, min(maxValue, Int((t * CGFloat(maxValue)).rounded())))
                    }
                    if arr != values { onChange(Array(arr.prefix(cells.count))) }
                })
            }
            .frame(height: 30 * z)
            Button { onChange([]) } label: { Text("×") }
                .buttonStyle(BangButtonStyle(compact: true))
                .help("Effacer la lane")
                .disabled(!values.contains { $0 > 0 })
        }
        .help("Glisser pour dessiner · ⌥ + glisser pour effacer · contour = valeur du symbole")
    }
}
