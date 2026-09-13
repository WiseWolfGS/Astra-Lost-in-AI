package org.wwgs.astralostinai;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class InventorySlotMappingTest {
    @Test void hotbarAndMainInventoryUseDifferentPacketLayouts() {
        assertEquals(36,InventorySlotMapping.handlerSlot(-2,0));
        assertEquals(44,InventorySlotMapping.handlerSlot(-2,8));
        assertEquals(9,InventorySlotMapping.handlerSlot(-2,9));
        assertEquals(35,InventorySlotMapping.handlerSlot(-2,35));
        assertEquals(36,InventorySlotMapping.handlerSlot(0,36));
    }
    @Test void armorCursorAndOtherContainersCannotConfirmSwap() {
        assertEquals(-1,InventorySlotMapping.handlerSlot(-2,36));
        assertEquals(-1,InventorySlotMapping.handlerSlot(-2,40));
        assertEquals(-1,InventorySlotMapping.handlerSlot(0,45));
        assertEquals(-1,InventorySlotMapping.handlerSlot(3,36));
        assertEquals(-1,InventorySlotMapping.handlerSlot(-1,-1));
    }
}
