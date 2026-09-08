#!/usr/bin/env python
# encoding: utf-8

"""
@version: v1.0
@author: chenwenlin
@contact: xxx@qq.com
@site: 
@software: PyCharm
@file: 坦克大战.py
@time: 2026/9/2 15:19
"""
# -*- coding: utf-8 -*-
"""
坦克大战 (Battle City) 迷你版
运行前请先安装 pygame:  pip install pygame
运行方式:  python tank_battle.py

操作说明:
    移动: 方向键 / WASD
    开火: 空格键
    暂停: ESC 或 P
    目标: 保护基地(下方金色图标), 消灭所有敌人
"""

import math
import random
import sys
import os
import pygame

# ============ 常量 ============
CELL = 40
COLS = 13
ROWS = 13
MAP_W = COLS * CELL          # 520
MAP_H = ROWS * CELL          # 520
INFO_H = 60                  # 顶部信息栏高度
SCREEN_W = MAP_W
SCREEN_H = MAP_H + INFO_H    # 580
FPS = 60

# 地图格子类型
EMPTY, BRICK, STEEL, WATER, BASE = 0, 1, 2, 3, 4

# 地图字符 -> 类型
TILE_CHARS = {
    '.': EMPTY,
    '#': BRICK,
    '$': STEEL,
    '~': WATER,
    'B': BASE,
}

# 13 x 13 地图（B 是基地）
MAP_STR = [
    ".............",
    "..#..#.#..#..",
    "..##.##.####.",
    ".............",
    ".#~~#...#~~#.",
    "#.~~..#..~~.#",
    ".............",
    ".##.##.##.##.",
    ".............",
    "..........#..",
    ".........###.",
    "....#####....",
    "....##B##....",
]

# 方向: 0上 1右 2下 3左
DIR_VEC = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}


def parse_map():
    m = []
    for row in MAP_STR:
        assert len(row) == COLS, "地图行长度错误"
        m.append([TILE_CHARS[ch] for ch in row])
    return m

def get_font(size):
    """找一个能显示中文的字体。

    直接指定字体文件路径，避免 pygame 在 Windows 上扫描系统字体时的
    match_font 已知 bug（会抛 TypeError）。
    """
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",                    # 微软雅黑
        r"C:\Windows\Fonts\msyhbd.ttc",                  # 微软雅黑粗体
        r"C:\Windows\Fonts\simhei.ttf",                  # 黑体
        r"C:\Windows\Fonts\simsun.ttc",                  # 宋体
        r"/System/Library/Fonts/PingFang.ttc",           # macOS 苹方
        r"/System/Library/Fonts/Hiragino Sans GB.ttc",   # macOS 冬青黑体
        r"/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux
        r"/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",          # Linux
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return pygame.font.Font(path, size)
            except Exception:
                continue
    # 兜底：尝试系统字体扫描（个别环境会报错，捕获后忽略）
    try:
        for name in ("microsoftyahei", "msyh", "simhei", "simsun",
                     "pingfangsc", "notosanscjksc"):
            path = pygame.font.match_font(name)
            if path:
                return pygame.font.Font(path, size)
    except Exception:
        pass
    # 最后兜底：pygame 内置字体（中文会显示成方框，但至少不会崩溃）
    return pygame.font.Font(None, size)


# def get_font(size):
#     """找一个能显示中文的字体"""
#     candidates = [
#         "microsoftyahei", "msyh", "simhei", "simsun",
#         "notosanscjksc", "pingfangsc", "dengxian", "wenquanyimicrohei",
#         "hiraginosansgb", "stheiti",
#     ]
#     for name in candidates:
#         path = pygame.font.match_font(name)
#         if path:
#             return pygame.font.Font(path, size)
#     return pygame.font.Font(None, size)


