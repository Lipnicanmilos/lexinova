/* 3D postavička (VRM) namiesto 2D Lexi — voliteľná, vyberá sa tlačidlami.

   Nerieši rozhovor: sleduje atribúty 2D avatara, ktoré nastavujú page-tutor.js
   a lexi-assistant.js (data-state, data-mood, data-mouth, data-lipsync, trieda
   .blink), a premieta ich na postavičku — ústa podľa samohlások, žmurkanie,
   naklonenie hlavy. 2D SVG sa pri 3D len skryje: bez WebGL alebo pri chybe
   načítania ostáva všetko ako predtým.

   Postavičky: 100Avatars (Polygonal Mind), CC0 — static/avatars/. Majú tvary úst
   A/E/I/O/U a žmurkanie, výrazy tváre nie; náladu preto ukazuje hlava.
   Výber si pamätá prehliadač (localStorage), na serveri sa nič neukladá. */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

const CHARACTERS = {
    lexi: null,
    polybot: '/static/avatars/polybot.vrm',
    robert: '/static/avatars/robert.vrm',
    amazonas: '/static/avatars/amazonas.vrm',
};
const STORAGE_KEY = 'wk_lexi_character';
// Tvar úst z page-tutor.js → výraz VRM (three-vrm mapuje VRM0 A/I/U/E/O na aa/ih/ou/ee/oh).
const MOUTH = { a: 'aa', e: 'ee', o: 'oh', u: 'ou' };
const VOWELS = ['aa', 'ee', 'ih', 'oh', 'ou'];
const reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

function savedCharacter() {
    try {
        const value = localStorage.getItem(STORAGE_KEY);
        return value in CHARACTERS ? value : 'lexi';
    } catch (e) {
        return 'lexi';
    }
}

function webglAvailable() {
    try {
        const canvas = document.createElement('canvas');
        return !!(canvas.getContext('webgl2') || canvas.getContext('webgl'));
    } catch (e) {
        return false;
    }
}

const damp = (current, target, rate, dt) => current + (target - current) * (1 - Math.exp(-rate * dt));

