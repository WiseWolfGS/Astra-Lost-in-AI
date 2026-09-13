package org.wwgs.astralostinai.client

import net.fabricmc.api.ClientModInitializer
import net.fabricmc.fabric.api.client.event.lifecycle.v1.ClientTickEvents
import net.fabricmc.loader.api.FabricLoader
import net.minecraft.client.MinecraftClient
import net.minecraft.registry.Registries
import net.minecraft.util.math.BlockPos
import com.google.gson.Gson
import com.google.gson.JsonObject
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.file.Files
import java.time.Duration
import java.util.UUID
import org.slf4j.LoggerFactory
import org.wwgs.astralostinai.CancellationTarget

class AstralostinaiClient : ClientModInitializer {
    private val gson = Gson()
    private val logger = LoggerFactory.getLogger("AstraBridge")
    private val http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build()
    private var session = UUID.randomUUID().toString()
    private var lastWorld: net.minecraft.client.world.ClientWorld? = null
    private var busy = false
    private var tick = 0
    private var remaining = 0
    private var activeId: String? = null
    private var result: Map<String, Any>? = null
    private var mining: MiningController? = null
    private var navigation: NavigationController? = null
    private var crafting: CraftingController? = null
    private var lastError = 0L
    private lateinit var config: JsonObject
    override fun onInitializeClient() {
        val path = FabricLoader.getInstance().configDir.resolve("astralostinai-bridge.json")
        if (!Files.exists(path)) {
            Files.writeString(path, """{"enabled":false,"url":"http://127.0.0.1:8765","token":""}""")
        }
        config = gson.fromJson(Files.readString(path), JsonObject::class.java)
        if (!config.get("enabled").asBoolean) {
            logger.info("AI bridge disabled; configure {}", path)
            return
        }
        require(config.get("token").asString.length >= 32) { "Bridge token must have at least 32 characters" }
        ClientTickEvents.START_CLIENT_TICK.register { client ->
            if (crafting != null) {
                if (!isReady(client)) release(client, "cancelled")
                else {
                    val outcome = crafting!!.tick()
                    if (outcome != null) { result = outcome; crafting = null; activeId = null }
                }
            }
            if (mining != null) {
                if (!isReady(client)) release(client, "cancelled")
                else {
                    val outcome = mining!!.tick()
                    if (outcome != null) {
                        result = outcome
                        mining = null
                        activeId = null
                    }
                }
            }
            if (navigation != null) {
                if (!isReady(client)) release(client, "cancelled")
                else {
                    val outcome = navigation!!.tick()
                    if (outcome != null) {
                        result = outcome
                        navigation = null
                        activeId = null
                    }
                }
            }
        }
        ClientTickEvents.END_CLIENT_TICK.register { client -> onTick(client) }
    }

    private fun isReady(client: MinecraftClient) = client.player != null && client.world != null &&
        client.currentScreen == null && !client.isPaused && client.player!!.isAlive &&
        client.interactionManager?.currentGameMode?.name == "SURVIVAL"

    private fun release(client: MinecraftClient, status: String, reason: String = "control_interrupted") {
        if (activeId == null) return
        client.options.forwardKey.isPressed = false
        client.options.backKey.isPressed = false
        client.options.leftKey.isPressed = false
        client.options.rightKey.isPressed = false
        client.options.jumpKey.isPressed = false
        client.options.sprintKey.isPressed = false
        client.player?.isSprinting = false
        val outcome = mining?.finish(status, reason)
            ?: crafting?.finish(status, reason)
            ?: navigation?.finish(status, reason)
            ?: mapOf("id" to activeId!!, "status" to status, "reason" to reason)
        @Suppress("UNCHECKED_CAST")
        val details = (outcome["details"] as? Map<String, Any>) ?: emptyMap()
        result = outcome + ("details" to (details + ("inputsReleased" to true)))
        mining = null
        crafting = null
        navigation = null
        activeId = null
        remaining = 0
    }

