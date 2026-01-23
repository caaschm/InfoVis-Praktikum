
import pytest

def test_manual_update_not_marked_ai(client):
    """
    Test that manually adding a new sentence (without ai_suggestion_text)
    does NOT mark it as AI-generated.
    """
    # 1. Create document
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Manual Update Test",
            "content": "Original sentence."
        }
    )
    assert create_response.status_code == 201
    doc = create_response.json()
    doc_id = doc["id"]
    
    # 2. Update with manual text
    # We add a new sentence "Manual sentence."
    new_content = "Original sentence. Manual sentence."
    
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": new_content
            # No ai_suggestion_text provided
        }
    )
    
    assert update_response.status_code == 200
    updated_doc = update_response.json()
    sentences = updated_doc["sentences"]
    assert len(sentences) == 2
    
    # Verify neither is AI generated
    for s in sentences:
        assert s["is_ai_generated"] is False


def test_ai_update_selective_marking(client):
    """
    Test that when ai_suggestion_text is provided, only the matching sentence
    is marked as AI-generated, and other new sentences are NOT.
    """
    # 1. Create document
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "AI Update Test",
            "content": "Original sentence."
        }
    )
    doc_id = create_response.json()["id"]
    
    # 2. Update with MIXED content (Manual + AI)
    # Scenario: The user manually typed "Manual addition." and also applied AI text "AI generated part."
    manual_text = "Manual addition."
    ai_text = "AI generated part."
    new_content = f"Original sentence. {manual_text} {ai_text}"
    
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": new_content,
            "ai_suggestion_text": ai_text
        }
    )
    
    assert update_response.status_code == 200
    updated_doc = update_response.json()
    sentences = updated_doc["sentences"]
    assert len(sentences) == 3
    
    # Check each sentence
    # "Original sentence." -> OLD, not AI
    # "Manual addition." -> NEW, matching nothing -> Should be NOT AI (This is the fix)
    # "AI generated part." -> NEW, matches ai_suggestion_text -> Should be AI
    
    s_original = next(s for s in sentences if "Original" in s["text"])
    s_manual = next(s for s in sentences if "Manual" in s["text"])
    s_ai = next(s for s in sentences if "AI generated" in s["text"])
    
    assert s_original["is_ai_generated"] is False
    assert s_manual["is_ai_generated"] is False  # This is the critical check!
    assert s_ai["is_ai_generated"] is True
