from app.services.similarity import find_similar_ticket


def test_similarity_function_exists():
    """
    Similarity function must exist.
    """
    assert callable(find_similar_ticket)


def test_similarity_returns_none_when_no_data():
    """
    When no resolved tickets exist, return None.
    """
    result = find_similar_ticket(
        new_message="Login not working",
        resolved_tickets=[]
    )
    assert result is None


def test_similarity_return_type():
    """
    If match exists, function must return dict or None.
    """
    result = find_similar_ticket(
        new_message="Login issue",
        resolved_tickets=[{"message": "Cannot login"}]
    )
    assert result is None or isinstance(result, dict)
