package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CancellationTargetTest {
    @Test void exactCurrentActionMatches() {
        assertTrue(CancellationTarget.matches("a","world","a","world"));
    }
    @Test void oldActionCannotCancelNewAction() {
        assertFalse(CancellationTarget.matches("old","world","new","world"));
    }
    @Test void oldWorldCannotCancelSameActionId() {
        assertFalse(CancellationTarget.matches("a","old","a","new"));
    }
    @Test void idleOrIncompleteRequestDoesNotCancel() {
        assertFalse(CancellationTarget.matches("a","world",null,"world"));
        assertFalse(CancellationTarget.matches(null,"world","a","world"));
        assertFalse(CancellationTarget.matches("a",null,"a","world"));
    }
}
