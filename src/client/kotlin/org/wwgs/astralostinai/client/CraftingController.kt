package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.item.ItemStack
import net.minecraft.registry.Registries
import net.minecraft.screen.slot.SlotActionType
import net.minecraft.util.Identifier

/** One recipe-book fill and one output transfer, verified against server slot packets. */
class CraftingController(private val client: MinecraftClient, private val id: String, private val recipe: String) {
    companion object {
        private var active: CraftingController? = null
        @JvmStatic fun inventory(syncId: Int, stacks: List<ItemStack>) {
            if (syncId == 0) active?.let { c -> stacks.forEachIndexed { i, s -> c.server[i] = s.copy() }; c.updates++ }
        }
        @JvmStatic fun slot(syncId: Int, slot: Int, stack: ItemStack) {
            if (syncId == 0) active?.let { c -> c.server[slot] = stack.copy(); c.updates++ }
        }
    }
    private val player = requireNotNull(client.player)
    private val world = requireNotNull(client.world)
    private val handler = player.playerScreenHandler
    private val server = mutableMapOf<Int, ItemStack>()
    private var updates = 0
    private var elapsed = 0
    private var taken = false
    private var requested = false
    private var beforeInput = 0
    private var beforeOutput = 0
    private val startHealth = player.health
    private val startNanos = System.nanoTime()
    private val output = "minecraft:$recipe"
    private val input = if (recipe.endsWith("_planks")) "minecraft:" + recipe.removeSuffix("_planks") + "_log" else "#planks"
    private val consumed = if (recipe == "crafting_table") 4 else if (recipe == "stick") 2 else 1
    private val produced = if (recipe == "crafting_table") 1 else 4
    private fun item(stack: ItemStack) = Registries.ITEM.getId(stack.item).toString()
    private fun matches(stack: ItemStack) = if (input == "#planks") item(stack) in WOODS.map { "minecraft:${it}_planks" } else item(stack) == input
    private fun countInput() = server.filterKeys { it in 1..4 || it in 9..44 }.values.sumOf { if (matches(it)) it.count else 0 }
    private fun countOutput() = server.filterKeys { it in 9..44 }.values.sumOf { if (item(it) == output) it.count else 0 }

    fun begin(): Map<String, Any>? {
        if (recipe !in WOODS.map { "${it}_planks" } + listOf("stick", "crafting_table")) return finish("rejected", "unsupported_recipe")
        if (player.currentScreenHandler !== handler || player.isUsingItem || !handler.cursorStack.isEmpty ||
            (0..4).any { !handler.getSlot(it).stack.isEmpty }) return finish("rejected", "crafting_grid_not_empty")
        (0..44).forEach { server[it] = handler.getSlot(it).stack.copy() }
        beforeInput = countInput(); beforeOutput = countOutput()
        if (beforeInput < consumed) return finish("rejected", "insufficient_materials")
        // Reserve one empty inventory slot instead of relying on optimistic stack merging.
        if ((9..44).none { handler.getSlot(it).stack.isEmpty }) return finish("rejected", "inventory_full")
        val entry = world.recipeManager.get(Identifier.of(output)).orElse(null) ?: return finish("rejected", "recipe_unavailable")
        active = this
        requested = true
        client.interactionManager!!.clickRecipe(handler.syncId, entry, false)
        return null
    }
    fun tick(): Map<String, Any>? {
        elapsed++
        if (client.player !== player || client.world !== world || player.currentScreenHandler !== handler)
            return finish("cancelled", "world_or_handler_changed")
        if (player.health < startHealth) return finish("cancelled", "health_decreased")
        if (!handler.cursorStack.isEmpty) return finish("cancelled", "cursor_changed")
        if (elapsed > 200 || System.nanoTime()-startNanos > 12_000_000_000L) return finish("timed_out", "crafting_sync_timeout")
        if (!taken) {
            val result = server[0]
            if (updates > 0 && result != null && item(result) == output && result.count == produced &&
                item(handler.getSlot(0).stack) == output && handler.getSlot(0).stack.count == produced) {
                taken = true
                client.interactionManager!!.clickSlot(handler.syncId, 0, 0, SlotActionType.QUICK_MOVE, player)
            }
        } else if (org.wwgs.astralostinai.CraftEvidence.verified(taken, updates,
            beforeInput-countInput(), countOutput()-beforeOutput, consumed, produced,
            (1..4).all { server[it]?.isEmpty == true })) return finish("completed", "craft_verified")
        return null
    }
    fun progress(): Map<String, Any> = mapOf("id" to id, "type" to "craft", "elapsedTicks" to elapsed,
        "phase" to if (taken) "verifying" else "filling")
    fun finish(status: String, reason: String): Map<String, Any> {
        if (active === this) active = null
        return mapOf("id" to id, "status" to status, "reason" to reason, "details" to mapOf(
            "recipe" to output, "inputConsumed" to (beforeInput-countInput()), "outputGained" to (countOutput()-beforeOutput),
            "verification" to "server_slot_packets", "outputTransferSent" to taken,
            "recipeRequestSent" to requested, "pendingChangesPossible" to (requested && status != "completed"),
            "gridMayContainMaterials" to (1..4).any { server[it]?.isEmpty == false },
            "elapsedTicks" to elapsed, "serverUpdates" to updates))
    }
}
private val WOODS = listOf("oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry")
