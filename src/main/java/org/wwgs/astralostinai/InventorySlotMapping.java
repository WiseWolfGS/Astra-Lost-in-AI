package org.wwgs.astralostinai;

public final class InventorySlotMapping {
    private InventorySlotMapping() {}
    public static int handlerSlot(int syncId, int slot) {
        if (syncId == 0) return slot >= 9 && slot <= 44 ? slot : -1;
        if (syncId == -2) return slot >= 0 && slot <= 8 ? slot+36 : slot >= 9 && slot <= 35 ? slot : -1;
        return -1;
    }
}
