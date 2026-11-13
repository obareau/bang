import BangCore
import CoreMIDI
import SwiftUI

/// Racine : calcule le facteur de zoom d'après la taille de la fenêtre
/// (référence 1360×820 = 100 %) multiplié par le zoom manuel (⌘+ / ⌘−),
/// puis le diffuse à toutes les vues via l'environnement.
struct ContentView: View {
    @EnvironmentObject var model: AppModel

    var body: some View {
        GeometryReader { geo in
            let fit = min(geo.size.width / Theme.baseSize.width, geo.size.height / Theme.baseSize.height)
            let z = min(3.0, max(0.75, fit * model.zoom))
            MainLayout()
                .environment(\.uiScale, z)
            }
        .ignoresSafeArea(edges: .top)
    }
}

struct MainLayout: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(spacing: 0) {
            TopBar()
            Rectangle().fill(Theme.line).frame(height: 1)
            HStack(spacing: 0) {
                ScrollView { GeneratorPanel().padding(14 * z) }
                    .frame(width: 286 * z)
                    .background(Theme.panel)
                Rectangle().fill(Theme.line).frame(width: 1)
                VStack(spacing: 0) {
                    VoiceRack()
                    Rectangle().fill(Theme.line).frame(height: 1)
                    PianoRoll()
                        .frame(height: 170 * z)
                }
            }
            Rectangle().fill(Theme.line).frame(height: 1)
            StatusBar()
        }
        .background(Theme.bg)
        .ignoresSafeArea(edges: .top)
        .sheet(isPresented: $studio.showSheet) {
            ConnectionsView()
                .environmentObject(model)
                .environmentObject(studio)
                .environment(\.uiScale, z)
                .preferredColorScheme(.dark)
        }
    }
}

// MARK: - Barre du haut : logo + transport + sorties

struct TopBar: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var play: PlayState

    var body: some View {
        HStack(spacing: 14 * z) {
            HStack(spacing: 0) {
                Text("BANG").foregroundStyle(Theme.ink)
                Text("!").foregroundStyle(Theme.accent)
            }
            .font(Theme.mono(20 * z, .bold))

            Text(Theme.spaced(model.session.params.mode.label))
                .font(Theme.mono(9 * z))
                .foregroundStyle(Theme.muted)
                .lineLimit(1)

            Spacer()

            Button(action: model.togglePlay) {
                Image(systemName: model.isPlaying ? "stop.fill" : "play.fill")
                    .font(.system(size: 13 * z, weight: .bold))
                    .frame(width: 30 * z, height: 22 * z)
            }
            .buttonStyle(BangButtonStyle(active: model.isPlaying, prominent: !model.isPlaying))
            .help("Lecture / Stop (Espace)")

            HStack(spacing: 4 * z) {
                Text(model.syncOn ? "SYNC" : "BPM").font(Theme.mono(9 * z))
                    .foregroundStyle(model.syncOn ? Theme.accent : Theme.muted)
                TextField("", value: $model.session.params.bpm, format: .number)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(13 * z, .bold))
                    .frame(width: 38 * z)
                    .multilineTextAlignment(.trailing)
                Button { model.session.params.bpm = max(20, model.session.params.bpm - 1) } label: { Text("−") }
                    .buttonStyle(BangButtonStyle(compact: true))
                Button { model.session.params.bpm = min(300, model.session.params.bpm + 1) } label: { Text("+") }
                    .buttonStyle(BangButtonStyle(compact: true))
                Button { model.tap() } label: { Text("TAP") }
                    .buttonStyle(BangButtonStyle(compact: true))
                    .disabled(model.syncOn)
                    .help("Tap tempo")
            }

            Text(String(format: "%03d/%03d", model.isPlaying ? play.step + 1 : 0, model.session.params.steps))
                .font(Theme.mono(13 * z))
                .foregroundStyle(model.isPlaying ? Theme.accent : Theme.dim)
                .monospacedDigit()

            OutputMenu()

            Button { model.studio.showSheet = true } label: { Text("CONNEXIONS") }
                .buttonStyle(BangButtonStyle(active: model.studio.oscTxOn || model.studio.oscRxOn))
                .help("OSC, Ableton Live, Strudel, MIDI Learn, NTS-1, MicroFreak")

            Button { model.exportMIDI() } label: { Text("EXPORT .mid") }
                .buttonStyle(BangButtonStyle())
                .help("Exporter le pattern en fichier MIDI (⌘E)")

            Button { model.exportWAV() } label: { Text(model.isRenderingWav ? "RENDU…" : "EXPORT .wav") }
                .buttonStyle(BangButtonStyle(active: model.isRenderingWav))
                .disabled(model.isRenderingWav)
                .help("Rendre le pattern en audio WAV avec le synthé interne (⇧⌘E)")

            Text("⇣ GLISSER")
                .font(Theme.mono(10 * z))
                .foregroundStyle(Theme.ink)
                .padding(.horizontal, 8 * z).padding(.vertical, 5 * z)
                .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.dim, style: StrokeStyle(lineWidth: 1, dash: [3, 2])))
                .onDrag { model.dragFile() }
                .help("Glisser le .mid vers Ableton, Logic ou le Finder")
        }
        .padding(.leading, 84)
        .padding(.trailing, 14 * z)
        .frame(height: 48 * z)
        .background(Theme.bg)
    }
}