    private fun onTick(client: MinecraftClient) {
        if (client.world !== lastWorld) {
            release(client, "cancelled")
            lastWorld = client.world
            session = UUID.randomUUID().toString()
        }
        val ready = isReady(client)
        if (!ready) release(client, "cancelled")
        else if (remaining > 0 && --remaining == 0) release(client, "completed")
        if (++tick % 5 != 0 || busy) return
        val player = client.player
        val world = client.world
        val state = linkedMapOf<String, Any?>(
            "session" to session, "protocol" to 1, "ready" to ready,
            "busy" to (activeId != null), "result" to result
        )
        state["capabilities"] = listOf("move", "look", "stop", "mine", "approach", "collect", "cancel", "select_hotbar", "craft")
        state["activeAction"] = crafting?.progress() ?: mining?.progress() ?: navigation?.progress()
            ?: activeId?.let { mapOf("id" to it, "type" to "move", "remainingTicks" to remaining) }
        if (player != null && world != null) {
            state["player"] = mapOf(
                "position" to listOf(player.x, player.y, player.z),
                "yaw" to player.yaw, "pitch" to player.pitch, "health" to player.health,
                "food" to player.hungerManager.foodLevel,
                "dimension" to world.registryKey.value.toString(),
                "selectedSlot" to player.inventory.selectedSlot,
                "mainHand" to mapOf("item" to Registries.ITEM.getId(player.mainHandStack.item).toString(),
                    "count" to player.mainHandStack.count, "damage" to player.mainHandStack.damage,
                    "maxDamage" to player.mainHandStack.maxDamage),
                "inventory" to (0 until player.inventory.size()).mapNotNull { slot ->
                    val stack = player.inventory.getStack(slot)
                    if (stack.isEmpty) null else mapOf("slot" to slot, "item" to Registries.ITEM.getId(stack.item).toString(), "count" to stack.count)
                }
            )
            state["environment"] = EnvironmentObserver.capture(client)
        }
        // Leave room below the bridge's 64 KiB request limit, even in unusual modded worlds.
        if (gson.toJson(state).toByteArray(Charsets.UTF_8).size > 60_000) {
            state["environment"] = mapOf("schema" to 1, "available" to false, "reason" to "payload_limit")
        }
        val sentResult = result
        val sentPlayer = player
        val sentWorld = world
        val started = System.nanoTime()
        val request = HttpRequest.newBuilder(URI.create(config.get("url").asString + "/v1/tick"))
            .timeout(Duration.ofSeconds(2))
            .header("Authorization", "Bearer " + config.get("token").asString)
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(gson.toJson(state))).build()
        busy = true
        http.sendAsync(request, HttpResponse.BodyHandlers.ofString()).whenComplete { response, error ->
            client.execute {
                busy = false
                try {
                    if (error != null) throw error
                    check(response != null) { "Bridge response was missing" }
                    check(response.statusCode() == 200) {
                        "Bridge HTTP ${response.statusCode()}: ${response.body().take(160)}"
                    }
                    if (result == sentResult) result = null
                    val body = gson.fromJson(response.body(), JsonObject::class.java)
                    val cancellation = body.getAsJsonObject("cancel")
                    if (cancellation != null) {
                        if (client.world === sentWorld && CancellationTarget.matches(
                                cancellation.get("id")?.asString, cancellation.get("session")?.asString,
                                activeId, session)) {
                            release(client, "cancelled", "cancel_requested")
                        }
                        return@execute // Cancellation always takes priority; no command in this response.
                    }
                    val command = body.getAsJsonObject("command") ?: return@execute
                    val id = command.get("id").asString
                    if (System.nanoTime() - started > 2_000_000_000L || client.player !== sentPlayer ||
                        client.world !== sentWorld || client.currentScreen != null || client.isPaused ||
                        !isReady(client) || !ready) {
                        result = mapOf("id" to id, "status" to "cancelled")
                        return@execute
                    }
                    apply(client, command)
                } catch (e: Exception) {
                    release(client, "cancelled")
                    if (System.currentTimeMillis() - lastError > 10_000) {
                        logger.warn("Bridge unavailable or invalid response: {}", e.message)
                        lastError = System.currentTimeMillis()
                    }
                }
            }
        }
    }

    private fun apply(client: MinecraftClient, command: JsonObject) {
        val id = command.get("id").asString
        val action = command.getAsJsonObject("action")
        when (action.get("type").asString) {
            "craft" -> {
                require(activeId == null)
                val controller = CraftingController(client, id, action.get("recipe").asString)
                val rejection = controller.begin()
                if (rejection != null) result = rejection
                else { crafting = controller; activeId = id }
            }
            "select_hotbar" -> {
                require(activeId == null)
                val player = requireNotNull(client.player)
                val slot = action.get("slot").asInt
                val expected = action.get("expectedItem").asString
                val actual = if (slot in 0..8) Registries.ITEM.getId(player.inventory.getStack(slot).item).toString() else ""
                val rejection = org.wwgs.astralostinai.HotbarSelection.rejection(slot, expected, actual,
                    player.isUsingItem || player.currentScreenHandler !== player.playerScreenHandler ||
                        !player.currentScreenHandler.cursorStack.isEmpty)
                if (rejection != null) {
                    result = mapOf("id" to id, "status" to "rejected", "reason" to rejection)
                } else {
                    val previous = player.inventory.selectedSlot
                    val network = requireNotNull(client.networkHandler)
                    network.sendPacket(net.minecraft.network.packet.c2s.play.UpdateSelectedSlotC2SPacket(slot))
                    player.inventory.selectedSlot = slot
                    result = mapOf("id" to id, "status" to "completed", "reason" to "hotbar_selected",
                        "details" to mapOf("previousSlot" to previous, "selectedSlot" to slot,
                            "item" to actual, "packetSent" to true, "verification" to "client_selection",
                            "serverConfirmed" to false))
                }
            }
            "approach", "collect" -> {
                require(activeId == null)
                val collect = action.get("type").asString == "collect"
                val controller = NavigationController(client, id, action.get("timeoutTicks").asInt,
                    blockTarget = if (collect) null else BlockPos(action.get("x").asInt, action.get("y").asInt, action.get("z").asInt),
                    entityId = if (collect) action.get("entityId").asInt else null)
                val rejection = controller.begin()
                if (rejection != null) result = rejection
                else {
                    navigation = controller
                    activeId = id
                }
            }
            "mine" -> {
                require(activeId == null)
                val controller = MiningController(client, id, BlockPos(
                    action.get("x").asInt, action.get("y").asInt, action.get("z").asInt
                ), action.get("timeoutTicks").asInt)
                val rejection = controller.begin()
                if (rejection != null) result = rejection
                else {
                    mining = controller
                    activeId = id
                }
            }
            "stop" -> {
                release(client, "cancelled")
                result = mapOf("id" to id, "status" to "completed")
            }
            "look" -> {
                val yaw = action.get("yaw").asFloat
                val pitch = action.get("pitch").asFloat
                require(yaw.isFinite() && pitch.isFinite())
                client.player!!.yaw = yaw.coerceIn(-180f, 180f)
                client.player!!.pitch = pitch.coerceIn(-90f, 90f)
                result = mapOf("id" to id, "status" to "completed")
            }
            "move" -> {
                require(activeId == null)
                val duration = action.get("ticks").asInt
                require(duration in 1..20)
                val key = when (action.get("direction").asString) {
                    "forward" -> client.options.forwardKey
                    "back" -> client.options.backKey
                    "left" -> client.options.leftKey
                    "right" -> client.options.rightKey
                    "jump" -> client.options.jumpKey
                    else -> error("Invalid direction")
                }
                activeId = id
                remaining = duration
                key.isPressed = true
            }
            else -> result = mapOf("id" to id, "status" to "rejected")
        }
    }
}
