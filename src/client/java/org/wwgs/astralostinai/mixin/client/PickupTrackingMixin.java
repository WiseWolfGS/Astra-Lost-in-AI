package org.wwgs.astralostinai.mixin.client;

import net.minecraft.client.network.ClientPlayNetworkHandler;
import net.minecraft.network.packet.s2c.play.ItemPickupAnimationS2CPacket;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.wwgs.astralostinai.client.NavigationController;

@Mixin(ClientPlayNetworkHandler.class)
public class PickupTrackingMixin {
    // TAIL is reached on the client thread, after vanilla's forceMainThread handling.
    @Inject(method="onItemPickupAnimation", at=@At("TAIL"))
    private void astra$trackPickup(ItemPickupAnimationS2CPacket packet, CallbackInfo ci) {
        NavigationController.onPickup(packet.getEntityId(),packet.getCollectorEntityId(),packet.getStackAmount());
    }
}
