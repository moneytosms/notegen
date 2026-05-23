from notes_gen.processing.filter import remove_meta


def test_removes_sponsor_mention():
    text = "Today's video is sponsored by NordVPN. Get 70% off at nordvpn.com/channel.\nNow let's talk about Python."
    result = remove_meta(text)
    assert "nordvpn" not in result.lower()
    assert "Python" in result


def test_removes_subscribe_call():
    text = "Please smash that like button and subscribe to my channel for more content!\nPython generators are powerful."
    result = remove_meta(text)
    assert "subscribe" not in result.lower()
    assert "generators" in result


def test_removes_social_plugs():
    text = "Follow me on Twitter @dev and Instagram @devgram.\nAsyncio uses an event loop."
    result = remove_meta(text)
    assert "twitter" not in result.lower()
    assert "event loop" in result


def test_keeps_conceptual_content():
    text = "Python's asyncio module provides infrastructure for writing single-threaded concurrent code."
    result = remove_meta(text)
    assert "asyncio" in result
    assert len(result) > 0


def test_empty_input():
    assert remove_meta("") == ""


def test_single_line_transcript_not_fully_stripped():
    """Transcript with no newlines must not lose all content when one phrase matches."""
    text = (
        "Welcome to this tutorial. "
        "Please like and subscribe to my channel for more content. "
        "Today we learn about Python generators. "
        "A generator yields values lazily."
    )
    result = remove_meta(text)
    assert "Python generators" in result
    assert "generator" in result
    assert "subscribe" not in result.lower()


def test_single_line_sponsor_mid_transcript():
    """Sponsor mention mid-transcript removed without eating surrounding content."""
    text = (
        "First let's cover async/await. "
        "This video is sponsored by NordVPN. "
        "Now back to coroutines and event loops."
    )
    result = remove_meta(text)
    assert "async" in result
    assert "coroutines" in result
    assert "nordvpn" not in result.lower()


def test_removes_patreon_plug():
    text = "Support me on Patreon to get early access.\nDecorators wrap functions."
    result = remove_meta(text)
    assert "patreon" not in result.lower()
    assert "Decorators" in result


def test_removes_merch_mention():
    text = "Check out my merch store at teespring.com/myshop.\nContext managers use __enter__ and __exit__."
    result = remove_meta(text)
    assert "merch" not in result.lower()
    assert "__enter__" in result
