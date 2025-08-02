# tools/gen_demo_clp.py
import json, uuid, datetime, random
project = {
    "id": str(uuid.uuid4()),
    "container": "20ft-std",
    "boxes": [
        {
            "id": str(uuid.uuid4()),
            "name": "Box-A",
            "size_mm": [1000, 800, 600],
            "weight_kg": 50,
            "color_hex": f"#{random.randint(0, 0xFFFFFF):06X}",
            "pos_mm": [0, 0, 0],
            "rot_deg": 0
        }
    ],
    "meta": {
        "version": "0.1.0",
        "created": datetime.datetime.utcnow().isoformat() + "Z",
        "author": "demo"
    }
}
path = "samples/demo_project.clp"
open(path, "w").write(json.dumps(project, indent=2))
print(f"Wrote {path}")
