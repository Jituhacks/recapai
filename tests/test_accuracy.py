"""
Milestone 1 — Task 5: Speech-to-Text Transcription Accuracy & Word Error Rate (WER) Evaluation
"""

import os
import sys
import glob

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.audio_service import extract_audio_with_ffmpeg, cleanup_files
from services.whisper_service import transcribe_audio_file
from services.accuracy_service import compute_wer_metrics, format_accuracy_report

# Ground truth reference transcript for the full Simplilearn AI Explained recording
REFERENCE_FULL_TRANSCRIPT = """
It's a weekend, and John decided to watch the latest movie recommended by Netflix at his friend's place.
Before heading out, he asked Siri about the weather and realized it would rain.
So he decided to take his Tesla for the long journey and switch to autopilot on the highway.
After coming home from the eventful day, he started wondering how technology made his life easy.
He did some research on the internet and found out that Netflix, Siri and Tesla are all using AI.
So what is AI? AI or artificial intelligence is nothing but making computer-based machines think and act like humans.
Artificial intelligence is not a new term. John McCarthy, a computer scientist, coined the term artificial intelligence back in 1956.
But it took time to evolve as it demanded heavy computing power.
Artificial intelligence is not confined to just movie recommendations and virtual assistants.
Broadly classifying, there are three types of AI:
Artificial narrow intelligence, also called weak AI, is the stage where machines can perform specific tasks.
Netflix, Siri, chatbots, facial recognition systems are all examples of artificial narrow intelligence.
Next up, we have artificial general intelligence, referred to as an intelligent agent's capacity to comprehend or pick up any intellectual skill that a human can.
We are halfway in successfully implementing this space. IBM's Watson supercomputer and GPT-3 fall under this category.
And lastly, Artificial Super Intelligence. It is the stage where machines surpass human intelligence.
You might have seen this in movies and imagined how the world would be if machines ruled.
Fascinated by this, John did more research and found out that machine learning, deep learning, and natural language processing are all connected with artificial intelligence.
Machine Learning, a subset of AI, is the process of automating and enhancing how computers learn from their experiences without human help.
Machine learning can be used in email spam detection, medical diagnosis, etc.
Deep learning can be considered a subset of machine learning. It is a field that is based on learning and improving on its own by examining computer algorithms.
While machine learning uses simpler concepts, deep learning works with artificial neural networks, which are designed to imitate the human brain.
This technology can be applied in face recognition, speech recognition, and many more applications.
Natural language processing, popularly known as NLP, can be defined as the ability of machines to understand human language and translate it.
Chatbots fall under this category.
Artificial intelligence is advancing in every crucial field like healthcare, education, robotics, banking, e-commerce, and the list goes on.
In healthcare, AI is used to identify diseases, helping healthcare service providers and their patients make better treatment and lifestyle decisions.
Coming to the education sector, AI is helping teachers automate grading, organizing and facilitating parent-teacher conversations.
In robotics, AI-powered robots employ real-time updates to detect obstructions in their path and instantly design their routes.
Artificial intelligence provides advanced data analytics that is transforming banking by reducing fraud and enhancing compliance.
With this growing demand for AI, more and more industries are looking for AI engineers who can help them develop intelligent systems and offer them lucrative salaries going north of $120,000.
The future of AI looks promising with the AI market expected to reach $190 billion by 2025.
So, on that note, I have a question for you. Artificial intelligence is about playing a computer game, creating a device using your own intelligence to program an intelligent machine, investing your brain power in a machine.
Give the correct answer along with your reasoning and stand a chance to win an Amazon voucher.
Think about it and leave your answers in the comments section and we will provide the answer next week.
We hope you enjoyed this video. If you did, a thumbs up would be really appreciated.
Here's your reminder to subscribe to our channel and click on the bell icon for more on the latest technologies and trends.
Thank you for watching and stay tuned for more from Simplilearn.
"""

REFERENCE_SHORT_TRANSCRIPT = """
It's a weekend, and John decided to watch the latest movie recommended by Netflix at his friend's place.
Before heading out, he asked Siri about the weather and realized it would rain.
So he decided to take his Tesla for the long journey and switch to autopilot on the highway.
After coming home from the eventful day, he started wondering how technology made his life easy.
He did some research on the internet and found out that Netflix, Siri and Tesla are all using AI.
So what is AI? AI or artificial intelligence is nothing but making computer-based machines think and act like humans.
Artificial intelligence is not a new term. John McCarthy, a computer scientist, coined the term artificial intelligence back in 1956.
"""

def test_transcription_accuracy_benchmark():
    """
    Evaluates transcription accuracy on multiple recordings and formats:
    1. MP4 Video (Simplilearn AI Explained Full)
    2. WAV Audio (Simplilearn AI Explained Full Audio Stream)
    3. MP3 Audio (Short tech talk excerpt)
    
    Verifies that Accuracy = 1 - WER >= 0.90 (90%) on suitable recordings.
    """
    test_cases = [
        {
            "name": "Simplilearn AI Explained",
            "file": glob.glob("Media/*.mp4")[0],
            "format": "MP4 Video",
            "reference": REFERENCE_FULL_TRANSCRIPT
        },
        {
            "name": "AI Explained Mono Audio",
            "file": "Media/demo_audio.wav",
            "format": "WAV Audio",
            "reference": REFERENCE_FULL_TRANSCRIPT
        },
        {
            "name": "Tech Talk Intro Snippet",
            "file": "Media/demo_short.mp3",
            "format": "MP3 Audio",
            "reference": REFERENCE_SHORT_TRANSCRIPT
        }
    ]

    benchmark_records = []

    for tc in test_cases:
        filepath = tc["file"]
        if not os.path.exists(filepath):
            continue

        temp_wav = f"audio/temp_acc_{os.path.basename(filepath)}.wav"
        try:
            extract_audio_with_ffmpeg(filepath, temp_wav)
            result = transcribe_audio_file(temp_wav)
            hypothesis = result["transcript"]

            metrics = compute_wer_metrics(tc["reference"], hypothesis)
            metrics["recording"] = tc["name"]
            metrics["format"] = tc["format"]

            benchmark_records.append(metrics)

            print(f"\n--- Benchmark: {tc['name']} ({tc['format']}) ---")
            print(f"Reference Words: {metrics['reference_words']}")
            print(f"Hypothesis Words: {metrics['hypothesis_words']}")
            print(f"Substitutions: {metrics['substitutions']}")
            print(f"Deletions: {metrics['deletions']}")
            print(f"Insertions: {metrics['insertions']}")
            print(f"WER: {metrics['wer']:.4f}")
            print(f"Accuracy: {metrics['accuracy_percent']}")

            assert metrics["accuracy"] >= 0.90, f"Accuracy {metrics['accuracy_percent']} is below 90% target!"

        finally:
            cleanup_files(temp_wav)

    report_table = format_accuracy_report(benchmark_records)
    print("\n" + "="*80)
    print("TASK 5: FINAL ACCURACY BENCHMARK REPORT")
    print("="*80)
    print(report_table)
    print("="*80)

if __name__ == "__main__":
    test_transcription_accuracy_benchmark()