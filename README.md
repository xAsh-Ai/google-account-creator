# Google Account Creator

Automated Google account creation system using ADB + OCR with VPN rotation and SMS verification.

## 🚀 Features

- **Automated Account Creation**: Creates Google accounts using Android devices controlled via ADB
- **OCR Technology**: Recognizes UI elements and performs human-like inputs
- **VPN Rotation**: Integrates with BrightProxy for IP rotation and anonymity
- **SMS Verification**: Automated SMS verification using 5sim.net service
- **Multi-Device Support**: Parallel processing across multiple Android devices
- **Device Fingerprint Randomization**: Maximizes account survival rates
- **Comprehensive Logging**: Detailed logging and survival rate monitoring
- **Human-like Behavior**: Simulates natural user interactions

## 📋 Requirements

- Python 3.9+
- Android devices with USB debugging enabled
- ADB (Android Debug Bridge) installed
- BrightProxy VPN service account
- 5sim.net SMS verification service account

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/xAsh-Ai/google-account-creator.git
   cd google-account-creator
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env file with your API keys and configuration
   ```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```env
# TaskMaster AI (for project management)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# VPN Service
BRIGHTPROXY_API_KEY=your_brightproxy_api_key_here
BRIGHTPROXY_USERNAME=your_brightproxy_username
BRIGHTPROXY_PASSWORD=your_brightproxy_password

# SMS Verification
FIVESIM_API_KEY=your_5sim_api_key_here
```

## 🚀 Usage

### Basic Usage

```bash
# Run with default settings (1 device)
python main.py

# Run with multiple devices
python main.py --devices 3

# Run with custom configuration
python main.py --config custom_config.json

# Run in verbose mode
python main.py --verbose

# Run with specific number of accounts
python main.py --accounts 10
```

### Advanced Usage

```bash
# Run with VPN rotation
python main.py --vpn-rotate --devices 2

# Run with custom delay settings
python main.py --min-delay 30 --max-delay 120

# Run with specific device IDs
python main.py --device-ids device1,device2,device3

# Run in headless mode
python main.py --headless
```

## 📁 Project Structure

```
google-account-creator/
├── core/                   # Core functionality modules
│   ├── __init__.py
│   ├── adb_controller.py   # ADB device control
│   ├── ocr_engine.py       # OCR text recognition
│   ├── vpn_manager.py      # VPN rotation management
│   └── sms_handler.py      # SMS verification handling
├── workers/                # Worker processes
│   ├── __init__.py
│   ├── account_worker.py   # Account creation worker
│   └── device_manager.py   # Device management
├── data/                   # Data storage
│   ├── accounts/           # Created account data
│   └── logs/              # Application logs
├── screenshots/            # OCR screenshots
├── tests/                  # Unit tests
├── docs/                   # Documentation
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## 🔧 Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=core --cov=workers

# Run specific test file
pytest tests/test_ocr_engine.py
```

### Code Formatting

```bash
# Format code with Black
black .

# Check code style with flake8
flake8 .

# Type checking with mypy
mypy .
```

## 📊 Monitoring

The system provides comprehensive logging and monitoring:

- **Account Creation Logs**: Detailed logs of each account creation attempt
- **Success/Failure Rates**: Statistics on account survival rates
- **Device Performance**: Monitoring of device responsiveness and errors
- **VPN Status**: VPN connection and rotation status
- **SMS Verification**: SMS reception and verification status

## ⚠️ Legal Notice

This tool is for educational and research purposes only. Users are responsible for:

- Complying with Google's Terms of Service
- Following applicable laws and regulations
- Using the tool ethically and responsibly
- Respecting rate limits and service guidelines

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/xAsh-Ai/google-account-creator/issues) page
2. Create a new issue with detailed information
3. Include logs and error messages when reporting bugs

## 🔄 Changelog

### v0.1.0 (Current)
- Initial project setup
- Basic project structure
- Core dependencies installation
- TaskMaster AI integration

---

**Note**: This project is actively under development. Features and documentation will be updated regularly. 