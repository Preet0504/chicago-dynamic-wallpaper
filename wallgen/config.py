"""Central settings for the generation pipeline. Everything here is local: Ollama models, mflux image models,
and HF perception models cached under ~/.cache/huggingface."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# --- language / vision models (Ollama) ---------------------------------------------------------------
VLM_PERCEPTION = "qwen3.5:122b"          # path B: looks at the image directly
LLM_PERCEPTION = "qwen3:8b"              # path A: reasons over the detector's object list
VLM_TIEBREAK = "inkling-2-mini:26b-a5b"  # settles disagreements between A and B
LLM_PLANNER = "gpt-oss:120b"             # season phases / selection rules from climate data
LLM_CODER = "gpt-oss:120b"               # writes and repairs scene_renderer.py
LLM_ROUTER = "qwen3:8b"                  # classifies ambiguous feedback (code vs image)
REVIEW_PANEL = ["qwen3.5:122b", "inkling-2-mini:26b-a5b"]   # different families, scored independently
# inkling with think=false still reasons internally and can spend the whole output budget on it without answering;
# its "minimal" level answers reliably (~1k tokens, ~50 s with six images)
THINK_OVERRIDE = {"inkling-2-mini:26b-a5b": "minimal"}
PANEL_PARALLEL = True                    # verified: qwen3.5 (79 GB) + inkling (22 GB) both 100% GPU together

# --- image models (mflux, separate uv tool env) ----------------------------------------------------------
MFLUX_PY = os.path.expanduser("~/.local/share/uv/tools/mflux/bin/python")
MFLUX_UPSCALE = os.path.expanduser("~/.local/bin/mflux-upscale-seedvr2")
EDIT_MODEL = "flux2-klein-4b"
EDIT_STEPS = 4
EDIT_QUANT = 8

# --- perception models (transformers, .venv-gen) ------------------------------------------------------
SEG_MODEL = "facebook/mask2former-swin-large-ade-semantic"
DET_MODEL = "IDEA-Research/grounding-dino-base"
SAM_MODEL = "facebook/sam-vit-base"
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Base-hf"

# --- working sizes ---------------------------------------------------------------------------------------
WORK_LONG = 1672        # analysis / plate resolution (long side)
OUT_W, OUT_H = 3840, 2160

# --- loop control ------------------------------------------------------------------------------------------
AGREE_JACCARD = 0.6     # perception: category-set agreement needed between path A and path B
PLATE_MAX_ROUNDS = 3    # loop A (templates)
RENDER_MAX_ROUNDS = 3   # loop B (renderer code)
PASS_MEAN = 3.6         # panel mean score (1-5) needed to accept
PASS_FLOOR = 2.5        # no single metric may average below this
PLATEAU_EPS = 0.1       # stop when a round improves the mean by less than this
DRIFT_MIN_EDGE_RECALL = 0.80   # deterministic gate: static-structure edges kept after plate generation

# --- fast mode (progressive delivery + tiered review) ---------------------------------------------------------
# A cheap single-model screen looks at original + candidate only (no tiles) and returns scores + a few issues. It can
# only ACCEPT: anything not clearly good (verdict != accept, any issue of severity >= 2, scores near the threshold, a
# deterministic check firing) escalates to the full multi-model panel, which alone can fail a frame.
REVIEW_TIER = "tiered"                  # "tiered" | "full"
SCREEN_MODEL = "qwen3.5:122b"           # chosen by measurement (wallgen/calibrate_screen.py)
SCREEN_ACCEPT_MEAN = 4.0                # screen mean needed to skip the panel
SCREEN_ACCEPT_FLOOR = 3.0               # and no metric below this
FAST_PLATE_ROUNDS = 2                   # loop A rounds in fast mode
FAST_RENDER_ROUNDS = 2                  # loop B rounds in fast mode
FAST_CASES = ["c01_night", "c04_noon", "c06_dusk", "c08_rain", "c10_fog", "c11_snow_night", "c12_winter_day"]
FAST_MAX_CASES = 6                      # c12 only when there is no snow template

RUBRIC = ["style_match", "composition_intact", "realism", "light_consistency", "season_correct",
          "edges_artifacts", "would_set_as_wallpaper"]