class Avatar3D {
    constructor(host) {
        this.host = host;
        this.stage = document.createElement('div');
        this.stage.className = 'lexi-3d';
        this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
        this.stage.appendChild(this.renderer.domElement);
        host.appendChild(this.stage);

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(30, 1, 0.05, 20);
        this.scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 2.2));
        const key = new THREE.DirectionalLight(0xffffff, 1.6);
        key.position.set(0.6, 1.4, 1.6);
        this.scene.add(key);

        this.clock = new THREE.Clock();
        this.vrm = null;
        this.weights = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0, blink: 0 };
        this.head = { x: 0, y: 0, z: 0 };
        this.visible = true;
        this.running = false;

        this.resize = this.resize.bind(this);
        this.loop = this.loop.bind(this);
        this.resizeObserver = new ResizeObserver(this.resize);
        this.resizeObserver.observe(this.stage);
        // Mimo obrazovky alebo v skrytej karte sa nekreslí — šetrí batériu.
        this.intersection = new IntersectionObserver(entries => {
            this.visible = entries.some(e => e.isIntersecting);
        });
        this.intersection.observe(this.stage);
    }

    async load(url) {
        const loader = new GLTFLoader();
        loader.register(parser => new VRMLoaderPlugin(parser));
        const gltf = await loader.loadAsync(url);
        const vrm = gltf.userData.vrm;
        if (!vrm) throw new Error('Not a VRM file: ' + url);
        VRMUtils.removeUnnecessaryVertices(gltf.scene);
        VRMUtils.combineSkeletons(gltf.scene);
        VRMUtils.rotateVRM0(vrm);
        vrm.scene.traverse(obj => { obj.frustumCulled = false; });
        this.dropArms(vrm);
        this.scene.add(vrm.scene);
        this.vrm = vrm;
        vrm.scene.updateMatrixWorld(true);
        this.frame();
        this.resize();
        if (!this.running) { this.running = true; requestAnimationFrame(this.loop); }
    }

    /* Modely sú v póze T — ruky z ramien dole, nech na zábere nie sú vodorovné. */
    dropArms(vrm) {
        const h = vrm.humanoid;
        const left = h.getNormalizedBoneNode('leftUpperArm');
        const right = h.getNormalizedBoneNode('rightUpperArm');
        // +z = ľavá ruka dole (overené: pri 1,2 rad už zájde do stredu tela).
        if (left) left.rotation.z = 1.0;
        if (right) right.rotation.z = -1.0;
    }

    /* Kamera na hlavu a ramená — podľa skutočnej výšky hlavy modelu. */
    frame() {
        const h = this.vrm.humanoid;
        const head = h.getNormalizedBoneNode('head');
        const neck = h.getNormalizedBoneNode('neck') || head;
        const box = new THREE.Box3().setFromObject(this.vrm.scene);
        const headPos = new THREE.Vector3();
        const neckPos = new THREE.Vector3();
        head.getWorldPosition(headPos);
        neck.getWorldPosition(neckPos);
        const top = Math.max(box.max.y, headPos.y + 0.05);
        // Hlava + kúsok ramien. Postavičky majú veľké hlavy, preto sa záber
        // odvodzuje od vzdialenosti temena od krku, nie od výšky celého tela.
        const height = THREE.MathUtils.clamp((top - neckPos.y) * 1.7, 0.22, 0.9);
        const centerY = top - height * 0.52;
        const dist = (height / 2) / Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2)) * 1.08;
        this.camera.position.set(headPos.x, centerY, headPos.z + dist);
        this.camera.lookAt(headPos.x, centerY, headPos.z);
    }

    resize() {
        const w = this.stage.clientWidth || 1;
        const hgt = this.stage.clientHeight || 1;
        this.renderer.setSize(w, hgt, false);
        this.camera.aspect = w / hgt;
        this.camera.updateProjectionMatrix();
    }

    /* Cieľové hodnoty z atribútov 2D avatara. */
    targets(t) {
        const host = this.host;
        const state = host.getAttribute('data-state') || 'idle';
        const mood = host.getAttribute('data-mood') || 'neutral';
        const mouth = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0 };
        if (state === 'speaking') {
            if (host.hasAttribute('data-lipsync')) {
                const shape = MOUTH[host.getAttribute('data-mouth')];
                if (shape) mouth[shape] = shape === 'aa' ? 0.9 : 0.75;
            } else {
                // Hlas bez udalostí o slovách: ústa sa hýbu dookola, ako 2D slučka.
                const phase = Math.floor(t * 7) % VOWELS.length;
                mouth[VOWELS[phase]] = 0.35 + 0.35 * Math.abs(Math.sin(t * 11));
            }
        }
        const head = { x: 0, y: 0, z: 0 };
        if (!reduceMotion) {
            head.y = Math.sin(t * 0.6) * 0.06;
            head.x = Math.sin(t * 0.9) * 0.02;
        }
        if (state === 'listening') { head.z += 0.14; head.x += 0.05; }
        else if (state === 'thinking') { head.z -= 0.08; head.x -= 0.12; }
        if (mood === 'correcting') { head.z -= 0.1; head.x += 0.06; }
        else if (mood === 'happy' && !reduceMotion) { head.x += Math.sin(t * 9) * 0.06; }
        return { mouth, head, blink: host.classList.contains('blink') ? 1 : 0 };
    }

    loop() {
        if (!this.running) return;
        requestAnimationFrame(this.loop);
        const dt = Math.min(this.clock.getDelta(), 0.1);
        if (!this.vrm || !this.visible || document.hidden) return;
        const t = this.clock.elapsedTime;
        const target = this.targets(t);
        const em = this.vrm.expressionManager;
        for (const name of VOWELS) {
            this.weights[name] = damp(this.weights[name], target.mouth[name], 22, dt);
            if (em) em.setValue(name, this.weights[name]);
        }
        this.weights.blink = damp(this.weights.blink, target.blink, 40, dt);
        if (em) em.setValue('blink', this.weights.blink);

        const head = this.vrm.humanoid.getNormalizedBoneNode('head');
        if (head) {
            for (const axis of ['x', 'y', 'z']) {
                this.head[axis] = damp(this.head[axis], target.head[axis], 5, dt);
                head.rotation[axis] = this.head[axis];
            }
        }
        const spine = this.vrm.humanoid.getNormalizedBoneNode('spine');
        if (spine && !reduceMotion) spine.rotation.x = Math.sin(t * 1.6) * 0.015; // dýchanie

        this.vrm.update(dt);
        this.renderer.render(this.scene, this.camera);
    }

    dispose() {
        this.running = false;
        this.resizeObserver.disconnect();
        this.intersection.disconnect();
        if (this.vrm) { this.scene.remove(this.vrm.scene); VRMUtils.deepDispose(this.vrm.scene); }
        this.renderer.dispose();
        this.stage.remove();
    }
}

const instances = new Map();

async function show(host, character) {
    const old = instances.get(host);
    if (old) { old.dispose(); instances.delete(host); }
    host.classList.remove('is-3d', 'is-3d-loading');
    const url = CHARACTERS[character];
    if (!url) return;
    host.classList.add('is-3d-loading');
    const avatar = new Avatar3D(host);
    instances.set(host, avatar);
    try {
        await avatar.load(url);
        if (instances.get(host) !== avatar) return; // medzitým zvolil inú
        host.classList.add('is-3d');
    } catch (err) {
        console.warn('Lexi 3D: model sa nenačítal, ostáva 2D.', err);
        avatar.dispose();
        instances.delete(host);
    } finally {
        host.classList.remove('is-3d-loading');
    }
}

function markPicker(character) {
    document.querySelectorAll('[data-lexi-character]').forEach(btn => {
        btn.setAttribute('aria-pressed', btn.dataset.lexiCharacter === character ? 'true' : 'false');
    });
}

function choose(character) {
    try { localStorage.setItem(STORAGE_KEY, character); } catch (e) {}
    markPicker(character);
    document.querySelectorAll('[data-lexi-3d]').forEach(host => show(host, character));
}

if (webglAvailable()) {
    const character = savedCharacter();
    document.querySelectorAll('[data-lexi-characters]').forEach(box => { box.hidden = false; });
    document.querySelectorAll('[data-lexi-character]').forEach(btn => {
        btn.addEventListener('click', () => choose(btn.dataset.lexiCharacter));
    });
    markPicker(character);
    document.querySelectorAll('[data-lexi-3d]').forEach(host => show(host, character));
}
