import os
import re
import logging
import chromadb
from chromadb.config import Settings
import config
from ai_matcher import HybridAIMatcher, normalize_text, expand_synonyms, build_item_representation

logger = logging.getLogger("college_lost_found.rag")

class RAGService:
    """
    Retrieval-Augmented Generation (RAG) vector service.
    Indexes lost and found items in ChromaDB using vector embeddings,
    synchronizes with SQLite records, and executes semantic retrieval.
    Includes automatic deterministic fallback using HybridAIMatcher to ensure zero downtime.
    """

    def __init__(self, chroma_path: str = None, collection_name: str = None, in_memory: bool = False):
        self.chroma_path = chroma_path or config.CHROMA_PATH
        self.collection_name = collection_name or config.CHROMA_COLLECTION
        self.in_memory = in_memory
        self.matcher = HybridAIMatcher()
        self.chroma_available = False
        self.client = None
        self.collection = None
        self._init_chroma()

    def _init_chroma(self):
        """Initializes ChromaDB client and collection safely."""
        try:
            if self.in_memory or self.chroma_path == ":memory:":
                self.client = chromadb.EphemeralClient()
            else:
                os.makedirs(self.chroma_path, exist_ok=True)
                self.client = chromadb.PersistentClient(path=self.chroma_path)
                
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self.chroma_available = True
            logger.info("ChromaDB vector store initialized successfully at: %s", self.chroma_path)
        except Exception as e:
            self.chroma_available = False
            self.collection = None
            logger.warning("ChromaDB vector store initialization failed (%s). Hybrid SQLite fallback active.", e)

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
        if not self.chroma_available or not self.collection or not item or "id" not in item:
            return

        try:
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
        except Exception as e:
            logger.warning("Failed to sync item %s to vector store: %s", item.get("id"), e)

    def delete_item(self, item_id: int):
        """Removes an item from the vector store."""
        if not self.chroma_available or not self.collection:
            return
        try:
            self.collection.delete(ids=[str(item_id)])
        except Exception as e:
            logger.warning("Failed to delete item %d from vector store: %s", item_id, e)

    def sync_all_from_db(self, db_conn):
        """Synchronizes all active records from SQLite into ChromaDB."""
        if not self.chroma_available or not self.collection:
            return 0

        try:
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
            logger.info("Synchronized %d items to ChromaDB vector store.", len(ids))
            return len(ids)
        except Exception as e:
            logger.warning("ChromaDB batch sync warning: %s", e)
            return 0

    def parse_intent(self, query: str) -> str:
        """
        Infers whether the student is looking for a 'lost' item or reporting a 'found' item.
        - If query indicates student lost an item -> search among 'found' items.
        - If query indicates student found an item -> search among 'lost' items.
        - Otherwise returns 'all'.
        """
        q = query.lower()
        lost_patterns = [
            r"\bi\s+lost\b", r"\blost\s+my\b", r"\blooking\s+for\s+my\b",
            r"\bmy\s+.*\s+is\s+lost\b", r"\bmisplaced\b", r"\bleft\s+behind\b",
            r"\bwhere\s+is\s+my\b"
        ]
        found_patterns = [
            r"\bi\s+found\b", r"\bfound\s+a\b", r"\bfound\s+an\b",
            r"\bpicked\s+up\b", r"\bsomeone\s+left\b"
        ]

        for p in lost_patterns:
            if re.search(p, q):
                return "found"  # Student lost something, search FOUND items

        for p in found_patterns:
            if re.search(p, q):
                return "lost"   # Student found something, search LOST reports

        return "all"

    def search(self, query: str, scope: str = "all", top_k: int = 5, db_conn = None) -> list:
        """
        Executes semantic vector search against ChromaDB and verifies against SQLite database.
        If ChromaDB is unavailable or encounters errors, seamlessly uses HybridAIMatcher fallback.
        """
        if not query or not query.strip():
            return []

        cleaned_query = query.strip()
        if not db_conn:
            return []

        # Determine target item type
        target_type = None
        if scope in ("lost", "found"):
            target_type = scope
        else:
            inferred = self.parse_intent(cleaned_query)
            if inferred in ("lost", "found"):
                target_type = inferred

        # Attempt ChromaDB semantic vector search first
        chroma_success = False
        retrieved_ids = []
        retrieved_distances = {}

        if self.chroma_available and self.collection:
            try:
                # If ChromaDB collection is empty, attempt a quick sync
                if self.collection.count() == 0 and db_conn:
                    self.sync_all_from_db(db_conn)

                if self.collection.count() > 0:
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

                    try:
                        results = self.collection.query(
                            query_texts=[cleaned_query],
                            n_results=n_results,
                            where=where_filter if target_type else {"status": "active"}
                        )
                    except Exception:
                        results = None

                    # If scoped query returned nothing, relax filter
                    if (not results or not results.get("ids") or not results["ids"][0]) and target_type:
                        try:
                            results = self.collection.query(
                                query_texts=[cleaned_query],
                                n_results=n_results,
                                where={"status": "active"}
                            )
                        except Exception:
                            results = None

                    if results and results.get("ids") and len(results["ids"]) > 0 and results["ids"][0]:
                        ids_list = results["ids"][0]
                        dists_list = results["distances"][0] if (results.get("distances") and len(results["distances"]) > 0) else []
                        for idx, id_str in enumerate(ids_list):
                            try:
                                item_id = int(id_str)
                                retrieved_ids.append(item_id)
                                dist = dists_list[idx] if idx < len(dists_list) else 0.5
                                similarity = max(0.0, min(1.0, 1.0 - (float(dist) / 2.0)))
                                retrieved_distances[item_id] = similarity
                            except (ValueError, TypeError):
                                continue
                        if retrieved_ids:
                            chroma_success = True
            except Exception as e:
                logger.warning("ChromaDB vector query error: %s. Using Hybrid matcher fallback.", e)
                chroma_success = False

        # If ChromaDB succeeded, load records for retrieved IDs
        if chroma_success and retrieved_ids:
            cursor = db_conn.cursor()
            placeholders = ",".join("?" for _ in retrieved_ids)
            cursor.execute(f"SELECT * FROM items WHERE id IN ({placeholders}) AND status = 'active'", retrieved_ids)
            candidate_rows = [dict(row) for row in cursor.fetchall()]
        else:
            # Fallback: retrieve all active items from SQLite database directly
            cursor = db_conn.cursor()
            if target_type and scope != "all":
                cursor.execute("SELECT * FROM items WHERE type = ? AND status = 'active'", (target_type,))
            else:
                cursor.execute("SELECT * FROM items WHERE status = 'active'")
            candidate_rows = [dict(row) for row in cursor.fetchall()]

        if not candidate_rows:
            return []

        # Rank all candidate rows using HybridAIMatcher (TF-IDF + Domain synonyms + Attributes)
        query_doc = {"item_name": cleaned_query, "description": cleaned_query, "location": cleaned_query}
        ranked_results = []

        for item in candidate_rows:
            item_id = item["id"]
            
            # Semantic text similarity
            item_text = build_item_representation(item)
            text_sim = self.matcher.compute_semantic_similarity(cleaned_query, item_text)
            
            # Incorporate ChromaDB vector similarity if available
            vector_sim = retrieved_distances.get(item_id, text_sim)
            base_similarity = (vector_sim * 0.6 + text_sim * 0.4) if item_id in retrieved_distances else text_sim

            # Attribute verification & evidence generation
            attr_eval = self.matcher.evaluate_structured_attributes(query_doc, item)
            evidence = list(attr_eval["evidence"])
            
            # Proximity and category checks from query text
            norm_q = normalize_text(cleaned_query)
            item_loc = normalize_text(item.get("location") or "")
            if item_loc and len(item_loc) > 2 and item_loc in norm_q:
                evidence.append(f"Location match: {item.get('location')}")

            item_cat = normalize_text(item.get("category") or "")
            if item_cat and item_cat != "other" and item_cat in norm_q:
                evidence.append(f"Category: {item.get('category')}")

            # Combined calibrated score
            combined_score = base_similarity + attr_eval["boost"]
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

        # Sort by similarity score descending
        ranked_results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return ranked_results[:top_k]


# Global singleton
rag_service_instance = RAGService()
