package org.wwgs.astralostinai.client

import net.minecraft.block.BlockState
import net.minecraft.client.MinecraftClient
import net.minecraft.item.ItemStack
import net.minecraft.registry.Registries
import net.minecraft.util.Hand
import net.minecraft.util.hit.BlockHitResult
import net.minecraft.util.hit.HitResult
import net.minecraft.util.math.BlockPos
import org.wwgs.astralostinai.MiningLifecycle

/** Advances vanilla's interaction manager once per tick, independently of window focus. */
class MiningController(
    private val client: MinecraftClient,
    private val id: String,
    private val target: BlockPos,
    private val timeoutTicks: Int
) {
    companion object {
        private var controllingAttack = false
        @JvmStatic fun isControllingAttack() = controllingAttack
    }
    private val world = requireNotNull(client.world)
    private val player = requireNotNull(client.player)
    private lateinit var original: BlockState
    private lateinit var tool: ItemStack
    private var slot = 0
    private var inventoryBefore: Map<String, Int> = emptyMap()
    private val startPosition = player.pos
    private val startHealth = player.health
    private val lifecycle = MiningLifecycle(timeoutTicks, System.nanoTime())

    private fun inventory(): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        for (slot in 0 until player.inventory.size()) {
            val stack = player.inventory.getStack(slot)
            if (!stack.isEmpty) {
                val item = Registries.ITEM.getId(stack.item).toString()
                counts[item] = (counts[item] ?: 0) + stack.count
            }
        }
        return counts
    }

    private fun aimedAtTarget(): BlockHitResult? {
        // Reject an entity in the crosshair even if the block raycast hits behind it.
        val crosshair = client.crosshairTarget as? BlockHitResult ?: return null
        if (crosshair.type != HitResult.Type.BLOCK || crosshair.blockPos != target) return null
        val ray = player.raycast(player.blockInteractionRange, 1f, false) as? BlockHitResult ?: return null
        return ray.takeIf { it.type == HitResult.Type.BLOCK && it.blockPos == target }
    }

    fun begin(): Map<String, Any>? {
        fun reject(reason: String) = mapOf("id" to id, "status" to "rejected", "reason" to reason)
        if (timeoutTicks !in 20..200) return reject("invalid_timeout")
        if (world.isOutOfHeightLimit(target) || !world.isChunkLoaded(target)) return reject("target_unloaded")
        if (!player.canInteractWithBlockAt(target, 0.0)) return reject("out_of_reach")
        val hit = aimedAtTarget() ?: return reject("target_not_in_crosshair")
        original = world.getBlockState(target)
        if (original.isAir) return reject("target_is_air")
        if (original.getHardness(world, target) < 0) return reject("unbreakable")
        if (!player.canHarvest(original)) return reject("unsuitable_tool")
        if (player.isUsingItem) return reject("using_item")
        tool = player.mainHandStack.copy()
        slot = player.inventory.selectedSlot
        inventoryBefore = inventory()
        client.interactionManager!!.cancelBlockBreaking()
        controllingAttack = true
        // Exactly one initial vanilla attack, followed by one progress update per client tick.
        if (!client.interactionManager!!.attackBlock(target, hit.side)) {
            return finish("rejected", "attack_rejected")
        }
        player.swingHand(Hand.MAIN_HAND)
        // Instant-break blocks must not leave a held attack aimed at the block behind them.
        if (world.getBlockState(target).block != original.block) {
            lifecycle.markBlockChanged()
            client.options.attackKey.isPressed = false
            client.interactionManager!!.cancelBlockBreaking()
        }
        return null
    }

    /** Runs at START_CLIENT_TICK, before vanilla handles attack input. */
    fun tick(): Map<String, Any>? {
        if (client.player !== player || client.world !== world) return finish("cancelled", "world_changed")
        if (!world.isChunkLoaded(target)) return finish("cancelled", "target_unloaded")
        if (player.health < startHealth) return finish("cancelled", "health_decreased")
        if (player.squaredDistanceTo(startPosition) > 0.25) return finish("cancelled", "player_moved")
        val changed = world.getBlockState(target).block != original.block
        when (lifecycle.step(changed, System.nanoTime())) {
            MiningLifecycle.Decision.COMPLETE -> return finish("completed", "block_change_observed")
            MiningLifecycle.Decision.TIMED_OUT -> return finish("timed_out", lifecycle.timeoutReason())
            MiningLifecycle.Decision.RESTORED -> return finish("rejected", "block_restored")
            MiningLifecycle.Decision.WAIT -> {
                client.options.attackKey.isPressed = false
                client.interactionManager?.cancelBlockBreaking()
                return null
            }
            MiningLifecycle.Decision.ADVANCE -> {}
        }
        if (player.inventory.selectedSlot != slot ||
            !ItemStack.areItemsAndComponentsEqual(player.mainHandStack, tool))
            return finish("cancelled", "tool_changed")
        if (player.isUsingItem) return finish("cancelled", "using_item")
        if (!player.canInteractWithBlockAt(target, 0.0)) return finish("cancelled", "out_of_reach")
        val hit = aimedAtTarget() ?: return finish("cancelled", "target_not_in_crosshair")
        if (!client.interactionManager!!.updateBlockBreakingProgress(target, hit.side))
            return finish("rejected", "progress_rejected")
        player.swingHand(Hand.MAIN_HAND)
        if (world.getBlockState(target).block != original.block) {
            lifecycle.markBlockChanged()
            client.interactionManager?.cancelBlockBreaking()
        }
        return null
    }

    fun progress(): Map<String, Any> = mapOf(
        "id" to id, "type" to "mine", "phase" to if (lifecycle.settling()) "settling" else "breaking",
        "elapsedTicks" to lifecycle.elapsedTicks(), "timeoutTicks" to timeoutTicks,
        "target" to listOf(target.x, target.y, target.z)
    )

    fun finish(status: String, reason: String): Map<String, Any> {
        controllingAttack = false
        client.options.attackKey.isPressed = false
        client.interactionManager?.cancelBlockBreaking()
        val available = client.player === player && client.world === world && world.isChunkLoaded(target)
        val after = if (available) inventory() else emptyMap()
        val delta = if (available) (inventoryBefore.keys + after.keys).associateWith {
            (after[it] ?: 0) - (inventoryBefore[it] ?: 0)
        }.filterValues { it != 0 } else emptyMap()
        return mapOf(
            "id" to id, "status" to status, "reason" to reason,
            "details" to mapOf(
                "target" to listOf(target.x, target.y, target.z),
                "originalBlock" to Registries.BLOCK.getId(original.block).toString(),
                "observedBlock" to if (available) Registries.BLOCK.getId(world.getBlockState(target).block).toString() else "unknown",
                "blockChanged" to (available && world.getBlockState(target).block != original.block),
                "inventoryDelta" to delta, "inventoryObserved" to available,
                "elapsedTicks" to lifecycle.elapsedTicks(), "verification" to "client_observation",
                "collectionGuaranteed" to false
            )
        )
    }
}
