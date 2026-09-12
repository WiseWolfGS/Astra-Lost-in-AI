package org.wwgs.astralostinai;

/** Ground walking with vanilla friction; only decides keys, never changes velocity. */
public final class WalkingControl {
    private WalkingControl() {}

    public static double collisionHalfWidth(double width) {
        // Match the actual body, allowing vanilla's floating-point contact tolerance.
        return width / 2.0 - 0.00001;
    }

    public static boolean arrived(double distance, double speed) {
        return distance <= 0.12 && speed <= 0.025;
    }

    public static boolean shouldWalk(double distance, double speed, double friction) {
        // velocity is the residual after the previous vanilla movement tick.
        // Release forward before the coast reaches the waypoint. A full input
        // pulse needs additional room; short pulses handle the final approach.
        double coast = speed / Math.max(0.01, 1.0 - friction);
        return distance > Math.max(0.10, coast + 0.12);
    }
}
