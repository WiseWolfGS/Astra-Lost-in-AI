package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.client.world.ClientWorld
import net.minecraft.entity.ItemEntity
import net.minecraft.registry.Registries
import net.minecraft.util.hit.BlockHitResult
import net.minecraft.util.hit.EntityHitResult
import net.minecraft.util.hit.HitResult
import net.minecraft.util.math.BlockPos

/** Bounded local game-state sensor. Blocks are not restricted to the camera's field of view. */
object EnvironmentObserver {
    private val potentialHazards = setOf(
        "minecraft:lava", "minecraft:fire", "minecraft:soul_fire", "minecraft:cactus",
        "minecraft:magma_block", "minecraft:sweet_berry_bush", "minecraft:powder_snow",
        "minecraft:wither_rose", "minecraft:campfire", "minecraft:soul_campfire",
        "minecraft:pointed_dripstone"
    )
    fun isPotentialHazard(id: String) = id in potentialHazards

    private fun block(world: ClientWorld, pos: BlockPos): Map<String, Any> {
        val state = world.getBlockState(pos)
        val id = Registries.BLOCK.getId(state.block).toString()
        val fluid = state.fluidState
        return mapOf(
            "id" to id, "air" to state.isAir,
            "collision" to !state.getCollisionShape(world, pos).isEmpty,
            "fluid" to if (fluid.isEmpty) "empty" else Registries.FLUID.getId(fluid.fluid).toString(),
            "potentialHazard" to (id in potentialHazards)
        )
    }

    fun capture(client: MinecraftClient): Map<String, Any> {
        val player = requireNotNull(client.player)
        val world = requireNotNull(client.world)
        val origin = player.blockPos.add(-4, -2, -4)
        val palette = mutableListOf<Map<String, Any>>()
        val indices = mutableMapOf<Map<String, Any>, Int>()
        val cells = ArrayList<Int>(486)
        var unknown = 0
        var omitted = 0
        // x changes fastest; then z; then y. Never request/generate missing chunks.
        for (y in 0 until 6) for (z in 0 until 9) for (x in 0 until 9) {
            val pos = origin.add(x, y, z)
            if (world.isOutOfHeightLimit(pos) || !world.isChunkLoaded(pos)) {
                cells.add(-1)
                unknown++
                continue
            }
            val entry = block(world, pos)
            val existing = indices[entry]
            if (existing != null) cells.add(existing)
            else if (palette.size < 128) {
                val index = palette.size
                palette.add(entry)
                indices[entry] = index
                cells.add(index)
            } else {
                cells.add(-2)
                omitted++
            }
        }
        val candidates = world.getOtherEntities(player, player.boundingBox.expand(8.0))
            .filter { it.isAlive && !it.isInvisible && player.squaredDistanceTo(it) <= 64.0 }
            .sortedBy { player.squaredDistanceTo(it) }
        // Limit raycasts even in dense entity farms. Occlusion test is not a camera FOV test.
        val entities = candidates.take(64).filter { player.canSee(it) }.take(16).map {
            val data = mutableMapOf<String, Any>(
                "id" to it.id, "type" to Registries.ENTITY_TYPE.getId(it.type).toString(),
                "position" to listOf(it.x, it.y, it.z), "distance" to player.distanceTo(it),
                "lineOfSight" to true
            )
            if (it is ItemEntity) {
                data["item"] = Registries.ITEM.getId(it.stack.item).toString()
                data["count"] = it.stack.count
                data["onGround"] = it.isOnGround
            }
            data
        }
        val hit = client.crosshairTarget
        val target: Map<String, Any> = when {
            hit is BlockHitResult && hit.type == HitResult.Type.BLOCK -> mapOf(
                "type" to "block", "position" to listOf(hit.blockPos.x, hit.blockPos.y, hit.blockPos.z),
                "face" to hit.side.name.lowercase(), "block" to block(world, hit.blockPos),
                "canHarvest" to player.canHarvest(world.getBlockState(hit.blockPos)),
                "hardness" to world.getBlockState(hit.blockPos).getHardness(world, hit.blockPos),
                "inReach" to player.canInteractWithBlockAt(hit.blockPos, 0.0),
                "distance" to player.eyePos.distanceTo(hit.pos)
            )
            hit is EntityHitResult -> mapOf(
                "type" to "entity", "id" to hit.entity.id,
                "entityType" to Registries.ENTITY_TYPE.getId(hit.entity.type).toString(),
                "distance" to player.eyePos.distanceTo(hit.pos)
            )
            else -> mapOf("type" to "miss")
        }
        return mapOf(
            "schema" to 1, "available" to true, "source" to "local_loaded_world",
            "sampledAt" to System.currentTimeMillis(), "worldTime" to world.time,
            "terrain" to mapOf(
                "origin" to listOf(origin.x, origin.y, origin.z), "size" to listOf(9, 6, 9),
                "order" to "y,z,x", "palette" to palette, "cells" to cells,
                "unknownCells" to unknown, "omittedCells" to omitted
            ),
            "entities" to entities, "entityRadius" to 8,
            "entitiesTruncated" to (candidates.size > 64 || entities.size == 16),
            "target" to target
        )
    }
}
