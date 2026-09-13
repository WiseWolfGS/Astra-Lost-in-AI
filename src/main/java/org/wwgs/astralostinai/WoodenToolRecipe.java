package org.wwgs.astralostinai;

public record WoodenToolRecipe(String id, int planks, int sticks) {
    public static WoodenToolRecipe find(String id) {
        return switch (id) {
            case "wooden_pickaxe", "wooden_axe" -> new WoodenToolRecipe(id,3,2);
            case "wooden_sword" -> new WoodenToolRecipe(id,2,1);
            case "wooden_shovel" -> new WoodenToolRecipe(id,1,2);
            case "wooden_hoe" -> new WoodenToolRecipe(id,2,2);
            default -> null;
        };
    }
}
