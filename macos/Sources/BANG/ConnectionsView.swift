import BangCore
import CoreMIDI
import SwiftUI

/// Fenêtre CONNEXIONS : OSC, Ableton, Strudel / export, MIDI Learn, NTS-1, MicroFreak.
struct ConnectionsView: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(alignment: .leading, spacing: 12 * z) {
            HStack {
                Text(Theme.spaced("Connexions")).font(Theme.mono(11 * z, .bold)).foregroundStyle(Theme.accent)
                Spacer()
                Button("Fermer") { studio.showSheet = false }
                    .buttonStyle(BangButtonStyle(compact: true))
                    .keyboardShortcut(.cancelAction)
            }
            Segmented(options: Studio.Tab.allCases, selection: $studio.tab) { $0.rawValue }
            Rectangle().fill(Theme.line).frame(height: 1)
            ScrollView {
                VStack(alignment: .leading, spacing: 12 * z) {
                    switch studio.tab {
                    case .osc: OSCTab()
                    case .ableton: AbletonTab()
                    case .export: ExportTab()
                    case .learn: LearnTab()
                    case .nts1: SynthPanel(title: "Korg NTS-1", sections: SynthPanel.nts1, channel: $studio.nts1Channel,
                                           note: "Sur le NTS-1, activer le paramètre global « MIDI RX ShortMessage » pour qu'il reçoive les CC.")
                    case .microfreak: SynthPanel(title: "Arturia MicroFreak", sections: SynthPanel.microfreak,
                                                 channel: $studio.mfChannel,
                                                 note: "CC vérifiés dans la documentation Arturia. Canal par défaut 9 = celui des voix MicroFreak de BANG!.")
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(20 * z)
        .frame(width: 820 * z, height: 600 * z)
        .background(Theme.bg)
        .font(Theme.mono(11 * z))
        .foregroundStyle(Theme.ink)
    }
}

/// Champ texte au style BANG!.
struct BangField: View {
    @Environment(\.uiScale) private var z
    let placeholder: String
    @Binding var text: String
    var width: CGFloat = 140

    var body: some View {
        TextField(placeholder, text: $text)
            .textFieldStyle(.plain)
            .font(Theme.mono(11 * z))
            .padding(5 * z)
            .frame(width: width * z)
            .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.line))
    }
}

private func intBinding(_ b: Binding<Int>) -> Binding<String> {
    Binding(get: { "\(b.wrappedValue)" }, set: { if let v = Int($0.filter(\.isNumber)) { b.wrappedValue = v } })
}

private struct Field: View {
    @Environment(\.uiScale) private var z
    let label: String
    var body: some View {
        Text(label).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).frame(width: 110 * z, alignment: .leading)
    }
}

// MARK: - OSC

struct OSCTab: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            HStack(spacing: 8 * z) {
                Field(label: "ÉMISSION")
                Button(studio.oscTxOn ? "ON" : "OFF") { studio.oscTxOn.toggle() }
                    .buttonStyle(BangButtonStyle(active: studio.oscTxOn, compact: true))
                BangField(placeholder: "hôte", text: $studio.oscHost)
                Text(":").foregroundStyle(Theme.dim)
                BangField(placeholder: "port", text: intBinding($studio.oscTxPort), width: 70)
                Text("SuperCollider 57120 · Max · TouchOSC").font(Theme.mono(9 * z)).foregroundStyle(Theme.dim)
            }
            HStack(spacing: 8 * z) {
                Field(label: "RÉCEPTION")
                Button(studio.oscRxOn ? "ON" : "OFF") { studio.oscRxOn.toggle() }
                    .buttonStyle(BangButtonStyle(active: studio.oscRxOn, compact: true))
                Text("port").foregroundStyle(Theme.dim)
                BangField(placeholder: "9000", text: intBinding($studio.oscRxPort), width: 70)
                if let e = studio.oscError { Text("⚠ \(e)").foregroundStyle(Theme.accent).font(Theme.mono(9 * z)) }
            }
            Text("""
            Émis : /bang/bpm · /bang/chaos · /bang/steps · /bang/mode · /bang/seed · /bang/voice/<n>/dna · /bang/voice/<n>/note \
            (à chaque nouveau pattern) ; pendant la lecture /bang/clock [step, steps] et /bang/<voix> [step, vélocité, note].
            Reçu : /bang/generate · /bang/vary · /bang/play · /bang/stop · /bang/param/<bpm|chaos|gravity|swing|microtiming|cc_depth|steps|transpose> \
            · /bang/density/<voix> f · /bang/lock/<n> i · /bang/mute/<n> i · /bang/slot/<1-8> · /bang/evolve i \
            · /bang/fill i · /bang/poly i · /bang/ab f (crossfader 0 = A, 1 = B) · /bang/glide.
            """)
            .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            SectionHeader(title: "Moniteur")
            VStack(alignment: .leading, spacing: 2 * z) {
                if studio.oscLog.isEmpty {
                    Text("Aucun message pour l'instant.").foregroundStyle(Theme.dim)
                }
                ForEach(studio.oscLog.prefix(40)) { e in
                    HStack(spacing: 8 * z) {
                        Text(e.time, format: .dateTime.hour().minute().second()).foregroundStyle(Theme.dim)
                        Text(e.incoming ? "RX" : "TX").foregroundStyle(e.incoming ? Theme.accent : Theme.muted)
                        Text(e.text).lineLimit(1)
                    }
                    .font(Theme.mono(9 * z))
                }
            }
        }
    }
}

