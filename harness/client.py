"""
client.py — shared ElevenLabs client setup.

Handles two environment quirks so the other modules don't have to:

1. Corporate SSL inspection.
   Managed laptops route HTTPS through a proxy that re-signs certificates with
   an internal CA. That CA is trusted by Windows but NOT by Python, which ships
   its own certificate bundle — hence CERTIFICATE_VERIFY_FAILED.

   The fix is `truststore`, which makes Python use the operating system's
   certificate store instead of its bundled one. That trusts the corporate CA
   because the OS already does, without disabling verification. Do not "fix"
   this by setting verify=False; that turns off certificate checking entirely.

2. SDK request shape.
   tests.create() takes a single `request` argument, not keyword arguments:
       create(*, request: TestsCreateRequestBody, ...)
"""

import os


def _use_os_certificates() -> bool:
    """Route Python's SSL through the OS certificate store. Returns True on success."""
    try:
        import truststore
        truststore.inject_into_ssl()
        return True
    except ImportError:
        return False


def get_client(require_agent: bool = False):
    """Build an authenticated client, or exit with a clear message."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise SystemExit("Missing ELEVENLABS_API_KEY in .env")

    if require_agent and not os.getenv("ELEVENLABS_AGENT_ID"):
        raise SystemExit("Missing ELEVENLABS_AGENT_ID in .env")

    if not _use_os_certificates():
        print("Note: truststore not installed. If you hit CERTIFICATE_VERIFY_FAILED "
              "on a corporate network, run: python -m pip install truststore\n")

    from elevenlabs import ElevenLabs
    return ElevenLabs(api_key=api_key)


def get_agent_id() -> str:
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")
    if not agent_id:
        raise SystemExit("Missing ELEVENLABS_AGENT_ID in .env")
    return agent_id
