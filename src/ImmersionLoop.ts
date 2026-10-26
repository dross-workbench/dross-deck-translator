/** Single-flight polling: stop invalidates in-flight completions and pending timers. */
export class ImmersionLoop {
    private generation = 0;
    private timer: ReturnType<typeof setTimeout> | null = null;
    active = false;

    start(periodMs: number, work: () => Promise<void>): void {
        this.stop();
        this.active = true;
        const generation = this.generation;
        const tick = async () => {
            if (!this.active || generation !== this.generation) return;
            try { await work(); }
            catch { this.stop(); }
            finally {
                if (this.active && generation === this.generation)
                    this.timer = setTimeout(() => { void tick(); }, Math.max(5000, periodMs));
            }
        };
        // Leave time to close the QAM before the first capture.
        this.timer = setTimeout(() => { void tick(); }, 2000);
    }

    stop(): void {
        this.active = false;
        this.generation++;
        if (this.timer !== null) clearTimeout(this.timer);
        this.timer = null;
    }
}
