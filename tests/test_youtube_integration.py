# ==============================================================================
# OPERATION JARVIS -- Test Suite: YouTube Production & DaVinci Resolve Integration
# ==============================================================================
import os
import sys
import json
import pytest

# Ensure root is in path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from youtube_production.creator_voice import get_voice_profile, sync_voice_profile_to_memory
from youtube_production.davinci_resolve import (
    inspect_resolve_environment,
    generate_cmx3600_edl,
    generate_fcpxml,
    install_resolve_assistant_script
)
from youtube_production.youtube_api import YouTubeClient, SCOPES, QUOTA_COSTS
from youtube_production.orchestrator import YouTubeProductionOrchestrator

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:04,500
Stop editing YouTube videos manually. Today we automate DaVinci Resolve with local AI.

2
00:00:05,800 --> 00:00:10,200
Basically um uh so yeah.

3
00:00:11,500 --> 00:00:17,000
In this first section we examine DaVinci Resolve project architecture and scripting workflows.

4
00:00:18,500 --> 00:00:24,000
Here is how you configure timeline video tracks and audio buses properly.

5
00:00:27,000 --> 00:00:33,000
Moving on to part two, we inspect YouTube Data API v3 upload authorization and scopes.

6
00:00:34,000 --> 00:00:41,000
OAuth 2.0 requires minimum permissions to protect creator accounts from token exposure.

7
00:00:43,000 --> 00:00:50,000
Finally in section three, we demonstrate full pipeline execution with human approval gates.

8
00:00:52,000 --> 00:00:58,000
Thank you for watching and check the description for project resources.
"""

def test_youtube_plugin_skills_discovery():
    """Verifies all 11 skills exist in the plugin directory with valid metadata."""
    skills_dir = os.path.join(ROOT, ".gemini", "config", "plugins", "youtube-production", "skills")
    assert os.path.exists(skills_dir), f"Plugin skills dir not found at {skills_dir}"
    
    expected_skills = [
        "yt-audit", "yt-chapters", "yt-comment", "yt-edit",
        "yt-package", "yt-plan", "yt-retention", "yt-script",
        "yt-seo", "yt-shorts", "yt-viral"
    ]
    for skill in expected_skills:
        skill_path = os.path.join(skills_dir, skill, "SKILL.md")
        assert os.path.exists(skill_path), f"Missing {skill}/SKILL.md"
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "name:" in content
            assert "description:" in content

def test_davinci_resolve_environment_detection():
    """Verifies detection of installed DaVinci Resolve 21.0.4 Free."""
    info = inspect_resolve_environment()
    assert info["installed"] is True
    assert "21.0" in info["version"]
    assert info["external_headless_scripting"] is False
    assert info["internal_workspace_scripts_supported"] is True
    assert "CMX 3600 EDL" in info["supported_interchange_formats"]

def test_davinci_edl_and_fcpxml_generation(tmp_path):
    """Verifies CMX 3600 EDL and FCPXML generation from cut lists."""
    cuts = [
        {"kind": "DEAD", "start": 4.5, "end": 5.8},
        {"kind": "FILLER", "start": 10.0, "end": 12.0}
    ]
    edl_file = tmp_path / "test.edl"
    fcpxml_file = tmp_path / "test.fcpxml"
    
    generate_cmx3600_edl(cuts, "source.mp4", 30.0, str(edl_file), fps=30)
    assert edl_file.exists()
    edl_text = edl_file.read_text(encoding="utf-8")
    assert "TITLE: JARVIS_DAVINCI_AUTO_EDIT" in edl_text
    assert "001  SOURCE   V     C" in edl_text
    
    generate_fcpxml(cuts, "source.mp4", 30.0, str(fcpxml_file), fps=30)
    assert fcpxml_file.exists()
    xml_text = fcpxml_file.read_text(encoding="utf-8")
    assert "<fcpxml" in xml_text
    assert "FFVideoFormat1080p30" in xml_text

def test_davinci_internal_assistant_installation():
    """Verifies installation of internal helper script in DaVinci user scripts folder."""
    path = install_resolve_assistant_script()
    assert path is not None
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        assert "JARVIS DaVinci Resolve Assistant" in f.read()

def test_youtube_api_safety_and_scopes():
    """Verifies least privilege scopes, quota costs, and human approval gating for public publishing."""
    client = YouTubeClient()
    status = client.get_status()
    assert "https://www.googleapis.com/auth/youtube.upload" in status["scopes"]
    assert "https://www.googleapis.com/auth/youtube.readonly" in status["scopes"]
    assert status["upload_cost_units"] == 1600
    
    # Private and unlisted must succeed
    v1 = client.validate_metadata(
        title="Valid Test Video",
        description="Description",
        privacy_status="private"
    )
    assert v1["valid"] is True
    
    v2 = client.validate_metadata(
        title="Valid Test Video",
        description="Description",
        privacy_status="unlisted"
    )
    assert v2["valid"] is True
    
    # Public publishing without confirmation MUST raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        client.validate_metadata(
            title="Public Video",
            description="Description",
            privacy_status="public",
            confirm_public_publishing=False
        )
    assert "Explicit human approval required" in str(exc_info.value)
    
    # Public publishing with confirmation succeeds
    v3 = client.validate_metadata(
        title="Public Video Confirmed",
        description="Description",
        privacy_status="public",
        confirm_public_publishing=True
    )
    assert v3["valid"] is True

def test_creator_voice_profile_and_memory():
    """Verifies creator voice preferences and sync with local memory."""
    profile = get_voice_profile()
    assert profile["default_upload_privacy"] == "private"
    assert profile["require_public_approval"] is True
    assert "game-changer" in profile["banned_words"]
    
    synced = sync_voice_profile_to_memory()
    assert synced is True
    assert os.path.exists(os.path.join(ROOT, "creator_voice.md"))

def test_orchestrator_end_to_end_pipeline(tmp_path):
    """Verifies complete production pipeline: hooks, title lint, dead air, chapters, upload manifest."""
    transcript_file = tmp_path / "test.srt"
    transcript_file.write_text(SAMPLE_SRT, encoding="utf-8")
    
    orch = YouTubeProductionOrchestrator()
    
    hooks = [
        "I spent 30 days analyzing 100 YouTube channels and here is why you are failing",
        "Stop editing YouTube videos manually: here is how to automate DaVinci Resolve in 60 seconds"
    ]
    titles = [
        {"title": "Automate DaVinci Resolve With Local AI Agents (2026 Walkthrough)", "thumb": "STOP EDITING"}
    ]
    
    package = orch.assemble_production_package(
        topic="Automate DaVinci Resolve With Local AI Agents",
        candidate_hooks=hooks,
        candidate_titles=titles,
        transcript_path=str(transcript_file),
        media_filename="take_1.mp4"
    )
    
    assert package["winning_hook"] is not None
    assert package["winning_title"] is not None
    assert package["davinci_edits"]["cut_count"] > 0
    assert os.path.exists(package["davinci_edits"]["edl_path"])
    assert os.path.exists(package["davinci_edits"]["fcpxml_path"])
    assert len(package["chapters"]["chapters"]) >= 3
    assert package["chapters"]["valid"] is True
    assert package["upload_manifest"]["status"]["privacyStatus"] == "private"
