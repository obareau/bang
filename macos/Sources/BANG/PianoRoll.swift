import BangCore
import SwiftUI

/// Piano-roll d'un cycle (rendu avec la seed courante) + tête de lecture.
struct PianoRoll: View {
    @Environment(\.uiScale) private var z
    @EnvironmentObject var model: AppModel
    @EnvironmentObject var play: PlayState

    struct Note { var start: Int; var end: Int; var pitch: Int; var vel: Int; var voice: Int }

    private func notes(_ events: [MIDIEvent]) -> [Note] {
        var open: [Int: [(Int, Int, Int)]] = [:]  // clé canal/note → (tick, vel, voix)
        var out: [Note] = []
        for e in events {
            let key = e.channel << 8 | e.data1
            switch e.kind {
            case .noteOn: open[key, default: []].append((e.tick, e.data2, e.voice))
            case .noteOff:
                if var stack = open[key], !stack.isEmpty {
                    let (t, v, vi) = stack.removeFirst()
                    open[key] = stack
                    out.append(Note(start: t, end: e.tick, pitch: e.data1, vel: v, voice: vi))
                }
            case .cc: break
            }
        }
        return out
    }

    var body: some View {
        let notes = notes(model.preview)
        let totalTicks = max(1, model.session.params.steps * Renderer.ticksPerStep)
        let lo = (notes.map(\.pitch).min() ?? 36) - 1
        let hi = (notes.map(\.pitch).max() ?? 60) + 1
        let selected = model.selectedVoice

        ZStack(alignment: .topLeading) {
            Canvas { ctx, size in
                let rows = max(1, hi - lo + 1)
                let rowH = size.height / CGFloat(rows)
                let xPerTick = size.width / CGFloat(totalTicks)
                // Grille : une ligne par temps (4 steps), plus marquée par mesure
                let beats = totalTicks / Renderer.ppq
                for b in 0...max(0, beats) {
                    let x = CGFloat(b * Renderer.ppq) * xPerTick
                    ctx.fill(Path(CGRect(x: x, y: 0, width: 1, height: size.height)),
                             with: .color(b % 4 == 0 ? Theme.dim : Theme.line))
                }
                for n in notes {
                    let x = CGFloat(n.start) * xPerTick
                    let w = max(2, CGFloat(n.end - n.start) * xPerTick - 1)
                    let y = size.height - CGFloat(n.pitch - lo + 1) * rowH
                    let r = CGRect(x: x, y: y, width: w, height: max(2, rowH - 1))
                    let color = n.voice == selected ? Theme.accent : Theme.ink.opacity(0.25 + 0.7 * Double(n.vel) / 127)
                    ctx.fill(Path(r), with: .color(color))
                }
                if model.isPlaying {
                    let x = (CGFloat(play.step) + 0.5) * CGFloat(Renderer.ticksPerStep) * xPerTick
                    ctx.fill(Path(CGRect(x: x, y: 0, width: 2, height: size.height)), with: .color(Theme.accent))
                }
            }
            .padding(.top, 24 * z)
            .padding(.bottom, 8 * z)

            Text("P I A N O - R O L L   ·   \(notes.count) notes   ·   \(lo + 1)–\(hi - 1)")
                .font(Theme.mono(9 * z))
                .foregroundStyle(Theme.dim)
                .padding(6 * z)
        }
        .padding(.horizontal, 14 * z)
        .background(Theme.bg)
    }
}
