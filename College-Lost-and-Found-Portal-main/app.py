import os
import time
import sqlite3
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

import config
import database
from ai_matcher import HybridAIMatcher
from llm_service import llm_service_instance
from rag_service import rag_service_instance

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("college_lost_found")

app = Flask(__name__, static_folder=None)

matcher = HybridAIMatcher()

def get_db():
    return database.get_db_connection()

# Initialize database schema safely on application boot without blocking port binding
with app.app_context():
    try:
        database.init_db()
    except Exception as e:
        logger.warning("Database schema init deferred: %s", e)

# -------------------------------------------------------------
# Health Check Endpoint (Render & Production Monitoring)
# -------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health_check():
    """Returns HTTP 200 with service readiness metrics."""
    return jsonify({
        'status': 'healthy',
        'service': 'college_lost_found_portal',
        'llm_provider': config.LLM_PROVIDER,
        'api_key_configured': llm_service_instance.is_api_key_configured(),
        'chroma_available': rag_service_instance.chroma_available,
        'timestamp': datetime.now().isoformat()
    }), 200

# -------------------------------------------------------------
# Static root route
# -------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# -------------------------------------------------------------
# AI RAG Natural Language Search Endpoint
# -------------------------------------------------------------
@app.route('/api/ai/search', methods=['POST'])
def ai_search():
    """
    RAG Search:
    1. Validates student natural-language query.
    2. Performs semantic vector retrieval across SQLite records (with Hybrid fallback).
    3. Feeds verified records to Multi-LLM service (Gemini / OpenRouter / OpenAI) to synthesize a grounded summary.
    4. Returns ranked real database records with similarity metrics.
    """
    start_time = time.time()
    data = request.get_json(silent=True)
    if not data:
        logger.warning("Search AI request received invalid or empty JSON body.")
        return jsonify({'message': 'Invalid request body. Expected JSON.'}), 400

    query = data.get('query', '').strip()
    if not query:
        logger.warning("Search AI request received empty query.")
        return jsonify({'message': 'Search query cannot be empty.'}), 400

    if len(query) > 500:
        return jsonify({'message': 'Query exceeds maximum allowed length of 500 characters.'}), 400

    scope = data.get('scope', 'all')
    if scope not in ('all', 'lost', 'found'):
        scope = 'all'

    limit = data.get('limit', 5)
    try:
        limit = max(1, min(10, int(limit)))
    except (ValueError, TypeError):
        limit = 5

    logger.info("Executing Search AI: query='%s', scope='%s', limit=%d", query, scope, limit)

    conn = get_db()
    try:
        # Retrieve semantically matching candidate items from database
        results = rag_service_instance.search(query=query, scope=scope, top_k=limit, db_conn=conn)

        # Pass query and factual records to LLM for grounded conversational explanation
        llm_output = llm_service_instance.synthesize_rag_response(query=query, retrieved_items=results)

        duration = time.time() - start_time
        logger.info("Search AI completed in %.2fs: %d items retrieved, LLM status: %s",
                    duration, len(results), llm_output.get('status'))

        return jsonify({
            'query': query,
            'scope': scope,
            'api_key_configured': llm_output.get('api_key_configured', False),
            'llm_response': llm_output.get('summary', ''),
            'disclaimer': llm_output.get('disclaimer', 'Possible matches — not confirmed ownership'),
            'status': llm_output.get('status', 'success'),
            'provider': llm_output.get('provider', 'local'),
            'items_found': len(results),
            'results': results
        }), 200
    except Exception as e:
        logger.error("AI Search error on query '%s': %s", query, e, exc_info=True)
        return jsonify({
            'message': 'An error occurred while processing the search request.',
            'results': []
        }), 500
    finally:
        conn.close()

