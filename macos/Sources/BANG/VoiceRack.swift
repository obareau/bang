import BangCore
import SwiftUI

struct VoiceRack: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(Array(model.session.voices.enumerated()), id: \.offset) { i, v in
                    if v.isCC {
                        CCRow(voice: v)
                    } else {
                        VoiceRow(index: i, voice: v)
                    }
                    Rectangle().fill(Theme.line.opacity(0.6)).frame(height: 1)
                }
            }
        }
        .background(Theme.bg)
    }
}

struct CCRow: View {
    @Environment(\.uiScale) private var z
    let voice: Voice
    var body: some View {
        HStack(spacing: 10 * z) {
            Text("CC").font(Theme.mono(10 * z, .bold)).foregroundStyle(Theme.dim).frame(width: 128 * z, alignment: .leading)
            Text(voice.dna).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
            Spacer()
            Text("drone · export + live").font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)
        }
        .padding(.horizontal, 14 * z)
        .frame(height: 30 * z)
    }
}

struct VoiceRow: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var play: PlayState
    let index: Int
    let voice: Voice
    @StateObject private var draft = Box("")

    private var s: BangSession { model.session }
    private var expanded: Bool { model.selectedVoice == index }
    private var locked: Bool { s.locked.contains(index) }
    private var audible: Bool { s.isAudible(index) }

    private var flash: Double {
        guard model.isPlaying, let t = play.hits[index] else { return 0 }
        return max(0, 1 - (Player.now() - t) / 0.18)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8 * z) {
            HStack(spacing: 10 * z) {
                Circle()
                    .fill(Theme.accent.opacity(flash))
                    .overlay(Circle().stroke(Theme.dim, lineWidth: 1))
                    .frame(width: 8 * z, height: 8 * z)

                VStack(alignment: .leading, spacing: 2 * z) {
                    Text(voice.label)
                        .font(Theme.mono(12 * z, .bold))
                        .foregroundStyle(audible ? Theme.ink : Theme.dim)
                        .lineLimit(1)
                    Text(meta)
                        .font(Theme.mono(9 * z))
                        .foregroundStyle(Theme.dim)
                        .lineLimit(1)
                }
                .frame(width: 110 * z, alignment: .leading)
                .contentShape(Rectangle())
                .onTapGesture { model.selectedVoice = expanded ? nil : index }

                DNAGrid(dna: voice.dna, babka: voice.isBabka || !DNA.isPlain(voice.dna),
                        playStep: model.isPlaying ? play.step : nil,
                        dimmed: !audible, locked: locked) { step in
                    model.session.cycleStep(index, step)
                }
                .frame(height: 26 * z)

                HStack(spacing: 4 * z) {
                    toggle("L", on: locked, help: "Verrouiller (protégé de Générer / Varier)") {
                        model.session.toggle(\.locked, index)
                    }
                    toggle("M", on: s.muted.contains(index), help: "Mute") { model.session.toggle(\.muted, index) }
                    toggle("S", on: s.soloed.contains(index), help: "Solo") { model.session.toggle(\.soloed, index) }
                }

                TransformMenu(index: index, voice: voice)
            }

            if expanded { detail }
        }
        .padding(.horizontal, 14 * z)
        .padding(.vertical, 8 * z)
        .background(expanded ? Theme.panel : Color.clear)
    }

    private var meta: String {
        let input = s.renderInput()
        let ch = input.channel(for: voice) + 1
        let note = voice.isMelodic ? "markov" : "n\(input.outputNote(for: voice))"
        let st = s.settings(for: index)
        var tags = ""
        if st.thin > 1 { tags += " ÷\(st.thin)" }
        if st.offset != 0 { tags += " +\(st.offset)" }
        if st.lfo != nil { tags += " ∿" }
        if st.velLane.contains(where: { $0 > 0 }) || st.probLane.contains(where: { $0 > 0 }) { tags += " ▤" }
        return "\(note) · ch\(ch) · \(voice.dna.count)\(tags)"
    }

    private func toggle(_ t: String, on: Bool, help: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) { Text(t).frame(width: 12 * z) }
            .buttonStyle(BangButtonStyle(active: on, compact: true))
            .help(help)
    }

    private var settings: VoiceSettings { s.settings(for: index) }

    private func bind(_ kp: WritableKeyPath<VoiceSettings, Double>) -> Binding<Double> {
        Binding(get: { settings[keyPath: kp] },
                set: { v in model.session.updateSettings(index) { $0[keyPath: kp] = v } })
    }

    @ViewBuilder private var detail: some View {
        VStack(alignment: .leading, spacing: 8 * z) {
            HStack(spacing: 8 * z) {
                Text("DNA").font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).frame(width: 40 * z, alignment: .leading)
                TextField("x-?↺░ · Babka : [x x] <a b> x(3,8)", text: $draft.value)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(12 * z))
                    .padding(5 * z)
                    .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.dim))
                    .onSubmit { model.session.setPattern(index, draft.value) }
                    .onAppear { draft.value = voice.dna }
                    .onChange(of: voice.dna) { new in draft.value = new }
                ForEach(["x", "-", "?", "↺", "░"], id: \.self) { sym in
                    Button(sym) { draft.value += sym }
                        .buttonStyle(BangButtonStyle(compact: true))
                        .help("Insérer \(sym)")
                }
                Button("OK") { model.session.setPattern(index, draft.value) }
                    .buttonStyle(BangButtonStyle(active: true, compact: true))
            }
            StructureRow(index: index, voice: voice)
            if DNA.isPlain(voice.dna) && !voice.isBabka {
                LaneEditor(title: "VÉL", dna: voice.dna, maxValue: 127, values: settings.velLane,
                           ghost: { $0.trigger ? $0.velocity : nil }) { v in
                    model.session.updateSettings(index) { $0.velLane = v }
                }
                LaneEditor(title: "PROB %", dna: voice.dna, maxValue: 100, values: settings.probLane,
                           ghost: { $0.trigger ? Int($0.prob * 100) : nil }) { v in
                    model.session.updateSettings(index) { $0.probLane = v }
                }
            }
            LFORow(index: index)
            HStack(spacing: 18 * z) {
                ParamSlider(label: "DENSITÉ", value: bind(\.density))
                ParamSlider(label: "DROP", value: bind(\.drop))
                ParamSlider(label: "SWING", value: bind(\.swing))
            }
            HStack(spacing: 12 * z) {
                Text("CANAL").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
                PopMenu(compact: true, entries: {
                    [MenuEntry.item("auto (\(voice.defaultChannel() + 1))", checked: settings.channel == nil) {
                        model.session.updateSettings(index) { $0.channel = nil }
                    }] + (0..<16).map { ch in
                        .item("\(ch + 1)", checked: settings.channel == ch) {
                            model.session.updateSettings(index) { $0.channel = ch }
                        }
                    }
                }) { Text(settings.channel.map { "\($0 + 1)" } ?? "auto (\(voice.defaultChannel() + 1))") }
                .frame(width: 110 * z)
                if voice.isMelodic {
                    Text("ACCORD").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
                    PopMenu(compact: true, entries: {
                        Chords.all.map { c in
                            .item(c.id, checked: settings.chord == c.id) {
                                model.session.updateSettings(index) { $0.chord = c.id }
                            }
                        }
                    }) { Text(settings.chord) }
                    .frame(width: 90 * z)
                }
                Spacer()
                Text(voice.type).font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)
            }
        }
        .padding(.leading, 18 * z)
    }
}

