class BaseScene extends Phaser.Scene {
    constructor() {
        super({ key: 'BaseScene' });
        this.gridSize = 41.6; // Based on 832/20
        this.cols = 20;
        this.rows = 25;
        this.mapWidth = 832;
        this.mapHeight = 1248;
    }

    preload() {
        this.load.image('mapBg', 'map_bg.png');
    }

    create() {
        this.mapContainer = this.add.container(0, 0);

        // Background
        const bg = this.add.image(0, 0, 'mapBg').setOrigin(0, 0);
        this.mapContainer.add(bg);

        // Grid
        this.drawGrid();

        // Buildings Layer
        this.buildingsGroup = this.add.group();
        this.mapContainer.add(this.buildingsGroup.getChildren());

        // Setup Camera
        this.setupCamera();

        // Ghost building for placement
        this.ghost = this.add.graphics();
        this.ghost.setAlpha(0.5);
        this.mapContainer.add(this.ghost);
        this.ghost.setVisible(false);

        // UI Layer (Non-moving)
        this.setupUI();

        // Load existing buildings
        this.loadBuildings();

        this.input.on('pointerdown', this.onPointerDown, this);
        this.input.on('pointermove', this.onPointerMove, this);
        this.input.on('pointerup', this.onPointerUp, this);
    }

    drawGrid() {
        const graphics = this.add.graphics();
        graphics.lineStyle(1, 0xffffff, 0.08);

        for (let x = 0; x <= this.mapWidth; x += this.gridSize) {
            graphics.moveTo(x, 0);
            graphics.lineTo(x, this.mapHeight);
        }
        for (let y = 0; y <= this.mapHeight; y += this.gridSize) {
            graphics.moveTo(0, y);
            graphics.lineTo(this.mapWidth, y);
        }
        graphics.strokePath();
        this.mapContainer.add(graphics);
    }

    setupCamera() {
        this.cameras.main.setBounds(0, 0, this.mapWidth, this.mapHeight);
        this.cameras.main.setZoom(0.8);
        this.cameras.main.centerOn(this.mapWidth / 2, this.mapHeight / 2);

        this.input.on('wheel', (pointer, gameObjects, deltaX, deltaY, deltaZ) => {
            const newZoom = this.cameras.main.zoom - deltaY * 0.001;
            this.cameras.main.setZoom(Phaser.Math.Clamp(newZoom, 0.4, 2));
        });
    }

    setupUI() {
        // We will keep HTML UI for menus, but Phaser can handle some tooltips
    }

    loadBuildings() {
        this.buildingsGroup.clear(true, true);
        if (window.buildings) {
            window.buildings.forEach(b => {
                this.addBuildingToMap(b);
            });
        }
    }

    addBuildingToMap(data) {
        const def = BUILDING_DATA[data.type];
        if (!def) return;

        const x = data.col * this.gridSize;
        const y = data.row * this.gridSize;
        const width = def.size * this.gridSize;
        const height = def.size * this.gridSize;

        const container = this.add.container(x, y);
        container.setData('id', data.id);

        // Procedural Graphic
        const shape = this.add.graphics();
        this.drawBuildingGraphic(shape, data.type, width, height);
        container.add(shape);

        // Level text
        if (!data.is_constructing) {
            const lvl = this.add.text(width - 5, -5, data.level, {
                fontSize: '10px',
                fontFamily: 'Orbitron',
                backgroundColor: '#fbbf24',
                color: '#000',
                padding: { x: 3, y: 1 }
            }).setOrigin(1, 0);
            container.add(lvl);
        } else {
            // Construction UI
            const progressBarBg = this.add.graphics();
            progressBarBg.fillStyle(0x000000, 0.5);
            progressBarBg.fillRect(5, height - 15, width - 10, 8);
            container.add(progressBarBg);

            const progressBar = this.add.graphics();
            container.add(progressBar);
            container.setData('progressBar', progressBar);
            container.setData('finishTime', data.finish_time);
            container.setData('totalTime', def.buildTime * 1000);
        }

        container.setInteractive(new Phaser.Geom.Rectangle(0, 0, width, height), Phaser.Geom.Rectangle.Contains);
        container.on('pointerdown', () => {
            if (!window.buildMode) {
                if (data.is_constructing) {
                    this.showInstantCompleteModal(data);
                } else {
                    window.openUpgradePanel(data);
                }
            }
        });

        this.buildingsGroup.add(container);
        this.mapContainer.add(container);
    }

