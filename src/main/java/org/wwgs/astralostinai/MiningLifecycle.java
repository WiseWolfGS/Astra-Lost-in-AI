package org.wwgs.astralostinai;

/** Pure timing state machine shared by the game controller and deterministic tests. */
public final class MiningLifecycle {
    public enum Decision { ADVANCE, WAIT, COMPLETE, TIMED_OUT, RESTORED }
    private final int timeoutTicks;
    private final long startedAt;
    private int elapsedTicks;
    private int settlingTicks;
    private Decision terminal;
    private String timeoutReason = "";

    public MiningLifecycle(int timeoutTicks, long startedAt) {
        if (timeoutTicks < 20 || timeoutTicks > 200) throw new IllegalArgumentException("invalid_timeout");
        this.timeoutTicks = timeoutTicks;
        this.startedAt = startedAt;
    }

    public void markBlockChanged() { settlingTicks = Math.max(1, settlingTicks); }
    public int elapsedTicks() { return elapsedTicks; }
    public boolean settling() { return settlingTicks > 0; }
    public String timeoutReason() { return timeoutReason; }

    public Decision step(boolean changed, long now) {
        if (terminal != null) return terminal;
        elapsedTicks++;
        if (now - startedAt > (timeoutTicks * 50L + 2500L) * 1_000_000L) {
            timeoutReason = "wall_timeout";
            return terminal = Decision.TIMED_OUT;
        }
        if (changed) {
            if (++settlingTicks >= 20) return terminal = Decision.COMPLETE;
            return Decision.WAIT;
        }
        if (settlingTicks > 0) return terminal = Decision.RESTORED;
        if (elapsedTicks >= timeoutTicks) {
            timeoutReason = "tick_timeout";
            return terminal = Decision.TIMED_OUT;
        }
        return Decision.ADVANCE;
    }
}