struct OutputMenu: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    var label: String {
        var parts: [String] = []
        if model.internalSynthOn { parts.append("Synthé \(model.drumKit.short)") }
        if let id = model.destinationID, let d = model.destinations.first(where: { $0.id == id }) { parts.append(d.name) }
        if model.virtualPortOn { parts.append("Virtuel") }
        return parts.isEmpty ? "Aucune sortie" : parts.joined(separator: " + ")
    }

    var body: some View {
        PopMenu(entries: {
            var e: [MenuEntry] = [
                .item("Synthé interne (General MIDI)", checked: model.internalSynthOn) { model.internalSynthOn.toggle() },
                .item("Port virtuel « BANG! » (pour DAW)", checked: model.virtualPortOn) { model.virtualPortOn.toggle() },
                .submenu("Kit batterie du synthé", DrumKit.allCases.map { k in
                    .item(k.label, checked: model.drumKit == k) { model.drumKit = k }
                }),
                .separator,
                .item("Aucune destination", checked: model.destinationID == nil) { model.destinationID = nil },
            ]
            for d in model.destinations {
                e.append(.item(d.name, checked: model.destinationID == d.id) { model.destinationID = d.id })
            }
            e += [.separator, .item("Rafraîchir les ports") { model.refreshDestinations() }]
            return e
        }) {
            HStack(spacing: 6 * z) {
                Image(systemName: "pianokeys")
                Text(label).lineLimit(1)
            }
        }
        .fixedSize()
    }
}

// MARK: - Panneau générateur

struct GeneratorPanel: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @StateObject private var showAdvanced = Box(false)

    private var p: Binding<GenParams> { $model.session.params }

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            SectionHeader(title: "Mode")
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 6 * z), GridItem(.flexible(), spacing: 6 * z)], spacing: 6 * z) {
                ForEach(Mode.allCases) { m in
                    Button { model.session.params.mode = m } label: {
                        Text(m.label).frame(maxWidth: .infinity, alignment: .leading).lineLimit(1)
                    }
                    .buttonStyle(BangButtonStyle(active: model.session.params.mode == m, compact: true))
                }
            }

            SectionHeader(title: "Paramètres")
            ParamSlider(label: "CHAOS", value: p.chaos)
            ParamSlider(label: "GRAVITÉ", value: p.gravity)
            ParamSlider(label: "CC DEPTH", value: p.ccDepth)
            ParamSlider(label: "SWING", value: p.swing)

            HStack {
                Text("STEPS").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 62 * z, alignment: .leading)
                Segmented(options: [8, 16, 32, 64, 128], selection: p.steps) { "\($0)" }
            }

            HStack(spacing: 6 * z) {
                Text("GAMME").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 62 * z, alignment: .leading)
                PopMenu(compact: true, entries: {
                    Scales.chromatic.map { r in
                        .item(r, checked: model.session.params.root == r) { model.session.params.root = r }
                    }
                }) { Text(model.session.params.root) }
                .frame(width: 58 * z)
                PopMenu(compact: true, entries: {
                    Scales.intervals.map { sc in
                        .item(sc.name, checked: model.session.params.scale == sc.id) { model.session.params.scale = sc.id }
                    }
                }) { Text(Scales.intervals.first { $0.id == model.session.params.scale }?.name ?? "—") }
            }
            .opacity(model.session.params.mode.usesScale ? 1 : 0.45)

            HStack(spacing: 6 * z) {
                Text("SEED").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 62 * z, alignment: .leading)
                TextField("auto", text: p.seed)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(10 * z))
                    .padding(4 * z)
                    .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.line))
                Button { model.session.params.seed = model.session.lastSeed } label: { Image(systemName: "pin") }
                    .buttonStyle(BangButtonStyle(active: !model.session.params.seed.isEmpty, compact: true))
                    .help("Figer la seed du pattern courant (reproductible)")
                Button { model.session.params.seed = "" } label: { Image(systemName: "dice") }
                    .buttonStyle(BangButtonStyle(compact: true))
                    .help("Seed aléatoire à chaque génération")
            }

            DisclosureGroup(isExpanded: $showAdvanced.value) {
                VStack(spacing: 8 * z) {
                    ParamSlider(label: "MICRO", value: p.microtiming)
                    ParamSlider(label: "COURBE", value: p.velCurve, range: 0.1...4)
                    ParamSlider(label: "HUMAIN", value: Binding(
                        get: { Double(model.session.params.velHumanize) },
                        set: { model.session.params.velHumanize = Int($0) }), range: 0...40, format: "%.0f")
                    ParamSlider(label: "VEL MIN", value: Binding(
                        get: { Double(model.session.params.velFloor) },
                        set: { model.session.params.velFloor = Int($0) }), range: 0...126, format: "%.0f")
                    ParamSlider(label: "VEL MAX", value: Binding(
                        get: { Double(model.session.params.velCeiling) },
                        set: { model.session.params.velCeiling = Int($0) }), range: 1...127, format: "%.0f")
                }
                .padding(.top, 6 * z)
            } label: {
                Text("VÉLOCITÉ & TIMING").font(Theme.mono(9 * z)).foregroundStyle(Theme.muted)
            }
            .tint(Theme.muted)

            Button { model.generate() } label: {
                Text("GÉNÉRER  ⌘G").frame(maxWidth: .infinity)
            }
            .buttonStyle(BangButtonStyle(prominent: true))
            .padding(.top, 4 * z)

            HStack(spacing: 6 * z) {
                Button { model.session.varyAll() } label: { Text("VARIER").frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle())
                Button { model.undo() } label: { Text("ANNULER").frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle())
                    .disabled(model.session.history.isEmpty)
            }

            LivePanel()

            SectionHeader(title: "Presets")
            HStack(spacing: 6 * z) {
                PopMenu(compact: true, entries: {
                    Presets.grooves.map { g in .item(g.name) { model.session.applyGroove(g.name) } }
                }) { Text("Groove") }
                PopMenu(compact: true, active: !model.session.currentPreset.isEmpty, entries: {
                    Presets.drumMachines.map { d in
                        .item(d.name, checked: model.session.currentPreset == d.name) { model.session.applyDrumPreset(d.name) }
                    }
                }) { Text(model.session.currentPreset.isEmpty ? "Machine" : model.session.currentPreset) }
            }

            HStack(spacing: 6 * z) {
                Text("KIT").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 62 * z, alignment: .leading)
                Segmented(options: DrumKit.allCases, selection: $model.drumKit) { $0.short }
            }
            .help("Batterie du synthé interne (canal 10) : General MIDI, ou 808 / 909 synthétisées")


            if model.session.params.mode == .weather || model.session.weather != nil {
                SectionHeader(title: "Météo Scaër")
                HStack {
                    Text(model.session.weather.map { String(format: "%.1f °C · %.0f km/h", $0.temperature, $0.windSpeed) } ?? "—")
                        .font(Theme.mono(10 * z))
                    Spacer()
                    Button("Actualiser") { model.refreshWeather() }
                        .buttonStyle(BangButtonStyle(compact: true))
                }
            }
        }
    }
}