# -------------------------------------------------------------
# Items Endpoints
# -------------------------------------------------------------
@app.route('/api/items', methods=['GET'])
def get_items():
    """
    Retrieves reported items.
    Privacy safeguard: Redacts sensitive student phone, email, and registration number
    from public feeds unless authorized campus staff provides X-Admin-Key.
    """
    is_admin = request.headers.get('X-Admin-Key') == config.ADMIN_KEY
    item_type = request.args.get('type')
    status_filter = request.args.get('status')

    query = 'SELECT * FROM items WHERE 1=1'
    params = []

    if item_type:
        query += ' AND type = ?'
        params.append(item_type)

    if status_filter:
        query += ' AND status = ?'
        params.append(status_filter)

    query += ' ORDER BY reported_at DESC'

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    items = []
    for row in rows:
        item = dict(row)
        if not is_admin:
            # Mask student personal information for privacy
            item['contact_number'] = 'Verification Required'
            item['contact_email'] = 'Protected'
            item['registration_number'] = 'Protected'
        items.append(item)

    return jsonify(items)

@app.route('/api/items', methods=['POST'])
def add_item():
    """
    Reports a new lost or found item.
    - Saves record in SQLite database.
    - Updates vector store for RAG retrieval.
    - Automatically computes matches against active opposite-type candidates.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message': 'Invalid JSON'}), 400

    item_type = data.get('type')
    item_name = data.get('item_name') or data.get('name')
    student_name = data.get('student_name')
    registration_number = data.get('registration_number')
    contact_number = data.get('contact_number')
    contact_email = data.get('contact_email')

    if not all([item_type, item_name, student_name, registration_number, contact_number, contact_email]):
        return jsonify({
            'message': 'Missing required fields: type, item_name, student_name, registration_number, contact_number, contact_email'
        }), 400

    if item_type not in ('lost', 'found'):
        return jsonify({'message': 'Invalid type. Must be "lost" or "found".'}), 400

    category = data.get('category', 'Other')
    description = data.get('description', '')
    color = data.get('color', '')
    brand = data.get('brand', '')
    distinctive_features = data.get('distinctive_features', '')
    location = data.get('location', '')
    item_date = data.get('item_date', '')
    department = data.get('department', '')
    year_of_study = data.get('year_of_study', '')
    reported_at = datetime.now().isoformat()

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO items (
                type, item_name, category, description, color, brand,
                distinctive_features, location, item_date, status,
                student_name, registration_number, contact_number,
                contact_email, department, year_of_study, reported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item_type, item_name, category, description, color, brand,
            distinctive_features, location, item_date,
            student_name, registration_number, contact_number,
            contact_email, department, year_of_study, reported_at
        ))
        new_id = cursor.lastrowid
        conn.commit()

        # Build dict for synchronization
        new_item = {
            'id': new_id,
            'type': item_type,
            'item_name': item_name,
            'category': category,
            'description': description,
            'color': color,
            'brand': brand,
            'distinctive_features': distinctive_features,
            'location': location,
            'item_date': item_date,
            'status': 'active',
            'reported_at': reported_at
        }

        # Sync into ChromaDB vector store safely
        try:
            rag_service_instance.sync_item(new_item)
        except Exception as e:
            logger.warning("RAG vector sync warning: %s", e)

        # Compute candidate matches against opposite-type active items
        opposite_type = 'found' if item_type == 'lost' else 'lost'
        candidates = conn.execute(
            "SELECT * FROM items WHERE type = ? AND status = 'active'",
            (opposite_type,)
        ).fetchall()

        now_str = datetime.now().isoformat()
        for cand in candidates:
            cand_dict = dict(cand)
            lost_item = new_item if item_type == 'lost' else cand_dict
            found_item = cand_dict if item_type == 'lost' else new_item

            score_info = matcher.score_pair(lost_item, found_item)
            if score_info['similarity_score'] >= config.SIMILARITY_THRESHOLD:
                explanation = llm_service_instance.generate_explanation(lost_item, found_item, score_info)
                evidence_str = "; ".join(score_info.get('evidence', []))

                cursor.execute('''
                    INSERT OR REPLACE INTO matches (
                        lost_item_id, found_item_id, similarity_score,
                        match_confidence, explanation, matching_evidence,
                        status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                ''', (
                    lost_item['id'], found_item['id'],
                    score_info['similarity_score'],
                    score_info['confidence'],
                    explanation, evidence_str,
                    now_str, now_str
                ))
        conn.commit()

        return jsonify({'message': 'Item added successfully', 'id': new_id}), 201
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Database error while adding item: %s", e, exc_info=True)
        return jsonify({'message': f'Database error: {e}'}), 500
    finally:
        conn.close()

# -------------------------------------------------------------
# Status Update Endpoint
# -------------------------------------------------------------
@app.route('/api/items/<int:item_id>/status', methods=['PATCH'])
def update_item_status(item_id):
    """Updates item status (active/resolved). Requires campus staff authorization."""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != config.ADMIN_KEY:
        return jsonify({'message': 'Unauthorized: Valid X-Admin-Key required'}), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get('status')
    if new_status not in ('active', 'resolved'):
        return jsonify({'message': 'Invalid status. Must be "active" or "resolved".'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'message': 'Item not found'}), 404

    # Update matches
    if new_status == 'resolved':
        cursor.execute(
            "UPDATE matches SET status = 'resolved' WHERE lost_item_id = ? OR found_item_id = ?",
            (item_id, item_id)
        )
    conn.commit()

    # Re-fetch item to sync with vector store
    cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
    item_row = cursor.fetchone()
    conn.close()

    if item_row:
        try:
            rag_service_instance.sync_item(dict(item_row))
        except Exception:
            pass

    return jsonify({'message': 'Item status updated successfully', 'status': new_status}), 200

# -------------------------------------------------------------
# Secure Admin Item Deletion Endpoint
# -------------------------------------------------------------
@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """
    Secure admin-only item deletion.
    Permanently deletes an item and cleans up related matches, claims, and vector embeddings.
    """
    admin_key = request.headers.get('X-Admin-Key')
    if not admin_key or admin_key != config.ADMIN_KEY:
        return jsonify({'success': False, 'message': 'Unauthorized: Valid admin authorization required'}), 403

    if item_id <= 0:
        return jsonify({'success': False, 'message': 'Invalid item ID'}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, item_name FROM items WHERE id = ?", (item_id,))
        item_row = cursor.fetchone()
        if not item_row:
            return jsonify({'success': False, 'message': 'Item not found'}), 404

        item_name = item_row['item_name']

        # Delete related claims
        cursor.execute("DELETE FROM claims WHERE item_id = ?", (item_id,))

        # Delete related matches
        cursor.execute("DELETE FROM matches WHERE lost_item_id = ? OR found_item_id = ?", (item_id, item_id))

        # Delete item record
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()

        # Clean up ChromaDB vector store
        try:
            rag_service_instance.delete_item(item_id)
        except Exception as e:
            logger.warning("Vector store cleanup warning for item %d: %s", item_id, e)

        logger.info("Admin successfully deleted item %d (%s)", item_id, item_name)
        return jsonify({
            'success': True,
            'message': f'Item "{item_name}" deleted successfully',
            'id': item_id
        }), 200
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Database error while deleting item %d: %s", item_id, e, exc_info=True)
        return jsonify({'success': False, 'message': 'Database error occurred during deletion'}), 500
    finally:
        conn.close()

# -------------------------------------------------------------
# Admin Verification Endpoint
# -------------------------------------------------------------
@app.route('/api/admin/verify', methods=['POST'])
def verify_admin():
    """Validates administrator authorization credentials."""
    admin_key = request.headers.get('X-Admin-Key')
    if not admin_key or admin_key != config.ADMIN_KEY:
        return jsonify({'authenticated': False, 'message': 'Unauthorized: Invalid admin key'}), 403
    return jsonify({'authenticated': True, 'message': 'Admin authorization verified'}), 200

# -------------------------------------------------------------
# Automated Matches Endpoints
# -------------------------------------------------------------
@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Lists candidate matches between lost and found items."""
    status_filter = request.args.get('status')

    query = '''
        SELECT m.id, m.lost_item_id, m.found_item_id, m.similarity_score,
               m.match_confidence, m.explanation, m.matching_evidence, m.status,
               l.item_name AS lost_name, l.status AS lost_status,
               f.item_name AS found_name, f.status AS found_status
        FROM matches m
        JOIN items l ON m.lost_item_id = l.id
        JOIN items f ON m.found_item_id = f.id
        WHERE l.status = 'active' AND f.status = 'active'
    '''
    params = []
    if status_filter:
        query += ' AND m.status = ?'
        params.append(status_filter)

    query += ' ORDER BY m.similarity_score DESC'

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()

    matches = []
    for r in rows:
        matches.append({
            'id': r['id'],
            'lost_id': r['lost_item_id'],
            'found_id': r['found_item_id'],
            'lost_item_name': r['lost_name'],
            'found_item_name': r['found_name'],
            'similarity_score': r['similarity_score'],
            'confidence': r['match_confidence'],
            'explanation': r['explanation'],
            'evidence': r['matching_evidence'],
            'status': r['status']
        })

    return jsonify(matches)

