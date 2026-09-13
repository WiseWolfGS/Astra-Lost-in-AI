package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.block.Blocks
import net.minecraft.item.Items
import net.minecraft.registry.Registries
import net.minecraft.util.Hand
import net.minecraft.util.hit.BlockHitResult
import net.minecraft.util.hit.HitResult
import net.minecraft.util.math.BlockPos
import net.minecraft.util.math.Box
import net.minecraft.util.math.Direction
import org.wwgs.astralostinai.WorkbenchPlacement

/** A single top-face placement. No repeated use or automatic slot movement. */
class WorkbenchPlacementController(private val client: MinecraftClient, private val id: String,
    private val support: BlockPos, private val expectedSupport: String) {
    private val player = requireNotNull(client.player)
    private val world = requireNotNull(client.world)
    private val destination = support.up()
    private val startHealth = player.health
    private val startTime = System.nanoTime()
    private var elapsed = 0
    private var before = 0
    private var sent = false
    private fun count() = (0 until player.inventory.size()).sumOf {
        val stack = player.inventory.getStack(it)
        if (stack.isOf(Items.CRAFTING_TABLE)) stack.count else 0
    }
    fun begin(): Map<String, Any>? {
        if (player.isUsingItem || player.currentScreenHandler !== player.playerScreenHandler ||
            !player.currentScreenHandler.cursorStack.isEmpty) return finish("rejected", "inventory_busy")
        if (!player.mainHandStack.isOf(Items.CRAFTING_TABLE)) return finish("rejected", "workbench_not_in_hand")
        if (world.isOutOfHeightLimit(destination) || !world.isChunkLoaded(support) || !world.isChunkLoaded(destination))
            return finish("rejected", "target_unloaded")
        val state = world.getBlockState(support)
        val actual = Registries.BLOCK.getId(state.block).toString()
        if (actual != expectedSupport) return finish("rejected", "support_changed")
        // Limit the first placement skill to ordinary non-interactive ground.
        if (actual !in setOf("minecraft:dirt", "minecraft:grass_block", "minecraft:stone", "minecraft:cobblestone") ||
            !state.isSideSolidFullSquare(world, support, Direction.UP)) return finish("rejected", "unsupported_ground")
        if (!world.getBlockState(destination).isAir || !world.getFluidState(destination).isEmpty)
            return finish("rejected", "destination_occupied")
        val box = Box(destination)
        if (box.intersects(player.boundingBox) || world.getOtherEntities(player, box).isNotEmpty())
            return finish("rejected", "destination_entity_collision")
        val crosshair = client.crosshairTarget as? BlockHitResult
        val hit = player.raycast(player.blockInteractionRange, 1f, false) as? BlockHitResult
        if (crosshair?.type != HitResult.Type.BLOCK || crosshair.blockPos != support || crosshair.side != Direction.UP ||
            hit?.type != HitResult.Type.BLOCK || hit.blockPos != support || hit.side != Direction.UP)
            return finish("rejected", "aim_at_support_top")
        if (!player.canInteractWithBlockAt(support, 0.0)) return finish("rejected", "out_of_reach")
        before = count()
        sent = true
        val response = client.interactionManager!!.interactBlock(player, Hand.MAIN_HAND, hit)
        if (!response.isAccepted) return finish("rejected", "placement_not_accepted")
        return null
    }
    fun tick(): Map<String, Any>? {
        elapsed++
        if (client.player !== player || client.world !== world) return finish("cancelled", "world_changed")
        if (player.health < startHealth) return finish("cancelled", "health_decreased")
        if (elapsed > 100 || System.nanoTime()-startTime > 7_000_000_000L) return finish("timed_out", "placement_timeout")
        if (WorkbenchPlacement.verified(sent, elapsed, before-count(), world.getBlockState(destination).isOf(Blocks.CRAFTING_TABLE)))
            return finish("completed", "workbench_placed")
        return null
    }
    fun progress(): Map<String, Any> = mapOf("id" to id, "type" to "place_workbench", "elapsedTicks" to elapsed)
    fun finish(status: String, reason: String): Map<String, Any> = mapOf("id" to id, "status" to status,
        "reason" to reason, "details" to mapOf("destination" to listOf(destination.x,destination.y,destination.z),
            "interactionSent" to sent, "pendingChangesPossible" to (sent && status != "completed"),
            "inventoryConsumed" to if (sent && client.player === player) before-count() else 0,
            "blockObserved" to (client.world === world && world.getBlockState(destination).isOf(Blocks.CRAFTING_TABLE)),
            "verification" to "client_observation", "serverConfirmed" to false, "elapsedTicks" to elapsed))
}
