package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.client.gui.screen.ingame.CraftingScreen
import net.minecraft.screen.CraftingScreenHandler
import net.minecraft.block.Blocks
import net.minecraft.util.Hand
import net.minecraft.util.hit.BlockHitResult
import net.minecraft.util.hit.HitResult
import net.minecraft.util.math.BlockPos

/** Opens one observed workbench and owns only the resulting crafting handler. */
class WorkbenchCraftingController(private val client: MinecraftClient, private val id: String,
    private val target: BlockPos, private val recipe: String) {
    private val player = requireNotNull(client.player)
    private val world = requireNotNull(client.world)
    private val health = player.health
    private var handler: CraftingScreenHandler? = null
    private var crafter: CraftingController? = null
    private var elapsed = 0
    private var opened = false
    private val started = System.nanoTime()
    fun allowsScreen(): Boolean = opened && client.currentScreen is CraftingScreen &&
        player.currentScreenHandler is CraftingScreenHandler && (handler == null || player.currentScreenHandler === handler)
    fun begin(): Map<String, Any>? {
        if (org.wwgs.astralostinai.WoodenToolRecipe.find(recipe) == null) return finish("rejected","unsupported_recipe")
        if (player.isSneaking || player.isUsingItem || player.currentScreenHandler !== player.playerScreenHandler ||
            !player.currentScreenHandler.cursorStack.isEmpty) return finish("rejected","inventory_busy")
        if (!world.getBlockState(target).isOf(Blocks.CRAFTING_TABLE)) return finish("rejected","workbench_missing")
        val crosshair = client.crosshairTarget as? BlockHitResult
        val hit = player.raycast(player.blockInteractionRange,1f,false) as? BlockHitResult
        if (crosshair?.type != HitResult.Type.BLOCK || crosshair.blockPos != target ||
            hit?.type != HitResult.Type.BLOCK || hit.blockPos != target || !player.canInteractWithBlockAt(target,0.0))
            return finish("rejected","aim_at_workbench")
        opened = true
        client.interactionManager!!.interactBlock(player,Hand.MAIN_HAND,hit)
        return null
    }
    fun tick(): Map<String, Any>? {
        elapsed++
        if (client.world !== world || client.player !== player || !world.getBlockState(target).isOf(Blocks.CRAFTING_TABLE))
            return finish("cancelled","workbench_or_world_changed")
        if (player.health < health) return finish("cancelled","health_decreased")
        if (elapsed > 280 || System.nanoTime()-started > 16_000_000_000L) return finish("timed_out","workbench_timeout")
        if (handler == null) {
            if (allowsScreen()) {
                handler = player.currentScreenHandler as CraftingScreenHandler
                crafter = CraftingController(client,id,recipe,handler!!)
                val rejected = crafter!!.begin()
                if (rejected != null) return finishResult(rejected)
            } else if (elapsed > 60) return finish("timed_out","workbench_open_timeout")
        } else {
            if (!allowsScreen()) return finish("cancelled","workbench_screen_closed")
            val result = crafter!!.tick()
            if (result != null) return finishResult(result)
        }
        return null
    }
    private fun finishResult(result: Map<String, Any>): Map<String, Any> {
        val close = handler != null && client.player === player && player.currentScreenHandler === handler
        if (close) player.closeHandledScreen()
        @Suppress("UNCHECKED_CAST")
        val details = result["details"] as? Map<String, Any> ?: emptyMap()
        return result + ("details" to (details + mapOf("workbench" to listOf(target.x,target.y,target.z),
            "screenCloseSent" to close, "openRequestSent" to opened, "lateOpenPossible" to (opened && handler == null))))
    }
    fun finish(status: String, reason: String): Map<String, Any> = finishResult(
        crafter?.finish(status,reason) ?: mapOf("id" to id,"status" to status,"reason" to reason))
    fun progress(): Map<String, Any> = mapOf("id" to id,"type" to "craft_workbench","elapsedTicks" to elapsed,
        "phase" to if (handler == null) "opening" else "crafting")
}
