package org.wwgs.astralostinai;

/** Evidence verification for single workbench placement. */
public final class WorkbenchPlacement {
    private WorkbenchPlacement() {}

    public static boolean verified(boolean interactionSent, int elapsedTicks, int inventoryConsumed, boolean blockObserved) {
        return interactionSent && elapsedTicks >= 5 && inventoryConsumed == 1 && blockObserved;
    }
}
