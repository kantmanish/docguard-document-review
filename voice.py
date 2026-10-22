"""Optional offline TTS; microphone speech-to-text varies by browser and OS."""
def speak_text(text):
    try:
        import pyttsx3
        engine=pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True, "Read-aloud finished."
    except Exception as e:
        return False, f"Read-aloud unavailable: {e}. Install pyttsx3 and a system voice."
