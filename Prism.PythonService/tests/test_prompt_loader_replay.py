"""The extractor few-shot replay must send each example's own output from the
file - including examples that carry a "note" - and never the note itself."""
import json

from extraction.prompt_loader import build_gemini_messages_for_extractor, load_fewshot_examples

PAPER = "SYNTHETIC PAPER BODY"


def test_every_example_replays_its_file_output():
    examples = load_fewshot_examples("claims")
    messages = build_gemini_messages_for_extractor(PAPER)

    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": PAPER}
    turns = messages[1:-1]
    assert len(turns) == 2 * len(examples)
    for i, example in enumerate(examples):
        user, model = turns[2 * i], turns[2 * i + 1]
        assert user == {"role": "user", "content": example["input_excerpt"]}
        assert model["role"] == "model"
        assert model["content"] == json.dumps(example["output"])
        assert json.loads(model["content"]) == example["output"]


def test_examples_with_notes_are_not_blanked():
    examples = load_fewshot_examples("claims")
    noted = [e for e in examples if "note" in e]
    assert noted, "fixture expectation: some examples carry a note"
    replayed = {m["content"] for m in build_gemini_messages_for_extractor(PAPER) if m["role"] == "model"}
    for example in noted:
        assert json.dumps(example["output"]) in replayed
    sent_claims = sum(len(json.loads(c)["claims"]) for c in replayed)
    assert sent_claims == sum(len(e["output"]["claims"]) for e in examples)


def test_do_not_extract_examples_replay_empty_claims():
    negatives = [e for e in load_fewshot_examples("claims") if e["example_type"].startswith("do_not_extract_")]
    assert negatives
    for example in negatives:
        assert example["output"] == {"claims": []}


def test_note_text_never_sent():
    messages = build_gemini_messages_for_extractor(PAPER)
    sent = "\n".join(m["content"] for m in messages)
    for example in load_fewshot_examples("claims"):
        if "note" in example:
            assert example["note"] not in sent