# -------------------------------------------------------------
# Claims Endpoints
# -------------------------------------------------------------
@app.route('/api/claims', methods=['POST'])
def submit_claim():
    """Submits a verification claim with identifying marks for an item."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'message': 'Invalid JSON'}), 400

    item_id = data.get('item_id')
    claimant_name = data.get('claimant_name')
    claimant_contact = data.get('claimant_contact')
    claimant_email = data.get('claimant_email')
    verification_details = data.get('verification_details')

    if not all([item_id, claimant_name, claimant_contact, claimant_email, verification_details]):
        return jsonify({'message': 'Missing required fields for claim submission'}), 400

    now_str = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO claims (
                item_id, claimant_name, claimant_contact,
                claimant_email, verification_details, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        ''', (item_id, claimant_name, claimant_contact, claimant_email, verification_details, now_str, now_str))
        claim_id = cursor.lastrowid
        conn.commit()
        return jsonify({'message': 'Claim submitted successfully', 'id': claim_id}), 201
    except sqlite3.Error as e:
        conn.rollback()
        logger.error("Database error while submitting claim: %s", e, exc_info=True)
        return jsonify({'message': f'Database error: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/claims', methods=['GET'])
def get_claims():
    """Inspects pending claims. Requires campus staff authorization."""
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != config.ADMIN_KEY:
        return jsonify({'message': 'Unauthorized: Valid X-Admin-Key required'}), 403

    conn = get_db()
    rows = conn.execute('SELECT * FROM claims ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# -------------------------------------------------------------
# Dashboard Statistics Endpoint
# -------------------------------------------------------------
@app.route('/api/dashboard/stats', methods=['GET'])
def get_stats():
    """Returns database metrics."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'lost'")
    total_lost = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE type = 'found'")
    total_found = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'active'")
    active_reports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE status = 'resolved'")
    resolved_reports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM matches WHERE status = 'pending'")
    potential_matches = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'total_lost': total_lost,
        'total_found': total_found,
        'active_reports': active_reports,
        'resolved_reports': resolved_reports,
        'potential_matches': potential_matches
    })

