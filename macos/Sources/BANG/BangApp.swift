import AppKit
import BangCore
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    var spaceHandler: (() -> Void)?
    weak var model: AppModel?
    private var monitor: Any?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // Nécessaire quand le binaire tourne hors bundle (`swift run`).
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        // Espace = lecture / stop, sauf quand on tape dans un champ texte.
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            let mods = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
            if event.keyCode == 49, mods.subtracting([.capsLock, .numericPad, .function]).isEmpty,
               !(NSApp.keyWindow?.firstResponder is NSText) {
                self?.spaceHandler?()
                return nil
            }
            return event
        }
        // Au lancement, aucun champ texte ne doit garder le focus (sinon
        // Espace taperait dans le champ BPM au lieu de lancer la lecture).
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            NSApp.windows.forEach { $0.makeFirstResponder(nil) }
        }
        // Diagnostic : BANG_SNAPSHOT=/chemin.png → la fenêtre se dessine dans
        // une image (sans permission d'enregistrement d'écran). BANG_SNAPSHOT_PLAY=1
        // lance la lecture avant la capture, BANG_SNAPSHOT_QUIT=1 quitte ensuite.
        let env = ProcessInfo.processInfo.environment
        // Diagnostic : BANG_SELFTEST_MODES=1 → lecture, puis les 14 modes
        // enchaînés (dans les deux sens) toutes les 0,3 s, puis quitte.
        if env["BANG_SELFTEST_MODES"] == "1" {
            let modes = Mode.allCases + Mode.allCases.reversed()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.model?.start() }
            for (i, m) in modes.enumerated() {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5 + Double(i) * 0.3) {
                    self.model?.selectedVoice = 6
                    self.model?.session.params.mode = m
                    self.model?.generate()
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5 + Double(modes.count) * 0.3) {
                print("BANG_SELFTEST_MODES ok (\(modes.count) changements)")
                NSApp.terminate(nil)
            }
        }
        // Diagnostic : BANG_SELFTEST_AUDIO=1 → joue un groove et mesure la sortie
        // du synthé interne avec chaque kit (tout, puis batterie seule), puis quitte.
        if env["BANG_SELFTEST_AUDIO"] == "1" {
            Task { @MainActor in
                guard let m = self.model else { return }
                m.internalSynthOn = true
                m.session.params.mode = .morph
                m.session.params.bpm = 120
                m.generate()
                m.start()
                try? await Task.sleep(nanoseconds: 500_000_000)
                for soloDrums in [false, true] {
                    // Solo sur les voix envoyées au canal batterie (10).
                    let input = m.session.renderInput()
                    m.session.soloed = soloDrums
                        ? Set(m.session.voices.indices.filter { !m.session.voices[$0].isCC && input.channel(for: $0) == 9 })
                        : []
                    for kit in DrumKit.allCases {
                        m.drumKit = kit
                        let (p, r) = await withCheckedContinuation { c in
                            m.synth.measure(seconds: 2) { c.resume(returning: ($0, $1)) }
                        }
                        print(String(format: "BANG_SELFTEST_AUDIO %@ %@ crête %.3f rms %.4f",
                                     soloDrums ? "batterie seule" : "tout          ", kit.short, p, r))
                    }
                }
                m.stop()
                NSApp.terminate(nil)
            }
        }
        // Diagnostic : BANG_SELFTEST_WAV=/dossier → exporte le pattern courant en
        // WAV (×2) avec chaque kit sous son nom preset-variation-date, puis quitte.
        if let dir = env["BANG_SELFTEST_WAV"] {
            Task { @MainActor in
                guard let m = self.model else { return }
                let saved = m.session
                // Pattern de contrôle : attaques attendues toutes les 0,25 s à 120 BPM.
                if env["BANG_SELFTEST_WAV_GRID"] == "1" {
                    m.session.voices = [Voice(36, "x---x---x---x---", "drum"), Voice(42, "--x---x---x---x-", "drum")]
                    m.session.params.bpm = 120
                    m.session.params.steps = 16
                    m.session.params.swing = 0
                    m.session.params.microtiming = 1
                    m.session.params.velHumanize = 0
                    m.session.muted = []; m.session.soloed = []; m.session.settings = [:]
                }
                m.wavLoops = 2
                try? m.midiData().write(to: URL(fileURLWithPath: dir).appendingPathComponent("reference.mid"))
                for kit in DrumKit.allCases {
                    m.drumKit = kit
                    let url = URL(fileURLWithPath: dir).appendingPathComponent(m.wavName + ".wav")
                    let r = await withCheckedContinuation { c in m.renderWAV(to: url) { c.resume(returning: $0) } }
                    switch r {
                    case .success(let res): print(String(format: "BANG_SELFTEST_WAV %@ %.2fs crête-avant %.3f", url.lastPathComponent, res.seconds, res.peakBefore))
                    case .failure(let e): print("BANG_SELFTEST_WAV ÉCHEC \(e.localizedDescription)")
                    }
                }
                m.session = saved
                try? await Task.sleep(nanoseconds: 1_200_000_000)  // laisse l'autosauvegarde passer
                NSApp.terminate(nil)
            }
        }
        // Diagnostic : BANG_SELFTEST_WAV_LOOP=/dossier → pattern qui déborde
        // (kick 808 long + charleston ouvert en fin) rendu ×1 en boucle parfaite
        // (loop.wav) et ×3 à plat (flat3.wav) pour comparer, puis quitte.
        if let dir = env["BANG_SELFTEST_WAV_LOOP"] {
            DispatchQueue.global().async {
                var p = GenParams()
                p.bpm = 120; p.steps = 16
                let input = RenderInput(voices: [Voice(36, "x---x---x---x---", "drum"),
                                                 Voice(46, "--------------x-", "drum")],
                                        params: p)
                let d = URL(fileURLWithPath: dir)
                for (name, loops, seamless) in [("loop", 1, true), ("flat3", 3, false)] {
                    let r = try? WavExport.render(input: input, numSteps: 16, loops: loops, seed: "1",
                                                  kit: .tr808, seamless: seamless,
                                                  to: d.appendingPathComponent(name + ".wav"))
                    print("BANG_SELFTEST_WAV_LOOP \(name) \(r.map { String(format: "%.3fs", $0.seconds) } ?? "ÉCHEC")")
                }
                DispatchQueue.main.async { NSApp.terminate(nil) }
            }
        }
        // Diagnostics du jeu live (session sauvegardée puis restaurée) :
        //  BANG_SELFTEST_LIVE=song  → 3 mémoires (notes 36/38/42) enchaînées « 1x2 2x1 3x1 »
        //  BANG_SELFTEST_LIVE=morph → coup au step 1 qui morphe vers le step 5 en 4 cycles
        //  BANG_SELFTEST_LIVE=sync:<source> → suit l'horloge MIDI de <source> (kick à chaque temps)
        //  BANG_SELFTEST_SECONDS : durée (défaut 5)
        if let what = env["BANG_SELFTEST_LIVE"] {
            Task { @MainActor in
                guard let m = self.model else { return }
                let saved = m.session
                let seconds = Double(env["BANG_SELFTEST_SECONDS"] ?? "") ?? 5
                m.internalSynthOn = false
                var s = BangSession()
                s.params.bpm = 240
                s.params.steps = 8
                if what == "song" {
                    for (i, note) in [(0, 36), (1, 38), (2, 42)] {
                        s.voices = [Voice(note, "x-------", "drum")]
                        s.saveSlot(i)
                    }
                    s.loadSlot(0)
                    m.session = s
                    m.song.text = "1x2 2x1 3x1"
                    m.song.on = true
                    m.start()
                } else if what == "morph" {
                    s.voices = [Voice(36, "----x---", "drum")]
                    s.saveSlot(1)
                    s.voices = [Voice(36, "x-------", "drum")]
                    m.session = s
                    m.morphTargetSlot = 1
                    m.morphCycles = 4
                    m.start()
                    m.toggleMorph()
                } else if what.hasPrefix("sync:") {
                    let name = String(what.dropFirst(5))
                    s.params.bpm = 60       // ignoré : c'est l'horloge externe qui mène
                    s.params.steps = 4      // un cycle = une noire
                    s.voices = [Voice(36, "x---", "drum")]
                    m.session = s
                    for _ in 0..<50 where m.syncSourceID == nil {   // la source peut apparaître après le lancement
                        m.refreshClockSources()
                        m.syncSourceID = m.clockSources.first { $0.name == name }?.id
                        if m.syncSourceID == nil { try? await Task.sleep(nanoseconds: 100_000_000) }
                    }
                    print("BANG_SELFTEST_LIVE sync source trouvée : \(m.syncSourceID != nil)")
                }
                try? await Task.sleep(nanoseconds: UInt64(seconds * 1e9))
                print("BANG_SELFTEST_LIVE fin : cycles \(m.cycleCount), horloge \(m.clockBPM.map { String(format: "%.2f BPM", $0) } ?? "-")")
                m.stop()
                m.song.on = false
                m.syncSourceID = nil
                m.session = saved
                try? await Task.sleep(nanoseconds: 1_200_000_000)
                NSApp.terminate(nil)
            }
        }
        if let path = env["BANG_SNAPSHOT"] {
            if let size = env["BANG_SNAPSHOT_SIZE"]?.split(separator: "x").compactMap({ Double($0) }), size.count == 2 {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    NSApp.windows.first(where: { $0.isVisible })?
                        .setFrame(NSRect(x: 0, y: 0, width: size[0], height: size[1]), display: true)
                }
            }
            if let mode = env["BANG_SNAPSHOT_MODE"].flatMap(Mode.init(rawValue:)) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
                    self.model?.session.params.mode = mode
                    self.model?.generate()
                    self.model?.session.updateSettings(0) { $0.velLane = [127, 0, 40, 0, 90, 0, 0, 20] }
                }
            }
            if let sel = env["BANG_SNAPSHOT_SELECT"].flatMap(Int.init) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                    self.model?.selectedVoice = sel
                    self.model?.session.updateSettings(sel) { $0.lfo = VoiceLFO(shape: .tri, target: .density, freq: 1, depth: 0.6) }
                }
            }
            if env["BANG_SNAPSHOT_PLAY"] == "1" {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.spaceHandler?() }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                if let view = NSApp.windows.first(where: { $0.isVisible })?.contentView,
                   let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds) {
                    view.cacheDisplay(in: view.bounds, to: rep)
                    try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: path))
                }
                if env["BANG_SNAPSHOT_QUIT"] == "1" { NSApp.terminate(nil) }
            }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

