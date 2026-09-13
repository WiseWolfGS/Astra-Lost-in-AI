package org.wwgs.astralostinai;

public final class CraftEvidence {
    private CraftEvidence() {}
    public static boolean verified(boolean transferSent, int packets, int consumed, int gained,
                                   int expectedConsumed, int expectedGained, boolean gridEmpty) {
        return transferSent && packets > 0 && consumed == expectedConsumed && gained == expectedGained && gridEmpty;
    }
}
