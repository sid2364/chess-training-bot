import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chess_trainer.bot_profile import BotProfile


def test_is_challenge_allowed_specific_user_only():
    profile = BotProfile(allowed_username=" SomeUser ")

    assert profile.is_challenge_allowed("someuser")
    assert not profile.is_challenge_allowed("otheruser")
    assert not profile.is_challenge_allowed(None)


def test_is_challenge_allowed_when_free_for_all_enabled():
    profile = BotProfile(allowed_username="SomeUser", allow_all_challengers=True)

    assert profile.is_challenge_allowed("otheruser")
    assert profile.is_challenge_allowed(None)


def test_is_challenge_allowed_when_no_username_configured():
    profile = BotProfile()

    assert profile.is_challenge_allowed("anyone")
    assert profile.is_challenge_allowed(None)
