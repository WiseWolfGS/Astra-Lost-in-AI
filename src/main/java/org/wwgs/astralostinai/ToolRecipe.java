package org.wwgs.astralostinai;

/** Material family and exact per-craft costs; wooden recipes retain their existing policy. */
public record ToolRecipe(String id, String material, int materialCount, int sticks) {
    public static ToolRecipe find(String id) {
        var wood = WoodenToolRecipe.find(id);
        if (wood != null) return new ToolRecipe(id,"planks",wood.planks(),wood.sticks());
        return switch (id) {
            case "stone_pickaxe", "stone_axe" -> new ToolRecipe(id,"stone_tool_materials",3,2);
            case "stone_sword" -> new ToolRecipe(id,"stone_tool_materials",2,1);
            case "stone_shovel" -> new ToolRecipe(id,"stone_tool_materials",1,2);
            case "stone_hoe" -> new ToolRecipe(id,"stone_tool_materials",2,2);
            default -> null;
        };
    }
}
