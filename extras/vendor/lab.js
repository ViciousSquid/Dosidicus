// Shared by the Laboratory pages: reading a save, and drawing a brain as it
// was at a moment of a squid's life.
//
// A save is a zip of JSON files. From 3.5 the game writes timeline.json into
// it (src/life_timeline.py): every life event in order, and every neuron and
// synapse with when it came to be. These pages show that; they do not work a
// life out for themselves, so they cannot disagree with the game about it.
(function () {
    const GAME = window.DOSIDICUS || {};

    const ERA_COLOURS = {
        hatchling: '#7d6a55', learning: '#2f6f9f', growing: '#3f9a8a',
        social: '#c9a227', parent: '#d9772b', dead: '#5a5560',
    };
    const KINDS = {
        hatched:        {icon: '🥚', label: 'Hatched',            colour: '#e8dcc0'},
        neuron:         {icon: '🧠', label: 'Grew a neuron',      colour: '#ffffff'},
        pruned:         {icon: '✂️', label: 'Lost a neuron',      colour: '#9aa0a6'},
        association:    {icon: '🔗', label: 'Formed a link',      colour: '#8fb8de'},
        belief:         {icon: '💡', label: 'Came to believe',    colour: '#7ddc7d'},
        belief_dropped: {icon: '💭', label: 'Stopped believing',  colour: '#9aa0a6'},
        encounter:      {icon: '🦑', label: 'Met another squid',  colour: '#7ddc7d'},
        fight:          {icon: '⚔️', label: 'Fought',             colour: '#ff6b6b'},
        mating:         {icon: '💞', label: 'Mated',              colour: '#ff9ecb'},
        egg:            {icon: '🥚', label: 'Laid an egg',        colour: '#ffd27d'},
        death:          {icon: '🪦', label: 'Died',               colour: '#c8c8d0'},
        memory:         {icon: '📌', label: 'Remembered',         colour: '#c9b8ff'},
    };

    function age(seconds) {
        seconds = Math.max(0, Math.round(Number(seconds) || 0));
        const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600);
        const m = Math.floor(seconds % 3600 / 60), s = seconds % 60;
        if (d) return `${d}d ${h}h`;
        if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
        return `${m}m ${String(s).padStart(2, '0')}s`;
    }

    function el(tag, attrs, ...children) {
        const node = document.createElement(tag);
        for (const [key, value] of Object.entries(attrs || {})) {
            if (key === 'class') node.className = value;
            else if (key === 'style') node.style.cssText = value;
            else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
            else if (value !== null && value !== undefined) node.setAttribute(key, value);
        }
        for (const child of children.flat()) {
            if (child === null || child === undefined || child === false) continue;
            node.appendChild(typeof child === 'object' ? child : document.createTextNode(String(child)));
        }
        return node;
    }

    // One save file -> a specimen. Text from a save is only ever put on the
    // page as text.
    async function readSave(file) {
        const zip = await JSZip.loadAsync(file);
        const save = {};
        let signature = '';
        for (const name of Object.keys(zip.files)) {
            const base = name.split('/').pop();
            if (base === 'uuid.txt') signature = (await zip.files[name].async('string')).trim();
            if (!base.endsWith('.json')) continue;
            try { save[base.slice(0, -5)] = JSON.parse(await zip.files[name].async('string')); }
            catch (e) { /* a file that is not JSON is not part of the squid */ }
        }
        if (!save.game_state && !save.brain_state) throw new Error('not a Dosidicus save');
        const squid = (save.game_state && save.game_state.squid) || {};
        const timeline = (save.timeline && Array.isArray(save.timeline.events)) ? save.timeline : null;
        return {
            file: file.name, signature, save, timeline,
            name: squid.name || (timeline && timeline.squid.name) || file.name,
            personality: squid.personality || '',
            uuid: squid.uuid || '',
            stats: save.statistics || {},
            life: (save.game_state && save.game_state.lifecycle) || {},
        };
    }

    // The brain as it was at moment `t` (seconds since the epoch): the
    // neurons born by then and the synapses formed by then. Anything that
    // appeared in the last `fresh` seconds is drawn bright.
    function brainAt(timeline, t) {
        const alive = new Set();
        const neurons = timeline.neurons.filter(n => !n.born || n.born <= t);
        neurons.forEach(n => alive.add(n.name));
        const connections = timeline.connections.filter(c =>
            (!c.since || c.since <= t) && alive.has(c.source) && alive.has(c.target));
        return {neurons, connections};
    }

    const NEURON_COLOURS = {
        drive: '#6fa8dc', sense: '#93c47d', action: '#f6b26b',
        'social sense': '#ffd966', social: '#e06666', grown: '#c9b8ff', neuron: '#bbbbbb',
    };

    function drawBrain(canvas, timeline, t, options) {
        options = options || {};
        const ratio = window.devicePixelRatio || 1;
        const width = canvas.clientWidth || 600, height = canvas.clientHeight || 380;
        canvas.width = width * ratio; canvas.height = height * ratio;
        const ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, width, height);
        if (!timeline || !timeline.neurons.length) return {neurons: 0, connections: 0};

        // Laid out by where every neuron will ever be, so nothing moves as
        // the brain grows: growth is seen as growth.
        const xs = timeline.neurons.map(n => n.x), ys = timeline.neurons.map(n => n.y);
        const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
        const pad = 34;
        const sx = x => pad + (maxX > minX ? (x - minX) / (maxX - minX) : 0.5) * (width - 2 * pad);
        const sy = y => pad + (maxY > minY ? (y - minY) / (maxY - minY) : 0.5) * (height - 2 * pad);
        const place = {};
        timeline.neurons.forEach(n => { place[n.name] = [sx(n.x), sy(n.y)]; });

        const now = brainAt(timeline, t);
        const fresh = options.fresh === undefined ? 1.5 : options.fresh;
        const highlight = new Set(options.highlight || []);
        const isNew = when => when && t - when <= fresh && t >= when;

        for (const c of now.connections) {
            const [x1, y1] = place[c.source], [x2, y2] = place[c.target];
            const bright = isNew(c.since) || (highlight.has(c.source) && highlight.has(c.target));
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
            ctx.lineWidth = bright ? 2.4 : Math.max(0.5, Math.min(2.2, Math.abs(c.weight) * 2.2));
            ctx.strokeStyle = bright ? '#ffffff'
                : c.weight >= 0 ? `rgba(110,200,140,${c.innate ? 0.30 : 0.62})`
                                : `rgba(230,110,110,${c.innate ? 0.30 : 0.62})`;
            ctx.stroke();
        }
        ctx.font = '10px system-ui, sans-serif'; ctx.textAlign = 'center';
        // A name goes above its neuron; where that would run into a
        // neighbour's name it goes below, or higher still.
        const taken = [];
        const clear = (x, y, w) => !taken.some(b => Math.abs(b.y - y) < 10 && Math.abs(b.x - x) < (b.w + w) / 2 + 3);
        for (const n of now.neurons) {
            const [x, y] = place[n.name];
            const bright = isNew(n.born) || highlight.has(n.name);
            ctx.beginPath(); ctx.arc(x, y, n.born ? 8 : 6.5, 0, Math.PI * 2);
            ctx.fillStyle = NEURON_COLOURS[n.kind] || '#bbbbbb'; ctx.fill();
            if (bright) { ctx.lineWidth = 3; ctx.strokeStyle = '#ffffff'; ctx.stroke(); }
            else if (n.born) { ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(255,255,255,.55)'; ctx.stroke(); }
            ctx.fillStyle = bright ? '#ffffff' : 'rgba(225,230,240,.78)';
            const label = n.name.replace(/_/g, ' '), w = ctx.measureText(label).width;
            const ly = [y - 11, y + 19, y - 22, y + 30].find(v => clear(x, v, w)) || y - 11;
            taken.push({x, y: ly, w});
            ctx.fillText(label, x, ly);
        }
        return {neurons: now.neurons.length, connections: now.connections.length};
    }

    window.Lab = {GAME, ERA_COLOURS, KINDS, NEURON_COLOURS, age, el, readSave, brainAt, drawBrain};
})();