    update(time, delta) {
        // Update progress bars
        this.buildingsGroup.getChildren().forEach(container => {
            const finishTime = container.getData('finishTime');
            if (finishTime) {
                const now = Date.now();
                const finish = new Date(finishTime).getTime();
                const total = container.getData('totalTime') || 300000;
                const remaining = finish - now;

                if (remaining <= 0) {
                    // Construction finished
                    // Ideally we should reload or update the specific building
                } else {
                    const progressBar = container.getData('progressBar');
                    const width = container.input.hitArea.width;
                    const height = container.input.hitArea.height;
                    const progress = 1 - (remaining / total); // This needs the original start time to be accurate

                    progressBar.clear();
                    progressBar.fillStyle(0x22c55e, 1);
                    progressBar.fillRect(5, height - 15, (width - 10) * Phaser.Math.Clamp(progress, 0, 1), 8);
                }
            }
        });
    }

    showInstantCompleteModal(data) {
        // Calculate cost based on remaining time
        const now = Date.now();
        const finish = new Date(data.finish_time).getTime();
        const remainingMinutes = Math.ceil((finish - now) / 60000);
        const cost = remainingMinutes * 10; // 10 gold per minute

        if (confirm(`هل تريد إنهاء البناء فوراً مقابل ${cost} ذهب؟`)) {
            this.instantComplete(data.id, cost);
        }
    }

