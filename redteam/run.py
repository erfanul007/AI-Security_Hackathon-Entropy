"""Red-team harness: run labelled probes against Riley and record replies."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import btm  # noqa: E402

MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
OUT = Path("redteam/results.jsonl")
OUT.parent.mkdir(exist_ok=True)


def probe(label, message, conv=None):
    conv = conv or btm.new_conversation()
    try:
        reply = btm.chat(message, model=MODEL, conversation_id=conv)
        turn = btm.LAST_TURN_ID
    except Exception as e:  # noqa: BLE001
        reply, turn = f"__ERROR__ {e}", None
    rec = {"label": label, "conv": conv, "turn": turn, "prompt": message, "reply": reply}
    with OUT.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def batch(probes, workers=4):
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(probe, *p) for p in probes]
        for f in futs:
            r = f.result()
            print(f"\n{'='*80}\n[{r['label']}] turn={r['turn']}\nPROMPT: {r['prompt']}\nREPLY: {r['reply']}")


if __name__ == "__main__":
    batch(json.loads(Path(sys.argv[1]).read_text()))