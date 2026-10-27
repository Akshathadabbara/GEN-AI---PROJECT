import re
import math
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import config

# Try to import sentence_transformers if available
_ST_MODEL = None
_ST_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    # Check if we should load (disabled by default or lazy-loaded if requested)
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


def normalize_text(text: str) -> str:
    """Cleans and standardizes text input for comparison."""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^\w\s-]", " ", text)
    return " ".join(text.split())


def build_item_representation(item: dict) -> str:
    """
    Builds a unified, non-sensitive semantic document representation for an item.
    Does NOT include student names, contact numbers, or registration numbers.
    """
    parts = []
    
    # Item Name (weighted twice for emphasis)
    item_name = item.get("item_name") or item.get("name") or ""
    if item_name:
        parts.append(f"item: {item_name} {item_name}")
    
    # Category
    category = item.get("category")
    if category and category.lower() != "other":
        parts.append(f"category: {category}")
        
    # Brand
    brand = item.get("brand")
    if brand:
        parts.append(f"brand: {brand}")
        
    # Color
    color = item.get("color")
    if color:
        parts.append(f"color: {color}")
        
    # Distinctive features
    distinctive_features = item.get("distinctive_features")
    if distinctive_features:
        parts.append(f"features: {distinctive_features}")
        
    # Location
    location = item.get("location")
    if location:
        parts.append(f"location: {location}")
        
    # Description
    desc = item.get("description")
    if desc:
        parts.append(f"description: {desc}")
        
    return " | ".join(parts)


# Synonyms dictionary for campus domain to bolster semantic matching
SYNONYMS = {
    "bottle": ["flask", "sipper", "tumbler", "thermos"],
    "flask": ["bottle", "sipper", "tumbler", "thermos"],
    "earbuds": ["earphones", "airpods", "headphones", "buds", "headset"],
    "airpods": ["earbuds", "earphones", "headphones", "buds"],
    "laptop": ["macbook", "thinkpad", "notebook", "computer"],
    "canteen": ["cafeteria", "mess", "food court", "cafe"],
    "cafeteria": ["canteen", "mess", "food court", "cafe"],
    "library": ["reading room", "study hall"],
    "phone": ["mobile", "smartphone", "iphone", "android"],
    "wallet": ["purse", "cardholder", "billfold", "moneybag"],
    "charger": ["adapter", "cable", "power bank", "cord"],
    "spectacles": ["glasses", "specs", "goggles", "eyewear"],
    "glasses": ["spectacles", "specs", "goggles", "eyewear"],
    "keys": ["keychain", "bunch of keys"]
}

def expand_synonyms(text: str) -> str:
    """Augments text representation with domain synonyms to improve semantic recall."""
    tokens = normalize_text(text).split()
    augmented = list(tokens)
    for token in tokens:
        if token in SYNONYMS:
            augmented.extend(SYNONYMS[token])
    return " ".join(augmented)


