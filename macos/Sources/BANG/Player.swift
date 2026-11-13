import BangCore
import Foundation

/// Horloge temps réel — l'équivalent natif de live_clock.LiveClock.
///
/// Un thread haute priorité rend un cycle complet du pattern à la fois
/// (Renderer, aléa frais à chaque cycle : les `?`, le Markov et les drops
/// varient d'un tour à l'autre comme en live), puis envoie chaque évènement
/// à son heure exacte. Toute modification de la session (édition de grille,
/// mute, densité, BPM…) est prise en compte immédiatement : le reste du
/// cycle est re-rendu depuis la position courante.
final class Player: @unchecked Sendable {
    typealias Output = @Sendable (UInt8, UInt8, UInt8) -> Void

    private let lock = NSLock()
    private var pending: RenderInput?
    private var running = false
    private var generation = 0
    private var thread: Thread?

    // État lu par l'UI
    private var step = 0
    private var steps = 1
    private var hits: [Int: Double] = [:]

    let output: Output

    init(output: @escaping Output) { self.output = output }

    var isRunning: Bool { lock.lock(); defer { lock.unlock() }; return running }

    func start(_ input: RenderInput) {
        lock.lock()
        guard !running else { lock.unlock(); return }
        running = true
        generation += 1
        let gen = generation
        pending = input
        lock.unlock()
        let t = Thread { [weak self] in self?.loop(gen) }
        t.qualityOfService = .userInteractive
        t.name = "BANG! clock"
        thread = t
        t.start()
    }

    func stop() {
        lock.lock(); running = false; lock.unlock()
        thread = nil
    }

    func update(_ input: RenderInput) {
        lock.lock(); pending = input; lock.unlock()
    }

    /// (step courant, nb de steps, dernier hit par voix en secondes uptime)
    func status() -> (Int, Int, [Int: Double]) {
        lock.lock(); defer { lock.unlock() }
        return (step, steps, hits)
    }

    static func now() -> Double { Double(DispatchTime.now().uptimeNanoseconds) / 1e9 }

    private func takePending() -> RenderInput? {
        lock.lock(); defer { lock.unlock() }
        let p = pending
        pending = nil
        return p
    }

    private func loop(_ gen: Int) {
        guard var input = takePending() else { return }
        let tps = Renderer.ticksPerStep
        func spt(_ bpm: Int) -> Double { 60.0 / (Double(max(1, bpm)) * Double(Renderer.ppq)) }

        var secPerTick = spt(input.params.bpm)
        var cycleTicks = max(1, input.params.steps) * tps
        var cycleStart = Player.now() + 0.03
        var events = Renderer.render(input, numSteps: input.params.steps, rng: Dice(), gate: 0.75)
        var idx = 0
        var sounding: [Int: Int] = [:]  // (canal<<8 | note) → nb de note-on actifs

        func dispatch(_ e: MIDIEvent) {
            let key = e.channel << 8 | e.data1
            switch e.kind {
            case .noteOn:
                sounding[key, default: 0] += 1
                if e.voice >= 0 {
                    lock.lock(); hits[e.voice] = Player.now(); lock.unlock()
                }
            case .noteOff:
                guard let n = sounding[key] else { return }  // jamais joué : on ignore
                if n <= 1 { sounding[key] = nil } else { sounding[key] = n - 1 }
            case .cc:
                break
            }
            output(e.statusByte, UInt8(e.data1), UInt8(e.data2))
        }

        while true {
            lock.lock(); let alive = running && generation == gen; lock.unlock()
            if !alive { break }

            var now = Player.now()

            // Modification de la session → re-rendu du reste du cycle.
            if let fresh = takePending() {
                let curTick = max(0, Int((now - cycleStart) / secPerTick))
                let newSPT = spt(fresh.params.bpm)
                cycleStart = now - Double(curTick) * newSPT
                secPerTick = newSPT
                cycleTicks = max(1, fresh.params.steps) * tps
                input = fresh
                let releases = events[idx...].filter { $0.kind == .noteOff }
                let ahead = Renderer.render(input, numSteps: input.params.steps, rng: Dice(), gate: 0.75)
                    .filter { $0.tick >= curTick }
                events = (releases + ahead).sorted { ($0.tick, $0.kind == .noteOn ? 1 : 0) < ($1.tick, $1.kind == .noteOn ? 1 : 0) }
                idx = 0
            }

            // Machine endormie / gros retard : on se recale au lieu de rattraper.
            if now - cycleStart > Double(cycleTicks) * secPerTick * 2 {
                cycleStart = now
                idx = events.count
            }

            let tickNow = (now - cycleStart) / secPerTick
            while idx < events.count && Double(events[idx].tick) <= tickNow {
                dispatch(events[idx])
                idx += 1
            }

            lock.lock()
            steps = cycleTicks / tps
            step = min(steps - 1, max(0, Int(tickNow) / tps))
            lock.unlock()

            if tickNow >= Double(cycleTicks) {
                // Fin de cycle : ce qui déborde (ratchets, jitter, note-off) passe au suivant.
                let carry = events[idx...].map { e -> MIDIEvent in
                    var c = e; c.tick -= cycleTicks; return c
                }
                cycleStart += Double(cycleTicks) * secPerTick
                let next = Renderer.render(input, numSteps: input.params.steps, rng: Dice(), gate: 0.75)
                events = (carry + next).sorted { ($0.tick, $0.kind == .noteOn ? 1 : 0) < ($1.tick, $1.kind == .noteOn ? 1 : 0) }
                idx = 0
                continue
            }

            let nextTick = idx < events.count ? min(Double(events[idx].tick), Double(cycleTicks)) : Double(cycleTicks)
            now = Player.now()
            let wait = cycleStart + nextTick * secPerTick - now
            if wait > 0 { Thread.sleep(forTimeInterval: min(wait, 0.004)) }
        }

        // Arrêt : on relâche tout ce qui sonne + All Notes Off.
        for key in sounding.keys {
            output(0x80 | UInt8((key >> 8) & 0x0F), UInt8(key & 0x7F), 0)
        }
        for ch in 0..<16 { output(0xB0 | UInt8(ch), 123, 0) }
        lock.lock(); step = 0; hits = [:]; lock.unlock()
    }
}
