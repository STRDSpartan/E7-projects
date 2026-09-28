from e7showcase.reference import artifact_info


def test_artifact_ocr_noise_is_corrected() -> None:
    assert artifact_info("Orbedel'aube")["fr"] == "Orbe de l'aube"  # type: ignore[index]
    assert artifact_info("Hote du banquet")["code"] == "art0186"  # type: ignore[index]
    assert artifact_info("Aubade Orb")["fr"] == "Orbe de l'aube"  # type: ignore[index]


def test_unknown_artifact() -> None:
    assert artifact_info("Lv. Max") is None
    assert artifact_info(None) is None
