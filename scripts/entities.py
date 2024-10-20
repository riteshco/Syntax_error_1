import pygame
from scripts.particle import Particle
import math
import random
from scripts.spark import Spark

class PhysicsEntity:
    def __init__(self, game, e_type, pos, size):
        self.game = game
        self.type = e_type
        self.pos = list(pos)  # [x, y] position
        self.size = size  # [width, height]
        self.velocity = [0, 0]  # [x_velocity, y_velocity]
        self.collisions = {'up': False, 'down': False, 'right': False, 'left': False}

        self.action = ''
        self.anim_offset = (-3, -3)
        self.flip = False
        self.set_action('idle')
        self.last_movement = [0, 0]

    def rect(self):
        return pygame.Rect(self.pos[0], self.pos[1], self.size[0], self.size[1])
        
    def set_action(self, action):
        if action != self.action:
            self.action = action
            self.animation = self.game.assets[self.type + '/' + self.action].copy()

    def update(self, tilemap, movement=(0, 0)):
        self.collisions = {'up': False, 'down': False, 'right': False, 'left': False}

        # Movement is now fully controlled in both x and y axes
        frame_movement = (movement[0] + self.velocity[0], movement[1] + self.velocity[1])

        # Update x-axis position
        self.pos[0] += frame_movement[0]
        entity_rect = self.rect()

        # Handle horizontal collisions
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[0] > 0:
                    entity_rect.right = rect.left
                    self.collisions['right'] = True
                if frame_movement[0] < 0:
                    entity_rect.left = rect.right
                    self.collisions['left'] = True
                self.pos[0] = entity_rect.x

        # Update y-axis position
        self.pos[1] += frame_movement[1]
        entity_rect = self.rect()

        # Handle vertical collisions
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[1] > 0:
                    entity_rect.bottom = rect.top
                    self.collisions['down'] = True
                if frame_movement[1] < 0:
                    entity_rect.top = rect.bottom
                    self.collisions['up'] = True
                self.pos[1] = entity_rect.y

        # Set flip direction based on horizontal movement
        if movement[0] > 0:
            self.flip = False
        if movement[0] < 0:
            self.flip = True

        self.last_movement = movement

        # No gravity, so velocity[1] is not affected anymore
        self.animation.update()

    def render(self, surf, offset=(0, 0)):
        surf.blit(
            pygame.transform.flip(self.animation.img(), self.flip, False),
            (self.pos[0] - offset[0] + self.anim_offset[0], self.pos[1] - offset[1] + self.anim_offset[1])
        )


