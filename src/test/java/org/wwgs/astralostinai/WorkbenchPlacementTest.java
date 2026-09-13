package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WorkbenchPlacementTest {
    @Test
    void verifiedRequiresSentObservedSufficientTicksAndSingleItemConsumed() {
        assertTrue(WorkbenchPlacement.verified(true, 5, 1, true));
        assertTrue(WorkbenchPlacement.verified(true, 10, 1, true));

        assertFalse(WorkbenchPlacement.verified(false, 5, 1, true), "Must be sent");
        assertFalse(WorkbenchPlacement.verified(true, 4, 1, true), "Ticks must be at least 5 for sync");
        assertFalse(WorkbenchPlacement.verified(true, 5, 0, true), "Must consume exactly 1 item");
        assertFalse(WorkbenchPlacement.verified(true, 5, 2, true), "Must consume exactly 1 item");
        assertFalse(WorkbenchPlacement.verified(true, 5, 1, false), "Block must be observed");
    }
}
