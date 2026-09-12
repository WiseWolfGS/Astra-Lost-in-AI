package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.wwgs.astralostinai.MiningLifecycle.Decision.*;

class MiningLifecycleTest {
    @Test void noMoreAttacksAfterInstantBreak() {
        var state = new MiningLifecycle(200, 0);
        state.markBlockChanged();
        for (int tick = 1; tick < 19; tick++) assertEquals(WAIT, state.step(true, tick * 50_000_000L));
        assertEquals(COMPLETE, state.step(true, 950_000_000L));
        assertEquals(COMPLETE, state.step(false, 1_000_000_000L));
    }
    @Test void restoredBlockAbortsInsteadOfRetrying() {
        var state = new MiningLifecycle(200, 0);
        assertEquals(ADVANCE, state.step(false, 50_000_000L));
        assertEquals(WAIT, state.step(true, 100_000_000L));
        assertEquals(RESTORED, state.step(false, 150_000_000L));
        assertEquals(RESTORED, state.step(true, 200_000_000L));
    }
    @Test void tickBudgetStopsUnchangedTarget() {
        var state = new MiningLifecycle(20, 0);
        for (int tick = 1; tick < 20; tick++) assertEquals(ADVANCE, state.step(false, tick * 50_000_000L));
        assertEquals(TIMED_OUT, state.step(false, 1_000_000_000L));
        assertEquals("tick_timeout", state.timeoutReason());
    }
    @Test void wallBudgetStopsSlowOrPausedExecution() {
        var state = new MiningLifecycle(200, 0);
        assertEquals(TIMED_OUT, state.step(false, 12_500_000_001L));
        assertEquals("wall_timeout", state.timeoutReason());
    }
    @Test void breakNearDeadlineCanSettleWithoutAnotherAttack() {
        var state = new MiningLifecycle(20, 0);
        for (int tick = 1; tick < 20; tick++) state.step(false, tick * 50_000_000L);
        state.markBlockChanged();
        assertEquals(WAIT, state.step(true, 1_000_000_000L));
    }
    @Test void invalidBudgetsAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> new MiningLifecycle(0, 0));
        assertThrows(IllegalArgumentException.class, () -> new MiningLifecycle(201, 0));
    }
}
