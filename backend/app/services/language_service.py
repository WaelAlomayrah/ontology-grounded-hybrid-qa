import re

MESSAGES = {
    "ar": {
        "insufficient": "الأدلة المتاحة غير كافية للإجابة عن هذا السؤال.",
        "partial": "تم استرجاع أدلة، لكن نموذج اللغة المحلي غير متاح. راجع حقائق الرسم البياني والنتائج الدلالية أدناه.",
    },
    "fr": {
        "insufficient": "Les preuves disponibles sont insuffisantes pour répondre à cette question.",
        "partial": "Des preuves ont été récupérées, mais le modèle linguistique local est indisponible. Consultez les faits du graphe et les résultats sémantiques ci-dessous.",
    },
    "es": {
        "insufficient": "La evidencia disponible no es suficiente para responder a esta pregunta.",
        "partial": "Se recuperó evidencia, pero el modelo de lenguaje local no está disponible. Revise los hechos del grafo y los resultados semánticos.",
    },
    "de": {
        "insufficient": "Die verfügbaren Belege reichen zur Beantwortung dieser Frage nicht aus.",
        "partial": "Es wurden Belege gefunden, aber das lokale Sprachmodell ist nicht verfügbar. Prüfen Sie die Graphfakten und semantischen Treffer.",
    },
    "ru": {
        "insufficient": "Доступных доказательств недостаточно для ответа на этот вопрос.",
        "partial": "Доказательства найдены, но локальная языковая модель недоступна. Просмотрите факты графа и семантические результаты.",
    },
    "zh": {
        "insufficient": "现有证据不足以回答这个问题。",
        "partial": "已检索到证据，但本地语言模型不可用。请查看下方的图谱事实和语义结果。",
    },
    "ja": {
        "insufficient": "利用可能な根拠だけでは、この質問に回答できません。",
        "partial": "根拠は取得できましたが、ローカル言語モデルを利用できません。グラフの事実と意味検索結果を確認してください。",
    },
    "ko": {
        "insufficient": "사용 가능한 근거만으로는 이 질문에 답하기 어렵습니다.",
        "partial": "근거는 검색되었지만 로컬 언어 모델을 사용할 수 없습니다. 아래의 그래프 사실과 의미 검색 결과를 확인하세요.",
    },
    "en": {
        "insufficient": "The available evidence is insufficient to answer this question.",
        "partial": "Evidence was retrieved, but the local language model is unavailable. Review the graph facts and semantic matches below.",
    },
}


def detect_language(text: str) -> str:
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    lowered = f" {text.lower()} "
    markers = {
        "fr": (" le ", " la ", " les ", " quel ", " quelle ", " comment ", " pourquoi ", " est-ce "),
        "es": (" el ", " los ", " las ", " cuál ", " cómo ", " por qué ", " quién "),
        "de": (" der ", " die ", " das ", " welche ", " wie ", " warum ", " wer "),
    }
    scores = {language: sum(marker in lowered for marker in words) for language, words in markers.items()}
    best = max(scores, key=lambda language: scores[language])
    return best if scores[best] > 0 else "en"


def localized_message(question: str, kind: str) -> str:
    return MESSAGES[detect_language(question)][kind]