struct TransformMenu: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    let index: Int
    let voice: Voice

    var body: some View {
        let locked = model.session.locked.contains(index)
        Button {
            guard !locked else { return }
            let n = max(1, voice.dna.count)
            let entries: [MenuEntry] = [
                .item("Varier  ~") { apply { DNA.vary($0, rng: Dice()) } },
                .item("Régénérer") { model.session.regen(index) },
                .separator,
                .item("Inverser") { apply(DNA.invert) },
                .item("Rotation →") { apply { DNA.rotate($0, by: 1) } },
                .item("Rotation ←") { apply { DNA.rotate($0, by: -1) } },
                .item("Miroir") { apply(DNA.reverse) },
                .item("Doubler") { apply(DNA.double) },
                .item("Diviser par 2") { apply(DNA.halve) },
                .submenu("Euclide", (1...min(n, 16)).map { k in
                    .item("\(k) / \(n)") { apply { _ in DNA.euclid(n: n, k: k) } }
                }),
                .separator,
                .item("Copier la DNA") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(voice.dna, forType: .string)
                },
                .item("MIDI Learn (jouer le rythme)…") { model.studio.learn(voice: index) },
                .item("Coller la DNA") {
                    if let s = NSPasteboard.general.string(forType: .string) { model.session.setPattern(index, s) }
                },
            ]
            PopMenu<EmptyView>.build(entries).popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
        } label: {
            Image(systemName: "ellipsis").font(.system(size: 12 * z, weight: .bold)).frame(width: 18 * z)
        }
        .buttonStyle(BangButtonStyle(compact: true))
        .opacity(locked ? 0.3 : 1)
        .help("Transformations")
    }

    private func apply(_ f: @escaping (String) -> String) {
        model.session.transform(index, f)
    }
}