@main
struct BangApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    @StateObject private var model = AppModel()

    var body: some Scene {
        Window("BANG!", id: "main") {
            ContentView()
                .environmentObject(model)
                .environmentObject(model.play)
                .frame(minWidth: 1080, minHeight: 640)
                .preferredColorScheme(.dark)
                .onAppear {
                    delegate.spaceHandler = { model.togglePlay() }
                    delegate.model = model
                }
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1360, height: 820)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Générer un pattern") { model.generate() }.keyboardShortcut("g")
                Button("Varier toutes les voix") { model.session.varyAll() }.keyboardShortcut("g", modifiers: [.command, .shift])
                Divider()
                Button("Ouvrir une session…") { model.openSession() }.keyboardShortcut("o")
                Button("Enregistrer la session…") { model.saveSession() }.keyboardShortcut("s")
                Button("Exporter en MIDI…") { model.exportMIDI() }.keyboardShortcut("e")
                Button("Exporter en WAV…") { model.exportWAV() }.keyboardShortcut("e", modifiers: [.command, .shift])
            }
            CommandGroup(replacing: .undoRedo) {
                Button("Annuler") { model.undo() }.keyboardShortcut("z")
            }
            CommandGroup(after: .toolbar) {
                Button("Agrandir l'interface") { model.zoomIn() }.keyboardShortcut("+")
                Button("Réduire l'interface") { model.zoomOut() }.keyboardShortcut("-")
                Button("Taille réelle (suit la fenêtre)") { model.zoom = 1 }.keyboardShortcut("0")
            }
            CommandMenu("Transport") {
                Button(model.isPlaying ? "Stop (Espace)" : "Lecture (Espace)") { model.togglePlay() }
                    .keyboardShortcut(.return, modifiers: .command)
                Divider()
                Toggle("Synthé interne (GM)", isOn: $model.internalSynthOn)
                Toggle("Port MIDI virtuel « BANG! »", isOn: $model.virtualPortOn)
            }
        }
    }
}
