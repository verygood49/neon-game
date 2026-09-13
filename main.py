import os
import sys
import math
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel, LabelBase
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.uix.widget import Widget

# ---------- 资源路径 ----------
def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


ASSET_DIR = resource_path('assets')
FONT_NAME = 'Roboto'

# 中文字体（可选）：把任意中文字体放到 assets/fonts/main.ttf 即可
_font_path = os.path.join(ASSET_DIR, 'fonts', 'main.ttf')
if os.path.exists(_font_path):
    LabelBase.register(name='CJK', fn_regular=_font_path)
    FONT_NAME = 'CJK'

IMG_NAMES = [
    'player', 'enemy_scout', 'enemy_gunner', 'enemy_raider',
    'boss', 'pu_triple', 'pu_shield', 'pu_life',
]


def hex_rgba(h, a=1.0):
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0, a)


def lerp_rgba(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(c1[i] + (c2[i] - c1[i]) * t for i in range(4))


def poly_pts(cx, cy, r, sides, rot=0):
    pts = []
    for i in range(sides):
        a = rot + i * math.tau / sides
        pts.extend([cx + math.cos(a) * r, cy + math.sin(a) * r])
    return pts


class GameWidget(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 加载图片纹理
        self.textures = {}
        for name in IMG_NAMES:
            path = os.path.join(ASSET_DIR, name + '.png')
            if os.path.exists(path):
                try:
                    self.textures[name] = CoreImage(path).texture
                except Exception as e:
                    print(f"[资源] {path} 加载失败：{e}")
        missing = [k for k in IMG_NAMES if k not in self.textures]
        if missing:
            print(f"未找到图片，用矢量图形代替：{missing}")

        self.keys = set()
        self.touch_x = None
        self.S = 1.0
        self._inited = False
        self._text_cache = {}

        Window.bind(on_key_down=self._on_kd, on_key_up=self._on_ku)

        Clock.schedule_once(self._try_init, 0)
        Clock.schedule_interval(self._tick, 1 / 60)

    # ---------------- 初始化 ----------------
    def _try_init(self, dt):
        if self.width < 10 or self.height < 10:
            Clock.schedule_once(self._try_init, 0.05)
            return
        self.S = min(self.width / 1000.0, self.height / 720.0)
        self.init_game()
        self._inited = True

    def init_game(self):
        S = self.S
        W, H = self.width, self.height

        self.stars = [{
            'x': random.uniform(0, W),
            'y': random.uniform(0, H),
            'spd': random.uniform(30, 220) * S,
            'r': random.uniform(0.6, 2.2) * S,
            'b': random.uniform(0.3, 1.0),
        } for _ in range(160)]

        self.player = {
            'x': W / 2, 'y': 110 * S,
            'r': 12 * S,
            'cooldown': 0,
            'invuln': 1.5,
            'shield': 0,
            'triple': 0,
            'lives': 3,
        }

        self.bullets = []
        self.ebullets = []
        self.enemies = []
        self.particles = []
        self.powerups = []
        self.floats = []

        self.score = 0
        self.wave = 0
        self.spawn_timer = 1.2
        self.wave_timer = 0
        self.shake = 0.0
        self.state = 'playing'
        self.boss = None
        self.boss_waves = set()
        self.ox = 0.0
        self.oy = 0.0

    # ---------------- 输入 ----------------
    KEY_MAP = {
        276: 'left', 275: 'right', 273: 'up', 274: 'down',
        97: 'a', 100: 'd', 119: 'w', 115: 's',
        32: 'space',
    }

    def _on_kd(self, win, key, *args):
        if key in (112, 27):        # P / Esc 暂停
            if self.state == 'playing':
                self.state = 'paused'
            elif self.state == 'paused':
                self.state = 'playing'
        elif key == 114:           # R 重开
            if self.state == 'over':
                self.init_game()
        elif key in self.KEY_MAP:
            self.keys.add(self.KEY_MAP[key])

    def _on_ku(self, win, key, *args):
        if key in self.KEY_MAP:
            self.keys.discard(self.KEY_MAP[key])

    def on_touch_down(self, touch):
        if self.state == 'over':
            self.init_game()
            return True
        self.touch_x = touch.x
        return True

    def on_touch_move(self, touch):
        if self.touch_x is not None:
            self.touch_x = touch.x
        return True

    def on_touch_up(self, touch):
        return True   # 手指松开，飞船停在原位

    # ---------------- 主循环 ----------------
    def _tick(self, dt):
        if not self._inited:
            return
        self.update(dt)
        self.draw()

    def update(self, dt):
        S = self.S
        W, H = self.width, self.height

        # 星空滚动
        for s in self.stars:
            s['y'] -= s['spd'] * dt
            if s['y'] < 0:
                s['y'] = H
                s['x'] = random.uniform(0, W)

        if self.state != 'playing':
            self.update_particles(dt)
            self.update_floats(dt)
            if self.shake > 0:
                self.shake = max(0.0, self.shake - dt * 24)
            return

        self.update_player(dt)
        self.update_bullets(dt)
        self.update_enemies(dt)
        self.update_boss(dt)
        self.update_ebullets(dt)
        self.update_particles(dt)
        self.update_floats(dt)
        self.update_powerups(dt)

        self.spawn_timer -= dt
        self.wave_timer += dt
        if self.wave_timer > 18:
            self.wave_timer = 0
            self.wave += 1

        # 每 5 波出现 BOSS
        if (self.wave + 1) % 5 == 0 and self.boss is None and self.wave not in self.boss_waves:
            self.spawn_boss()
            self.boss_waves.add(self.wave)
            self.add_float(W / 2, H / 2, "BOSS", '#ff3366')
            self.shake = 12 * S

        if self.spawn_timer <= 0:
            if self.boss is None:
                self.spawn_enemy()
                base = max(0.35, 1.2 - self.wave * 0.12)
                self.spawn_timer = base * random.uniform(0.7, 1.3)
            else:
                self.spawn_timer = 0.5

        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 24)

    # ---------------- 玩家 ----------------
    def update_player(self, dt):
        S = self.S
        W, H = self.width, self.height
        p = self.player

        spd = 420 * S
        dx = dy = 0
        if 'left' in self.keys or 'a' in self.keys:
            dx -= 1
        if 'right' in self.keys or 'd' in self.keys:
            dx += 1
        if 'up' in self.keys or 'w' in self.keys:
            dy += 1
        if 'down' in self.keys or 's' in self.keys:
            dy -= 1

        # 触屏优先：水平跟随手指
        if self.touch_x is not None:
            target = max(p['r'] + 8, min(W - p['r'] - 8, self.touch_x))
            p['x'] += (target - p['x']) * min(1.0, dt * 18)
        else:
            if dx and dy:
                dx *= 0.7071
                dy *= 0.7071
            p['x'] += dx * spd * dt
            p['y'] += dy * spd * dt

        r = p['r']
        p['x'] = max(r + 8, min(W - r - 8, p['x']))
        p['y'] = max(r + 8, min(H - r - 8, p['y']))

        # 引擎尾焰
        if random.random() < 0.7:
            self.particles.append({
                'x': p['x'] + random.uniform(-3, 3) * S,
                'y': p['y'] - r * 0.9,
                'vx': random.uniform(-30, 30) * S,
                'vy': random.uniform(-220, -120) * S,
                'life': 0.3, 'max': 0.3,
                'color': random.choice(['#3ec6ff', '#5ee8ff', '#a06bff']),
                'size': random.uniform(1.2, 2.6) * S,
            })

        # 自动开火
        p['cooldown'] -= dt
        if p['cooldown'] <= 0:
            p['cooldown'] = 0.11
            self.fire()

        if p['invuln'] > 0:
            p['invuln'] -= dt
        if p['triple'] > 0:
            p['triple'] -= dt

    def fire(self):
        S = self.S
        p = self.player
        sp = 820 * S
        angles = [math.pi / 2]
        if p['triple'] > 0:
            angles = [math.pi / 2 - 0.17, math.pi / 2, math.pi / 2 + 0.17]
        for a in angles:
            self.bullets.append({
                'x': p['x'], 'y': p['y'] + p['r'],
                'vx': math.cos(a) * sp,
                'vy': math.sin(a) * sp,
                'r': 3 * S, 'life': 2.0,
            })

    def update_bullets(self, dt):
        W, H = self.width, self.height
        for b in self.bullets:
            b['x'] += b['vx'] * dt
            b['y'] += b['vy'] * dt
            b['life'] -= dt
        self.bullets = [b for b in self.bullets if b['life'] > 0 and
                        -50 < b['y'] < H + 50 and -50 < b['x'] < W + 50]

        for b in self.bullets[:]:
            for e in self.enemies[:]:
                ddx = b['x'] - e['x']
                ddy = b['y'] - e['y']
                if ddx * ddx + ddy * ddy < (b['r'] + e['r']) ** 2:
                    e['hp'] -= 1
                    e['flash'] = 1.0
                    if e['hp'] <= 0:
                        self.kill_enemy(e)
                    else:
                        self.burst(e['x'], e['y'], e['color'], 5)
                    if b in self.bullets:
                        self.bullets.remove(b)
                    break

        if self.boss and not self.boss['entering']:
            bb = self.boss
            for b in self.bullets[:]:
                ddx = b['x'] - bb['x']
                ddy = b['y'] - bb['y']
                if ddx * ddx + ddy * ddy < (bb['r'] * 0.85) ** 2:
                    bb['hp'] -= 1
                    bb['flash'] = 1.0
                    self.burst(b['x'], b['y'], bb['color'], 4)
                    if b in self.bullets:
                        self.bullets.remove(b)
                    if bb['hp'] <= 0:
                        self.kill_boss()
                    break

    # ---------------- 敌人 ----------------
    def spawn_enemy(self):
        S = self.S
        W, H = self.width, self.height
        roll = random.random()
        w = self.wave
        if roll < max(0.35, 0.8 - w * 0.06):
            self.enemies.append({
                'x': random.uniform(60 * S, W - 60 * S),
                'y': H + 30 * S,
                'vx': random.uniform(-40, 40) * S,
                'vy': random.uniform(110, 170) * S * (1 + w * 0.04),
                'r': 16 * S, 'hp': 1,
                'color': '#5ee86a', 'score': 100,
                'flash': 0.0, 'shape': 'diamond', 't': 0.0,
                'img': 'enemy_scout',
            })
        elif roll < 0.85:
            self.enemies.append({
                'x': random.uniform(80 * S, W - 80 * S),
                'y': H + 40 * S,
                'vx': random.uniform(-25, 25) * S,
                'vy': random.uniform(65, 95) * S * (1 + w * 0.03),
                'r': 22 * S, 'hp': 2 + w // 3,
                'color': '#ff7a3d', 'score': 250,
                'flash': 0.0, 'shape': 'hexagon',
                'fire_rate': max(0.9, 2.0 - w * 0.12),
                'fire_cd': random.uniform(0.5, 1.5),
                't': 0.0,
                'img': 'enemy_gunner',
            })
        else:
            self.enemies.append({
                'x': random.uniform(60 * S, W - 60 * S),
                'y': H + 30 * S,
                'vx': 0.0,
                'vy': random.uniform(200, 260) * S * (1 + w * 0.05),
                'r': 13 * S, 'hp': 1,
                'color': '#ff3366', 'score': 180,
                'flash': 0.0, 'shape': 'triangle',
                'zigzag': True, 't': 0.0,
                'img': 'enemy_raider',
            })

    def update_enemies(self, dt):
        S = self.S
        W, H = self.width, self.height

        for e in self.enemies:
            e['y'] -= e['vy'] * dt
            e['x'] += e['vx'] * dt
            e['t'] += dt
            if e.get('zigzag'):
                e['vx'] = math.sin(e['t'] * 5) * 200 * S
            if e['x'] - e['r'] < 0:
                e['x'] = e['r']
                e['vx'] = abs(e['vx'])
            elif e['x'] + e['r'] > W:
                e['x'] = W - e['r']
                e['vx'] = -abs(e['vx'])

            if e.get('fire_rate'):
                e['fire_cd'] -= dt
                if e['fire_cd'] <= 0 and e['y'] > 150 * S:
                    e['fire_cd'] = e['fire_rate'] * random.uniform(0.8, 1.2)
                    self.enemy_shoot(e)

            if e['flash'] > 0:
                e['flash'] = max(0.0, e['flash'] - dt * 6)

        self.enemies = [e for e in self.enemies if e['y'] >= -40 * S]

        p = self.player
        for e in self.enemies[:]:
            ddx = e['x'] - p['x']
            ddy = e['y'] - p['y']
            if ddx * ddx + ddy * ddy < (e['r'] * 0.75 + p['r'] * 0.7) ** 2:
                if p['invuln'] <= 0:
                    self.damage_player()
                e['hp'] -= 3
                if e['hp'] <= 0:
                    self.kill_enemy(e)

    def kill_enemy(self, e):
        S = self.S
        if e in self.enemies:
            self.enemies.remove(e)
        self.score += e['score']
        self.add_float(e['x'], e['y'], f"+{e['score']}", '#ffffff')
        self.burst(e['x'], e['y'], e['color'], 18)
        self.shake = min(8 * S, self.shake + 2 * S)
        if random.random() < 0.40:
            kind = random.choice(['triple', 'triple', 'shield', 'life'])
            self.powerups.append({'x': e['x'], 'y': e['y'],
                                  'vy': -110 * S, 'kind': kind})

    def enemy_shoot(self, e):
        p = self.player
        dx = p['x'] - e['x']
        dy = p['y'] - e['y']
        d = math.hypot(dx, dy) or 1
        sp = 320 * self.S
        self.ebullets.append({
            'x': e['x'], 'y': e['y'] - e['r'],
            'vx': dx / d * sp, 'vy': dy / d * sp,
            'r': 5 * self.S, 'life': 5.0,
        })

    # ---------------- BOSS ----------------
    def spawn_boss(self):
        S = self.S
        hp = 40 + self.wave * 8
        self.boss = {
            'x': self.width / 2,
            'y': self.height + 150 * S,
            'vx': 130 * S,
            'vy': -90 * S,
            'r': 80 * S,
            'hp': hp, 'max_hp': hp,
            'color': '#a06bff',
            'flash': 0.0,
            'entering': True,
            'fire_cd': 1.5,
            'pattern_cd': 3.5,
            'pattern_index': 0,
            'score': 2000 + self.wave * 100,
        }

    def update_boss(self, dt):
        b = self.boss
        if not b:
            return
        S = self.S
        W, H = self.width, self.height

        if b['entering']:
            b['y'] += b['vy'] * dt
            if b['y'] <= H - 150 * S:
                b['y'] = H - 150 * S
                b['entering'] = False
            return

        # 入场后高度锁定，只左右移动
        b['y'] = H - 150 * S
        b['x'] += b['vx'] * dt
        if b['x'] - b['r'] < 20 * S:
            b['x'] = 20 * S + b['r']
            b['vx'] = abs(b['vx'])
        elif b['x'] + b['r'] > W - 20 * S:
            b['x'] = W - 20 * S - b['r']
            b['vx'] = -abs(b['vx'])

        if b['flash'] > 0:
            b['flash'] = max(0.0, b['flash'] - dt * 6)

        b['fire_cd'] -= dt
        if b['fire_cd'] <= 0:
            b['fire_cd'] = max(0.55, 1.4 - self.wave * 0.05)
            self.boss_shoot(b)

        b['pattern_cd'] -= dt
        if b['pattern_cd'] <= 0:
            b['pattern_cd'] = 4.0
            b['pattern_index'] = (b['pattern_index'] + 1) % 3
            self.boss_pattern(b)

        p = self.player
        ddx = p['x'] - b['x']
        ddy = p['y'] - b['y']
        if ddx * ddx + ddy * ddy < (b['r'] * 0.75 + p['r']) ** 2:
            if p['invuln'] <= 0:
                self.damage_player()

        if b['y'] < -300 * S or b['y'] > H + 300 * S:
            self.boss = None

    def boss_shoot(self, b):
        p = self.player
        dx = p['x'] - b['x']
        dy = p['y'] - b['y']
        sp = 380 * self.S
        for off in (-0.18, 0, 0.18):
            a = math.atan2(dy, dx) + off
            self.ebullets.append({
                'x': b['x'], 'y': b['y'] - b['r'] * 0.5,
                'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                'r': 6 * self.S, 'life': 5.0,
            })

    def boss_pattern(self, b):
        idx = b['pattern_index']
        sp = 300 * self.S
        if idx == 0:
            n = 16
            for i in range(n):
                a = i * math.tau / n
                self.ebullets.append({
                    'x': b['x'], 'y': b['y'],
                    'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                    'r': 6 * self.S, 'life': 5.0,
                })
        elif idx == 1:
            for off in range(-3, 4):
                a = -math.pi / 2 + off * 0.16
                self.ebullets.append({
                    'x': b['x'], 'y': b['y'] - b['r'] * 0.5,
                    'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                    'r': 6 * self.S, 'life': 5.0,
                })
        else:
            p = self.player
            dx = p['x'] - b['x']
            dy = p['y'] - b['y']
            base = math.atan2(dy, dx)
            for off in (-0.3, -0.15, 0, 0.15, 0.3):
                a = base + off
                self.ebullets.append({
                    'x': b['x'], 'y': b['y'] - b['r'] * 0.4,
                    'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                    'r': 6 * self.S, 'life': 5.0,
                })

    def kill_boss(self):
        b = self.boss
        if not b:
            return
        S = self.S
        self.score += b['score']
        self.add_float(b['x'], b['y'], f"+{b['score']}", '#ffd23f')
        for _ in range(3):
            self.burst(b['x'] + random.uniform(-60, 60) * S,
                       b['y'] + random.uniform(-40, 40) * S,
                       b['color'], 35)
        self.shake = 24 * S
        for _ in range(4):
            kind = random.choice(['triple', 'shield', 'life'])
            self.powerups.append({
                'x': b['x'] + random.uniform(-80, 80) * S,
                'y': b['y'] + random.uniform(-30, 30) * S,
                'vy': -110 * S, 'kind': kind,
            })
        self.boss = None

    def update_ebullets(self, dt):
        W, H = self.width, self.height
        for b in self.ebullets:
            b['x'] += b['vx'] * dt
            b['y'] += b['vy'] * dt
            b['life'] -= dt
        self.ebullets = [b for b in self.ebullets if b['life'] > 0 and
                         -50 < b['x'] < W + 50 and -50 < b['y'] < H + 50]

        p = self.player
        for b in self.ebullets[:]:
            ddx = b['x'] - p['x']
            ddy = b['y'] - p['y']
            if ddx * ddx + ddy * ddy < (b['r'] + p['r'] * 0.7) ** 2:
                self.ebullets.remove(b)
                if p['invuln'] <= 0:
                    self.damage_player()

    def damage_player(self):
        S = self.S
        p = self.player
        if p['shield'] > 0:
            p['shield'] = 0
            p['invuln'] = 1.2
            self.burst(p['x'], p['y'], '#3ec6ff', 22)
            self.add_float(p['x'], p['y'] + 40 * S, 'SHIELD', '#3ec6ff')
            self.shake = 10 * S
            return
        p['lives'] -= 1
        p['invuln'] = 2.0
        self.burst(p['x'], p['y'], '#ff3366', 30)
        self.shake = 14 * S
        if p['lives'] <= 0:
            self.state = 'over'

    # ---------------- 粒子 / 文字 ----------------
    def burst(self, x, y, color, n=10):
        S = self.S
        for _ in range(n):
            a = random.uniform(0, math.tau)
            sp = random.uniform(60, 340) * S
            self.particles.append({
                'x': x, 'y': y,
                'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                'life': random.uniform(0.3, 0.7), 'max': 0.7,
                'color': color,
                'size': random.uniform(1.5, 3.5) * S,
            })

    def update_particles(self, dt):
        for p in self.particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vx'] *= (1 - 1.5 * dt)
            p['vy'] *= (1 - 1.5 * dt)
            p['life'] -= dt
        self.particles = [p for p in self.particles if p['life'] > 0]
        if len(self.particles) > 500:
            del self.particles[:-500]

    def add_float(self, x, y, text, color):
        self.floats.append({'x': x, 'y': y, 'text': text,
                            'color': color, 'life': 0.9})

    def update_floats(self, dt):
        for f in self.floats:
            f['y'] += 55 * dt
            f['life'] -= dt
        self.floats = [f for f in self.floats if f['life'] > 0]

    # ---------------- 道具 ----------------
    def update_powerups(self, dt):
        S = self.S
        p = self.player
        kept = []
        for u in self.powerups:
            u['y'] += u['vy'] * dt
            if u['y'] < -30 * S:
                continue
            ddx = u['x'] - p['x']
            ddy = u['y'] - p['y']
            if ddx * ddx + ddy * ddy < (24 * S + p['r']) ** 2:
                self.apply_powerup(u['kind'], u['x'], u['y'])
                continue
            kept.append(u)
        self.powerups = kept

    def apply_powerup(self, kind, x, y):
        S = self.S
        p = self.player
        if kind == 'triple':
            p['triple'] = 8.0
            self.add_float(x, y + 20 * S, 'TRIPLE', '#ffd23f')
            self.burst(x, y, '#ffd23f', 14)
        elif kind == 'shield':
            p['shield'] = 1
            self.add_float(x, y + 20 * S, 'SHIELD', '#3ec6ff')
            self.burst(x, y, '#3ec6ff', 14)
        elif kind == 'life':
            p['lives'] = min(5, p['lives'] + 1)
            self.add_float(x, y + 20 * S, '+1 LIFE', '#ff3366')
            self.burst(x, y, '#ff3366', 14)

    # ---------------- 绘制 ----------------
    def _text_tex(self, text, color, size):
        key = (text, color, size)
        if key in self._text_cache:
            return self._text_cache[key]
        lbl = CoreLabel(text=text, font_size=size,
                        color=hex_rgba(color), font_name=FONT_NAME,
                        bold=True)
        lbl.refresh()
        self._text_cache[key] = lbl.texture
        if len(self._text_cache) > 150:
            self._text_cache.clear()
            self._text_cache[key] = lbl.texture
        return lbl.texture

    def _draw_text(self, text, x, y, color='#ffffff', size=20, anchor='center'):
        tex = self._text_tex(text, color, size)
        tw, th = tex.size
        Color(1, 1, 1, 1)
        if anchor == 'center':
            Rectangle(texture=tex, pos=(x - tw / 2, y - th / 2), size=tex.size)
        elif anchor == 'left':
            Rectangle(texture=tex, pos=(x, y - th / 2), size=tex.size)
        elif anchor == 'right':
            Rectangle(texture=tex, pos=(x - tw, y - th / 2), size=tex.size)

    def draw(self):
        S = self.S
        W, H = self.width, self.height

        self.ox = self.oy = 0.0
        if self.shake > 0:
            self.ox = random.uniform(-self.shake, self.shake)
            self.oy = random.uniform(-self.shake, self.shake)

        self.canvas.clear()
        with self.canvas:
            Color(*hex_rgba('#050510'))
            Rectangle(pos=(0, 0), size=(W, H))

            # 星空
            for s in self.stars:
                b = s['b']
                Color(120 * b / 255, 180 * b / 255, 255 * b / 255, 1)
                r = s['r']
                Ellipse(pos=(s['x'] - r, s['y'] - r), size=(r * 2, r * 2))

            self._draw_particles()
            self._draw_powerups()
            self._draw_enemies()
            self._draw_boss()
            self._draw_ebullets()
            self._draw_bullets()
            self._draw_player()
            self._draw_floats()
            self._draw_hud()

    def _draw_particles(self):
        bg = hex_rgba('#050510')
        for p in self.particles:
            f = max(0.0, p['life'] / p['max'])
            r = p['size'] * f
            if r < 0.4:
                continue
            col = lerp_rgba(bg, hex_rgba(p['color']), f)
            Color(*col)
            Ellipse(pos=(p['x'] + self.ox - r, p['y'] + self.oy - r),
                    size=(r * 2, r * 2))

    def _draw_bullets(self):
        for b in self.bullets:
            x = b['x'] + self.ox
            y = b['y'] + self.oy
            r = b['r']
            Color(*hex_rgba('#0d3b4a'))
            Ellipse(pos=(x - r * 2.4, y - r * 2.4), size=(r * 4.8, r * 4.8))
            Color(*hex_rgba('#eaffff'))
            Ellipse(pos=(x - r, y - r), size=(r * 2, r * 2))
            Color(*hex_rgba('#5ee8ff'))
            Line(circle=(x, y, r), width=1.5)

    def _draw_ebullets(self):
        for b in self.ebullets:
            x = b['x'] + self.ox
            y = b['y'] + self.oy
            r = b['r']
            Color(*hex_rgba('#4a0d1e'))
            Ellipse(pos=(x - r * 2, y - r * 2), size=(r * 4, r * 4))
            Color(*hex_rgba('#ffd0dd'))
            Ellipse(pos=(x - r, y - r), size=(r * 2, r * 2))
            Color(*hex_rgba('#ff3366'))
            Line(circle=(x, y, r), width=1.5)

    def _draw_enemies(self):
        S = self.S
        for e in self.enemies:
            x = e['x'] + self.ox
            y = e['y'] + self.oy
            r = e['r']

            tex = self.textures.get(e.get('img', ''))
            if tex:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex,
                          pos=(x - tex.width / 2, y - tex.height / 2),
                          size=(tex.width, tex.height))
            else:
                col = hex_rgba(e['color'])
                if e['flash'] > 0:
                    col = lerp_rgba(col, (1, 1, 1, 1), e['flash'] * 0.8)
                shape = e.get('shape', 'diamond')
                if shape == 'diamond':
                    pts = poly_pts(x, y, r, 4, rot=math.pi / 2)
                elif shape == 'hexagon':
                    pts = poly_pts(x, y, r, 6, rot=0)
                else:
                    pts = poly_pts(x, y, r, 3, rot=-math.pi / 2)
                Color(*col)
                Line(points=pts, close=True, width=2 * S)
                Ellipse(pos=(x - r * 0.35, y - r * 0.35),
                        size=(r * 0.7, r * 0.7))

            if e['flash'] > 0:
                Color(1, 1, 1, e['flash'] * 0.8)
                Line(circle=(x, y, r), width=2 * S)

    def _draw_boss(self):
        b = self.boss
        if not b:
            return
        x = b['x'] + self.ox
        y = b['y'] + self.oy
        r = b['r']

        tex = self.textures.get('boss')
        if tex:
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                      pos=(x - tex.width / 2, y - tex.height / 2),
                      size=(tex.width, tex.height))
        else:
            pts = poly_pts(x, y, r, 6, rot=0)
            Color(*hex_rgba('#a06bff'))
            Line(points=pts, close=True, width=3 * self.S)
            Color(*hex_rgba('#c9a2ff'))
            Ellipse(pos=(x - r * 0.35, y - r * 0.35),
                    size=(r * 0.7, r * 0.7))

        if b['flash'] > 0:
            Color(1, 1, 1, b['flash'] * 0.8)
            Line(circle=(x, y, r), width=3 * self.S)

    def _draw_player(self):
        p = self.player
        x = p['x'] + self.ox
        y = p['y'] + self.oy
        r = p['r']

        if p['invuln'] > 0 and int(p['invuln'] * 20) % 2 == 0:
            return

        if p['shield'] > 0:
            Color(*hex_rgba('#3ec6ff'))
            Line(circle=(x, y, r * 1.9), width=2 * self.S)
            Color(*hex_rgba('#7fe0ff'))
            Line(circle=(x, y, r * 1.6), width=1.5)

        tex = self.textures.get('player')
        if tex:
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                      pos=(x - tex.width / 2, y - tex.height / 2),
                      size=(tex.width, tex.height))
        else:
            pts = [x, y + r * 1.4,
                   x - r * 0.9, y - r * 0.9,
                   x, y - r * 0.3,
                   x + r * 0.9, y - r * 0.9]
            Color(*hex_rgba('#5ee8ff'))
            Line(points=pts, close=True, width=2 * self.S)
            Color(*hex_rgba('#ffffff'))
            Ellipse(pos=(x - r * 0.3, y - r * 0.3), size=(r * 0.6, r * 0.6))

    def _draw_powerups(self):
        S = self.S
        cmap = {'triple': '#ffd23f', 'shield': '#3ec6ff', 'life': '#ff3366'}
        imap = {'triple': 'pu_triple', 'shield': 'pu_shield', 'life': 'pu_life'}
        for u in self.powerups:
            x = u['x'] + self.ox
            y = u['y'] + self.oy
            tex = self.textures.get(imap[u['kind']])
            if tex:
                Color(1, 1, 1, 1)
                Rectangle(texture=tex,
                          pos=(x - tex.width / 2, y - tex.height / 2),
                          size=(tex.width, tex.height))
            else:
                Color(*hex_rgba(cmap[u['kind']]))
                Ellipse(pos=(x - 15 * S, y - 15 * S), size=(30 * S, 30 * S))
                Color(1, 1, 1, 1)
                Ellipse(pos=(x - 8 * S, y - 8 * S), size=(16 * S, 16 * S))

    def _draw_floats(self):
        for f in self.floats:
            t = max(0.0, min(1.0, f['life'] / 0.9))
            self._draw_text(f['text'], f['x'] + self.ox,
                            f['y'] + self.oy, f['color'],
                            int(15 * self.S) or 12, 'center')

    def _draw_hud(self):
        S = self.S
        W, H = self.width, self.height

        self._draw_text(f"SCORE {self.score}", 20 * S, H - 30 * S,
                        '#e8f4ff', int(20 * S) or 14, 'left')
        self._draw_text(f"WAVE {self.wave + 1}", W / 2, H - 28 * S,
                        '#ffd23f', int(18 * S) or 13, 'center')

        # 生命：右上角三角形
        for i in range(self.player['lives']):
            cx = W - 32 * S - i * 26 * S
            cy = H - 32 * S
            pts = poly_pts(cx, cy, 11 * S, 3, rot=-math.pi / 2)
            Color(*hex_rgba('#ff3366'))
            Line(points=pts, close=True, width=2)

        if self.player['triple'] > 0:
            self._draw_text(f"TRIPLE {self.player['triple']:.1f}s",
                            W - 28 * S, H - 62 * S,
                            '#ffd23f', int(14 * S) or 11, 'right')

        if self.boss and not self.boss['entering']:
            b = self.boss
            bar_w = min(440 * S, W * 0.55)
            bar_h = 14 * S
            bx = W / 2 - bar_w / 2
            by = H - 90 * S
            ratio = max(0.0, b['hp'] / b['max_hp'])
            self._draw_text("BOSS", W / 2, by + 24 * S,
                            '#ff3366', int(15 * S) or 11, 'center')
            Color(*hex_rgba('#2a0a2e'))
            Rectangle(pos=(bx, by), size=(bar_w, bar_h))
            Color(*hex_rgba('#a06bff'))
            Line(rectangle=(bx, by, bar_w, bar_h), width=2)
            Color(*hex_rgba('#ff3366'))
            Rectangle(pos=(bx, by), size=(bar_w * ratio, bar_h))

        if self.state == 'paused':
            Color(0, 0, 0, 0.7)
            Rectangle(pos=(0, 0), size=(W, H))
            self._draw_text("PAUSED", W / 2, H / 2,
                            '#5ee8ff', int(32 * S) or 22, 'center')
        elif self.state == 'over':
            Color(0, 0, 0, 0.75)
            Rectangle(pos=(0, 0), size=(W, H))
            self._draw_text("GAME OVER", W / 2, H / 2 + 30 * S,
                            '#ff3366', int(42 * S) or 28, 'center')
            self._draw_text(f"SCORE {self.score}", W / 2, H / 2 - 20 * S,
                            '#ffffff', int(24 * S) or 16, 'center')
            self._draw_text("TAP TO RESTART", W / 2, H / 2 - 60 * S,
                            '#5ee8ff', int(18 * S) or 13, 'center')


class NeonApp(App):
    def build(self):
        self.title = "Neon Annihilator"
        Window.clearcolor = (0.02, 0.02, 0.06, 1)
        return GameWidget()


if __name__ == '__main__':
    NeonApp().run()
