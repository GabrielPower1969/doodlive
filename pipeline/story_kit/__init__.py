"""story_kit: the shared half of every story pack's Blender scripts (docs/STORY-KIT.md).

A pack script (pipeline/<xx>_characters.py, <xx>_animate.py, <xx>_<set>.py) keeps only what is unique to its story:
constants (cast, palette, proportions, regions, anchors), its builders and its clips. Everything that used to be
copied from the previous pack lives in one part file here:

  characters.py   rig skeleton, heads, hair shells, hands, robes / hoods / belts, eyelids, part objects, pixel
                  anchors + ID-map UV fixes, workbench / camera / page material, previews, posetest, uvcheck, verify
  animation.py    design-axis maths, Catmull-Rom keys, blink / syllables / beats, two-bone IK, gait, kneel,
                  prop aiming, staff solve, action baking + writing, GLB checks, look-dev camera and materials
  stage.py        set primitives (box, lathe, tube, extrude, puff, ngon_top, blade, lumpy), raster masks, drawing
                  projections (front / plan / oblique / side), UV-from-drawing, page / flat / texture materials

Use, at the point where the pack used to define these functions:

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import story_kit
    story_kit.include(globals(), "characters")

`include` executes the part file inside the pack module's own namespace. That is deliberate: the functions behave
exactly as if they were written in the pack file (same globals, default arguments evaluated in the pack, overridable
by a later `def` of the same name), which is what lets an existing pack move onto the kit with byte-identical output.
Each part file's docstring lists the names a pack must provide; `missing(globals(), part)` reports the ones it lacks.
"""
import ast
import builtins
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = ("characters", "animation", "stage")


def _path(part):
    if part not in PARTS:
        raise ValueError(f"story_kit: unknown part {part!r} (one of {PARTS})")
    return os.path.join(HERE, part + ".py")


def include(ns, part):
    """Run story_kit/<part>.py inside namespace `ns` (a pack module's globals()). The pack's __doc__ is kept."""
    p = _path(part)
    doc = ns.get("__doc__")
    with open(p, encoding="utf-8") as f:
        exec(compile(f.read(), p, "exec"), ns)
    ns["__doc__"] = doc
    ns.setdefault("STORY_KIT_PARTS", []).append(part)


def defined(part):
    """Names of the functions a part defines."""
    with open(_path(part), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]


def missing(ns, part):
    """Global names the part's functions read that neither the part, the pack namespace nor builtins provide.
    Call it with a pack's globals() after its imports: names a `from x import *` brings in count as provided."""
    with open(_path(part), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    own = set(defined(part))
    loads, stores = set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            (stores if isinstance(n.ctx, ast.Store) else loads).add(n.id)
        elif isinstance(n, ast.arg):
            stores.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.ExceptHandler)) and n.name:
            stores.add(n.name)
        elif isinstance(n, ast.alias):                       # imports inside the part's functions
            stores.add((n.asname or n.name).split(".")[0])
    implicit = {"__file__", "__name__"}
    return sorted(loads - stores - own - implicit - set(ns) - set(dir(builtins)))
