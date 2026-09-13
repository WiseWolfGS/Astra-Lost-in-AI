package org.wwgs.astralostinai;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class WoodenToolRecipeTest {
    @Test void toolCostsRemainSeparate() {
        assertEquals(3,WoodenToolRecipe.find("wooden_pickaxe").planks());
        assertEquals(2,WoodenToolRecipe.find("wooden_pickaxe").sticks());
        assertEquals(1,WoodenToolRecipe.find("wooden_sword").sticks());
        assertEquals(1,WoodenToolRecipe.find("wooden_shovel").planks());
        assertEquals(2,WoodenToolRecipe.find("wooden_hoe").planks());
    }
    @Test void unsupportedRecipesCannotEnterWorkbenchCrafting() {
        assertNull(WoodenToolRecipe.find("diamond_pickaxe"));
        assertNull(WoodenToolRecipe.find("oak_planks"));
    }
}
