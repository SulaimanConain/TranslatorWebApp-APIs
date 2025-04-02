# Healthcare AI Translator

A real-time speech-to-text translation application designed for healthcare providers to communicate effectively with patients who speak different languages.

![Healthcare AI Translator](https://i.imgur.com/your-screenshot.jpg)

## Features

- 🎤 Real-time speech recognition
- 🌐 Support for multiple languages
- ⚡ Instant word-by-word transcription
- 🔄 Real-time translation
- 🌙 Dark/Light theme support
- 📱 Responsive design for all devices
- 🌍 Cross-browser compatibility

## Supported Languages

### Input Languages
- Arabic
- Bengali
- Chinese (Simplified & Traditional)
- English
- French
- German
- Gujarati
- Hindi
- Kannada
- Malayalam
- Marathi
- Mongolian
- Nepali
- Persian
- Portuguese
- Punjabi
- Russian
- Sindhi
- Spanish
- Swedish
- Tamil
- Telugu
- Urdu

### Translation Languages
- English
- Hindi
- Arabic
- Portuguese

## Tech Stack

- **Frontend:**
  - HTML5
  - CSS3
  - JavaScript (ES6+)
  - Web Speech API

- **Backend:**
  - Python
  - Flask
  - Flask-CORS
  - Langdetect
  - Lingua

- **AI/ML:**
  - Local LLM (Ollama)
  - LlamaX3 Model

## Prerequisites

- Python 3.8 or higher
- Ollama installed and running locally
- Modern web browser (Chrome, Firefox, Safari, or Edge)
- Microphone access

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/healthcare-ai-translator.git
   cd healthcare-ai-translator
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Ensure Ollama is running with the LlamaX3 model:
   ```bash
   ollama run mannix/llamax3-8b-alpaca
   ```

5. Start the Flask server:
   ```bash
   python app.py
   ```

6. Open your browser and navigate to:
   ```
   http://localhost:8888
   ```

## Usage

1. Select the patient's language from the "Patient's Language" dropdown
2. Choose your preferred language in "Healthcare Provider's Language"
3. Click the "Start Recording" button
4. Speak clearly into your microphone
5. View real-time transcription and translation
6. Click "Stop Recording" when finished

## Browser Compatibility

- Google Chrome (Recommended)
- Mozilla Firefox
- Microsoft Edge
- Safari
- Mobile browsers

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Web Speech API for speech recognition
- Ollama for local LLM support
- Flask for the backend framework
- All contributors and supporters

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.