/// Grille DNA dessinée : une case par step (ou, pour Babka, une case par
/// atome avec sa durée réelle). Clic = fait tourner le symbole.
struct DNAGrid: View {
    @Environment(\.uiScale) private var z
    let dna: String
    let babka: Bool
    let playStep: Int?
    let dimmed: Bool
    let locked: Bool
    let onTap: (Int) -> Void

    private var cells: [(cell: DNACell, sym: Character, width: Double)] {
        if babka {
            return Babka.parse(dna, cycle: 0).map { st in
                let sym: Character = !st.cell.trigger ? "-" : st.cell.ratchet > 1 ? "↺" :
                    st.cell.jitter > 0 ? "░" : st.cell.prob < 1 ? "?" : "x"
                return (st.cell, sym, st.duration)
            }
        }
        return dna.map { (DNA.cell($0), $0, 1.0) }
    }

    var body: some View {
        let cells = self.cells
        let total = max(1e-9, cells.reduce(0) { $0 + $1.width })
        GeometryReader { geo in
            Canvas { ctx, size in
                guard !cells.isEmpty else { return }
                let unit = size.width / total
                let gap: CGFloat = unit > 8 ? 2 : 1
                // Position de lecture dans le pattern (en steps)
                var playPos: Double? = nil
                if let p = playStep { playPos = Double(p).truncatingRemainder(dividingBy: total) }
                var x = 0.0
                var unitCount = 0.0
                for c in cells {
                    let w = c.width * unit
                    let rect = CGRect(x: x + gap / 2, y: 2, width: max(1, w - gap), height: size.height - 4)
                    let isPlay = playPos.map { $0 >= unitCount - 1e-9 && $0 < unitCount + c.width - 1e-9 } ?? false
                    draw(&ctx, c.sym, rect, play: isPlay)
                    // Repère de temps (toutes les 4 steps)
                    if !babka, Int(unitCount) % 4 == 0 {
                        ctx.fill(Path(CGRect(x: x + gap / 2, y: size.height - 1, width: max(1, w - gap), height: 1)),
                                 with: .color(Theme.dim))
                    }
                    x += w
                    unitCount += c.width
                }
            }
            .opacity(dimmed ? 0.35 : 1)
            .contentShape(Rectangle())
            .gesture(SpatialTapGesture().onEnded { v in
                guard !babka, !locked, !cells.isEmpty else { return }
                let idx = Int(v.location.x / (geo.size.width / total))
                if idx >= 0 && idx < cells.count { onTap(idx) }
            })
        }
        .help(babka ? "Pattern Babka — édition via le champ DNA (clic sur le nom)" :
                      "Clic : - → x → ? → ↺ → ░")
    }

    private func draw(_ ctx: inout GraphicsContext, _ sym: Character, _ r: CGRect, play: Bool) {
        let ink = play ? Theme.accent : Theme.ink
        let box = Path(roundedRect: r, cornerRadius: 2)
        switch sym {
        case "x":
            ctx.fill(box, with: .color(ink.opacity(play ? 1 : 0.88)))
        case "?":
            ctx.stroke(box, with: .color(ink.opacity(0.8)), lineWidth: 1)
            let half = CGRect(x: r.minX, y: r.midY, width: r.width, height: r.height / 2)
            ctx.fill(Path(roundedRect: half, cornerRadius: 1), with: .color(ink.opacity(0.55)))
        case "↺":
            ctx.fill(box, with: .color(ink.opacity(0.18)))
            let bw = max(1, r.width / 5)
            for k in 0..<3 {
                let bx = r.minX + r.width * (0.2 + 0.3 * Double(k)) - bw / 2
                ctx.fill(Path(CGRect(x: bx, y: r.minY + 2, width: bw, height: r.height - 4)), with: .color(ink))
            }
        case "░":
            // Trame ordonnée 2×2 : rappel du dithering Robōtariis
            ctx.stroke(box, with: .color(ink.opacity(0.5)), lineWidth: 1)
            var y = r.minY + 1
            var row = 0
            while y < r.maxY - 1 {
                var px = r.minX + 1 + Double(row % 2) * 2
                while px < r.maxX - 1 {
                    ctx.fill(Path(CGRect(x: px, y: y, width: 1.5, height: 1.5)), with: .color(ink.opacity(0.9)))
                    px += 4
                }
                y += 2
                row += 1
            }
        default:
            ctx.stroke(box, with: .color(play ? Theme.accent : Theme.line), lineWidth: play ? 1.5 : 1)
        }
    }
}
