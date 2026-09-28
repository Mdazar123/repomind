from paystream.auth.tokens import issue_token, token_is_active


def test_fresh_token_is_active():
    now = 1_700_000_000.0
    token = issue_token("ada", ttl_seconds=3600, now=now)
    assert token_is_active(token, now=now + 10)


def test_expired_token_is_inactive():
    now = 1_700_000_000.0
    token = issue_token("ada", ttl_seconds=60, now=now)
    assert not token_is_active(token, now=now + 120)
