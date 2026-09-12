package org.wwgs.astralostinai;

import java.util.Objects;

/** Cancellation is scoped to an exact action in the current world session. */
public final class CancellationTarget {
    private CancellationTarget() {}
    public static boolean matches(String requestedId, String requestedSession,
                                  String activeId, String currentSession) {
        return activeId != null && requestedId != null && requestedSession != null
                && Objects.equals(requestedId, activeId)
                && Objects.equals(requestedSession, currentSession);
    }
}
