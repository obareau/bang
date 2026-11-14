import AppKit
import BangCore
import CoreMIDI
import SwiftUI

/// Section LIVE du panneau de gauche : horloge, évolution, mémoires
/// (auto, A/B), morph et Song — tout ce qui sert à jouer sur scène.
struct LivePanel: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @StateObject private var songDraft = Box("")

    private func label(_ s: String) -> some View {
        Text(s).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 62 * z, alignment: .leading)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            SectionHeader(title: "Live")

            // Horloge : tap + synchro MIDI
            HStack(spacing: 6 * z) {
                label("HORLOGE")
                Button { model.tap() } label: { Text("TAP").frame(width: 34 * z) }
                    .buttonStyle(BangButtonStyle(compact: true))
                    .disabled(model.syncOn)
                    .help("Tapez au moins deux fois en rythme (médiane des 5 derniers)")
                PopMenu(compact: true, active: model.syncOn, entries: {
                    var e: [MenuEntry] = [.item("Interne (BPM de BANG!)", checked: !model.syncOn) { model.syncSourceID = nil }]
                    if !model.clockSources.isEmpty { e.append(.separator) }
                    for s in model.clockSources {
                        e.append(.item("MIDI clock : \(s.name)", checked: model.syncSourceID == s.id) { model.syncSourceID = s.id })
                    }
                    e += [.separator, .item("Rafraîchir les sources") { model.refreshClockSources() }]
                    return e
                }) {
                    Text(model.syncOn ? (model.clockBPM.map { String(format: "SYNC %.1f", $0) } ?? "SYNC …") : "INTERNE")
                        .lineLimit(1)
                }
                .help("Suivre l'horloge MIDI (24 ppq, Start/Stop) d'un DAW ou d'une machine")
            }

            // FILL (conditions « fill » / « !fill » des voix)
            HStack(spacing: 6 * z) {
                label("FILL")
                Button { model.fill.toggle() } label: { Text(model.fill ? "FILL ON" : "FILL").frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle(active: model.fill, prominent: model.fill, compact: true))
                    .keyboardShortcut("f", modifiers: [.command, .option])
            }
            .help("Mode FILL : les voix réglées sur « FILL » ne jouent que pendant ce mode, « sauf FILL » se taisent (⌥⌘F)")

            // Auto-évolution
            HStack(spacing: 6 * z) {
                label("ÉVOLUTION")
                Segmented(options: [0, 1, 2, 4, 8], selection: $model.evolveEvery) { $0 == 0 ? "off" : "×\($0)" }
            }
            .help("Une variation automatique toutes les N répétitions du pattern")

            // A/B
            HStack(spacing: 6 * z) {
                label("A / B")
                ForEach([false, true], id: \.self) { isB in
                    let name: Character = isB ? "B" : "A"
                    let filled = (isB ? model.session.slotB : model.session.slotA) != nil
                    Text(String(name))
                        .font(Theme.mono(11 * z, .bold))
                        .frame(maxWidth: .infinity, minHeight: 22 * z)
                        .foregroundStyle(model.activeAB == name && filled ? Theme.bg : (filled ? Theme.accent : Theme.dim))
                        .background(RoundedRectangle(cornerRadius: 3)
                            .fill(model.activeAB == name && filled ? Theme.accent : Color.clear))
                        .overlay(RoundedRectangle(cornerRadius: 3).stroke(filled ? Theme.accent : Theme.line))
                        .contentShape(Rectangle())
                        .onTapGesture {
                            if NSEvent.modifierFlags.contains(.option) || !filled { model.storeAB(isB) }
                            else { model.loadAB(isB) }
                        }
                }
            }
            .help("Clic : charger · ⌥ clic : mémoriser le pattern courant")

            // Mémoires + avance auto
            SlotStrip()
            HStack(spacing: 6 * z) {
                Button { model.autoAdvance.toggle(); if model.autoAdvance { model.song.on = false } } label: {
                    Text("AUTO").frame(width: 40 * z)
                }
                .buttonStyle(BangButtonStyle(active: model.autoAdvance, compact: true))
                .help("Change de mémoire automatiquement (tirage pondéré parmi les mémoires pleines)")
                Text("tous les").font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)
                PopMenu(compact: true, entries: {
                    [1, 2, 4, 8, 16].map { n in .item("\(n) cycle\(n > 1 ? "s" : "")", checked: model.advanceEvery == n) { model.advanceEvery = n } }
                }) { Text("\(model.advanceEvery)") }
                .frame(width: 52 * z)
                Text("cycles").font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)
            }
            Text("⌥ clic : mémoriser · clic droit : poids")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)

            // Morph
            HStack(spacing: 6 * z) {
                label("MORPH")
                Text("→").font(Theme.mono(10 * z)).foregroundStyle(Theme.dim)
                PopMenu(compact: true, entries: {
                    (0..<8).map { i in
                        .item("Mémoire \(i + 1)\(model.session.slots[i] == nil ? " (vide)" : "")",
                              checked: model.morphTargetSlot == i) { model.morphTargetSlot = i }
                    }
                }) { Text("\(model.morphTargetSlot + 1)") }
                .frame(width: 44 * z)
                PopMenu(compact: true, entries: {
                    [2, 4, 8, 16, 32].map { n in .item("en \(n) cycles", checked: model.morphCycles == n) { model.morphCycles = n } }
                }) { Text("\(model.morphCycles)c") }
                .frame(width: 52 * z)
                Button { model.toggleMorph() } label: { Text(model.morph == nil ? "GO" : "STOP").frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle(active: model.morph != nil, compact: true))
            }
            .help("Passe en douceur du pattern courant à une mémoire, sur N cycles (pendant la lecture)")
            if let m = model.morph {
                GeometryReader { g in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Theme.line)
                        Capsule().fill(Theme.accent).frame(width: g.size.width * m.progress)
                    }
                }
                .frame(height: 4 * z)
            }

            // Song
            HStack(spacing: 6 * z) {
                label("SONG")
                TextField("1x4 2x2 3", text: $songDraft.value)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(10 * z))
                    .padding(4 * z)
                    .overlay(RoundedRectangle(cornerRadius: 3).stroke(model.song.on ? Theme.accent : Theme.line))
                    .onSubmit { model.song.text = songDraft.value }
                    .onAppear { songDraft.value = model.song.text }
                Button {
                    model.song.text = songDraft.value
                    model.toggleSong()
                } label: { Text(model.song.on ? "STOP" : "GO").frame(width: 38 * z) }
                .buttonStyle(BangButtonStyle(active: model.song.on, compact: true))
            }
            .help("Enchaîne les mémoires : « 1x4 2x2 3 » = mémoire 1 pendant 4 cycles, 2 pendant 2, 3 pendant 1, puis reboucle")
            if model.song.on {
                let chain = SongChain.parse(model.song.text)
                if !chain.parts.isEmpty {
                    let part = chain.parts[min(model.song.part, chain.parts.count - 1)]
                    Text("▶ mémoire \(part.slot + 1) · \(model.song.repeat_ + 1)/\(part.repeats)   ·   \(chain.description)")
                        .font(Theme.mono(9 * z)).foregroundStyle(Theme.accent).lineLimit(2)
                }
            }
        }
    }
}

