import pdfplumber
import requests
import base64
import spacy
import heapq

# Load spaCy's English NLP model
nlp = spacy.load("en_core_web_sm")

API_BASE_URL = "https://api.sws.speechify.com"
VOICE_ID = "george"

# Function to summarize the text using spaCy
def summarize_text_spacy(input_text):
    doc = nlp(input_text)
  
    # Create a frequency distribution of words (excluding stop words and punctuation)
    word_freq = {}
    for word in doc:
        if word.text.lower() not in nlp.Defaults.stop_words and word.is_alpha:
            if word.text.lower() not in word_freq:
                word_freq[word.text.lower()] = 1
            else:
                word_freq[word.text.lower()] += 1

    # Get the maximum frequency
    max_freq = max(word_freq.values(), default=1)

    # Normalize the word frequencies (scale them)
    for word in word_freq:
        word_freq[word] = (word_freq[word] / max_freq)

    # Score each sentence based on the frequency of words it contains
    sentence_scores = {}
    for sent in doc.sents:
        for word in sent:
            if word.text.lower() in word_freq:
                if sent not in sentence_scores:
                    sentence_scores[sent] = word_freq[word.text.lower()]
                else:
                    sentence_scores[sent] += word_freq[word.text.lower()]

    # Select the top N sentences (based on the highest score)
    num_sentences = 5  # Adjust as needed
    summarized_sentences = heapq.nlargest(num_sentences, sentence_scores, key=sentence_scores.get)

    # Combine the summarized sentences to form the summary
    summary = " ".join([str(sentence) for sentence in summarized_sentences])
  
    return summary

# Function to generate the podcast script
def generate_podcast_script(pdf_text, summary):
    podcast_script = (
        "Welcome to today's podcast! Let's dive into an exciting topic.\n\n"
        f"\n{pdf_text}\n\n"
        f":\n{summary}\n\n"
        "Hope you learned something new and interesting today!"
    )
    return podcast_script

# Function to convert text to audio using Speechify API
def get_audio(text):
    url = f"{API_BASE_URL}/v1/audio/speech"
    payload = {
        "input": f"<speak>{text}</speak>",
        "voice_id": VOICE_ID,
        "audio_format": "mp3",
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    } 

    response = requests.post(url, json=payload, headers=headers)

    if not response.ok:
        raise Exception(f"{response.status_code} {response.reason}\n{response.text}")

    response_data = response.json()
    decoded_audio_data = base64.b64decode(response_data["audio_data"])

    return decoded_audio_data

# Function to convert PDF to text using pdfplumber
def convert_pdf_to_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        text = ''
        # Loop through all pages and extract text
        for page in pdf.pages:
            text += page.extract_text()
    return text.strip()

def main():
    # Path to your PDF file
    pdf_file = "input.pdf"

    # Extract text from the PDF
    pdf_text = convert_pdf_to_text(pdf_file)
    if not pdf_text:
        print("Error: The PDF appears to be empty or contains unsupported content.")
        return

    # Summarize the extracted text
    summary = summarize_text_spacy(pdf_text)

    # Generate the podcast script
    podcast_script = generate_podcast_script(pdf_text, summary)

    # Save the podcast script to a text file
    with open("output.txt", "w", encoding="utf-8") as text_file:
        text_file.write(podcast_script)

    # Generate audio from the podcast script
    audio = get_audio(podcast_script)

    # Save the audio as an MP3 file
    output_file = "speech.mp3"
    with open(output_file, "wb") as file:
        file.write(audio)

    print(f"Podcast script saved to 'output.txt' and audio saved to '{output_file}'.")

if __name__ == "__main__":
    main()
