from app.services.ollama_service import (
    _arabic_question_with_foreign_script,
    _remove_foreign_script_fragments,
)


def test_detects_and_removes_cjk_translation_from_arabic_answer():
    question = "في أي إدارة يعمل الموظف سعود العمري؟"
    answer = "يعمل في إدارة المبيعات [G1].\n需要更多信息。"

    assert _arabic_question_with_foreign_script(question, answer)
    assert _remove_foreign_script_fragments(answer) == "يعمل في إدارة المبيعات [G1]."

def test_detects_cyrillic_leakage_from_arabic_answer():
    assert _arabic_question_with_foreign_script(
        "أين يعمل سعود؟", "Согласно البيانات، يعمل هنا."
    )
