package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import java.util.Set;
import static org.junit.jupiter.api.Assertions.*;
import static org.wwgs.astralostinai.FlatPathfinder.*;

class NavigationTest {
    @Test void routesAroundWallUsingOnlyCardinalSteps() {
        Cell start=new Cell(0,0), goal=new Cell(2,0);
        var wall=Set.of(new Cell(1,0),new Cell(1,-1));
        var path=find(start,goal::equals,(a,b)->!wall.contains(b));
        assertEquals(start,path.getFirst());
        assertEquals(goal,path.getLast());
        assertEquals(5,path.size());
        for(int i=1;i<path.size();i++){
            Cell a=path.get(i-1),b=path.get(i);
            assertEquals(1,Math.abs(a.x()-b.x())+Math.abs(a.z()-b.z()));
            assertFalse(wall.contains(b));
        }
    }
    @Test void cannotCutDiagonalCornerOrCrossUnknownSpace() {
        assertTrue(find(new Cell(0,0),new Cell(1,1)::equals,(a,b)->false).isEmpty());
    }
    @Test void searchRemainsWithinLocalRange() {
        assertTrue(find(new Cell(0,0),new Cell(5,0)::equals,(a,b)->true).isEmpty());
    }
    @Test void negativeCoordinatesAreHandled() {
        var path=find(new Cell(-3,-2),new Cell(-1,-2)::equals,(a,b)->true);
        assertEquals(3,path.size());
        assertEquals(new Cell(-1,-2),path.getLast());
    }
    @Test void alreadyAtGoalHasNoWalkingEdge() {
        Cell start=new Cell(0,0);
        assertEquals(java.util.List.of(start),find(start,start::equals,(a,b)->false));
    }
    @Test void twelveEdgeBudgetRejectsLongDetour() {
        // Only this U-shaped one-cell corridor is allowed: length 14 to a nearby endpoint.
        var corridor=new java.util.ArrayList<Cell>();
        for(int z=0;z<=4;z++) corridor.add(new Cell(0,z));
        for(int x=1;x<=4;x++) corridor.add(new Cell(x,4));
        for(int z=3;z>=-2;z--) corridor.add(new Cell(4,z));
        var allowed=Set.copyOf(corridor);
        assertTrue(find(new Cell(0,0),new Cell(4,-2)::equals,(a,b)->allowed.contains(b)).isEmpty());
    }
    @Test void disappearingEntityAloneDoesNotProvePickup() {
        var evidence=new PickupEvidence(20,1,3);
        assertEquals(0,evidence.verifiedCount(4));
    }
    @Test void unrelatedPacketsDoNotProvePickup() {
        var evidence=new PickupEvidence(20,1,3);
        evidence.record(21,1,2);
        evidence.record(20,2,2);
        evidence.record(20,1,0);
        assertEquals(0,evidence.verifiedCount(5));
    }
    @Test void packetAndInventoryAreBothRequiredAndCountIsBounded() {
        var evidence=new PickupEvidence(20,1,3);
        evidence.record(20,1,2);
        assertEquals(0,evidence.verifiedCount(3));
        assertEquals(1,evidence.verifiedCount(4));
        assertEquals(2,evidence.verifiedCount(10));
        assertEquals(0,evidence.verifiedCount(2));
    }
}
