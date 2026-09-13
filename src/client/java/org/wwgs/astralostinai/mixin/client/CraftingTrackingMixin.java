package org.wwgs.astralostinai.mixin.client;

import net.minecraft.client.network.ClientPlayNetworkHandler;
import net.minecraft.network.packet.s2c.play.InventoryS2CPacket;
import net.minecraft.network.packet.s2c.play.ScreenHandlerSlotUpdateS2CPacket;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.wwgs.astralostinai.client.CraftingController;

@Mixin(ClientPlayNetworkHandler.class)
public class CraftingTrackingMixin {
    @Inject(method="onInventory", at=@At("TAIL"))
    private void astra$inventory(InventoryS2CPacket packet, CallbackInfo ci) {
        CraftingController.inventory(packet.getSyncId(), packet.getContents());
        org.wwgs.astralostinai.client.HotbarTransferController.inventory(packet.getSyncId(), packet.getContents());
    }
    @Inject(method="onScreenHandlerSlotUpdate", at=@At("TAIL"))
    private void astra$slot(ScreenHandlerSlotUpdateS2CPacket packet, CallbackInfo ci) {
        CraftingController.slot(packet.getSyncId(), packet.getSlot(), packet.getStack());
        org.wwgs.astralostinai.client.HotbarTransferController.slot(packet.getSyncId(), packet.getSlot(), packet.getStack());
    }
}
