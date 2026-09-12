package org.wwgs.astralostinai;

/** Completion requires both an event for the selected entity and a positive item count delta. */
public final class PickupEvidence {
    private final int entityId, collectorId, initialCount;
    private int packetCount;
    public PickupEvidence(int entityId, int collectorId, int initialCount) {
        this.entityId=entityId;
        this.collectorId=collectorId;
        this.initialCount=initialCount;
    }
    public void record(int entityId, int collectorId, int amount) {
        if (this.entityId==entityId && this.collectorId==collectorId && amount>0)
            packetCount=(int)Math.min(1_000_000L,(long)packetCount+amount);
    }
    public int packetCount() { return packetCount; }
    public int delta(int currentCount) { return currentCount-initialCount; }
    public int verifiedCount(int currentCount) { return Math.min(packetCount,Math.max(0,delta(currentCount))); }
}
