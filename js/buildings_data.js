const BUILDING_DATA = {
    townhall: {
        name: 'قاعة المدينة',
        type: 'townhall',
        size: 4,
        health: 1500,
        cost: 10000,
        buildTime: 300, // 5 minutes
        icon: '🏛️',
        description: 'قلب قاعدتك. ترقيتها تفتح مبانٍ جديدة.'
    },
    cannon: {
        name: 'مدفع',
        type: 'cannon',
        size: 3,
        health: 400,
        cost: 250,
        buildTime: 60,
        icon: '💣',
        description: 'دفاع أساسي ضد القوات الأرضية.',
        range: 7,
        damage: 10
    },
    archerTower: {
        name: 'برج رماة',
        type: 'archerTower',
        size: 3,
        health: 350,
        cost: 300,
        buildTime: 90,
        icon: '🏹',
        description: 'يستهدف القوات البرية والجوية.',
        range: 9,
        damage: 8
    },
    goldStorage: {
        name: 'مخزن ذهب',
        type: 'goldStorage',
        size: 3,
        health: 500,
        cost: 500,
        buildTime: 120,
        icon: '📦',
        description: 'يخزن الذهب الذي يتم جمعه.'
    },
    elixirStorage: {
        name: 'مخزن إكسير',
        type: 'elixirStorage',
        size: 3,
        health: 500,
        cost: 500,
        buildTime: 120,
        icon: '💧',
        description: 'يخزن الإكسير اللازم للتدريب.'
    },
    wall: {
        name: 'جدار',
        type: 'wall',
        size: 1,
        health: 1000,
        cost: 50,
        buildTime: 0,
        icon: '🧱',
        description: 'دفاع سلبي يبطئ الأعداء.'
    },
    decoration: {
        name: 'زينة',
        type: 'decoration',
        size: 1,
        health: 10,
        cost: 100,
        buildTime: 0,
        icon: '🌲',
        description: 'لجعل قاعدتك أجمل.'
    }
};
