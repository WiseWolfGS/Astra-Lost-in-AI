package org.wwgs.astralostinai;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class ToolRecipeTest {
    @Test void stoneCostsUseTheirOwnMaterialFamily() {
        assertEquals(new ToolRecipe("stone_pickaxe", "stone_tool_materials", 3, 2), ToolRecipe.find("stone_pickaxe"));
        assertEquals(3, ToolRecipe.find("stone_axe").materialCount());
        assertEquals(1, ToolRecipe.find("stone_sword").sticks());
        assertEquals(1, ToolRecipe.find("stone_shovel").materialCount());
        assertEquals(2, ToolRecipe.find("stone_hoe").materialCount());
    }
    @Test void woodPolicyIsPreservedAndUnsupportedRecipesRejected() {
        assertEquals(new ToolRecipe("wooden_pickaxe", "planks", 3, 2), ToolRecipe.find("wooden_pickaxe"));
        assertNull(ToolRecipe.find("iron_pickaxe"));
        assertNull(ToolRecipe.find("oak_planks"));
    }
}