// MARK: - Ableton

struct AbletonTab: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            Text("Nécessite AbletonOSC (github.com/ideoforms/AbletonOSC) installé comme Control Surface dans Live.")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted)
            HStack(spacing: 8 * z) {
                Field(label: "LIVE")
                BangField(placeholder: "hôte", text: $studio.abletonHost)
                Text(":").foregroundStyle(Theme.dim)
                BangField(placeholder: "11000", text: intBinding($studio.abletonPort), width: 70)
            }
            HStack(spacing: 8 * z) {
                Field(label: "DESTINATION")
                Text("1re piste").foregroundStyle(Theme.dim)
                BangField(placeholder: "1", text: intBinding($studio.abletonTrack), width: 50)
                Text("scène").foregroundStyle(Theme.dim)
                BangField(placeholder: "1", text: intBinding($studio.abletonSlot), width: 50)
            }
            HStack(spacing: 8 * z) {
                Button("ENVOYER LES CLIPS") { studio.sendToAbleton() }.buttonStyle(BangButtonStyle(prominent: true))
                Button("BPM DEPUIS LIVE") { studio.syncTempoFromAbleton() }.buttonStyle(BangButtonStyle())
            }
            Text("Un clip par voix, sur des pistes consécutives (les clips existants à cet emplacement sont remplacés), et le tempo de Live réglé sur celui de BANG!.")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            if !studio.abletonStatus.isEmpty { Text(studio.abletonStatus).foregroundStyle(Theme.accent) }
        }
    }
}

// MARK: - Strudel / export

struct ExportTab: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            HStack(spacing: 8 * z) {
                Button("COPIER LE CODE STRUDEL") { studio.copyStrudel() }.buttonStyle(BangButtonStyle(prominent: true))
                Button("UN .mid PAR VOIX…") { studio.exportVoices() }.buttonStyle(BangButtonStyle())
                Button("GABARIT TOUCHOSC…") { studio.saveTouchOSC() }.buttonStyle(BangButtonStyle())
                    .disabled(Studio.touchOSCTemplate == nil)
            }
            Text(StrudelExport.code(model.session))
                .font(Theme.mono(10 * z))
                .textSelection(.enabled)
                .padding(10 * z)
                .frame(maxWidth: .infinity, alignment: .leading)
                .overlay(RoundedRectangle(cornerRadius: 3).stroke(Theme.line))
            Text("À coller sur strudel.cc. Les voix Babka ne sont pas converties. Le gabarit TouchOSC pilote BANG! en OSC (activer la réception).")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted)
        }
    }
}

// MARK: - MIDI Learn

