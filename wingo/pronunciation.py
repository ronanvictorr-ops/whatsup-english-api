import base64
import json
import os
from pathlib import Path

import requests


def extract_reference_text(answer: str | None) -> str | None:
    text = answer or ""
    lowered = text.lower()
    marker = "repeat after me:"
    marker_index = lowered.rfind(marker)
    if marker_index >= 0:
        remainder = text[marker_index + len(marker):]
        for line in remainder.splitlines():
            candidate = line.strip(" -\t\"'")
            if candidate:
                return candidate[:500]
    return None


def _content_type(audio_path: Path) -> str:
    if audio_path.suffix.lower() in {".ogg", ".opus"}:
        return "audio/ogg; codecs=opus"
    return "audio/wav; codecs=audio/pcm; samplerate=16000"


def _score(data, key):
    value = data.get(key)
    return round(float(value), 1) if value is not None else None


def parse_azure_assessment(payload: dict) -> dict:
    candidates = payload.get("NBest") or []
    if not candidates:
        raise ValueError("Azure response did not include NBest assessment data")

    candidate = candidates[0]
    assessment = candidate.get("PronunciationAssessment") or {}
    words = []
    for word in candidate.get("Words") or []:
        word_assessment = word.get("PronunciationAssessment") or {}
        phonemes = []
        for phoneme in word.get("Phonemes") or []:
            phoneme_assessment = phoneme.get("PronunciationAssessment") or {}
            phonemes.append({
                "phoneme": phoneme.get("Phoneme"),
                "accuracy_score": _score(phoneme_assessment, "AccuracyScore"),
            })
        words.append({
            "word": word.get("Word"),
            "accuracy_score": _score(word_assessment, "AccuracyScore"),
            "error_type": word_assessment.get("ErrorType", "None"),
            "phonemes": phonemes,
        })

    return {
        "provider": "azure",
        "status": "completed",
        "accuracy_score": _score(assessment, "AccuracyScore"),
        "fluency_score": _score(assessment, "FluencyScore"),
        "completeness_score": _score(assessment, "CompletenessScore"),
        "prosody_score": _score(assessment, "ProsodyScore"),
        "pronunciation_score": _score(assessment, "PronScore"),
        "words": words,
    }


def assess_pronunciation(audio_path: Path, reference_text: str) -> dict:
    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    if not key or not region:
        return {
            "provider": "transcription_only",
            "status": "acoustic_unavailable",
            "accuracy_score": None,
            "fluency_score": None,
            "completeness_score": None,
            "prosody_score": None,
            "pronunciation_score": None,
            "words": [],
        }

    assessment_config = {
        "ReferenceText": reference_text,
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableProsodyAssessment": True,
    }
    encoded_config = base64.b64encode(
        json.dumps(assessment_config).encode("utf-8")
    ).decode("ascii")
    url = (
        f"https://{region}.stt.speech.microsoft.com/"
        "speech/recognition/conversation/cognitiveservices/v1"
    )
    response = requests.post(
        url,
        params={"language": "en-US", "format": "detailed"},
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Pronunciation-Assessment": encoded_config,
            "Content-Type": _content_type(audio_path),
            "Accept": "application/json",
        },
        data=audio_path.read_bytes(),
        timeout=30,
    )
    response.raise_for_status()
    return parse_azure_assessment(response.json())


def build_pronunciation_feedback(result: dict, reference_text: str, transcript: str) -> str:
    if result.get("status") == "acoustic_unavailable":
        return (
            "Consegui entender seu audio e transcrevi: "
            f'"{transcript}".\n\n'
            "A avaliacao acustica detalhada ainda nao esta configurada, entao nao vou "
            "inventar uma nota de pronuncia.\n\n"
            f"Repeat after me:\n{reference_text}"
        )
    if result.get("status") != "completed":
        return (
            "Consegui entender seu audio, mas a analise acustica falhou temporariamente. "
            "Nao vou inventar uma nota.\n\n"
            f"Repeat after me:\n{reference_text}"
        )

    weakest_word = None
    scored_words = [
        item for item in result.get("words", [])
        if item.get("accuracy_score") is not None
    ]
    if scored_words:
        weakest_word = min(scored_words, key=lambda item: item["accuracy_score"])

    lines = [
        "Avaliacao de pronuncia",
        f"Precisao: {result.get('accuracy_score') or 0:.0f}/100",
        f"Fluencia: {result.get('fluency_score') or 0:.0f}/100",
        f"Completude: {result.get('completeness_score') or 0:.0f}/100",
    ]
    if result.get("prosody_score") is not None:
        lines.append(f"Ritmo e entonacao: {result['prosody_score']:.0f}/100")
    if weakest_word and weakest_word["accuracy_score"] < 80:
        lines.append(
            f"Foco desta tentativa: {weakest_word['word']} "
            f"({weakest_word['accuracy_score']:.0f}/100)."
        )
        scored_phonemes = [
            item for item in weakest_word.get("phonemes", [])
            if item.get("accuracy_score") is not None
        ]
        if scored_phonemes:
            weakest_phoneme = min(
                scored_phonemes,
                key=lambda item: item["accuracy_score"],
            )
            lines.append(
                f"Som para praticar: /{weakest_phoneme['phoneme']}/ "
                f"({weakest_phoneme['accuracy_score']:.0f}/100)."
            )
    else:
        lines.append("Muito bem: a frase ficou clara. Agora tente deixa-la mais natural.")
    lines.extend(["", "Repeat after me:", reference_text])
    return "\n".join(lines)
