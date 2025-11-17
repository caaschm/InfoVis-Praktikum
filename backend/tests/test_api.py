"""Smoke tests for Plottery backend."""
import pytest

# Test client is provided by conftest.py fixture


def test_health_endpoint(client):
    """Test that the health endpoint returns 200 OK."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_root_endpoint(client):
    """Test that the root endpoint returns welcome message."""
    response = client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Plottery" in data["message"]


def test_create_and_get_document(client):
    """Test creating a document and retrieving it."""
    # Create document
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Test Story",
            "content": "This is the first sentence. This is the second sentence."
        }
    )
    
    assert create_response.status_code == 201
    document = create_response.json()
    assert document["title"] == "Test Story"
    assert len(document["sentences"]) == 2
    
    # Get document
    doc_id = document["id"]
    get_response = client.get(f"/api/documents/{doc_id}")
    
    assert get_response.status_code == 200
    retrieved = get_response.json()
    assert retrieved["id"] == doc_id
    assert retrieved["title"] == "Test Story"


def test_list_documents(client):
    """Test listing all documents."""
    response = client.get("/api/documents/")
    
    assert response.status_code == 200
    documents = response.json()
    assert isinstance(documents, list)


def test_update_sentence(client):
    """Test updating a sentence with new text and emojis."""
    # Create document first
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Test Story",
            "content": "Once upon a time."
        }
    )
    
    document = create_response.json()
    sentence_id = document["sentences"][0]["id"]
    
    # Update sentence
    update_response = client.patch(
        f"/api/sentences/{sentence_id}",
        json={
            "text": "Once upon a time in a magical land.",
            "emojis": ["🧙‍♂️", "✨", "🏰"]
        }
    )
    
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["text"] == "Once upon a time in a magical land."
    assert len(updated["emojis"]) == 3


@pytest.mark.asyncio
async def test_ai_emoji_generation(client):
    """Test AI emoji generation endpoint (uses dummy data for now)."""
    # Create document first
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Test Story",
            "content": "The dragon roared fiercely."
        }
    )
    
    document = create_response.json()
    sentence_id = document["sentences"][0]["id"]
    
    # Request emoji suggestions
    ai_response = client.post(
        "/api/ai/emojis-from-text",
        json={
            "document_id": document["id"],
            "sentence_id": sentence_id,
            "text": "The dragon roared fiercely."
        }
    )
    
    assert ai_response.status_code == 200
    result = ai_response.json()
    assert "emojis" in result
    assert isinstance(result["emojis"], list)
    assert len(result["emojis"]) <= 5


@pytest.mark.asyncio
async def test_ai_text_generation(client):
    """Test AI text generation from emojis (uses dummy data for now)."""
    # Create document first
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Test Story",
            "content": "Beginning of story."
        }
    )
    
    document = create_response.json()
    
    # Request text suggestions
    ai_response = client.post(
        "/api/ai/text-from-emojis",
        json={
            "document_id": document["id"],
            "sentence_id": None,
            "emojis": ["😱", "🌙", "🏚️"]
        }
    )
    
    assert ai_response.status_code == 200
    result = ai_response.json()
    assert "suggested_text" in result
    assert isinstance(result["suggested_text"], str)
    assert len(result["suggested_text"]) > 0
