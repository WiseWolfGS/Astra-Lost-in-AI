package org.wwgs.astralostinai;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class CraftEvidenceTest {
    @Test void exactRecipeEvidenceRequired() {
        assertTrue(CraftEvidence.verified(true,3,1,4,1,4,true));
        assertFalse(CraftEvidence.verified(true,3,0,4,1,4,true));
        assertFalse(CraftEvidence.verified(true,3,1,0,1,4,true));
        assertFalse(CraftEvidence.verified(true,3,2,8,1,4,true));
    }
    @Test void predictedOrPartialChangesAreNotSuccess() {
        assertFalse(CraftEvidence.verified(false,3,1,4,1,4,true));
        assertFalse(CraftEvidence.verified(true,0,1,4,1,4,true));
        assertFalse(CraftEvidence.verified(true,3,1,4,1,4,false));
    }
}
