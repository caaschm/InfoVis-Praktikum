
import pytest
import json

def test_manual_edit_removes_highlight(client):
    """
    Test that manually editing an AI-generated sentence removes the highlight.
    """
    # 1. Create document
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Edit Test",
            "content": "Original text."
        }
    )
    doc_id = create_response.json()["id"]
    sentence_id = create_response.json()["sentences"][0]["id"]
    
    # 2. Mark it as AI generated (simulating Apply button logic manually via DB hacking or just relying on existing flow being mocked? 
    # Actually we can use the backend logic we know handles this: pass ai_suggestion_text)
    
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "AI generated.",
            "ai_suggestion_text": "AI generated."
        }
    )
    assert update_response.status_code == 200
    s = update_response.json()["sentences"][0]
    assert s["is_ai_generated"] is True
    
    # 3. Manually edit the text (via sentences endpoint)
    # Change "AI generated." to "AI generated manually."
    # NOTE: New behavior is to PRESERVE highlight during edit to ensure splitting works correctly later.
    
    edit_response = client.patch(
        f"/api/sentences/{s['id']}",
        json={
            "text": "AI generated manually."
        }
    )
    
    assert edit_response.status_code == 200
    edited_s = edit_response.json()
    
    # Also verify via document fetch
    doc_response = client.get(f"/api/documents/{doc_id}")
    doc_s = doc_response.json()["sentences"][0]
    
    # EXPECTATION CHANGED: Edit preserves highlight (until split)
    assert doc_s["is_ai_generated"] is True

def test_manual_add_no_highlight(client):
    """
    Test that manually adding a sentence does NOT highlight it.
    """
    # 1. Create
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Add Test",
            "content": "Old."
        }
    )
    doc_id = create_response.json()["id"]
    
    # 2. Update via documents endpoint (split logic)
    # Add "New manual."
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "Old. New manual."
        }
    )
    
    sentences = update_response.json()["sentences"]
    assert len(sentences) == 2
    
    manual_s = next(s for s in sentences if "New manual" in s["text"])
    assert manual_s["is_ai_generated"] is False

def test_punctuation_edit_preserves_highlight(client):
    """
    Test that editing ONLY punctuation preserves the AI highlight.
    """
    # 1. Create with AI text (no dot)
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Punct Test",
            "content": "Old text"
        }
    )
    doc_id = create_response.json()["id"]
    s = create_response.json()["sentences"][0]
    
    # 2. Mark as AI
    client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "AI text",
            "ai_suggestion_text": "AI text"
        }
    )
    
    # Refresh sentence ID (as document update recreates sentences)
    doc_response = client.get(f"/api/documents/{doc_id}")
    s = doc_response.json()["sentences"][0]
    
    # 3. Add dot (via sentences endpoint - simulates quick edit)
    edit_response = client.patch(
        f"/api/sentences/{s['id']}",
        json={
            "text": "AI text."
        }
    )
    assert edit_response.status_code == 200
    assert edit_response.json()["is_ai_generated"] is True
    
    # 4. Add dot (via documents endpoint - simulates split/merged edit)
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "AI text.."  # Two dots
        }
    )
    s_updated = update_response.json()["sentences"][0]
    # Normalization should handle "AI text.." matching "AI text." or "AI text"
    assert s_updated["is_ai_generated"] is True

def test_multiple_ai_generations_preserve_highlight(client):
    """
    Test that adding a NEW AI sentence keeps the OLD AI sentence highlighted.
    """
    # 1. Start with initial AI sentence
    create_response = client.post(
        "/api/documents/",
        json={
            "title": "Multi AI Test",
            "content": "Old text."
        }
    )
    doc_id = create_response.json()["id"]
    
    # Mark first as AI
    client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "AI First.",
            "ai_suggestion_text": "AI First."
        }
    )
    s1 = client.get(f"/api/documents/{doc_id}").json()["sentences"][0]
    assert s1["text"] == "AI First."
    assert s1["is_ai_generated"] is True
    
    # 2. Add SECOND AI sentence (simulating apply)
    # The new content has both sentences
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={
            "content": "AI First. AI Second.",
            "ai_suggestion_text": "AI Second." # Only the new one is in the suggestion
        }
    )
    
    sentences = update_response.json()["sentences"]
    assert len(sentences) == 2
    
    old_s = next(s for s in sentences if "First" in s["text"])
    new_s = next(s for s in sentences if "Second" in s["text"])
    
    assert new_s["is_ai_generated"] is True, "New sentence should be highlighted"
    assert old_s["is_ai_generated"] is True, "Old sentence should STAY highlighted"

def test_split_extended_ai_sentence(client):
    """
    Test that when an extended AI sentence (AI+Manual) is split, the AI part keeps highlight.
    """
    # 1. Start with AI sentence
    create_response = client.post("/api/documents/", json={"title": "Split Test", "content": "Old."})
    doc_id = create_response.json()["id"]
    client.patch(f"/api/documents/{doc_id}", json={"content": "AI Part.", "ai_suggestion_text": "AI Part."})
    
    # 2. Simulate "lazy" typing that merges sentences locally/temporarily in DB
    # User types " Manual" -> "AI Part. Manual" (stored as one sentence initially)
    # Refresh ID just in case
    s = client.get(f"/api/documents/{doc_id}").json()["sentences"][0]
    client.patch(f"/api/sentences/{s['id']}", json={"text": "AI Part. Manual"})
    
    # Verify intermediate state: One big sentence, Flag TRUE (preserved by recent changes)
    s_merged = client.get(f"/api/documents/{doc_id}").json()["sentences"][0]
    assert s_merged["text"] == "AI Part. Manual"
    assert s_merged["is_ai_generated"] is True
    
    # 3. Simulate structural split (update document content)
    # The backend should split "AI Part. Manual" -> "AI Part." + "Manual"
    # And "AI Part." should RECOVER the True flag from the merged parent
    update_response = client.patch(
        f"/api/documents/{doc_id}",
        json={"content": "AI Part. Manual"}
    )
    
    sentences = update_response.json()["sentences"]
    assert len(sentences) == 2
    
    ai_part = next(s for s in sentences if "AI Part" in s["text"])
    manual_part = next(s for s in sentences if "Manual" in s["text"])
    
    assert ai_part["is_ai_generated"] is True, "AI Prefix should keep highlight"
    assert manual_part["is_ai_generated"] is False, "Manual suffix should NOT be highlighted"
