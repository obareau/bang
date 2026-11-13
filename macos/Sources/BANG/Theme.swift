import SwiftUI

/// Charte Robōtariis : fond #0A0A0A, blanc #F2F2F2, un seul accent orange
/// #F97316, gris de structure #2E2E2E / #484848, Menlo partout.
/// Facteur de zoom de l'interface (1 = fenêtre de référence).
/// EnvironmentKey écrit à la main : la macro @Entry exige Xcode.
private struct UIScaleKey: EnvironmentKey {
    static let defaultValue: CGFloat = 1
}

extension EnvironmentValues {
    var uiScale: CGFloat {
        get { self[UIScaleKey.self] }
        set { self[UIScaleKey.self] = newValue }
    }
}

enum Theme {
    /// Taille de fenêtre pour laquelle l'interface est à 100 %.
    static let baseSize = CGSize(width: 1360, height: 820)

    /// Les contrôles natifs (curseurs, menus) n'ont que des tailles discrètes.
    static func controlSize(_ z: CGFloat) -> ControlSize {
        z < 1.15 ? .small : (z < 1.6 ? .regular : .large)
    }

    static let bg = Color(hex: 0x0A0A0A)
    static let ink = Color(hex: 0xF2F2F2)
    static let accent = Color(hex: 0xF97316)
    static let line = Color(hex: 0x2E2E2E)
    static let dim = Color(hex: 0x484848)
    static let panel = Color(hex: 0x111111)
    static let muted = Color(hex: 0xF2F2F2).opacity(0.5)

    static func mono(_ size: CGFloat = 11, _ weight: Font.Weight = .regular) -> Font {
        .custom("Menlo", size: size).weight(weight)
    }

    /// Sur-titre interlettré : une espace entre chaque caractère.
    static func spaced(_ s: String) -> String {
        s.uppercased().map(String.init).joined(separator: " ")
    }
}

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: opacity)
    }
}

/// Bouton plat bordé, accent orange quand actif.
struct BangButtonStyle: ButtonStyle {
    @Environment(\.uiScale) private var z
    var active = false
    var prominent = false
    var compact = false

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.mono((compact ? 10 : 11) * z, prominent ? .bold : .regular))
            .padding(.horizontal, (compact ? 6 : 10) * z)
            .padding(.vertical, (compact ? 3 : 6) * z)
            .frame(minHeight: (compact ? 20 : 26) * z)
            .foregroundStyle(prominent ? Theme.bg : (active ? Theme.accent : Theme.ink))
            .background(
                RoundedRectangle(cornerRadius: 3)
                    .fill(prominent ? Theme.accent : (active ? Theme.accent.opacity(0.12) : Color.clear))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 3)
                    .stroke(prominent ? Theme.accent : (active ? Theme.accent : Theme.line), lineWidth: 1)
            )
            .opacity(configuration.isPressed ? 0.6 : 1)
            .contentShape(Rectangle())
    }
}

struct SectionHeader: View {
    @Environment(\.uiScale) private var z
    let title: String
    var body: some View {
        HStack(spacing: 8) {
            Text(Theme.spaced(title))
                .font(Theme.mono(9 * z, .bold))
                .foregroundStyle(Theme.accent)
            Rectangle().fill(Theme.line).frame(height: 1)
        }
        .padding(.top, 6 * z)
    }
}

/// Curseur libellé : « CHAOS ───●── 0.30 »
struct ParamSlider: View {
    @Environment(\.uiScale) private var z
    let label: String
    @Binding var value: Double
    var range: ClosedRange<Double> = 0...1
    var format = "%.2f"

    var body: some View {
        HStack(spacing: 8 * z) {
            Text(label)
                .font(Theme.mono(10 * z))
                .foregroundStyle(Theme.muted)
                .frame(width: 62 * z, alignment: .leading)
            BangSlider(value: $value, range: range)
            Text(String(format: format, value))
                .font(Theme.mono(10 * z))
                .foregroundStyle(Theme.ink)
                .frame(width: 34 * z, alignment: .trailing)
        }
    }
}
