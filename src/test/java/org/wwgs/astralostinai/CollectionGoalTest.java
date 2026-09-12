package org.wwgs.astralostinai;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class CollectionGoalTest {
    private List<FlatPathfinder.Cell> route(boolean fallback, boolean blocked) {
        // Synthetic translated case: item under a remaining overhead trunk.
        var root = new FlatPathfinder.Cell(2, 0);
        return FlatPathfinder.find(root,
            c -> CollectionGoal.near(c.x()+.5-.536, c.z()+.5-.234, fallback),
            (a,b) -> !blocked && !(b.x()==0 && b.z()==0));
    }
    @Test void overheadTrunkNeedsAdjacentStandPosition() {
        assertTrue(route(false,false).isEmpty());
        var path=route(true,false);
        assertFalse(path.isEmpty());
        assertFalse(path.contains(new FlatPathfinder.Cell(0,0)));
    }
    @Test void fallbackNeverCrossesBlockedEdges() {
        assertTrue(route(true,true).isEmpty());
    }
    @Test void candidateRadiusIsBoundedAndNotPickupProof() {
        assertTrue(CollectionGoal.near(.8,0,true));
        assertFalse(CollectionGoal.near(.8,0,false));
        assertFalse(CollectionGoal.near(1.01,0,true));
    }
}
