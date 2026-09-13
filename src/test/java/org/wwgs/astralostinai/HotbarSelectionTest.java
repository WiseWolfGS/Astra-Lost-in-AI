package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class HotbarSelectionTest {
    @Test void hotbarBoundsIncludeEmptyHand() {
        assertNull(HotbarSelection.rejection(0,"minecraft:air","minecraft:air",false));
        assertNull(HotbarSelection.rejection(8,"minecraft:stick","minecraft:stick",false));
        assertEquals("invalid_hotbar_slot",HotbarSelection.rejection(9,"a","a",false));
        assertEquals("invalid_hotbar_slot",HotbarSelection.rejection(-1,"a","a",false));
    }
    @Test void staleItemCannotChangeSelection() {
        assertEquals("slot_item_changed",HotbarSelection.rejection(1,"minecraft:stick","minecraft:air",false));
        assertEquals("slot_item_changed",HotbarSelection.rejection(1,null,"minecraft:air",false));
    }
    @Test void itemUseOrContainerMustFinishFirst() {
        assertEquals("inventory_busy",HotbarSelection.rejection(1,"a","a",true));
    }
}