struct LearnTab: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var studio: Studio

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            HStack(spacing: 8 * z) {
                Field(label: "ENTRÉE MIDI")
                PopMenu(compact: true, active: studio.learnSourceID != nil, entries: {
                    var e: [MenuEntry] = [.item("Aucune", checked: studio.learnSourceID == nil) { studio.learnSourceID = nil }]
                    for s in studio.learnSources {
                        e.append(.item(s.name, checked: studio.learnSourceID == s.id) { studio.learnSourceID = s.id })
                    }
                    e += [.separator, .item("Rafraîchir") { studio.refreshLearnSources() }]
                    return e
                }) { Text(studio.learnSources.first { $0.id == studio.learnSourceID }?.name ?? "Choisir…") }
                .frame(width: 260 * z)
            }
            Text("Choisis une voix : après un décompte de 2 temps, joue le rythme sur tes pads pendant la longueur de la voix. Chaque frappe devient un « x » au step le plus proche.")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            ForEach(Array(model.session.voices.enumerated()), id: \.offset) { i, v in
                if !v.isCC && !v.isBabka {
                    HStack(spacing: 10 * z) {
                        Button("⏺") { studio.learn(voice: i) }
                            .buttonStyle(BangButtonStyle(active: studio.learning, compact: true))
                            .disabled(studio.learning || studio.learnSourceID == nil)
                        Text(v.label).frame(width: 110 * z, alignment: .leading)
                        Text(v.dna).font(Theme.mono(10 * z)).foregroundStyle(Theme.muted).lineLimit(1)
                    }
                }
            }
            if !studio.learnState.isEmpty {
                Text(studio.learnState).font(Theme.mono(13 * z, .bold)).foregroundStyle(Theme.accent)
            }
        }
    }
}

// MARK: - Panneaux synthés

struct SynthPanel: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var studio: Studio
    let title: String
    let sections: [(String, [(String, Int)])]
    @Binding var channel: Int
    let note: String

    /// CC officiels Korg (tableau MIDI du NTS-1 digital kit, 2019).
    static let nts1: [(String, [(String, Int)])] = [
        ("Oscillateur", [("Type", 53), ("Shape", 54), ("Alt", 55), ("LFO rate", 24), ("LFO depth", 26)]),
        ("Filtre", [("Type", 42), ("Cutoff", 43), ("Résonance", 44), ("Sweep depth", 45), ("Sweep rate", 46)]),
        ("Enveloppe", [("Type", 14), ("Attack", 16), ("Release", 19), ("Trémolo depth", 20), ("Trémolo rate", 21)]),
        ("Modulation", [("Type", 88), ("Time", 28), ("Depth", 29)]),
        ("Delay", [("Type", 89), ("Time", 30), ("Depth", 31), ("Mix", 33)]),
        ("Reverb", [("Type", 90), ("Time", 34), ("Depth", 35), ("Mix", 36)]),
        ("Arpège", [("Pattern", 117), ("Intervals", 118), ("Length", 119)]),
    ]

    /// CC confirmés par Arturia pour le MicroFreak.
    static let microfreak: [(String, [(String, Int)])] = [
        ("Oscillateur", [("Type", 9), ("Wave", 10), ("Timbre", 12), ("Shape", 13)]),
        ("Filtre", [("Cutoff", 23), ("Résonance", 83)]),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 10 * z) {
            HStack(spacing: 8 * z) {
                Text(title).font(Theme.mono(12 * z, .bold))
                Spacer()
                Text("CANAL").font(Theme.mono(10 * z)).foregroundStyle(Theme.muted)
                PopMenu(compact: true, entries: {
                    (1...16).map { c in .item("\(c)", checked: channel == c) { channel = c } }
                }) { Text("\(channel)") }
                .frame(width: 56 * z)
            }
            Text(note + " Les CC partent vers la destination MIDI choisie et le port virtuel « BANG! ».")
                .font(Theme.mono(9 * z)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 18 * z), GridItem(.flexible(), spacing: 18 * z)],
                      alignment: .leading, spacing: 14 * z) {
                ForEach(sections, id: \.0) { name, knobs in
                    VStack(alignment: .leading, spacing: 6 * z) {
                        SectionHeader(title: name)
                        ForEach(knobs, id: \.1) { label, cc in
                            let key = "\(title)-\(cc)"
                            ParamSlider(label: "\(label)", value: Binding(
                                get: { Double(studio.ccValues[key] ?? 64) },
                                set: { studio.sendCC(cc, Int($0.rounded()), channel: channel, key: key) }),
                                range: 0...127, format: "%.0f")
                            .help("CC \(cc)")
                        }
                    }
                }
            }
        }
    }
}
