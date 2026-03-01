"""
Symptom keyword to ICD-10-CM mapping for medical condition search.
Used when USE_MOCK_DATA=false to resolve free-text symptoms to MedlinePlus Connect queries.
Aligned with mock condition names and common symptom terms.
"""

# Symptom/condition keywords -> ICD-10-CM codes (MedlinePlus Connect uses ICD-10-CM)
# Format: lowercase keyword -> list of ICD-10 codes
# Source: ICD-10-CM, MedlinePlus condition pages
_SYMPTOM_TO_ICD: dict[str, list[str]] = {
    # Common Cold (J00 - Acute nasopharyngitis)
    "cold": ["J00"],
    "colds": ["J00"],
    "common cold": ["J00"],
    "runny nose": ["J00"],
    "congestion": ["J00"],
    "sneezing": ["J00"],
    "nasopharyngitis": ["J00"],
    # Seasonal Allergies (J30.9 - Allergic rhinitis)
    "allergy": ["J30.9"],
    "allergies": ["J30.9"],
    "allergic": ["J30.9"],
    "rhinitis": ["J30.9"],
    "hay fever": ["J30.9"],
    "pollen": ["J30.9"],
    "itchy eyes": ["J30.9"],
    "postnasal drip": ["J30.9"],
    # Influenza (J11 - Influenza with other respiratory manifestations)
    "flu": ["J11"],
    "influenza": ["J11"],
    "fever": ["J11", "A09"],
    "chills": ["J11"],
    "body aches": ["J11"],
    # Tension Headache (G44.2 - Tension-type headache)
    "tension headache": ["G44.2"],
    "tension": ["G44.2"],
    "pressure": ["G44.2"],
    "tightness": ["G44.2"],
    # Migraine (G43.1 - Migraine with aura; G43.0 - Migraine without aura)
    "migraine": ["G43.1"],
    "migraines": ["G43.1"],
    "headache": ["G43.1", "G44.2", "R51"],
    "headaches": ["G43.1", "G44.2", "R51"],
    "throbbing": ["G43.1"],
    "aura": ["G43.1"],
    "sensitivity to light": ["G43.1"],
    "sensitivity to sound": ["G43.1"],
    # Gastroenteritis (A09 - Diarrhea and gastroenteritis)
    "gastroenteritis": ["A09"],
    "stomach flu": ["A09"],
    "nausea": ["A09", "R11"],
    "vomiting": ["A09", "R11"],
    "diarrhea": ["A09"],
    "stomach cramps": ["A09"],
    "abdominal pain": ["A09", "R10"],
    # Acid Reflux / GERD (K21 - Gastro-esophageal reflux disease)
    "gerd": ["K21"],
    "acid reflux": ["K21"],
    "heartburn": ["K21"],
    "reflux": ["K21"],
    "regurgitation": ["K21"],
    # UTI (N39.0 - Urinary tract infection)
    "uti": ["N39.0"],
    "urinary": ["N39.0"],
    "bladder": ["N39.0"],
    "painful urination": ["N39.0"],
    "burning when urinating": ["N39.0"],
    "frequent urination": ["N39.0"],
    "pelvic pain": ["N39.0"],
    # Bronchitis (J20 - Acute bronchitis)
    "bronchitis": ["J20"],
    "cough": ["J20", "J00", "J11"],
    "mucus": ["J20"],
    "shortness of breath": ["J20", "J96"],
    "chest discomfort": ["J20"],
    # Anxiety (F41.1 - Generalized anxiety disorder)
    "anxiety": ["F41.1"],
    "worry": ["F41.1"],
    "nervousness": ["F41.1"],
    "restlessness": ["F41.1"],
    # Insomnia (G47.0 - Insomnia)
    "insomnia": ["G47.0"],
    "sleeplessness": ["G47.0"],
    "difficulty falling asleep": ["G47.0"],
    "waking at night": ["G47.0"],
    # Muscle Strain (M62.81 - Muscle weakness; S36 - Sprain)
    "muscle strain": ["M62.81"],
    "muscle pain": ["M62.81"],
    "stiffness": ["M62.81"],
    "sprain": ["S36"],
    "strain": ["M62.81"],
    # Edema / Fluid Overload (R60.9 - Edema)
    "edema": ["R60.9"],
    "swelling": ["R60.9"],
    "fluid retention": ["R60.9"],
    "puffy legs": ["R60.9"],
    "ankle swelling": ["R60.9"],
    "weight gain": ["R60.9"],
}


def get_icd_codes_for_symptoms(query: str) -> list[str]:
    """
    Map free-text symptom query to ICD-10-CM codes.
    Returns deduplicated list of codes, ordered by relevance.
    """
    q = (query or "").lower().strip()
    if not q:
        return []
    terms = [t for t in q.split() if len(t) >= 2]
    seen: set[str] = set()
    result: list[str] = []
    # Prefer exact phrase matches first
    if q in _SYMPTOM_TO_ICD:
        for code in _SYMPTOM_TO_ICD[q]:
            if code not in seen:
                seen.add(code)
                result.append(code)
    # Then individual terms
    for term in terms:
        if term in _SYMPTOM_TO_ICD:
            for code in _SYMPTOM_TO_ICD[term]:
                if code not in seen:
                    seen.add(code)
                    result.append(code)
    return result
