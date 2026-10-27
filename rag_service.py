import os
import re
import chromadb
from chromadb.config import Settings
import config
from ai_matcher import HybridAIMatcher, normalize_text, expand_synonyms

class RAGService:
    """
    Retrieval-Augmented Generation (RAG) vector service.
    Indexes lost and found items in ChromaDB using vector embeddings,
    synchronizes with SQLite records, and executes semantic retrieval.
    """

    def __init__(self, chroma_path: str = None, collection_name: str = None, in_memory: bool = False):
        self.chroma_path = chroma_path or config.CHROMA_PATH
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self.in_memory = in_memory
        self.matcher = HybridAIMatcher()
        self._init_chroma()

    def _init_chroma(self):
        """Initializes ChromaDB client and collection."""
        if self.in_memory or self.chroma_path == ":memory:":
            self.client = chromadb.EphemeralClient()
        else:
            os.makedirs(self.chroma_path, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.chroma_path)
            
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def build_item_document(self, item: dict) -> str:
        """
        Builds a privacy-safe, high-information semantic document for embedding.
        NEVER includes student names, registration numbers, or contact details.
        """
        parts = []
        item_name = item.get("item_name") or item.get("name") or "Unknown Item"
        parts.append(f"Item: {item_name}")

        category = item.get("category")
        if category and str(category).lower() != "other":
            parts.append(f"Category: {category}")

        item_type = item.get("type")
        if item_type:
            parts.append(f"Type: {item_type}")

        color = item.get("color")
        if color:
            parts.append(f"Color: {color}")

        brand = item.get("brand")
        if brand:
            parts.append(f"Brand: {brand}")

        distinctive = item.get("distinctive_features")
        if distinctive:
            parts.append(f"Features: {distinctive}")

        location = item.get("location")
        if location:
            parts.append(f"Location: {location}")

        desc = item.get("description")
        if desc:
            parts.append(f"Description: {desc}")

        item_date = item.get("item_date") or item.get("reported_at")
        if item_date:
            parts.append(f"Date: {str(item_date)[:10]}")

        status = item.get("status")
        if status:
            parts.append(f"Status: {status}")

        return " | ".join(parts)

    def sync_item(self, item: dict):
        """Adds or updates a single item in the ChromaDB vector collection."""
        if not item or "id" not in item:
            return

        item_id = str(item["id"])
        doc = self.build_item_document(item)
        metadata = {
            "id": int(item["id"]),
            "type": str(item.get("type", "lost")).lower(),
            "status": str(item.get("status", "active")).lower(),
            "category": str(item.get("category") or "Other"),
            "location": str(item.get("location") or "")
        }

        self.collection.upsert(
            ids=[item_id],
            documents=[doc],
            metadatas=[metadata]
        )

    def delete_item(self, item_id: int):
        """Removes an item from the vector store."""
        try:
            self.collection.delete(ids=[str(item_id)])
        except Exception:
            pass

    def sync_all_from_db(self, db_conn):
        """Synchronizes all active records from SQLite into ChromaDB."""
        cursor = db_conn.cursor()
        cursor.execute("SELECT * FROM items")
        rows = cursor.fetchall()

        if not rows:
            return 0

        ids = []
        docs = []
        metadatas = []

        for row in rows:
            item = dict(row)
            item_id = str(item["id"])
            ids.append(item_id)
            docs.append(self.build_item_document(item))
            metadatas.append({
                "id": int(item["id"]),
                "type": str(item.get("type", "lost")).lower(),
                "status": str(item.get("status", "active")).lower(),
                "category": str(item.get("category") or "Other"),
                "location": str(item.get("location") or "")
            })

        if ids:
            self.collection.upsert(
                ids=ids,
                documents=docs,
                metadatas=metadatas
            )
        return len(ids)

    def parse_intent(self, query: str) -> str:
        """
        Infers whether the student is looking for a 'lost' item or reporting a 'found' item.
        - If query indicates student lost an item -> search among 'found' items.
        - If query indicates student found an item -> search among 'lost' items.
        - Otherwise returns 'all'.
        """
        q = query.lower()
        # "I lost...", "lost my...", "looking for my...", "missing..."
        lost_patterns = [
            r"\bi\s+lost\b", r"\blost\s+my\b", r"\blooking\s+for\s+my\b",
            r"\bmy\s+.*\s+is\s+lost\b", r"\bmisplaced\b", r"\bleft\s+behind\b",
            r"\bwhere\s+is\s+my\b"
        ]
        # "I found...", "found a...", "picked up..."
        found_patterns = [
            r"\bi\s+found\b", r"\bfound\s+a\b", r"\bfound\s+an\b",
            r"\bpicked\s+up\b", r"\bsomeone\s+left\b"
        ]

        for p in lost_patterns:
            if re.search(p, q):
                return "found"  # Student lost something, search FOUND items!

        for p in found_patterns:
            if re.search(p, q):
                return "lost"   # Student found something, search LOST reports!

        return "all"

    def search(self, query: str, scope: str = "all", top_k: int = 5, db_conn = None) -> list:
        """
        Executes semantic vector search against ChromaDB and verifies against SQLite database.
        Returns candidate items ranked by calibrated similarity score.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.strip()

        # If ChromaDB is empty and DB connection is provided, auto-sync
        if self.collection.count() == 0 and db_conn:
            self.sync_all_from_db(db_conn)

        if self.collection.count() == 0:
            return []

        # Determine target item type
        target_type = None
        if scope in ("lost", "found"):
            target_type = scope
        else:
            inferred = self.parse_intent(cleaned_query)
            if inferred in ("lost", "found"):
                target_type = inferred

        # Build ChromaDB where filter
        where_filter = {"status": "active"}
        if target_type:
            where_filter = {
                "$and": [
                    {"status": "active"},
                    {"type": target_type}
                ]
            }

        n_results = min(top_k * 3, max(1, self.collection.count()))
        results = None
        if target_type and scope != "all":
            # Strict scope requested by user
            try:
                results = self.collection.query(
                    query_texts=[cleaned_query],
                    n_results=n_results,
                    where=where_filter
                )
            except Exception:
                results = None
        elif target_type and scope == "all":
            # Inferred target type: try target type first, fallback to all active items if none found
            try:
                results = self.collection.query(
                    query_texts=[cleaned_query],
                    n_results=n_results,
                    where=where_filter
                )
            except Exception:
                results = None

            if not results or not results.get("ids") or not results["ids"][0]:
                try:
                    results = self.collection.query(
                        query_texts=[cleaned_query],
                        n_results=n_results,
                        where={"status": "active"}
                    )
                except Exception:
                    results = None
        else:
            try:
                results = self.collection.query(
                    query_texts=[cleaned_query],
                    n_results=n_results,
                    where={"status": "active"}
                )
            except Exception:
                results = None

        if not results or not results.get("ids") or not results["ids"][0]:
            try:
                results = self.collection.query(
                    query_texts=[cleaned_query],
                    n_results=n_results
                )
            except Exception:
                return []

        retrieved_ids = []
        retrieved_distances = {}
        if results and "ids" in results and results["ids"]:
            for id_str, dist in zip(results["ids"][0], results["distances"][0]):
                item_id = int(id_str)
                retrieved_ids.append(item_id)
                # In ChromaDB cosine space: distance in [0, 2], similarity = 1 - (dist / 2)
                similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
                retrieved_distances[item_id] = similarity

        if not retrieved_ids or not db_conn:
            return []

        # Retrieve authoritative SQLite database records
        cursor = db_conn.cursor()
        placeholders = ",".join("?" for _ in retrieved_ids)
        cursor.execute(f"SELECT * FROM items WHERE id IN ({placeholders}) AND status = 'active'", retrieved_ids)
        db_items = [dict(row) for row in cursor.fetchall()]

        ranked_results = []
        for item in db_items:
            item_id = item["id"]
            vector_sim = retrieved_distances.get(item_id, 0.5)

            # Attribute verification & evidence generation using HybridAIMatcher
            # Create a mock query item for attribute comparison
            query_doc = {"item_name": cleaned_query, "description": cleaned_query, "location": cleaned_query}
            attr_eval = self.matcher.evaluate_structured_attributes(query_doc, item)

            evidence = list(attr_eval["evidence"])
            
            # Check location proximity from text query
            item_loc = normalize_text(item.get("location") or "")
            if item_loc and item_loc in normalize_text(cleaned_query):
                evidence.append(f"Location match: {item.get('location')}")

            # Check category match
            item_cat = normalize_text(item.get("category") or "")
            if item_cat and item_cat != "other" and item_cat in normalize_text(cleaned_query):
                evidence.append(f"Category: {item.get('category')}")

            # Combined score: vector similarity + attribute boost
            combined_score = vector_sim + attr_eval["boost"]
            calibrated_score = round(max(0.05, min(0.96, combined_score)), 3)

            # Confidence label
            if calibrated_score >= config.STRONG_MATCH_THRESHOLD:
                confidence = "Strong potential match"
            elif calibrated_score >= config.POSSIBLE_MATCH_THRESHOLD:
                confidence = "Possible match"
            else:
                confidence = "Low similarity"

            if not evidence and calibrated_score >= config.SIMILARITY_THRESHOLD:
                evidence.append("Semantic similarity between search query and item description")

            item_result = {
                "id": item["id"],
                "type": item["type"],
                "item_name": item["item_name"],
                "category": item.get("category") or "Other",
                "description": item.get("description") or "",
                "color": item.get("color") or "",
                "brand": item.get("brand") or "",
                "distinctive_features": item.get("distinctive_features") or "",
                "location": item.get("location") or "Not specified",
                "item_date": item.get("item_date") or item.get("reported_at", "")[:10],
                "status": item.get("status") or "active",
                "reported_at": item.get("reported_at", ""),
                "similarity_score": calibrated_score,
                "confidence": confidence,
                "evidence": evidence
            }
            ranked_results.append(item_result)

        # Sort by similarity_score descending
        ranked_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return ranked_results[:top_k]

# Global singleton
rag_service_instance = RAGService()