struct SlotStrip: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    var body: some View {
        HStack(spacing: 5 * z) {
            ForEach(0..<8, id: \.self) { i in
                let filled = model.session.slots[i] != nil
                let current = filled && model.session.currentSlot == i
                Text("\(i + 1)")
                    .font(Theme.mono(10 * z, .bold))
                    .frame(maxWidth: .infinity, minHeight: 24 * z)
                    .foregroundStyle(current ? Theme.bg : (filled ? Theme.accent : Theme.dim))
                    .background(RoundedRectangle(cornerRadius: 3).fill(current ? Theme.accent : Color.clear))
                    .overlay(RoundedRectangle(cornerRadius: 3).stroke(filled ? Theme.accent : Theme.line))
                    .contentShape(Rectangle())
                    .overlay(alignment: .topTrailing) {
                        if model.session.slotWeights[i] > 1 {
                            Text("\(model.session.slotWeights[i])").font(Theme.mono(7 * z)).foregroundStyle(Theme.muted).padding(2 * z)
                        }
                    }
                    .contextMenu {
                        Text("Poids pour l'avance auto")
                        ForEach(1...9, id: \.self) { w in
                            Button("\(w)\(model.session.slotWeights[i] == w ? "  ✓" : "")") { model.session.slotWeights[i] = w }
                        }
                    }
                    .onTapGesture {
                        if NSEvent.modifierFlags.contains(.option) || !filled {
                            model.session.saveSlot(i)
                            model.status = "Pattern mémorisé en \(i + 1)."
                        } else {
                            model.session.loadSlot(i)
                            model.status = "Mémoire \(i + 1) chargée."
                        }
                    }
            }
        }
    }
}

struct StatusBar: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel

    var body: some View {
        HStack(spacing: 16 * z) {
            Text(model.status).lineLimit(1)
            Spacer()
            Text("seed \(model.session.lastSeed.prefix(16))")
                .textSelection(.enabled)
            Text("\(model.session.voices.filter { !$0.isCC }.count) voix")
        }
        .font(Theme.mono(10 * z))
        .foregroundStyle(Theme.muted)
        .padding(.horizontal, 14 * z)
        .frame(height: 24 * z)
        .background(Theme.bg)
    }
}
