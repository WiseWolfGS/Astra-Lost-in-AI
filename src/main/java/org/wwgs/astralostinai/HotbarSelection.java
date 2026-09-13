package org.wwgs.astralostinai;

/** Guard the observed target before changing the selected hotbar slot. */
public final class HotbarSelection {
    private HotbarSelection() {}
    public static String rejection(int slot, String expectedItem, String actualItem, boolean busy) {
        if (slot < 0 || slot > 8) return "invalid_hotbar_slot";
        if (busy) return "inventory_busy";
        if (expectedItem == null || !expectedItem.equals(actualItem)) return "slot_item_changed";
        return null;
    }
}
