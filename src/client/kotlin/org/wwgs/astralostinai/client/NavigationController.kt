package org.wwgs.astralostinai.client

import net.minecraft.client.MinecraftClient
import net.minecraft.entity.ItemEntity
import net.minecraft.item.Item
import net.minecraft.registry.Registries
import net.minecraft.util.hit.HitResult
import net.minecraft.util.math.BlockPos
import net.minecraft.util.math.Box
import net.minecraft.util.math.Direction
import net.minecraft.util.math.Vec3d
import net.minecraft.world.RaycastContext
import org.wwgs.astralostinai.FlatPathfinder
import org.wwgs.astralostinai.CollectionGoal
import org.wwgs.astralostinai.PickupEvidence
import org.wwgs.astralostinai.WalkingControl
import kotlin.math.*

/** Short, flat, collision-checked walking. No teleports, jump, sprint or block modification. */
class NavigationController(
    private val client: MinecraftClient,
    private val id: String,
    private val timeoutTicks: Int,
    private val blockTarget: BlockPos? = null,
    private val entityId: Int? = null
) {
    companion object {
        private var collector: NavigationController? = null
        @JvmStatic fun onPickup(entityId: Int, playerId: Int, amount: Int) {
            collector?.evidence?.record(entityId, playerId, amount)
        }
    }
    private val player = requireNotNull(client.player)
    private val world = requireNotNull(client.world)
    private val feetY = floor(player.y).toInt()
    private val start = player.pos
    private val startHealth = player.health
    private val startTime = System.nanoTime()
    private val type = if (entityId == null) "approach" else "collect"
    private var itemEntity: ItemEntity? = null
    private var item: Item? = null
    private var evidence: PickupEvidence? = null
    private var targetPoint = Vec3d.ZERO
    private var targetBlockId = ""
    private var path: List<FlatPathfinder.Cell> = emptyList()
    private var waypoint = 0
    private var elapsed = 0
    private var arrivedTicks = 0
    private var lastProgress = start
    private var walkingTicks = 0
    private var safetyFailure: Map<String, Any> = emptyMap()
    private var searchPasses = 0
    private var nearCandidates = 0
    private var blockedEdges = 0
    private var blockedGoals = 0
    private var hiddenGoals = 0
    private var lastSearchFailure: Map<String, Any> = emptyMap()

    private fun searchDetails(): Map<String, Any> = mapOf("passes" to searchPasses,
        "nearCandidates" to nearCandidates, "blockedEdges" to blockedEdges,
        "blockedGoals" to blockedGoals, "hiddenGoals" to hiddenGoals,
        "lastBlocked" to lastSearchFailure)

    private fun point(cell: FlatPathfinder.Cell) = Vec3d(cell.x()+0.5, feetY.toDouble(), cell.z()+0.5)
    private fun horizontalDistance(a: Vec3d, b: Vec3d) = hypot(a.x-b.x, a.z-b.z)
    private fun clearKeys() {
        client.options.forwardKey.isPressed = false
        client.options.backKey.isPressed = false
        client.options.leftKey.isPressed = false
        client.options.rightKey.isPressed = false
        client.options.jumpKey.isPressed = false
        client.options.sprintKey.isPressed = false
        player.isSprinting = false
    }
    private fun countItem(): Int = (0 until player.inventory.size()).sumOf {
        val stack=player.inventory.getStack(it)
        if (stack.item === item) stack.count else 0
    }
    private fun known(pos: BlockPos) = !world.isOutOfHeightLimit(pos) && world.isChunkLoaded(pos)
    private fun hazardous(pos: BlockPos): Boolean {
        val state=world.getBlockState(pos)
        return !state.fluidState.isEmpty || EnvironmentObserver.isPotentialHazard(Registries.BLOCK.getId(state.block).toString())
    }

    private fun traversable(from: Vec3d, to: Vec3d): Boolean {
        safetyFailure = emptyMap()
        fun blocked(reason: String, pos: BlockPos? = null): Boolean {
            safetyFailure = mapOf("reason" to reason, "from" to listOf(from.x,from.y,from.z),
                "to" to listOf(to.x,to.y,to.z)) + (pos?.let { mapOf(
                    "position" to listOf(it.x,it.y,it.z),
                    "block" to if(known(it)) Registries.BLOCK.getId(world.getBlockState(it).block).toString() else "unknown"
                ) } ?: emptyMap())
            return false
        }
        if (abs(from.y-feetY)>0.08 || abs(to.y-feetY)>0.08) return false
        // Inflating by .15 rejected valid positions touching leaves/walls.
        // Use the actual body; control inertia separately at every waypoint.
        val half=WalkingControl.collisionHalfWidth(player.width.toDouble())
        val box=Box(min(from.x,to.x)-half, feetY+0.01, min(from.z,to.z)-half,
            max(from.x,to.x)+half, feetY+player.height.toDouble(), max(from.z,to.z)+half)
        for (x in floor(box.minX).toInt()..floor(box.maxX-0.0001).toInt())
            for (z in floor(box.minZ).toInt()..floor(box.maxZ-0.0001).toInt()) {
                val support=BlockPos(x,feetY-1,z)
                if (!known(support)) return blocked("support_unloaded",support)
                if (hazardous(support)) return blocked("hazardous_support",support)
                if (!world.getBlockState(support).isSideSolidFullSquare(world,support,Direction.UP))
                    return blocked("unsupported_footprint",support)
                for (y in feetY..floor(box.maxY-0.0001).toInt()) {
                    val pos=BlockPos(x,y,z)
                    if (!known(pos)) return blocked("body_unloaded",pos)
                    if (hazardous(pos)) return blocked("hazardous_body",pos)
                    if (!world.isSpaceEmpty(player,box.intersection(Box(pos)))) return blocked("body_collision",pos)
                }
            }
        return if(world.isSpaceEmpty(player,box)) true else blocked("entity_or_world_collision")
    }

    private fun visibleFrom(feet: Vec3d): Boolean {
        val eye=feet.add(0.0,player.eyeY-player.y,0.0)
        val hit=world.raycast(RaycastContext(eye,targetPoint,RaycastContext.ShapeType.OUTLINE,
            RaycastContext.FluidHandling.NONE,player))
        return if (blockTarget != null) hit.type==HitResult.Type.BLOCK && hit.blockPos==blockTarget
            else hit.type==HitResult.Type.MISS
    }

    fun begin(): Map<String, Any>? {
        fun reject(reason:String)=mapOf("id" to id,"status" to "rejected","reason" to reason,
            "details" to mapOf("safetyFailure" to safetyFailure,"position" to listOf(player.x,player.y,player.z),
                "search" to searchDetails()))
        if (timeoutTicks !in 20..200) return reject("invalid_timeout")
        if (!player.isOnGround || abs(player.y-feetY)>0.05 || player.hasVehicle() || player.isUsingItem)
            return reject("requires_flat_ground")
        if (blockTarget != null) {
            if (!known(blockTarget)) return reject("target_unloaded")
            val state=world.getBlockState(blockTarget)
            if (state.isAir) return reject("target_is_air")
            targetBlockId=Registries.BLOCK.getId(state.block).toString()
            targetPoint=Vec3d.ofCenter(blockTarget)
        } else {
            itemEntity=world.getEntityById(requireNotNull(entityId)) as? ItemEntity ?: return reject("item_not_found")
            val target=itemEntity!!
            if (!target.isAlive || !target.isOnGround || !player.canSee(target)) return reject("item_not_settled_or_visible")
            item=target.stack.item
            evidence=PickupEvidence(target.id,player.id,countItem())
            targetPoint=target.pos.add(0.0,target.height/2.0,0.0)
        }
        if (horizontalDistance(start,targetPoint)>4.0 || abs(targetPoint.y-feetY)>2.5)
            return reject("target_outside_local_range")
        if (entityId!=null && abs(targetPoint.y-feetY)>0.5) return reject("item_on_other_level")
        if (!traversable(start,start)) return reject("unsafe_start")
        val root=FlatPathfinder.Cell(player.blockX,player.blockZ)
        if (!traversable(start,point(root))) return reject("unsafe_start")
        fun search(fallback: Boolean): List<FlatPathfinder.Cell> {
            searchPasses++
            return FlatPathfinder.find(root,{ cell ->
                val candidate=point(cell)
                val near=if (blockTarget!=null) horizontalDistance(candidate,targetPoint)<=2.0
                    else CollectionGoal.near(candidate.x-targetPoint.x,candidate.z-targetPoint.z,fallback)
                if (!near) false else {
                    nearCandidates++
                    if (!traversable(candidate,candidate)) {
                        blockedGoals++; lastSearchFailure=safetyFailure; false
                    } else if (!visibleFrom(candidate)) { hiddenGoals++; false } else true
                }
            },{ a,b ->
                val safe=traversable(point(a),point(b))
                if (!safe) { blockedEdges++; lastSearchFailure=safetyFailure }
                safe
            })
        }
        path=search(false)
        // A drop beneath an overhead block may have no safe cell centre within
        // .72. Try nearby stand positions once; never relax body/support checks.
        if (path.isEmpty() && entityId!=null) path=search(true)
        if (path.isEmpty()) return reject("no_flat_path")
        clearKeys()
        if (entityId!=null) collector=this
        return null
    }

    fun tick(): Map<String, Any>? {
        elapsed++
        if (client.player!==player || client.world!==world) return finish("cancelled","world_changed")
        if (player.health<startHealth) return finish("cancelled","health_decreased")
        if (abs(player.y-feetY)>0.08 || !player.isOnGround || player.hasVehicle()) return finish("cancelled","left_flat_ground")
        if (System.nanoTime()-startTime>(timeoutTicks*50L+2500L)*1_000_000L || elapsed>timeoutTicks)
            return finish("timed_out","navigation_timeout")
        if (!traversable(player.pos,player.pos)) return finish("cancelled","path_became_unsafe")
        if (entityId!=null) {
            if (evidence!!.verifiedCount(countItem())>0) return finish("completed","pickup_verified")
            if (evidence!!.packetCount()>0) {
                clearKeys()
                return null // Wait for inventory synchronization; packet alone is insufficient.
            }
            val current=world.getEntityById(entityId)
            if (current!==itemEntity || !itemEntity!!.isAlive) return finish("cancelled","item_disappeared_without_pickup")
            if (itemEntity!!.stack.item!==item) return finish("cancelled","item_changed")
            if (horizontalDistance(itemEntity!!.pos,targetPoint)>0.35 || abs(itemEntity!!.y-targetPoint.y)>0.35)
                return finish("cancelled","item_moved")
        } else if (!known(blockTarget!!) || Registries.BLOCK.getId(world.getBlockState(blockTarget).block).toString()!=targetBlockId) {
            return finish("cancelled","target_changed")
        }
        val speed=hypot(player.velocity.x,player.velocity.z)
        if (waypoint<path.size && WalkingControl.arrived(horizontalDistance(player.pos,point(path[waypoint])),speed)) waypoint++
        if (waypoint>=path.size) {
            clearKeys()
            if (horizontalDistance(player.pos,point(path.last()))>0.6) return finish("cancelled","drifted_from_goal")
            arrivedTicks++
            if (blockTarget!=null) {
                face(targetPoint)
                if (arrivedTicks>=6) {
                    if (!player.canInteractWithBlockAt(blockTarget,0.0) || !visibleFrom(player.pos))
                        return finish("cancelled","target_not_reachable")
                    return finish("completed","approach_verified")
                }
            }
            return null
        }
        val next=point(path[waypoint])
        if (horizontalDistance(player.pos,next)>1.5 || !traversable(player.pos,next))
            return finish("cancelled","path_blocked")
        if (++walkingTicks%20==0) {
            if (horizontalDistance(player.pos,lastProgress)<0.08) return finish("cancelled","stuck")
            lastProgress=player.pos
        }
        clearKeys()
        player.yaw=Math.toDegrees(atan2(-(next.x-player.x),next.z-player.z)).toFloat()
        val friction=world.getBlockState(player.blockPos.down()).block.slipperiness.toDouble()*0.91
        client.options.forwardKey.isPressed=WalkingControl.shouldWalk(horizontalDistance(player.pos,next),speed,friction)
        return null
    }

    private fun face(target:Vec3d) {
        val delta=target.subtract(player.eyePos)
        player.yaw=Math.toDegrees(atan2(-delta.x,delta.z)).toFloat()
        player.pitch=(-Math.toDegrees(atan2(delta.y,hypot(delta.x,delta.z)))).toFloat()
    }

    fun progress(): Map<String, Any> = mapOf("id" to id,"type" to type,"elapsedTicks" to elapsed,
        "waypoint" to waypoint,"pathLength" to path.size,"phase" to if(waypoint>=path.size) "verifying" else "walking")

    fun finish(status:String,reason:String): Map<String, Any> {
        clearKeys()
        if (collector===this) collector=null
        val available=client.player===player && client.world===world
        val after=if(available) countItem() else 0
        return mapOf("id" to id,"status" to status,"reason" to reason,"details" to mapOf(
            "type" to type,"target" to listOf(targetPoint.x,targetPoint.y,targetPoint.z),
            "position" to listOf(player.x,player.y,player.z),"elapsedTicks" to elapsed,
            "path" to path.map { listOf(it.x(),feetY,it.z()) },
            "item" to (item?.let { Registries.ITEM.getId(it).toString() } ?: ""),
            "targetEntityId" to (entityId ?: -1),"pickupPacketCount" to (evidence?.packetCount() ?: 0),
            "inventoryDelta" to if(available) (evidence?.delta(after) ?: 0) else 0,
            "verifiedCollectedCount" to if(available) (evidence?.verifiedCount(after) ?: 0) else 0,
            "inventoryObserved" to available
            ,"safetyFailure" to safetyFailure,"search" to searchDetails()
        ))
    }
}
