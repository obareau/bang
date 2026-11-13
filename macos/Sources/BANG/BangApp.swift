import AppKit
import BangCore
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    var spaceHandler: (() -> Void)?
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
        if let path = env["BANG_SNAPSHOT"] {
            if let size = env["BANG_SNAPSHOT_SIZE"]?.split(separator: "x").compactMap({ Double($0) }), size.count == 2 {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    NSApp.windows.first(where: { $0.isVisible })?
                        .setFrame(NSRect(x: 0, y: 0, width: size[0], height: size[1]), display: true)
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
                .onAppear { delegate.spaceHandler = { model.togglePlay() } }
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