# ============ 坦克 ============
class Tank:
    W = 34
    H = 34

    def __init__(self, x, y, direction, color, is_player, speed):
        self.rect = pygame.Rect(x, y, self.W, self.H)
        self.direction = direction
        self.color = color
        self.is_player = is_player
        self.speed = speed
        self.cool = 0.0          # 开火冷却
        self.alive = True
        self.invincible = 0.0    # 无敌时间(秒)
        self.move_timer = 0.0    # 敌人换向计时
        self.shoot_timer = 1.0   # 敌人开火计时

    def move(self, dt, solids):
        vx, vy = DIR_VEC[self.direction]
        step = self.speed * dt
        old = self.rect.copy()
        if vx:
            self.rect.x += int(round(vx * step))
            if self.rect.collidelist(solids) != -1:
                self.rect.x = old.x
        if vy:
            self.rect.y += int(round(vy * step))
            if self.rect.collidelist(solids) != -1:
                self.rect.y = old.y
        self.rect.clamp_ip(pygame.Rect(0, 0, MAP_W, MAP_H))


# ============ 子弹 ============
class Bullet:
    def __init__(self, x, y, direction, owner, speed=340):
        self.rect = pygame.Rect(x, y, 8, 8)
        self.direction = direction
        self.owner = owner
        self.speed = speed
        self.color = (255, 240, 80)
        self.alive = True


# ============ 爆炸 ============
class Explosion:
    def __init__(self, cx, cy, big=False):
        self.cx, self.cy = cx, cy
        self.t = 0.0
        self.dur = 0.45 if not big else 0.7
        self.big = big

    def update(self, dt):
        self.t += dt

    @property
    def done(self):
        return self.t >= self.dur

    def draw(self, screen, ox, oy):
        p = self.t / self.dur
        if self.big:
            r1, r2 = int(6 + 30 * p), int(3 + 18 * p)
        else:
            r1, r2 = int(4 + 18 * p), int(2 + 10 * p)
        cx, cy = int(self.cx) + ox, int(self.cy) + oy
        pygame.draw.circle(screen, (255, 200, 60), (cx, cy), r1)
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), r2)


