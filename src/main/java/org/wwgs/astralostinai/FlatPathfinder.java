package org.wwgs.astralostinai;

import java.util.*;
import java.util.function.BiPredicate;
import java.util.function.Predicate;

/** Four-neighbour BFS, restricted to a 9x9 area and at most twelve edges. */
public final class FlatPathfinder {
    public record Cell(int x, int z) {}
    private FlatPathfinder() {}

    public static List<Cell> find(Cell start, Predicate<Cell> goal, BiPredicate<Cell, Cell> traversable) {
        var queue = new ArrayDeque<Cell>();
        var previous = new HashMap<Cell, Cell>();
        var depth = new HashMap<Cell, Integer>();
        queue.add(start);
        depth.put(start, 0);
        while (!queue.isEmpty()) {
            Cell current = queue.remove();
            if (goal.test(current)) {
                var route = new ArrayList<Cell>();
                for (Cell cell = current; cell != null; cell = previous.get(cell)) route.add(cell);
                Collections.reverse(route);
                return route;
            }
            if (depth.get(current) >= 12) continue;
            for (int[] delta : new int[][]{{0,-1},{1,0},{0,1},{-1,0}}) {
                Cell next = new Cell(current.x + delta[0], current.z + delta[1]);
                if (Math.abs(next.x-start.x)>4 || Math.abs(next.z-start.z)>4 || depth.containsKey(next)) continue;
                if (!traversable.test(current, next)) continue;
                previous.put(next, current);
                depth.put(next, depth.get(current)+1);
                queue.add(next);
            }
        }
        return List.of();
    }
}
