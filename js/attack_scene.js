class AttackScene extends Phaser.Scene {
    constructor() {
        super({ key: 'AttackScene' });
    }

    preload() {
        this.load.image('mapBg', 'map_bg.png');
    }

    create() {
        this.mapWidth = 832;
        this.mapHeight = 1248;
        this.add.image(0, 0, 'mapBg').setOrigin(0, 0);

        this.buildings = this.add.group();
        this.troops = this.add.group();
        this.projectiles = this.add.group();

        // Load current base for attacking
        this.setupDefenderBase();

        this.cameras.main.setBounds(0, 0, this.mapWidth, this.mapHeight);
        this.cameras.main.setZoom(0.6);
        this.cameras.main.centerOn(this.mapWidth/2, this.mapHeight/2);

        this.input.on('pointerdown', (pointer) => {
            this.spawnTroop(pointer.worldX, pointer.worldY);
        });

        this.add.text(10, 10, 'انقر لنشر الجنود (النموذج الأولي للهجوم)', {
            fontSize: '20px',
            fill: '#fff',
            backgroundColor: '#000'
        }).setScrollFactor(0);
    }

    setupDefenderBase() {
        if (!window.buildings) return;

        window.buildings.forEach(b => {
            const def = BUILDING_DATA[b.type];
            if (!def) return;

            const x = b.col * 41.6 + (def.size * 41.6) / 2;
            const y = b.row * 41.6 + (def.size * 41.6) / 2;

            const container = this.add.container(x, y);
            const graphics = this.add.graphics();

            // Draw simplified building
            graphics.fillStyle(0xdc2626, 0.8);
            graphics.fillRect(-(def.size * 41.6)/2, -(def.size * 41.6)/2, def.size * 41.6, def.size * 41.6);
            container.add(graphics);

            container.setData('health', def.health || 500);
            container.setData('type', b.type);
            container.setData('isDefensive', !!def.range);
            container.setData('range', def.range * 41.6 || 0);
            container.setData('damage', def.damage || 0);
            container.setData('lastFireTime', 0);

            this.buildings.add(container);
        });
    }

    spawnTroop(x, y) {
        const troop = this.add.container(x, y);
        const graphics = this.add.graphics();
        graphics.fillStyle(0x22c55e, 1);
        graphics.fillCircle(0, 0, 10);
        troop.add(graphics);

        troop.setData('health', 100);
        troop.setData('speed', 100); // px per second
        this.troops.add(troop);
    }

    update(time, delta) {
        // Troops Logic
        this.troops.getChildren().forEach(troop => {
            const target = this.findNearestTarget(troop, this.buildings);
            if (target) {
                const angle = Phaser.Math.Angle.Between(troop.x, troop.y, target.x, target.y);
                const distance = Phaser.Math.Distance.Between(troop.x, troop.y, target.x, target.y);

                if (distance > 30) {
                    troop.x += Math.cos(angle) * (troop.getData('speed') * delta / 1000);
                    troop.y += Math.sin(angle) * (troop.getData('speed') * delta / 1000);
                } else {
                    // Attack building
                    target.setData('health', target.getData('health') - 1);
                    if (target.getData('health') <= 0) {
                        target.destroy();
                    }
                }
            }
        });

        // Defensive Buildings Logic
        this.buildings.getChildren().forEach(b => {
            if (b.getData('isDefensive')) {
                const target = this.findNearestTarget(b, this.troops);
                if (target) {
                    const distance = Phaser.Math.Distance.Between(b.x, b.y, target.x, target.y);
                    if (distance <= b.getData('range')) {
                        const now = time;
                        if (now - b.getData('lastFireTime') > 1000) {
                            this.fireProjectile(b, target);
                            b.setData('lastFireTime', now);
                        }
                    }
                }
            }
        });

        // Projectiles Logic
        this.projectiles.getChildren().forEach(p => {
            const target = p.getData('target');
            if (!target.active) {
                p.destroy();
                return;
            }

            const angle = Phaser.Math.Angle.Between(p.x, p.y, target.x, target.y);
            p.x += Math.cos(angle) * 300 * delta / 1000;
            p.y += Math.sin(angle) * 300 * delta / 1000;

            if (Phaser.Math.Distance.Between(p.x, p.y, target.x, target.y) < 10) {
                target.setData('health', target.getData('health') - 10);
                if (target.getData('health') <= 0) target.destroy();
                p.destroy();
            }
        });
    }

    findNearestTarget(source, group) {
        let closest = null;
        let minDistance = Infinity;

        group.getChildren().forEach(target => {
            const dist = Phaser.Math.Distance.Between(source.x, source.y, target.x, target.y);
            if (dist < minDistance) {
                minDistance = dist;
                closest = target;
            }
        });
        return closest;
    }

    fireProjectile(source, target) {
        const p = this.add.circle(source.x, source.y, 5, 0xffff00);
        p.setData('target', target);
        this.projectiles.add(p);
    }
}
