"""3D postavička Lexi (VRM) — súbory na mieste a zapojenie do stránok.

Samotné vykresľovanie je v prehliadači (Three.js); tu strážime to, čo by sa
potichu rozbilo: import map ukazuje na existujúce súbory, GLTFLoader nájde
svoj relatívny import, modely sú VRM s tvarmi úst a CSP pustí textúry (blob:).
"""
import json
import struct
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
MODELS = ("polybot", "robert", "amazonas")


def _vrm_json(path: Path) -> dict:
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    chunk_len = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + chunk_len].decode("utf-8"))


@pytest.mark.parametrize("name", MODELS)
def test_models_are_cc0_vrm_with_mouth_shapes(name):
    vrm = _vrm_json(STATIC / "avatars" / f"{name}.vrm")["extensions"]["VRM"]
    assert vrm["meta"]["licenseName"] == "CC0"
    presets = {g["presetName"] for g in vrm["blendShapeMaster"]["blendShapeGroups"]}
    assert {"a", "e", "i", "o", "u", "blink"} <= presets


def test_vendor_files_and_relative_imports_exist():
    three = STATIC / "vendor" / "three"
    assert (three / "three.module.min.js").exists() and (three / "three.core.min.js").exists()
    # GLTFLoader importuje '../utils/BufferGeometryUtils.js' — musí sedieť priečinok.
    assert "../utils/BufferGeometryUtils.js" in (three / "loaders" / "GLTFLoader.js").read_text(encoding="utf-8")
    assert (three / "utils" / "BufferGeometryUtils.js").exists()
    assert (STATIC / "vendor" / "three-vrm" / "three-vrm.module.min.js").exists()
    assert (three / "LICENSE").exists() and (STATIC / "vendor" / "three-vrm" / "LICENSE").exists()


def test_tutor_page_wires_3d_avatar(client):
    client.post("/api/v1/register", json={"email": "avatar3d@example.com", "password": "Abcdef12"})
    client.post("/api/v1/login", json={"email": "avatar3d@example.com", "password": "Abcdef12"})
    res = client.get("/tutor")
    html = res.text
    assert 'id="tutorAvatar"' in html and "data-lexi-3d" in html
    assert '"three": "/static/vendor/three/three.module.min.js"' in html
    assert "lexi-avatar3d.js" in html and 'data-lexi-character="polybot"' in html
    # GLTFLoader číta textúry vybalené z modelu cez blob: — CSP ich musí pustiť.
    assert "connect-src 'self' blob:" in res.headers["content-security-policy"]
