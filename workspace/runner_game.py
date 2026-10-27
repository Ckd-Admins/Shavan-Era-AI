import pygame
import random

# Initialize PyGame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 400
SCREEN_HEIGHT = 600
SCREEN = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Ira - Endless Runner Prototype")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Player setup
player_width = 50
player_height = 50
player_x = SCREEN_WIDTH // 2 - player_width // 2
player_y = SCREEN_HEIGHT - player_height - 20
player_speed = 5

# Obstacle setup
obstacle_width = 50
obstacle_height = 50
obstacle_speed = 7
obstacles = []

# Game loop variables
running = True
clock = pygame.time.Clock()
score = 0

def draw_player(x, y):
    pygame.draw.rect(SCREEN, GREEN, [x, y, player_width, player_height])

def draw_obstacle(obstacle_list):
    for obs in obstacle_list:
        pygame.draw.rect(SCREEN, RED, obs)

def check_collision(player_rect, obstacle_list):
    for obs in obstacle_list:
        if player_rect.colliderect(obs):
            return True
    return False

# Main Game Loop
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # Player movement
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT] and player_x > 0:
        player_x -= player_speed
    if keys[pygame.K_RIGHT] and player_x < SCREEN_WIDTH - player_width:
        player_x += player_speed

    # Create new obstacles
    if random.randrange(0, 50) == 1:
        obs_x = random.randrange(0, SCREEN_WIDTH - obstacle_width)
        obs_y = -obstacle_height
        obstacles.append(pygame.Rect(obs_x, obs_y, obstacle_width, obstacle_height))

    # Move obstacles and remove off-screen ones
    for obs in obstacles[:]:
        obs.y += obstacle_speed
        if obs.y > SCREEN_HEIGHT:
            obstacles.remove(obs)
            score += 1

    # Drawing
    SCREEN.fill(WHITE)
    draw_player(player_x, player_y)
    draw_obstacle(obstacles)

    # Collision detection
    player_rect = pygame.Rect(player_x, player_y, player_width, player_height)
    if check_collision(player_rect, obstacles):
        running = False
        print(f"Game Over! Final Score: {score}")

    # Display score (basic)
    font = pygame.font.SysFont(None, 35)
    score_text = font.render(f"Score: {score}", True, BLACK)
    SCREEN.blit(score_text, (10, 10))

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
