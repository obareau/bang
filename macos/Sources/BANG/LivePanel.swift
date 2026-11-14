import AppKit
import BangCore
import CoreMIDI
import SwiftUI

/// Section LIVE du panneau de gauche : horloge, FILL et évolution, puis les
/// blocs MÉMOIRES (8 cases, transition, AUTO, SONG) et A ↔ B (crossfader).
struct LivePanel: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            SectionHeader(title: "Live")

            // Horloge : tap + synchro MIDI
            HStack(spacing: 6 * z) {
                LiveLabel("HORLOGE")
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
                LiveLabel("FILL")
                Button { model.fill.toggle() } label: { Text(model.fill ? "FILL ON" : "FILL").frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle(active: model.fill, prominent: model.fill, compact: true))
                    .keyboardShortcut("f", modifiers: [.command, .option])
            }
            .help("Mode FILL : les voix réglées sur « FILL » ne jouent que pendant ce mode, « sauf FILL » se taisent (⌥⌘F)")

            // Auto-évolution
            HStack(spacing: 6 * z) {
                LiveLabel("ÉVOLUTION")
                Segmented(options: [0, 1, 2, 4, 8], selection: $model.evolveEvery) { $0 == 0 ? "off" : "×\($0)" }
            }
            .help("Une variation automatique toutes les N répétitions du pattern")

            MemoriesBlock()
            ABBlock()
        }
    }
}

/// Libellé de ligne à largeur fixe (colonne de gauche).
struct LiveLabel: View {
    @Environment(\.uiScale) private var z
    let text: String
    init(_ text: String) { self.text = text }
    var body: some View {
        Text(text).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
            .lineLimit(1).fixedSize()
            .frame(width: 70 * z, alignment: .leading)
    }
}

/// Une case de mémoire (1…8, A ou B).
struct PadView: View {
    @Environment(\.uiScale) private var z
    let title: String
    var filled: Bool
    /// Le pattern courant est exactement cette case.
    var current = false
    /// Le pattern courant vient de cette case mais a été modifié depuis.
    var modified = false
    /// ENREGISTRER est armé : la case attend un clic.
    var armed = false
    /// Fondu en cours vers cette case (0…1).
    var progress: Double? = nil
    var badge: String? = nil

    var body: some View {
        Text(title)
            .font(Theme.mono(10 * z, .bold))
            .frame(maxWidth: .infinity, minHeight: 24 * z)
            .foregroundStyle(current ? Theme.bg : (filled ? Theme.accent : (armed ? Theme.accent.opacity(0.7) : Theme.dim)))
            .background(RoundedRectangle(cornerRadius: 3)
                .fill(current ? Theme.accent : (armed ? Theme.accent.opacity(0.10) : Color.clear)))
            .overlay(RoundedRectangle(cornerRadius: 3)
                .strokeBorder(filled || armed ? Theme.accent : Theme.line,
                              style: StrokeStyle(lineWidth: 1, dash: armed ? [3 * z, 2 * z] : [])))
            .overlay(alignment: .topTrailing) {
                if modified {
                    Circle().fill(Theme.accent).frame(width: 5 * z, height: 5 * z).padding(3 * z)
                } else if let badge {
                    Text(badge).font(Theme.mono(7 * z)).foregroundStyle(current ? Theme.bg : Theme.muted).padding(2 * z)
                }
            }
            .overlay(alignment: .bottomLeading) {
                if let p = progress {
                    GeometryReader { g in
                        Rectangle().fill(Theme.accent)
                            .frame(width: g.size.width * max(0.08, p), height: 3 * z)
                            .frame(maxHeight: .infinity, alignment: .bottom)
                    }
                }
            }
            .contentShape(Rectangle())
    }
}