# ============ 绘制辅助 ============
def draw_tank(s, tank, ox, oy):
    if tank.invincible > 0 and int(tank.invincible * 10) % 2 == 0:
        return  # 无敌时闪烁
    x, y = tank.rect.x + ox, tank.rect.y + oy
    w, h = tank.rect.w, tank.rect.h
    c = tank.color
    dark = tuple(max(0, v - 70) for v in c)

    # 履带
    if tank.direction in (0, 2):
        pygame.draw.rect(s, (70, 70, 70), (x, y, 8, h))
        pygame.draw.rect(s, (70, 70, 70), (x + w - 8, y, 8, h))
        for i in range(0, h, 8):
            pygame.draw.line(s, (40, 40, 40), (x, y + i), (x + 8, y + i), 1)
            pygame.draw.line(s, (40, 40, 40), (x + w - 8, y + i), (x + w, y + i), 1)
    else:
        pygame.draw.rect(s, (70, 70, 70), (x, y, w, 8))
        pygame.draw.rect(s, (70, 70, 70), (x, y + h - 8, w, 8))
        for i in range(0, w, 8):
            pygame.draw.line(s, (40, 40, 40), (x + i, y), (x + i, y + 8), 1)
            pygame.draw.line(s, (40, 40, 40), (x + i, y + h - 8), (x + i, y + h), 1)

    # 车身
    pygame.draw.rect(s, c, (x + 8, y + 8, w - 16, h - 16))
    pygame.draw.rect(s, dark, (x + 8, y + 8, w - 16, h - 16), 2)

    # 炮管 + 炮塔
    if tank.direction == 0:
        pygame.draw.rect(s, dark, (x + w // 2 - 3, y - 5, 6, 14))
        pygame.draw.rect(s, c, (x + w // 2 - 6, y + h // 2 - 5, 12, 12))
    elif tank.direction == 2:
        pygame.draw.rect(s, dark, (x + w // 2 - 3, y + h - 9, 6, 14))
        pygame.draw.rect(s, c, (x + w // 2 - 6, y + h // 2 - 7, 12, 12))
    elif tank.direction == 1:
        pygame.draw.rect(s, dark, (x + w - 9, y + h // 2 - 3, 14, 6))
        pygame.draw.rect(s, c, (x + w // 2 - 6, y + h // 2 - 6, 12, 12))
    else:
        pygame.draw.rect(s, dark, (x - 5, y + h // 2 - 3, 14, 6))
        pygame.draw.rect(s, c, (x + w // 2 - 6, y + h // 2 - 6, 12, 12))

    # 玩家标记
    if tank.is_player:
        pygame.draw.circle(s, (255, 255, 255), (x + w // 2, y + h // 2), 3)


def draw_eagle(s, x, y):
    """基地(鹰旗)"""
    pygame.draw.rect(s, (200, 40, 40), (x + 3, y + 3, CELL - 6, CELL - 6))
    pygame.draw.rect(s, (255, 200, 50), (x + 6, y + 6, CELL - 12, CELL - 12))
    cx, cy = x + CELL // 2, y + CELL // 2
    R, r = 14, 6
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    pygame.draw.polygon(s, (200, 40, 40), pts)


# ============ 游戏主体 ============
class BattleCity:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("坦克大战 - Battle City")
        self.clock = pygame.time.Clock()
        self.font_big = get_font(44)
        self.font_mid = get_font(26)
        self.font_small = get_font(19)
        self.time = 0.0
        self.reset(1)
        self.state = "start"  # start / play / pause / gameover / victory
        self.player.invincible = 0.0

    # ---------- 重置 ----------
    def reset(self, wave=1):
        self.map = parse_map()
        self.wave = wave
        self.score = 0
        self.lives = 3
        self.enemies = []
        self.bullets = []
        self.explosions = []
        self.player = None
        self.respawn_timer = 0.0
        self.spawn_points = [(0, 0), (6, 0), (12, 0)]
        self.enemy_left_total = min(24, 10 + 4 * wave)   # 待出动敌人总数
        self.max_on_field = min(2 + wave, 5)             # 同屏最多敌人数
        self.spawn_timer = 0.0
        self.spawn_interval = max(0.5, 2.0 - wave * 0.2)
        self.base_alive = True
        self.state = "play"
        self.start_player(0.0)

    def start_player(self, invincible=3.0):
        x = 2 * CELL + 3
        y = 12 * CELL + 3
        self.player = Tank(x, y, 0, (255, 205, 0), True, speed=180)
        self.player.invincible = invincible

    # ---------- 障碍 / 生成 ----------
    def solids(self, skip=None):
        rects = []
        for r in range(ROWS):
            for c in range(COLS):
                t = self.map[r][c]
                if t in (BRICK, STEEL, WATER, BASE):
                    rects.append(pygame.Rect(c * CELL, r * CELL, CELL, CELL))
        for e in self.enemies:
            if e is not skip and e.alive:
                rects.append(e.rect)
        if self.player and self.player is not skip and self.player.alive:
            rects.append(self.player.rect)
        return rects

    def spawn_enemy(self):
        random.shuffle(self.spawn_points)
        occ = [e.rect for e in self.enemies] + [self.player.rect]
        for (c, r) in self.spawn_points:
            x, y = c * CELL + 3, r * CELL + 3
            rect = pygame.Rect(x, y, 34, 34)
            if rect.collidelist(occ) == -1:
                color = random.choice([
                    (220, 60, 40), (80, 200, 80),
                    (150, 150, 150), (80, 140, 220),
                ])
                speed = random.uniform(70, 95) + self.wave * 6
                e = Tank(x, y, random.randint(0, 3), color, False, speed)
                e.shoot_timer = random.uniform(0.5, 1.5)
                e.move_timer = random.uniform(0.2, 0.8)
                self.enemies.append(e)
                return True
        return False

    def shoot(self, tank, speed=None):
        if speed is None:
            speed = 380 if tank.is_player else 300
        vx, vy = DIR_VEC[tank.direction]
        cx = tank.rect.centerx + vx * 20 - 4
        cy = tank.rect.centery + vy * 20 - 4
        self.bullets.append(Bullet(cx, cy, tank.direction, tank, speed))

    # ---------- 更新 ----------
    def update(self, dt, keys):
        self.update_spawn(dt)
        self.update_player(dt, keys)
        self.update_enemies(dt)
        self.update_bullets(dt)
        for ex in self.explosions:
            ex.update(dt)
        self.explosions = [ex for ex in self.explosions if not ex.done]
        self.enemies = [e for e in self.enemies if e.alive]

        if not self.base_alive:
            self.state = "gameover"
        elif self.enemy_left_total <= 0 and not self.enemies:
            self.state = "victory"

    def update_spawn(self, dt):
        if self.enemy_left_total <= 0:
            return
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len(self.enemies) < self.max_on_field:
            if self.spawn_enemy():
                self.enemy_left_total -= 1
                self.spawn_timer = self.spawn_interval

    # def update_player(self, dt, keys):
    #     p = self.player
    #     if not p or not p.alive:
    #         if self.respawn_timer > 0:
    #             self.respawn_timer -= dt
    #             if self.respawn_timer <= 0:
    #                 self.start_player(3.0)
    #         return
    #     if keys[pygame.K_UP] or keys[pygame.K_w]:
    #         p.direction = 0
    #     elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
    #         p.direction = 2
    #     elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
    #         p.direction = 3
    #     elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
    #         p.direction = 1
    #
    #     p.cool -= dt
    #     if keys[pygame.K_SPACE] and p.cool <= 0:
    #         self.shoot(p)
    #         p.cool = 0.28
    #
    #     if p.invincible > 0:
    #         p.invincible -= dt
    #     # p.move(dt, self.solids())
    #     p.move(dt, self.solids(skip=p))

    def update_player(self, dt, keys):
        p = self.player
        if not p or not p.alive:
            if self.respawn_timer > 0:
                self.respawn_timer -= dt
                if self.respawn_timer <= 0:
                    self.start_player(3.0)
            return

        # 读取方向键；没按方向键时坦克原地不动
        moving = False
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            p.direction, moving = 0, True
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            p.direction, moving = 2, True
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            p.direction, moving = 3, True
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            p.direction, moving = 1, True

        p.cool -= dt
        if keys[pygame.K_SPACE] and p.cool <= 0:
            self.shoot(p)
            p.cool = 0.28

        if p.invincible > 0:
            p.invincible -= dt

        if moving:
            p.move(dt, self.solids(skip=p))


    def update_enemies(self, dt):
        for e in self.enemies:
            if not e.alive:
                continue
            solids = self.solids(skip=e)
            e.move_timer -= dt
            e.shoot_timer -= dt
            if e.move_timer <= 0:
                e.move_timer = random.uniform(0.6, 2.0)
                # 45% 概率朝玩家方向移动
                if self.player and self.player.alive and random.random() < 0.45:
                    dx = self.player.rect.centerx - e.rect.centerx
                    dy = self.player.rect.centery - e.rect.centery
                    if abs(dx) > abs(dy):
                        e.direction = 1 if dx > 0 else 3
                    else:
                        e.direction = 2 if dy > 0 else 0
                else:
                    e.direction = random.randint(0, 3)

            before = (e.rect.x, e.rect.y)
            e.move(dt, solids)
            # 卡住时立刻换向，避免原地不动
            if (e.rect.x, e.rect.y) == before:
                e.move_timer = 0.05
                e.direction = (e.direction + random.choice((1, 3))) % 4

            if e.shoot_timer <= 0:
                self.shoot(e)
                e.shoot_timer = random.uniform(1.2, 2.8) / (1 + self.wave * 0.15)

    def update_bullets(self, dt):
        for b in self.bullets:
            if not b.alive:
                continue
            vx, vy = DIR_VEC[b.direction]
            b.rect.x += int(round(vx * b.speed * dt))
            b.rect.y += int(round(vy * b.speed * dt))
            # 出界
            if (b.rect.right < 0 or b.rect.left > MAP_W or
                    b.rect.bottom < 0 or b.rect.top > MAP_H):
                b.alive = False
                continue
            self.bullet_vs_map(b)

        # 子弹 vs 坦克
        for b in self.bullets:
            if not b.alive:
                continue
            if b.owner is self.player:
                for e in self.enemies:
                    if e.alive and b.rect.colliderect(e.rect):
                        e.alive = False
                        b.alive = False
                        self.score += 100 + self.wave * 50
                        self.explosions.append(
                            Explosion(e.rect.centerx, e.rect.centery, big=True))
                        break
            else:
                p = self.player
                if p and p.alive and b.rect.colliderect(p.rect):
                    b.alive = False
                    self.hit_player()

        # 子弹互撞抵消
        for i in range(len(self.bullets)):
            for j in range(i + 1, len(self.bullets)):
                a, b2 = self.bullets[i], self.bullets[j]
                if a.alive and b2.alive and a.rect.colliderect(b2.rect):
                    a.alive = False
                    b2.alive = False

        self.bullets = [b for b in self.bullets if b.alive]

    def bullet_vs_map(self, b):
        r0 = max(0, b.rect.top // CELL)
        r1 = min(ROWS - 1, (b.rect.bottom - 1) // CELL)
        c0 = max(0, b.rect.left // CELL)
        c1 = min(COLS - 1, (b.rect.right - 1) // CELL)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                t = self.map[r][c]
                if t == EMPTY or t == WATER:
                    continue  # 子弹可飞过水面
                if t == BRICK:
                    self.map[r][c] = EMPTY
                    b.alive = False
                    self.explosions.append(Explosion(c * CELL + 20, r * CELL + 20))
                elif t == STEEL:
                    b.alive = False
                    self.explosions.append(
                        Explosion(b.rect.centerx, b.rect.centery))
                elif t == BASE:
                    b.alive = False
                    self.map[r][c] = EMPTY
                    self.base_alive = False
                    self.explosions.append(
                        Explosion(c * CELL + 20, r * CELL + 20, big=True))

    def hit_player(self):
        p = self.player
        if p.invincible > 0:
            return
        self.lives -= 1
        self.explosions.append(Explosion(p.rect.centerx, p.rect.centery, big=True))
        p.alive = False
        if self.lives <= 0:
            self.state = "gameover"
        else:
            self.respawn_timer = 1.5

    # ---------- 绘制 ----------
    def draw(self):
        s = self.screen
        s.fill((0, 0, 0))
        self.draw_map()
        for e in self.enemies:
            draw_tank(s, e, 0, INFO_H)
        if self.player and self.player.alive:
            draw_tank(s, self.player, 0, INFO_H)
        for b in self.bullets:
            pygame.draw.rect(s, b.color, (b.rect.x, b.rect.y + INFO_H, 8, 8))
        for ex in self.explosions:
            ex.draw(s, 0, INFO_H)
        self.draw_info()

        if self.state == "start":
            self.draw_start()
        elif self.state == "pause":
            self.draw_pause()
        elif self.state == "gameover":
            self.draw_gameover()
        elif self.state == "victory":
            self.draw_victory()

    def draw_map(self):
        s = self.screen
        ox, oy = 0, INFO_H
        for r in range(ROWS):
            for c in range(COLS):
                t = self.map[r][c]
                x, y = c * CELL + ox, r * CELL + oy
                if t == BRICK:
                    pygame.draw.rect(s, (150, 90, 40), (x, y, CELL, CELL))
                    pygame.draw.rect(s, (190, 120, 55), (x + 2, y + 2, CELL - 4, CELL - 4))
                    pygame.draw.line(s, (120, 70, 30), (x + 2, y + CELL // 2 - 1),
                                     (x + CELL - 2, y + CELL // 2 - 1), 1)
                    pygame.draw.line(s, (120, 70, 30), (x + CELL // 2 - 1, y + 2),
                                     (x + CELL // 2 - 1, y + CELL // 2 - 2), 1)
                    pygame.draw.line(s, (120, 70, 30), (x + CELL // 4, y + CELL // 2),
                                     (x + CELL // 4, y + CELL - 2), 1)
                    pygame.draw.line(s, (120, 70, 30), (x + 3 * CELL // 4, y + CELL // 2),
                                     (x + 3 * CELL // 4, y + CELL - 2), 1)
                elif t == STEEL:
                    pygame.draw.rect(s, (190, 190, 195), (x, y, CELL, CELL))
                    pygame.draw.rect(s, (150, 150, 155), (x + 3, y + 3, CELL - 6, CELL - 6))
                    pygame.draw.line(s, (240, 240, 250), (x + 3, y + 3),
                                     (x + CELL - 3, y + CELL - 3), 2)
                    pygame.draw.line(s, (240, 240, 250), (x + CELL - 3, y + 3),
                                     (x + 3, y + CELL - 3), 2)
                elif t == WATER:
                    pygame.draw.rect(s, (30, 90, 160), (x, y, CELL, CELL))
                    off = int(self.time * 6) % 4
                    for i in range(3):
                        yy = y + 8 + i * 12 + (0 if i % 2 == 0 else off)
                        pygame.draw.line(s, (80, 160, 220), (x + 2, yy),
                                         (x + CELL - 2, yy), 2)
                elif t == BASE:
                    draw_eagle(s, x, y)
        pygame.draw.rect(s, (90, 90, 90), (ox, oy, MAP_W, MAP_H), 2)

    def draw_info(self):
        s = self.screen
        pygame.draw.rect(s, (30, 30, 30), (0, 0, SCREEN_W, INFO_H))
        pygame.draw.line(s, (100, 100, 100), (0, INFO_H), (SCREEN_W, INFO_H), 2)
        items = [
            f"分数 {self.score}",
            f"生命 {self.lives}",
            f"剩余 {self.enemy_left_total + len(self.enemies)}",
            f"波次 {self.wave}",
        ]
        x = 12
        for it in items:
            img = self.font_small.render(it, True, (255, 255, 255))
            s.blit(img, (x, 20))
            x += img.get_width() + 24

    def overlay(self, alpha=170):
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, alpha))
        self.screen.blit(ov, (0, 0))

    def draw_start(self):
        self.overlay()
        title = self.font_big.render("坦 克 大 战", True, (255, 220, 60))
        self.screen.blit(title, title.get_rect(center=(SCREEN_W // 2, 140)))
        lines = [
            "移动：方向键 / WASD",
            "开火：空格键",
            "暂停：ESC 或 P",
            "",
            "保护基地，消灭所有敌人！",
            "砖墙可摧毁，钢板不可摧毁",
            "",
            "按 Enter 开始游戏",
        ]
        y = 215
        for line in lines:
            img = self.font_small.render(line, True, (255, 255, 255))
            self.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, y)))
            y += 32

    def draw_pause(self):
        self.overlay(120)
        img = self.font_mid.render("暂停中（按 P 或 ESC 继续）", True, (255, 255, 255))
        self.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2)))

    def draw_gameover(self):
        self.overlay()
        t1 = self.font_big.render("游 戏 结 束", True, (255, 80, 80))
        t2 = self.font_mid.render(f"最终得分：{self.score}", True, (255, 255, 255))
        t3 = self.font_small.render("按 Enter 重新开始", True, (200, 200, 200))
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W // 2, 220)))
        self.screen.blit(t2, t2.get_rect(center=(SCREEN_W // 2, 290)))
        self.screen.blit(t3, t3.get_rect(center=(SCREEN_W // 2, 350)))

    def draw_victory(self):
        self.overlay()
        t1 = self.font_big.render("胜 利 ！", True, (80, 255, 80))
        t2 = self.font_mid.render(f"得分：{self.score}    波次：{self.wave}", True, (255, 255, 255))
        t3 = self.font_small.render("按 Enter 挑战下一波", True, (200, 200, 200))
        self.screen.blit(t1, t1.get_rect(center=(SCREEN_W // 2, 220)))
        self.screen.blit(t2, t2.get_rect(center=(SCREEN_W // 2, 290)))
        self.screen.blit(t3, t3.get_rect(center=(SCREEN_W // 2, 350)))

    # ---------- 主循环 ----------
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            self.time += dt

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        if self.state in ("play", "pause"):
                            self.state = "pause" if self.state == "play" else "play"
                    elif event.key == pygame.K_RETURN:
                        if self.state == "start":
                            self.reset(1)
                        elif self.state == "victory":
                            self.reset(self.wave + 1)
                        elif self.state == "gameover":
                            self.reset(1)

            keys = pygame.key.get_pressed()
            if self.state == "play":
                self.update(dt, keys)

            self.draw()
            pygame.display.flip()


if __name__ == "__main__":
    BattleCity().run()