class Enemy(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, 'enemy', pos, size)
        self.walking = 0
        self.detection_radius = 100  # Distance within which enemy detects and follows player
        self.attack_range = 20  # Distance within which the enemy deals melee damage
        self.attack_damage = 10  # Damage dealt to the player on hit
        self.attack_cooldown = 0  # Cooldown time between attacks
        self.noise_factor = 0.3  # Factor for random noise in movement when stuck
        self.path = []  # Store the path found by the A* algorithm
        self.target_tile = None

    def update(self, tilemap, movement=(0, 0)):
        # Calculate distance to the player
        player_distance_x = self.game.player.pos[0] - self.pos[0]
        player_distance_y = self.game.player.pos[1] - self.pos[1]
        distance_to_player = math.sqrt(player_distance_x ** 2 + player_distance_y ** 2)

        # Follow the player horizontally and vertically
        if not self.game.player.dashing:
            if distance_to_player < self.detection_radius:
                if abs(player_distance_x) > self.attack_range:
                    if player_distance_x > 0:
                        movement = (0.7, movement[1])
                        self.flip = False
                    else:
                        movement = (-0.7, movement[1])
                        self.flip = True
                if abs(player_distance_y) > self.attack_range:
                    if player_distance_y > 0:
                        movement = (movement[0], 0.7)
                    else:
                        movement = (movement[0], -0.7)

        # Add noise when enemy hits a wall to prevent sticking
        if self.collisions['left'] or self.collisions['right'] or self.collisions['up'] or self.collisions['down']:
            # Add small random noise to x and y movement to unstuck
            noise_x = random.uniform(-self.noise_factor, self.noise_factor)
            noise_y = random.uniform(-self.noise_factor, self.noise_factor)
            movement = (movement[0] + noise_x, movement[1] + noise_y)

        player_pos = self.game.player.pos
        current_tile = (self.pos[0] // tilemap.tile_size, self.pos[1] // tilemap.tile_size)
        player_tile = (player_pos[0] // tilemap.tile_size, player_pos[1] // tilemap.tile_size)

        # Recalculate path if necessary
        if not self.path or self.target_tile != player_tile:
            self.path = astar(current_tile, player_tile, tilemap)
            self.target_tile = player_tile

        if self.path:
            # Move along the path
            next_tile = self.path[0]
            if next_tile == current_tile:
                self.path.pop(0)  # Reached this tile, move to next

            if self.path:
                next_tile = self.path[0]
                dx = next_tile[0] - current_tile[0]
                dy = next_tile[1] - current_tile[1]
                movement = (dx * 0.7, dy * 0.7)

        super().update(tilemap, movement=movement)

        # Check for attack range and cooldown
        if distance_to_player < self.attack_range and self.attack_cooldown <= 0:
            self.attack_player()
            self.attack_cooldown = 30  # Set a cooldown period between attacks

        # Reduce attack cooldown over time
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        # Set action based on movement
        if movement[0] != 0 or movement[1] != 0:
            self.set_action('run')
        else:
            self.set_action('idle')

    def attack_player(self):
        if self.game.player.invincible_time <= 0:
            # Deal damage to the player and apply knockback
            self.game.player.health -= self.attack_damage
            self.game.player.invincible_time = 30  # Player is invincible for 30 frames after taking damage

            # Apply knockback to the player
            knockback_direction = -1 if self.flip else 1
            self.game.player.knockback = [knockback_direction * 5, -3]


class Player(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, 'player', pos, size)
        self.dashing = 0
        self.health = 100
        self.invincible_time = 0
        self.knockback = [0, 0]

    def update(self, tilemap, movement=(0, 0)):
        if self.invincible_time > 0:
            self.invincible_time -= 1

        # Apply knockback
        if self.knockback[0] != 0 or self.knockback[1] != 0:
            movement = (self.knockback[0], movement[1] + self.knockback[1])
            self.knockback[0] = max(0, self.knockback[0] - 0.5) if self.knockback[0] > 0 else min(0, self.knockback[0] + 0.5)
            self.knockback[1] = max(0, self.knockback[1] - 0.5) if self.knockback[1] > 0 else min(0, self.knockback[1] + 0.5)


        super().update(tilemap, movement=movement)

        # Trigger walking animation
        if movement[0] != 0:
            self.set_action('run')
        else:
            self.set_action('idle')

        # Dashing logic
        if abs(self.dashing) in {60, 50}:
            for i in range(20):
                angle = random.random() * math.pi * 2
                speed = random.random() * 0.5 + 0.5
                pvelocity = [math.cos(angle) * speed, math.sin(angle) * speed]
                self.game.particles.append(Particle(self.game, 'particle', self.rect().center, velocity=pvelocity, frame=random.randint(0, 7)))

        if self.dashing > 0:
            self.dashing = max(self.dashing - 1, 0)
        if self.dashing < 0:
            self.dashing = min(self.dashing + 1, 0)
        if abs(self.dashing) > 50:
            self.velocity[0] = abs(self.dashing) / self.dashing * 8
            if abs(self.dashing) == 51:
                self.velocity[0] *= 0.1
            pvelocity = [abs(self.dashing) / self.dashing * random.random() * 3, 0]
            self.game.particles.append(Particle(self.game, 'particle', self.rect().center, velocity=pvelocity, frame=random.randint(0, 7)))

        # Reduce horizontal velocity over time
        if self.velocity[0] > 0:
            self.velocity[0] = max(self.velocity[0] - 0.1, 0)
        else:
            self.velocity[0] = min(self.velocity[0] + 0.1, 0)

        # Reduce vertical velocity over time
        if self.velocity[1] > 0:
            self.velocity[1] = max(self.velocity[1] - 0.1, 0)
        else:
            self.velocity[1] = min(self.velocity[1] + 0.1, 0)
    def render(self, surf, offset=(0, 0)):
        if abs(self.dashing) <= 50:
            super().render(surf, offset=offset)

    def dash(self):
        if not self.dashing:
            self.game.sfx['dash'].play()
            if self.flip:
                self.dashing = -60
            else:
                self.dashing = 60

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.die()  # Implement a death sequence

    def die(self):
        # Handle player's death, reload level, or show game over
        print("Player is dead!")
        self.game.load_level(self.game.level)



class Node:
    def __init__(self, position, parent=None):
        self.position = position
        self.parent = parent
        self.g = 0  # Distance to start node
        self.h = 0  # Distance to end node (heuristic)
        self.f = 0  # Total cost

def astar(start, end, tilemap):
    # Initialize both open and closed lists
    open_list = []
    closed_list = []

    # Add the start node to the open list
    start_node = Node(start)
    open_list.append(start_node)

    while open_list:
        # Get the current node (node with the lowest f cost)
        current_node = min(open_list, key=lambda node: node.f)
        open_list.remove(current_node)
        closed_list.append(current_node)

        # Check if we have reached the goal
        if current_node.position == end:
            path = []
            while current_node:
                path.append(current_node.position)
                current_node = current_node.parent
            return path[::-1]  # Return the path reversed (from start to end)

        # Generate neighbors (up, down, left, right)
        neighbors = [
            (0, -1), (0, 1),  # Up, Down
            (-1, 0), (1, 0)   # Left, Right
        ]

        for offset in neighbors:
            neighbor_position = (current_node.position[0] + offset[0], current_node.position[1] + offset[1])

            # Check if the neighbor is within bounds and walkable
            if tilemap.is_walkable(neighbor_position) and neighbor_position not in [node.position for node in closed_list]:
                neighbor_node = Node(neighbor_position, current_node)

                # Calculate costs
                neighbor_node.g = current_node.g + 1  # Assuming uniform cost for each step
                neighbor_node.h = abs(neighbor_node.position[0] - end[0]) + abs(neighbor_node.position[1] - end[1])  # Manhattan distance
                neighbor_node.f = neighbor_node.g + neighbor_node.h

                # Check if neighbor is already in open list with a lower g value
                if not any(node.position == neighbor_node.position and node.g < neighbor_node.g for node in open_list):
                    open_list.append(neighbor_node)

    return None

class Chest:
    def __init__(self, game, position):
        self.game = game
        self.image = self.game.assets['chest']
        self.rect = self.image.get_rect(topleft=position)
        self.collected = False  # To track if the chest is collected
    
    def render(self, display, offset):
        if not self.collected:
            display.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))
    
    def update(self, player_rect):
        # Check if the player collides with the chest
        if self.rect.colliderect(player_rect):
            self.collected = True  # Chest vanishes when collected
            self.game.score+=10
