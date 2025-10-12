import matplotlib
import matplotlib.pyplot as plt
from collections import deque
matplotlib.use('TkAgg')


def get_reachable_cells_manhattan(grid, start, max_steps):
    width, height = len(grid[0]), len(grid)
    visited = set()
    q = deque([(start, 0)])
    reachable = {}

    while q:
        (x, y), steps = q.popleft()
        if steps > max_steps or (x, y) in visited:
            continue
        visited.add((x, y))
        reachable[(x, y)] = steps
        
        # Только 4 направления (манхэттенское расстояние)
        for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] != '#':
                q.append(((nx, ny), steps + 1))
    
    return reachable

# создаем более сложное поле
grid = [
    ['.', '.', '.', '.', '.', '.', '.', '.', '.'],
    ['.', '#', '#', '.', '.', '#', '.', '.', '.'],
    ['.', '.', '#', '.', '#', '#', '.', '#', '.'],
    ['.', '.', '.', '.', '.', '.', '.', '#', '.'],
    ['#', '.', '#', '#', '.', '.', '.', '.', '.'],
    ['.', '.', '.', '.', '.', '#', '.', '.', '.'],
    ['.', '#', '.', '#', '.', '.', '#', '.', '.'],
    ['.', '.', '.', '.', '.', '.', '.', '.', '.'],
    ['.', '.', '.', '#', '.', '.', '.', '.', '.']
]

start = (2, 4)
max_steps = 5
reachable = get_reachable_cells_manhattan(grid, start, max_steps)

# визуализация
fig, ax = plt.subplots(figsize=(6, 6))
for y in range(len(grid)):
    for x in range(len(grid[0])):
        color = 'white'
        if (x, y) == start:
            color = 'green'
        elif grid[y][x] == '#':
            color = 'black'
        elif (x, y) in reachable:
            color = 'skyblue'
        rect = plt.Rectangle((x, y), 1, 1, facecolor=color, edgecolor='gray')
        ax.add_patch(rect)

        # показываем номер шага, если клетка достижима и не старт
        if (x, y) in reachable and (x, y) != start:
            ax.text(x + 0.5, y + 0.5, str(reachable[(x, y)]),
                    ha='center', va='center', fontsize=8, color='black')

ax.set_xlim(0, len(grid[0]))
ax.set_ylim(0, len(grid))
ax.set_aspect('equal')
ax.invert_yaxis()
ax.axis('off')
plt.show()
