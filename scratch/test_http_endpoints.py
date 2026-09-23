import requests
import json

base_url = "http://127.0.0.1:5000"

print("--- 1. Testing GET / ---")
r_index = requests.get(f"{base_url}/")
print(f"Status: {r_index.status_code}, Length: {len(r_index.text)} bytes")
assert r_index.status_code == 200
assert "Infosys Springboard" in r_index.text

print("\n--- 2. Testing GET /health ---")
r_health = requests.get(f"{base_url}/health")
health_data = r_health.json()
print(json.dumps(health_data, indent=2))
assert r_health.status_code == 200
assert health_data["status"] == "healthy"
assert health_data["ffmpeg_available"] == True

print("\n--- 3. Testing GET /api/sample-video-info ---")
r_sample = requests.get(f"{base_url}/api/sample-video-info")
sample_data = r_sample.json()
print(json.dumps(sample_data, indent=2))
assert r_sample.status_code == 200
assert sample_data["available"] == True

print("\n--- 4. Testing POST /transcribe (End-to-End Flow) ---")
r_transcribe = requests.post(f"{base_url}/transcribe", data={"use_sample": "true"})
print(f"Status: {r_transcribe.status_code}")
transcribe_data = r_transcribe.json()

assert r_transcribe.status_code == 200
assert transcribe_data["success"] == True

print(f"Filename: {transcribe_data['filename']}")
print(f"Filesize: {transcribe_data['filesize_mb']} MB")
print(f"Language: {transcribe_data['language']}")
print(f"Metrics: {json.dumps(transcribe_data['metrics'], indent=2)}")
print(f"Total Segments: {len(transcribe_data['segments'])}")
print(f"Sample Segment #1: {json.dumps(transcribe_data['segments'][0], indent=2)}")
print(f"Sample Segment #2: {json.dumps(transcribe_data['segments'][1], indent=2)}")
print(f"\nTranscript (first 350 chars):\n{transcribe_data['transcript'][:350]}...\n")
print(f"SRT preview (first 150 chars):\n{transcribe_data['srt'][:150]}...\n")

print("============================================================")
print("SUCCESS: ALL ENDPOINTS & PIPELINE VERIFIED SUCCESSFULLY!")
print("============================================================")
