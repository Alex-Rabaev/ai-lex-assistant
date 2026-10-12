"""Constants for audio transcription module.

Contains error messages, duration limits, and supported formats
for audio message processing.
"""

# Duration limit (5 minutes)
MAX_AUDIO_DURATION_SECONDS = 300

# Supported audio MIME types
SUPPORTED_AUDIO_FORMATS = [
    "audio/ogg",
    "audio/mpeg",
    "audio/mp4",
    "audio/wav",
]

# System error messages for agent communication
# These messages are sent to the agent who responds naturally to the user
AUDIO_TOO_LONG = "[SYSTEM: Audio too long (>5min)]"
TRANSCRIPTION_FAILED = "[SYSTEM: Audio transcription failed]"
UNSUPPORTED_FORMAT = "[SYSTEM: Unsupported audio format]"