/// Ligne LFO dans le détail d'une voix.
struct LFORow: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    let index: Int

    private var lfo: VoiceLFO? { model.session.settings(for: index).lfo }

    private func set(_ f: @escaping (inout VoiceLFO?) -> Void) {
        model.session.updateSettings(index) { f(&$0.lfo) }
    }

    var body: some View {
        HStack(spacing: 10 * z) {
            Text("LFO").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
            Segmented(options: ["off"] + VoiceLFO.Shape.allCases.map(\.rawValue),
                      selection: Binding(
                        get: { lfo?.shape.rawValue ?? "off" },
                        set: { v in set { l in
                            if let shape = VoiceLFO.Shape(rawValue: v) {
                                var n = l ?? VoiceLFO(); n.shape = shape; l = n
                            } else { l = nil }
                        } })) { $0 }
                .frame(width: 230 * z)
            if let l = lfo {
                Segmented(options: VoiceLFO.Target.allCases.map(\.rawValue),
                          selection: Binding(get: { l.target.rawValue },
                                             set: { v in set { $0?.target = VoiceLFO.Target(rawValue: v) ?? .density } })) {
                    $0 == "density" ? "densité" : "drop"
                }
                .frame(width: 130 * z)
                ParamSlider(label: "VITESSE", value: Binding(get: { l.freq }, set: { v in set { $0?.freq = v } }),
                            range: 0.05...4)
                ParamSlider(label: "PROFOND.", value: Binding(get: { l.depth }, set: { v in set { $0?.depth = v } }))
            } else {
                Spacer()
            }
        }
    }
}
