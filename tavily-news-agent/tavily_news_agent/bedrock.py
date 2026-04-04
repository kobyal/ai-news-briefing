"""AWS Bedrock LLM client for the Tavily News Agent.

Uses boto3 + anthropic[bedrock] SDK. Credentials are read from:
  1. AWS_PROFILE env var (SSO profile — recommended)
  2. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY env vars (IAM user)
  3. Default AWS credential chain (instance profile, ~/.aws/credentials)
"""
import json
import os
import time


# Bedrock model IDs — EU cross-region inference profiles (account 599843985030)
_DEFAULT_WRITER_MODEL     = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
_DEFAULT_TRANSLATOR_MODEL = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

_WRITER_MODEL     = lambda: os.environ.get("BEDROCK_WRITER_MODEL",     _DEFAULT_WRITER_MODEL)
_TRANSLATOR_MODEL = lambda: os.environ.get("BEDROCK_TRANSLATOR_MODEL", _DEFAULT_TRANSLATOR_MODEL)
_REGION           = lambda: os.environ.get("AWS_BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-west-1"))


def _get_client():
    """Create AnthropicBedrock client from available credentials."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic[bedrock] not installed — run: pip install 'anthropic[bedrock]'")

    kwargs = {"aws_region": _REGION()}

    # SSO profile takes priority when no explicit keys (set AWS_PROFILE env var)
    # Explicit IAM keys override profile if both are set
    ak = os.environ.get("AWS_ACCESS_KEY_ID")
    sk = os.environ.get("AWS_SECRET_ACCESS_KEY")
    st = os.environ.get("AWS_SESSION_TOKEN")
    profile = os.environ.get("AWS_PROFILE")

    if ak and sk:
        kwargs["aws_access_key"] = ak
        kwargs["aws_secret_key"] = sk
        if st:
            kwargs["aws_session_token"] = st
    elif profile:
        # Let boto3 resolve SSO credentials via profile
        import boto3
        session = boto3.Session(profile_name=profile, region_name=_REGION())
        creds = session.get_credentials().get_frozen_credentials()
        kwargs["aws_access_key"]    = creds.access_key
        kwargs["aws_secret_key"]    = creds.secret_key
        if creds.token:
            kwargs["aws_session_token"] = creds.token

    return anthropic.AnthropicBedrock(**kwargs)


def invoke(prompt: str, *, model: str, system: str = None,
           json_mode: bool = False, label: str = "") -> str:
    """Call Bedrock Claude and return the text response."""
    client = _get_client()

    if json_mode:
        # Prefix with JSON instruction since Bedrock doesn't support response_format
        prompt = prompt + "\n\nReturn ONLY valid JSON. No markdown fences, no explanation."

    messages = [{"role": "user", "content": prompt}]
    kwargs = {
        "model": model,
        "max_tokens": 4096,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    t0 = time.time()
    response = client.messages.create(**kwargs)
    elapsed = time.time() - t0

    text = response.content[0].text if response.content else ""

    # Cost estimate (rough — Haiku is ~$0.0008/1K input, $0.004/1K output on Bedrock)
    in_tok  = response.usage.input_tokens  if hasattr(response, "usage") else 0
    out_tok = response.usage.output_tokens if hasattr(response, "usage") else 0
    cost_est = (in_tok * 0.0008 + out_tok * 0.004) / 1000
    print(f"    ✓  {label:<22} {elapsed:5.1f}s   model={model.split('.')[-1][:30]}  ~${cost_est:.4f}")
    return text


def test_connectivity() -> bool:
    """Quick ping to verify Bedrock is reachable with current credentials."""
    try:
        response = invoke(
            "Reply with only the word: OK",
            model=_WRITER_MODEL(),
            label="BedrockTest",
        )
        return "ok" in response.lower()
    except Exception as e:
        print(f"  [Bedrock] Connectivity test failed: {e}")
        return False
