import AppKit
import SwiftUI

/// Contrôles dessinés en SwiftUI : contrairement aux contrôles AppKit (qui
/// n'ont que mini/small/regular/large), ils suivent le zoom en continu.

/// Une entrée de menu déroulant.
enum MenuEntry {
    case item(String, checked: Bool = false, action: () -> Void)
    case separator
    case submenu(String, [MenuEntry])
}

/// Bouton au look BANG! qui ouvre un vrai menu natif (NSMenu) sous lui.
struct PopMenu<Label: View>: View {
    @Environment(\.uiScale) private var z
    var compact = false
    var active = false
    let entries: () -> [MenuEntry]
    @ViewBuilder let label: () -> Label

    var body: some View {
        Button {
            let menu = PopMenu.build(entries())
            menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)
        } label: {
            HStack(spacing: 4 * z) {
                label()
                Spacer(minLength: 0)
                Image(systemName: "chevron.down").font(.system(size: 7 * z, weight: .bold))
                    .foregroundStyle(Theme.muted)
            }
        }
        .buttonStyle(BangButtonStyle(active: active, compact: compact))
    }

    private final class Target: NSObject {
        let action: () -> Void
        init(_ a: @escaping () -> Void) { action = a }
        @objc func fire() { action() }
    }

    static func build(_ entries: [MenuEntry]) -> NSMenu {
        let menu = NSMenu()
        menu.autoenablesItems = false
        for e in entries {
            switch e {
            case .separator:
                menu.addItem(.separator())
            case let .item(title, checked, action):
                let t = Target(action)
                let it = NSMenuItem(title: title, action: #selector(Target.fire), keyEquivalent: "")
                it.target = t
                it.representedObject = t  // garde la cible en vie
                it.state = checked ? .on : .off
                menu.addItem(it)
            case let .submenu(title, children):
                let it = NSMenuItem(title: title, action: nil, keyEquivalent: "")
                it.submenu = build(children)
                menu.addItem(it)
            }
        }
        return menu
    }
}

/// Curseur fin à piste et poignée, mis à l'échelle.
struct BangSlider: View {
    @Environment(\.uiScale) private var z
    @Binding var value: Double
    var range: ClosedRange<Double> = 0...1

    var body: some View {
        GeometryReader { geo in
            let span = range.upperBound - range.lowerBound
            let t = span > 0 ? (value - range.lowerBound) / span : 0
            let knob = 11 * z
            let w = max(1, geo.size.width - knob)
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.line).frame(height: 3 * z)
                Capsule().fill(Theme.accent).frame(width: knob / 2 + w * t, height: 3 * z)
                Circle()
                    .fill(Theme.ink)
                    .frame(width: knob, height: knob)
                    .offset(x: w * t)
            }
            .frame(maxHeight: .infinity)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { g in
                let nt = min(1, max(0, (g.location.x - knob / 2) / w))
                value = range.lowerBound + nt * span
            })
        }
        .frame(height: 18 * z)
    }
}

/// Sélecteur segmenté (ex. STEPS 8/16/32/64/128).
struct Segmented<T: Hashable>: View {
    @Environment(\.uiScale) private var z
    let options: [T]
    @Binding var selection: T
    let title: (T) -> String

    var body: some View {
        HStack(spacing: 3 * z) {
            ForEach(options, id: \.self) { o in
                Button { selection = o } label: { Text(title(o)).frame(maxWidth: .infinity) }
                    .buttonStyle(BangButtonStyle(active: selection == o, compact: true))
            }
        }
    }
}
