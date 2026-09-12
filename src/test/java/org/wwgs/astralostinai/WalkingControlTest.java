package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class WalkingControlTest {
    @Test void recordedLeafContactDoesNotBecomeAnArtificialCollision() {
        double z = -13.300000011920929;
        double width = (double)0.6f;
        assertTrue(z + width/2 + .15 > -13); // old expanded body overlaps leaves
        assertTrue(z + WalkingControl.collisionHalfWidth(width) < -13);
    }

    @Test void realWallOverlapStillCollides() {
        assertTrue(-13.2 + WalkingControl.collisionHalfWidth((double)0.6f) > -13);
    }

    @Test void nearWaypointDoesNotPermitTurningAtWalkingSpeed() {
        assertFalse(WalkingControl.arrived(.10, .12));
        assertTrue(WalkingControl.arrived(.10, .02));
        assertFalse(WalkingControl.shouldWalk(.20, .12, .546));
    }

    @Test void recordedCornerIsTraversedWithoutDriftingIntoSouthernWall() {
        simulate(-68.7534729681626, -18.85985731716721,
                new double[][]{{-68.5,-18.5},{-67.5,-18.5}}, -18.30);
    }

    @Test void rightAnglePathSettlesBeforeEachTurn() {
        simulate(0.8,0.3,new double[][]{{.5,.5},{1.5,.5},{1.5,1.5},{2.5,1.5}}, 1.70);
    }

    private void simulate(double x,double z,double[][] path,double maxZ) {
        double vx=0,vz=0;
        int waypoint=0;
        for(int tick=0;tick<200;tick++) {
            double dx=path[waypoint][0]-x,dz=path[waypoint][1]-z;
            double distance=Math.hypot(dx,dz),speed=Math.hypot(vx,vz);
            if(WalkingControl.arrived(distance,speed)) {
                if(++waypoint==path.length) return;
                dx=path[waypoint][0]-x; dz=path[waypoint][1]-z;
                distance=Math.hypot(dx,dz);
            }
            // Vanilla grass-ground approximation: input acceleration .1*.98,
            // movement then velocity friction .6*.91. No collision clamping:
            // crossing the wall fails instead of hiding steering error.
            if(WalkingControl.shouldWalk(distance,speed,.546)) {
                vx+=.098*dx/distance; vz+=.098*dz/distance;
            }
            x+=vx; z+=vz; vx*=.546; vz*=.546;
            assertTrue(z<maxZ,"walk drifted outside corridor at tick " + tick + ": " + z);
        }
        fail("did not reach goal within action budget");
    }
}
