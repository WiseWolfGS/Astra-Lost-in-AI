package org.wwgs.astralostinai;

/** Candidate stand positions only. Actual collection still requires pickup evidence. */
public final class CollectionGoal {
    private CollectionGoal() {}
    public static boolean near(double dx, double dz, boolean fallback) {
        return Math.hypot(dx, dz) <= (fallback ? 1.0 : 0.72);
    }
}
