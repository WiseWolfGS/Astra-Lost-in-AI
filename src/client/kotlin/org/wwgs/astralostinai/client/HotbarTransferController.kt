package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.item.ItemStack
import net.minecraft.registry.Registries
import net.minecraft.screen.slot.SlotActionType

/** One SWAP request, preserving both stacks and verifying two server slot updates. */
class HotbarTransferController(private val client: MinecraftClient, private val id: String,
    private val source: Int, private val hotbar: Int, private val expectedSource: String,
    private val expectedTarget: String, private val sourceCount: Int, private val targetCount: Int) {
    companion object {
        private var active: HotbarTransferController? = null
        @JvmStatic fun inventory(syncId: Int, stacks: List<ItemStack>) {
            if (syncId == 0) active?.let { c -> stacks.forEachIndexed { i,s -> c.receive(i,s) } }
        }
        @JvmStatic fun slot(syncId: Int, slot: Int, stack: ItemStack) {
            val mapped = org.wwgs.astralostinai.InventorySlotMapping.handlerSlot(syncId,slot)
            if (mapped >= 0) active?.receive(mapped,stack)
        }
    }
    private val player = requireNotNull(client.player)
    private val world = requireNotNull(client.world)
    private val handler = player.playerScreenHandler
    private val destination = hotbar+36
    private var originalSource = ItemStack.EMPTY
    private var originalTarget = ItemStack.EMPTY
    private var serverSource: ItemStack? = null
    private var serverTarget: ItemStack? = null
    private var elapsed = 0
    private var sent = false
    private val started = System.nanoTime()
    private val health = player.health
    private fun item(stack: ItemStack) = Registries.ITEM.getId(stack.item).toString()
    private fun receive(slot: Int, stack: ItemStack) {
        if (slot == source) serverSource = stack.copy()
        if (slot == destination) serverTarget = stack.copy()
    }
    fun begin(): Map<String, Any>? {
        if (source !in 9..35 || hotbar !in 0..8) return finish("rejected","invalid_inventory_slot")
        if (player.currentScreenHandler !== handler || player.isUsingItem || !handler.cursorStack.isEmpty)
            return finish("rejected","inventory_busy")
        originalSource = handler.getSlot(source).stack.copy()
        originalTarget = handler.getSlot(destination).stack.copy()
        if (originalSource.isEmpty) return finish("rejected","source_empty")
        if (item(originalSource) != expectedSource || originalSource.count != sourceCount ||
            item(originalTarget) != expectedTarget || originalTarget.count != targetCount)
            return finish("rejected","inventory_changed")
        if (ItemStack.areEqual(originalSource,originalTarget)) return finish("rejected","identical_stacks")
        active = this; sent = true
        client.interactionManager!!.clickSlot(handler.syncId,source,hotbar,SlotActionType.SWAP,player)
        return null
    }
    fun tick(): Map<String, Any>? {
        elapsed++
        if (client.player !== player || client.world !== world || player.currentScreenHandler !== handler)
            return finish("cancelled","world_or_handler_changed")
        if (player.health < health) return finish("cancelled","health_decreased")
        if (!handler.cursorStack.isEmpty) return finish("cancelled","cursor_changed")
        if (elapsed > 100 || System.nanoTime()-started > 7_000_000_000L) return finish("timed_out","inventory_sync_timeout")
        if (serverSource != null && serverTarget != null && ItemStack.areEqual(serverSource,originalTarget) &&
            ItemStack.areEqual(serverTarget,originalSource)) return finish("completed","hotbar_transfer_verified")
        return null
    }
    fun progress(): Map<String, Any> = mapOf("id" to id,"type" to "move_hotbar","elapsedTicks" to elapsed)
    fun finish(status: String, reason: String): Map<String, Any> {
        if (active === this) active = null
        return mapOf("id" to id,"status" to status,"reason" to reason,"details" to mapOf(
            "sourceSlot" to source,"hotbarSlot" to hotbar,"sourceItem" to item(originalSource),
            "displacedItem" to item(originalTarget),"sourceCount" to originalSource.count,
            "displacedCount" to originalTarget.count,"requestSent" to sent,
            "sourcePacketObserved" to (serverSource != null),"targetPacketObserved" to (serverTarget != null),
            "verification" to "server_slot_packets","pendingChangesPossible" to (sent && status != "completed")))
    }
}