    async instantComplete(bId, cost) {
        try {
            const response = await fetch(`${window.BACKEND_URL}/buildings/complete-instant`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: window.tg.initDataUnsafe?.user?.id,
                    building_id: bId,
                    cost: cost
                })
            });
            const data = await response.json();
            if (data.status === 'ok') {
                window.showToast('تم إنهاء البناء! 🎉', 'success');
                // Force check-status to refresh everything, it will call loadBuildings()
                window.checkUserStatus();
            } else {
                window.showToast(data.error, 'error');
            }
        } catch (e) {
            window.showToast('خطأ في الاتصال', 'error');
        }
    }

    drawBuildingGraphic(graphics, type, w, h) {
        graphics.lineStyle(2, 0x000000, 0.5);

        let color = 0x71717a;
        let secondaryColor = 0x3f3f46;

        if (type === 'townhall') {
            color = 0x4f46e5; secondaryColor = 0x312e81;
        } else if (type.includes('gold')) {
            color = 0xeab308; secondaryColor = 0x854d0e;
        } else if (type.includes('elixir')) {
            color = 0xdb2777; secondaryColor = 0x831843;
        } else if (type === 'cannon') {
            color = 0x18181b; secondaryColor = 0x52525b;
        } else if (type === 'archerTower') {
            color = 0x78350f; secondaryColor = 0x451a03;
        } else if (type === 'wall') {
            color = 0x52525b; secondaryColor = 0x27272a;
        }

        // Base plate
        graphics.fillStyle(0x333333, 0.4);
        graphics.fillRect(0, 0, w, h);

        // Main body
        graphics.fillStyle(color, 1);
        graphics.fillRoundedRect(4, 4, w - 8, h - 8, 4);
        graphics.strokeRoundedRect(4, 4, w - 8, h - 8, 4);

        // Details based on type
        graphics.fillStyle(secondaryColor, 1);
        if (type === 'townhall') {
            graphics.fillRect(w*0.2, h*0.2, w*0.6, h*0.6);
            graphics.fillStyle(0xffffff, 0.3);
            graphics.fillRect(w*0.3, h*0.3, w*0.4, h*0.1); // Roof highlight
        } else if (type === 'cannon') {
            graphics.fillCircle(w/2, h/2, w*0.3);
            graphics.fillStyle(0x000000, 1);
            graphics.fillCircle(w/2, h/2, w*0.15); // Barrel hole
        } else if (type === 'archerTower') {
            graphics.fillRect(w*0.1, h*0.1, w*0.8, h*0.2); // Top part
            graphics.fillRect(w*0.4, h*0.3, w*0.2, h*0.6); // Pillar
        } else if (type.includes('Storage')) {
            graphics.fillRoundedRect(w*0.2, h*0.2, w*0.6, h*0.6, 2);
            graphics.lineStyle(1, 0xffffff, 0.5);
            graphics.strokeRect(w*0.3, h*0.3, w*0.4, h*0.4);
        } else if (type === 'wall') {
            graphics.fillRect(w*0.1, h*0.4, w*0.8, h*0.2);
        }
    }

    onPointerDown(pointer) {
        if (window.buildMode && window.selectedBuildType) return;
        this.isDragging = true;
        this.dragStartX = pointer.x;
        this.dragStartY = pointer.y;
        this.camStartX = this.cameras.main.scrollX;
        this.camStartY = this.cameras.main.scrollY;
    }

    onPointerMove(pointer) {
        if (this.isDragging) {
            const dx = (this.dragStartX - pointer.x) / this.cameras.main.zoom;
            const dy = (this.dragStartY - pointer.y) / this.cameras.main.zoom;
            this.cameras.main.setScroll(this.camStartX + dx, this.camStartY + dy);
        }

        if (window.buildMode && window.selectedBuildType) {
            this.updateGhost(pointer);
        }
    }

    onPointerUp(pointer) {
        this.isDragging = false;

        if (window.buildMode && window.selectedBuildType && this.ghost.visible) {
            this.placeBuilding(pointer);
        }
    }

    updateGhost(pointer) {
        const worldPoint = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
        const col = Math.floor(worldPoint.x / this.gridSize);
        const row = Math.floor(worldPoint.y / this.gridSize);

        const def = BUILDING_DATA[window.selectedBuildType];
        if (!def) return;

        const size = def.size;

        if (col >= 0 && row >= 0 && col + size <= this.cols && row + size <= this.rows) {
            const x = col * this.gridSize;
            const y = row * this.gridSize;
            const w = size * this.gridSize;
            const h = size * this.gridSize;

            const canPlace = this.checkCollision(col, row, size);

            this.ghost.clear();
            this.ghost.fillStyle(canPlace ? 0x22c55e : 0xef4444, 0.5);
            this.ghost.fillRect(x, y, w, h);
            this.ghost.setVisible(true);

            this.lastValidPos = { col, row, canPlace };
        } else {
            this.ghost.setVisible(false);
        }
    }

    checkCollision(col, row, size) {
        // Simple collision check against existing buildings
        for (let b of window.buildings) {
            const bDef = BUILDING_DATA[b.type];
            if (!bDef) continue;
            const bSize = bDef.size;

            if (!(col + size <= b.col ||
                  col >= b.col + bSize ||
                  row + size <= b.row ||
                  row >= b.row + bSize)) {
                return false;
            }
        }
        return true;
    }

    async placeBuilding(pointer) {
        if (!this.lastValidPos || !this.lastValidPos.canPlace) return;

        const def = BUILDING_DATA[window.selectedBuildType];
        if (window.playerData.gold < def.cost) {
            window.showToast('ذهب غير كافٍ!', 'error');
            return;
        }

        const newBuilding = {
            type: window.selectedBuildType,
            col: this.lastValidPos.col,
            row: this.lastValidPos.row,
            level: 1
        };

        // Call backend
        try {
            const response = await fetch(`${window.BACKEND_URL}/buildings/start-build`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: window.tg.initDataUnsafe?.user?.id,
                    ...newBuilding,
                    cost: def.cost,
                    buildTime: def.buildTime
                })
            });
            const data = await response.json();
            if (data.status === 'ok') {
                newBuilding.id = data.building_id;
                newBuilding.finish_time = data.finish_time;
                newBuilding.is_constructing = data.finish_time ? 1 : 0;
                window.buildings.push(newBuilding);
                window.playerData.gold -= def.cost;
                window.updateUI();
                this.addBuildingToMap(newBuilding);
                window.showToast('تم البدء في البناء! 🎉', 'success');
            } else {
                window.showToast(data.error, 'error');
            }
        } catch (e) {
            window.showToast('خطأ في الاتصال', 'error');
        }
    }
}
