import sys
import math
import random
import pygame
import os

from scripts.utils import load_image, load_images, Animation
from scripts.entities import PhysicsEntity, Player, Enemy
from scripts.tilemap import Tilemap
from scripts.particle import Particle
from scripts.spark import Spark

class Game:
    def __init__(self):
        pygame.init()

        pygame.display.set_caption('pypypy in cave game')
        self.screen = pygame.display.set_mode((640, 480))
        self.display = pygame.Surface((320, 240), pygame.SRCALPHA)
        self.display_2 = pygame.Surface((320, 240))

        self.clock = pygame.time.Clock()

        self.movement_x = [False, False]
        self.movement_y = [False, False]

        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'stone': load_images('tiles/stone'),
            'player': load_image('entities/player.png'),
            'background': load_image('yellow_bg.png'),
            'enemy/idle': Animation(load_images('entities/enemy/idle'), img_dur=6),
            'enemy/run': Animation(load_images('entities/enemy/run'), img_dur=4),
            'player/idle': Animation(load_images('entities/player/idle'), img_dur=6),
            'player/run': Animation(load_images('entities/player/run'), img_dur=4),
            'player/jump': Animation(load_images('entities/player/jump')),
            'player/slide': Animation(load_images('entities/player/slide')),
            'particle/leaf': Animation(load_images('particles/leaf'), img_dur=20, loop=False),
            'particle/particle': Animation(load_images('particles/particle'), img_dur=6, loop=False),
            'gun': load_image('gun.png'),
            'projectile': load_image('projectile.png'),
        }

        self.sfx = {
            'jump': pygame.mixer.Sound('ninja_data/sfx/jump.wav'),
            'ambience': pygame.mixer.Sound('ninja_data/sfx/ambience.wav'),
            'dash': pygame.mixer.Sound('ninja_data/sfx/dash.wav'),
            'shoot': pygame.mixer.Sound('ninja_data/sfx/shoot.wav'),
            'hit': pygame.mixer.Sound('ninja_data/sfx/hit.wav'),
        }

        self.sfx['ambience'].set_volume(0.2)
        self.sfx['jump'].set_volume(0.7)
        self.sfx['shoot'].set_volume(0.4)
        self.sfx['dash'].set_volume(0.3)
        self.sfx['hit'].set_volume(0.8)

        self.player = Player(self, (50, 50), (8, 15))

        self.tilemap = Tilemap(self, tile_size=16)

        self.level = 0

        self.load_level(0)

        self.screenshake = 0

        self.start_time = pygame.time.get_ticks()  # Record the start time
        self.time_limit = 2 * 60 * 1000  # 2 minutes in milliseconds
        self.timer_font = pygame.font.SysFont(None, 40)  # Font for the timer
        self.timer_rect = pygame.Rect(220, 10, 100, 50)  # Position and size of the timer

        self.paused = False

        self.state = "menu"  # Add game state: "menu" or "game"
        self.menu_font = pygame.font.SysFont(None, 80)  # Font for menu

    def load_level(self, map_id):
        self.tilemap.load('ninja_data/maps/' + str(map_id) + '.json')

        self.leaf_spawners = []
        for tree in self.tilemap.extract([('large_decor', 2)], keep=True):
            self.leaf_spawners.append(pygame.Rect(4 + tree['pos'][0], 4 + tree['pos'][1], 23, 13))

        self.enemies = []
        for spawner in self.tilemap.extract([('spawners', 0), ('spawners', 1)]):
            if spawner['variant'] == 0:
                self.player.pos = spawner['pos']
            else:
                self.enemies.append(Enemy(self, spawner['pos'], (8, 15)))

        self.projectiles = []
        self.particles = []
        self.sparks = []

        self.scroll = [0, 0]
        self.dead = 0
        self.transition = -30

    def display_menu(self):
        self.screen.fill((0, 0, 0))
        title_surface = self.menu_font.render('Cave Game', True, (255, 255, 255))
        start_surface = self.menu_font.render('Press Enter to Start', True, (255, 255, 255))
        quit_surface = self.menu_font.render('Press Q to Quit', True, (255, 255, 255))

        self.screen.blit(title_surface, (120, 100))
        self.screen.blit(start_surface, (50, 200))
        self.screen.blit(quit_surface, (80, 300))

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:  # Start game when Enter is pressed
                    self.state = "game"
                if event.key == pygame.K_q:  # Quit game
                    pygame.quit()
                    sys.exit()

    def run(self):
        pygame.mixer.music.load('ninja_data/music.wav')
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        self.sfx['ambience'].play(-1)

        while True:
            if self.state == "menu":
                self.display_menu()  # Display the menu until player starts the game
            elif self.state == "game":
                self.display.fill((0, 0, 0, 0))
                self.display_2.blit(self.assets['background'], (0, 0))

                self.screenshake = max(0, self.screenshake - 1)

                if len(self.enemies):
                    self.transition += 1
                    if self.transition > 30:
                        self.level = min(len(os.listdir('ninja_data/maps')) - 1, self.level + 1)
                        self.load_level(self.level)
                if self.transition < 0:
                    self.transition += 1

                # Timer logic
                elapsed_time = pygame.time.get_ticks() - self.start_time
                remaining_time = max(0, self.time_limit - elapsed_time)
                minutes = remaining_time // 60000
                seconds = (remaining_time % 60000) // 1000

                if remaining_time > 0:
                    timer_text = f'{minutes}:{seconds:02}'
                else:
                    timer_text = '!'  # Show exclamation mark when time hits zero


                if self.dead:
                    self.dead += 1
                    if self.dead >= 10:
                        self.transition = min(self.transition + 1, 30)
                    if self.dead > 40:
                        self.load_level(self.level)

                self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 30
                self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.scroll[1]) / 30
                render_scroll = (int(self.scroll[0]), int(self.scroll[1]))

                self.tilemap.render(self.display, offset=render_scroll)

                timer_surface = self.timer_font.render(timer_text, True, (255, 0, 0))  # Render in red
                self.display.blit(timer_surface, self.timer_rect)

                
                for enemy in self.enemies.copy():
                    kill = enemy.update(self.tilemap, (0, 0))
                    enemy.render(self.display, offset=render_scroll)
                    if kill:
                        self.enemies.remove(enemy)

                if not self.dead:
                    self.player.update(self.tilemap, (self.movement_x[1] - self.movement_x[0], self.movement_y[1] - self.movement_y[0]))
                    self.player.render(self.display, offset=render_scroll)



            for spark in self.sparks.copy():
                kill = spark.update()
                spark.render(self.display, offset=render_scroll)
                if kill:
                    self.sparks.remove(spark)

            display_mask = pygame.mask.from_surface(self.display)
            display_sillhouette = display_mask.to_surface(setcolor=(0,0,0,180) , unsetcolor=(0,0,0,0))

            for offset in [(-1,0) , (1,0) , (0,1) , (0,-1)]:
                self.display_2.blit(display_sillhouette , offset)
            
            for particle in self.particles.copy():
                kill = particle.update()
                particle.render(self.display, offset=render_scroll)
                if particle.type == 'leaf':
                    particle.pos[0] += math.sin(particle.animation.frame * 0.035) * 0.3
                if kill:
                    self.particles.remove(particle)
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_b:
                        sys.exit()
                    if event.key == pygame.K_a:
                        self.movement_x[0] = True
                    if event.key == pygame.K_d:
                        self.movement_x[1] = True
                    if event.key == pygame.K_w:
                        self.movement_y[0] = True
                    if event.key == pygame.K_s:
                        self.movement_y[1] = True
                    if event.key == pygame.K_x:
                        self.player.dash()
                    
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_a:
                        self.movement_x[0] = False
                    if event.key == pygame.K_d:
                        self.movement_x[1] = False
                    if event.key == pygame.K_w:
                        self.movement_y[0] = False
                    if event.key == pygame.K_s:
                        self.movement_y[1] = False

            if self.transition:
                transition_surf = pygame.Surface(self.display.get_size())
                pygame.draw.circle(transition_surf , (255,255,255), (self.display.get_width() //2 , self.display.get_height()//2) , (30 - abs(self.transition))* 8)
                transition_surf.set_colorkey((255,255,255))
                self.display.blit(transition_surf , (0,0))

            
            self.display_2.blit(self.display, (0,0))

            
            
            srceenshake_offset = (random.random() * self.screenshake - self.screenshake / 2,random.random() * self.screenshake - self.screenshake / 2 ) 
            
            self.screen.blit(pygame.transform.scale(self.display_2, self.screen.get_size()), srceenshake_offset)
            pygame.display.update()
            self.clock.tick(60)

Game().run()