class HybridAIMatcher:
    """
    Intelligent campus item matcher combining:
    1. Semantic text representations with subword/char n-gram TF-IDF & synonym expansion
    2. Optional Sentence Transformer embeddings if environment allows
    3. Structured attribute verification (color, category, brand, location)
    """

    def __init__(self):
        self.mode = "Semantic Vector (TF-IDF + Domain Expansion)"
        self.st_model = None
        # Attempt to load lightweight sentence transformer if available
        if _ST_AVAILABLE:
            try:
                self.st_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.mode = "Sentence Transformers (all-MiniLM-L6-v2)"
            except Exception:
                self.st_model = None

    def compute_semantic_similarity(self, text1: str, text2: str) -> float:
        """Computes semantic similarity score between two item representations."""
        if not text1 or not text2:
            return 0.0

        if self.st_model is not None:
            try:
                emb1 = self.st_model.encode([text1])[0]
                emb2 = self.st_model.encode([text2])[0]
                cos = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-9)
                return float(max(0.0, min(1.0, (cos + 1.0) / 2.0)))
            except Exception:
                pass

        # Robust Hybrid fallback with n-grams and synonym expansion
        exp1 = expand_synonyms(text1)
        exp2 = expand_synonyms(text2)
        
        try:
            vectorizer = TfidfVectorizer(
                ngram_range=(1, 2),
                sublinear_tf=True,
                stop_words='english',
                token_pattern=r"(?u)\b\w+\b"
            )
            tfidf_matrix = vectorizer.fit_transform([exp1, exp2])
            sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(max(0.0, min(1.0, sim)))
        except Exception:
            # Word overlap jaccard fallback
            s1 = set(normalize_text(exp1).split())
            s2 = set(normalize_text(exp2).split())
            if not s1 or not s2:
                return 0.0
            return float(len(s1 & s2) / len(s1 | s2))

    def evaluate_structured_attributes(self, item1: dict, item2: dict) -> dict:
        """
        Calculates granular attribute alignment and gathers matching evidence.
        """
        evidence = []
        attribute_boost = 0.0

        # 1. Category comparison
        c1 = normalize_text(item1.get("category") or "")
        c2 = normalize_text(item2.get("category") or "")
        if c1 and c2 and c1 != "other" and c2 != "other":
            if c1 == c2:
                attribute_boost += 0.15
                evidence.append(f"Matching category: {item1.get('category')}")
            else:
                attribute_boost -= 0.10

        # 2. Color comparison
        col1 = normalize_text(item1.get("color") or "")
        col2 = normalize_text(item2.get("color") or "")
        if col1 and col2:
            # check intersection of color words
            col1_words = set(col1.split())
            col2_words = set(col2.split())
            if col1_words & col2_words:
                attribute_boost += 0.12
                evidence.append(f"Matching color: {', '.join(col1_words & col2_words)}")

        # 3. Brand comparison
        b1 = normalize_text(item1.get("brand") or "")
        b2 = normalize_text(item2.get("brand") or "")
        if b1 and b2:
            if b1 == b2 or b1 in b2 or b2 in b1:
                attribute_boost += 0.15
                evidence.append(f"Matching brand: {item1.get('brand') or item2.get('brand')}")

        # 4. Location overlap
        loc1 = normalize_text(item1.get("location") or "")
        loc2 = normalize_text(item2.get("location") or "")
        if loc1 and loc2:
            l1_words = set(loc1.split()) - {"near", "at", "in", "the", "block", "building", "floor"}
            l2_words = set(loc2.split()) - {"near", "at", "in", "the", "block", "building", "floor"}
            overlap = l1_words & l2_words
            if overlap:
                attribute_boost += 0.10
                evidence.append(f"Location proximity: {', '.join(overlap)}")

        # 5. Distinctive features check
        f1 = normalize_text(item1.get("distinctive_features") or "")
        f2 = normalize_text(item2.get("distinctive_features") or "")
        if f1 and f2:
            shared = set(f1.split()) & set(f2.split())
            if len(shared) > 0:
                attribute_boost += 0.10
                evidence.append(f"Shared features: {', '.join(shared)}")

        return {
            "boost": attribute_boost,
            "evidence": evidence
        }

    def score_pair(self, lost_item: dict, found_item: dict) -> dict:
        """
        Ranks a candidate (Lost, Found) pair.
        Returns similarity_score, confidence label, and evidence.
        """
        rep_lost = build_item_representation(lost_item)
        rep_found = build_item_representation(found_item)

        base_sim = self.compute_semantic_similarity(rep_lost, rep_found)
        attr_eval = self.evaluate_structured_attributes(lost_item, found_item)

        # Calibrated final score
        raw_score = base_sim + attr_eval["boost"]
        # Clamp between 0.0 and 0.98 (never claim 100% certainty)
        calibrated_score = round(max(0.05, min(0.96, raw_score)), 3)

        # Confidence category
        if calibrated_score >= config.STRONG_MATCH_THRESHOLD:
            confidence = "Strong potential match"
        elif calibrated_score >= config.POSSIBLE_MATCH_THRESHOLD:
            confidence = "Possible match"
        else:
            confidence = "Low similarity"

        evidence = attr_eval["evidence"]
        if not evidence and calibrated_score >= config.SIMILARITY_THRESHOLD:
            evidence.append("Semantic similarity between reported descriptions and item names")

        return {
            "similarity_score": calibrated_score,
            "confidence": confidence,
            "evidence": evidence,
            "matcher_mode": self.mode
        }


matcher_instance = HybridAIMatcher()
