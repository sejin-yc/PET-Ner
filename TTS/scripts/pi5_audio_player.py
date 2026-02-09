#!/usr/bin/env python3
"""
라즈베리파이5 음성 재생 클라이언트.
- MQTT topic 'pi5/audio/play' 구독
- payload: {"id": 1, "audioUrl": "http://server/api/uploads/audio/xxx.wav", "userId": 1, "type": "tts_cloned"}
- audioUrl에서 WAV 다운로드 → I2S(ALSA)로 재생 → 서버에 재생 상태 PATCH (PLAYED/FAILED)
환경변수:
  MQTT_BROKER: 브로커 주소 (기본 tcp://localhost:1883)
  MQTT_TOPIC: 구독 토픽 (기본 pi5/audio/play)
  MQTT_USERNAME, MQTT_PASSWORD: (선택)
  SERVER_BASE_URL: 서버 주소, 상태 업데이트용 (예 http://192.168.0.10:8080/api)
  ALSA_DEVICE: aplay 디바이스 (기본 hw:0,0 또는 plughw:0,0)
"""
import json
import os
import subprocess
import tempfile
import urllib.request
import urllib.error

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("pip install paho-mqtt")
    raise

MQTT_BROKER = os.getenv("MQTT_BROKER", "tcp://localhost:1883").replace("tcp://", "").split(":")
MQTT_HOST = MQTT_BROKER[0] if MQTT_BROKER else "localhost"
MQTT_PORT = int(MQTT_BROKER[1]) if len(MQTT_BROKER) > 1 else 1883
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "pi5/audio/play")
MQTT_USER = os.getenv("MQTT_USERNAME", "")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")
SERVER_BASE_URL = os.getenv("SERVER_BASE_URL", "http://localhost:8080/api").rstrip("/")
ALSA_DEVICE = os.getenv("ALSA_DEVICE", "plughw:0,0")


def download_wav(url: str) -> bytes:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def play_wav_with_aplay(wav_path: str, device: str = ALSA_DEVICE) -> bool:
    try:
        subprocess.run(
            ["aplay", "-D", device, "-q", wav_path],
            check=True,
            timeout=120,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"aplay error: {e}")
        return False


def update_status(playback_id: int, status: str, error_message: str = None):
    url = f"{SERVER_BASE_URL}/audio/{playback_id}/status"
    data = {"status": status}
    if error_message:
        data["errorMessage"] = error_message[:500]
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            method="PATCH",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"Status updated: {playback_id} -> {status}")
    except Exception as e:
        print(f"Failed to update status: {e}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except Exception as e:
        print(f"Invalid JSON: {e}")
        return
    playback_id = payload.get("id")
    audio_url = payload.get("audioUrl")
    if not playback_id or not audio_url:
        print("Missing id or audioUrl")
        return
    print(f"Play id={playback_id} url={audio_url}")
    update_status(playback_id, "PLAYING")
    tmp = None
    try:
        wav_bytes = download_wav(audio_url)
        if not wav_bytes:
            update_status(playback_id, "FAILED", "Empty download")
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(wav_bytes)
            tmp = f.name
        if play_wav_with_aplay(tmp):
            update_status(playback_id, "PLAYED")
        else:
            update_status(playback_id, "FAILED", "aplay failed")
    except urllib.error.URLError as e:
        update_status(playback_id, "FAILED", f"Download error: {e}")
    except Exception as e:
        update_status(playback_id, "FAILED", str(e))
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def main():
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        print(f"MQTT connect failed: {e}")
        return
    client.subscribe(MQTT_TOPIC)
    print(f"Subscribed to {MQTT_TOPIC}. SERVER_BASE_URL={SERVER_BASE_URL}")
    client.loop_forever()


if __name__ == "__main__":
    main()
