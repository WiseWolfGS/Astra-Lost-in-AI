package org.wwgs.astralostinai.mixin.client;

import net.minecraft.client.MinecraftClient;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;
import org.wwgs.astralostinai.client.MiningController;

/** Prevent vanilla input from cancelling or double-advancing an AI mining action. */
@Mixin(MinecraftClient.class)
public class MiningInputMixin {
    @Inject(method = "handleBlockBreaking", at = @At("HEAD"), cancellable = true)
    private void astra$ownBreaking(boolean breaking, CallbackInfo ci) {
        if (MiningController.isControllingAttack()) ci.cancel();
    }

    @Inject(method = "doAttack", at = @At("HEAD"), cancellable = true)
    private void astra$ownAttack(CallbackInfoReturnable<Boolean> cir) {
        if (MiningController.isControllingAttack()) cir.setReturnValue(false);
    }
}