# -------------------------------------------------------------
# Safe Static File Route and API Error Handlers
# -------------------------------------------------------------
ALLOWED_STATIC_EXTENSIONS = {
    '.html', '.htm', '.css', '.js', '.json',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    '.woff', '.woff2', '.ttf', '.eot'
}

@app.route('/<path:filename>')
def static_files(filename):
    """Serves static assets safely while blocking sensitive server files."""
    # Prevent interception of API routes
    if filename.startswith('api/') or filename == 'api' or filename.startswith('health'):
        return jsonify({'message': 'Endpoint not found'}), 404

    # Prevent path traversal and hidden files
    normalized = os.path.normpath(filename).replace('\\', '/')
    parts = normalized.split('/')
    if any(part.startswith('.') for part in parts):
        return jsonify({'message': 'Access denied'}), 403

    ext = os.path.splitext(normalized)[1].lower()
    if ext not in ALLOWED_STATIC_EXTENSIONS:
        return jsonify({'message': 'File type not permitted'}), 403

    return send_from_directory('.', normalized)

@app.errorhandler(400)
def handle_bad_request(e):
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Bad Request: ' + str(getattr(e, 'description', 'Invalid request'))}), 400
    return e

@app.errorhandler(404)
def handle_not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Endpoint not found'}), 404
    return e

@app.errorhandler(405)
def handle_method_not_allowed(e):
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Method not allowed for this endpoint'}), 405
    return e

@app.errorhandler(500)
def handle_internal_server_error(e):
    logger.error("Internal Server Error on %s %s: %s", request.method, request.path, e, exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Internal server error. Please try again later.'}), 500
    return e

@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    logger.error("Unhandled Exception on %s %s: %s", request.method, request.path, e, exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({'message': 'Internal server error'}), 500
    raise e

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=config.DEBUG)