/// Bloc MÉMOIRES : ranger des patterns, les rejouer (net ou en fondu), les enchaîner.
struct MemoriesBlock: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @StateObject private var songDraft = Box("")

    private var option: Bool { NSEvent.modifierFlags.contains(.option) }

    var body: some View {
        let playing = model.playingMemory
        VStack(alignment: .leading, spacing: 8 * z) {
            SectionHeader(title: "Mémoires")

            Button { model.storeArmed.toggle() } label: {
                HStack(spacing: 6 * z) {
                    Circle().fill(model.storeArmed ? Theme.bg : Theme.accent).frame(width: 7 * z, height: 7 * z)
                    Text(model.storeArmed ? "CLIQUE UNE CASE : 1–8, A OU B" : "ENREGISTRER LE PATTERN")
                        .lineLimit(1)
                }
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(BangButtonStyle(active: model.storeArmed, prominent: model.storeArmed, compact: true))
            .help("Range le pattern courant : clique ce bouton, puis la case voulue (mémoire 1–8, A ou B). Raccourci : ⌥ clic sur la case. Re-cliquer ici annule.")

            HStack(spacing: 5 * z) {
                ForEach(0..<8, id: \.self) { i in pad(i, playing: playing) }
            }

            HStack(spacing: 6 * z) {
                Text(statusText(playing))
                    .font(Theme.mono(9 * z))
                    .foregroundStyle(model.morph != nil || playing != nil ? Theme.accent : Theme.muted)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                if model.morph != nil {
                    Button { model.cancelFade() } label: { Text("STOP") }
                        .buttonStyle(BangButtonStyle(compact: true))
                        .help("Arrête le fondu : on reste sur le pattern courant")
                }
            }

            HStack(spacing: 6 * z) {
                LiveLabel("TRANSITION")
                Segmented(options: [0, 2, 4, 8, 16], selection: $model.transitionCycles) { $0 == 0 ? "net" : "\($0)c" }
            }
            .help("Quand tu cliques une mémoire pendant la lecture : bascule nette, ou fondu sur 2 à 16 cycles (les rythmes se mélangent peu à peu, voix par voix)")

            HStack(spacing: 6 * z) {
                LiveLabel("AUTO")
                Segmented(options: [0, 2, 4, 8, 16], selection: Binding(
                    get: { model.autoAdvance ? model.advanceEvery : 0 },
                    set: { n in
                        model.autoAdvance = n > 0
                        if n > 0 { model.advanceEvery = n; model.song.on = false }
                    })) { $0 == 0 ? "off" : "×\($0)" }
            }
            .help("Change de mémoire tout seul tous les N cycles, au hasard parmi les mémoires pleines. Clic droit sur une mémoire : son poids (plus il est fort, plus elle revient).")

            HStack(spacing: 6 * z) {
                LiveLabel("SONG")
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

    private func pad(_ i: Int, playing: Int?) -> some View {
        let slot = model.session.slots[i]
        let filled = slot != nil
        let weight = model.session.slotWeights[i]
        return PadView(title: "\(i + 1)", filled: filled,
                       current: playing == i,
                       modified: filled && playing != i && model.memBase == i,
                       armed: model.storeArmed,
                       progress: model.morph?.slot == i ? model.morph?.progress : nil,
                       badge: model.autoAdvance && filled && weight > 1 ? "\(weight)" : nil)
            .onTapGesture { model.memoryTapped(i, store: option) }
            .help(help(i, slot))
            .contextMenu {
                if filled {
                    Button("Jouer") { model.recallMemory(i) }
                    if model.transitionCycles > 0 {
                        Button("Jouer tout de suite (sans fondu)") { model.recallMemory(i, now: true) }
                    }
                }
                Button(filled ? "Remplacer par le pattern courant" : "Enregistrer le pattern courant ici") { model.storeMemory(i) }
                if filled {
                    Divider()
                    Button("Copier dans A") { model.session.copySlot(i, toAB: false) }
                    Button("Copier dans B") { model.session.copySlot(i, toAB: true) }
                    Menu("Poids pour AUTO : \(weight)") {
                        ForEach(1...9, id: \.self) { w in
                            Button("\(w)\(weight == w ? "  ✓" : "")") { model.setWeight(i, w) }
                        }
                    }
                    Divider()
                    Button("Vider la mémoire \(i + 1)") { model.clearMemory(i) }
                }
            }
    }

    private func help(_ i: Int, _ s: BangSession.Snapshot?) -> String {
        guard let s else { return "Mémoire \(i + 1) : vide. Clic : y ranger le pattern courant." }
        let voices = s.voices.filter { !$0.isCC }.count
        return "Mémoire \(i + 1) : \(s.params.mode.label) · \(voices) voix · \(s.params.steps) steps · \(s.params.bpm) BPM.\n"
            + "Clic : jouer · ⌥ clic : remplacer par le pattern courant · clic droit : plus d'options."
    }

    private func statusText(_ playing: Int?) -> String {
        if let m = model.morph {
            let done = Int((m.progress * Double(m.cycles)).rounded())
            return "Fondu vers la mémoire \(m.slot + 1) · cycle \(done)/\(m.cycles)"
        }
        if let p = playing { return "▶ Tu joues la mémoire \(p + 1)." }
        if let b = model.memBase, model.session.slots[b] != nil {
            return "Mémoire \(b + 1) modifiée (non enregistrée) · ⌥ clic sur \(b + 1) pour la mettre à jour."
        }
        if model.session.slots.allSatisfy({ $0 == nil }) {
            return "Aucune mémoire : ENREGISTRER, puis clique une case."
        }
        return "Le pattern courant n'est dans aucune mémoire."
    }
}

/// Bloc A ↔ B : deux patterns aux extrémités d'un crossfader.
struct ABBlock: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    private var option: Bool { NSEvent.modifierFlags.contains(.option) }

    var body: some View {
        let pos = model.abPosition
        VStack(alignment: .leading, spacing: 8 * z) {
            SectionHeader(title: "A ↔ B")
            HStack(spacing: 8 * z) {
                pad(false, pos)
                Crossfader(position: pos, enabled: model.abReady) { model.setABMix($0) }
                pad(true, pos)
            }
            Text(caption(pos))
                .font(Theme.mono(9 * z))
                .foregroundStyle(pos != nil && model.abReady ? Theme.accent : Theme.muted)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .center)
                .multilineTextAlignment(.center)
            HStack(spacing: 6 * z) {
                LiveLabel("GLISSER")
                Segmented(options: [2, 4, 8, 16], selection: $model.abGlideCycles) { "\($0)c" }
                Button { model.toggleGlide() } label: {
                    Text(model.abGlide != nil ? "STOP" : ((pos ?? 0) >= 0.5 ? "→ A" : "→ B")).frame(width: 36 * z)
                }
                .buttonStyle(BangButtonStyle(active: model.abGlide != nil, compact: true))
                .disabled(!model.abReady)
            }
            .help("Le crossfader part tout seul vers l'autre côté, un cran à chaque cycle (pendant la lecture)")
        }
    }

    private func pad(_ b: Bool, _ pos: Double?) -> some View {
        let name = b ? "B" : "A"
        let filled = (b ? model.session.slotB : model.session.slotA) != nil
        return PadView(title: name, filled: filled, current: pos == (b ? 1 : 0), armed: model.storeArmed)
            .frame(width: 34 * z)
            .onTapGesture { model.abTapped(b, store: option) }
            .help(filled
                  ? "\(name) : clic pour y aller (crossfader tout \(b ? "à droite" : "à gauche")) · ⌥ clic : remplacer par le pattern courant · clic droit : options"
                  : "\(name) : vide. Clic : y ranger le pattern courant.")
            .contextMenu {
                if filled {
                    Button("Aller à \(name)") { model.abReady ? model.setABMix(b ? 1 : 0) : model.loadAB(b) }
                }
                Button(filled ? "Remplacer par le pattern courant" : "Enregistrer le pattern courant ici") { model.storeAB(b) }
                if filled {
                    Menu("Copier dans la mémoire") {
                        ForEach(0..<8, id: \.self) { k in
                            Button("\(k + 1)\(model.session.slots[k] == nil ? "" : "  (remplace)")") { model.session.copyAB(b, toSlot: k) }
                        }
                    }
                    Divider()
                    Button("Vider \(name)") { model.clearAB(b) }
                }
                if model.abReady { Button("Échanger A et B") { model.swapAB() } }
            }
    }

    private func caption(_ pos: Double?) -> String {
        let a = model.session.slotA != nil, b = model.session.slotB != nil
        if !a && !b { return "Range un pattern en A et un autre en B, puis fais glisser de l'un à l'autre." }
        if !a || !b { return "Range aussi un pattern en \(a ? "B" : "A") pour pouvoir fondre." }
        guard let p = pos else { return "Le pattern courant n'est ni A ni B · clique A ou B pour y revenir." }
        let arrow = model.abGlide.map { $0.to == 1 ? "  → B" : "  → A" } ?? ""
        if p == 0 { return "100 % A\(arrow)" }
        if p == 1 { return "100 % B\(arrow)" }
        let pb = Int((p * 100).rounded())
        return "A \(100 - pb) %  ·  B \(pb) %\(arrow)"
    }
}

/// Crossfader : la poignée part de A (gauche) vers B (droite).
struct Crossfader: View {
    @Environment(\.uiScale) private var z
    let position: Double?
    let enabled: Bool
    let onChange: (Double) -> Void

    var body: some View {
        GeometryReader { geo in
            let knob = 12 * z
            let w = max(1, geo.size.width - knob)
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.line).frame(height: 4 * z)
                ForEach([0.0, 0.25, 0.5, 0.75, 1.0], id: \.self) { t in
                    Rectangle().fill(Theme.dim)
                        .frame(width: 1, height: (t == 0.5 ? 12 : 8) * z)
                        .offset(x: knob / 2 + w * t)
                }
                if let p = position {
                    Capsule().fill(Theme.accent.opacity(0.5))
                        .frame(width: knob / 2 + w * p, height: 4 * z)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(enabled ? Theme.accent : Theme.dim)
                        .frame(width: knob, height: 20 * z)
                        .offset(x: w * p)
                }
            }
            .frame(maxHeight: .infinity)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { g in
                onChange(min(1, max(0, (g.location.x - knob / 2) / w)))
            })
        }
        .frame(height: 24 * z)
        .opacity(enabled ? 1 : 0.5)
        .help("Crossfader : à gauche A, à droite B. Entre les deux, les rythmes de A et B se mélangent voix par voix.")
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
